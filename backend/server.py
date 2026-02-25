from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "public"
GAMES_DIR = ROOT / "games"
DATA_DIR = ROOT / "data"
SESSION_PATH = DATA_DIR / "session.json"
AVATARS_PATH = PUBLIC_DIR / "avatars" / "avatars.json"

MAX_GAME_BYTES = 20 * 1024 * 1024
DEFAULT_UPLOAD_TOKEN = "maribro-upload"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **payload}


def _err(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


def _expected_upload_token() -> str:
    token = os.getenv("MARIBRO_UPLOAD_TOKEN", DEFAULT_UPLOAD_TOKEN).strip()
    return token or DEFAULT_UPLOAD_TOKEN


def _ensure_dirs() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_DIR / "avatars").mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_avatars_index() -> List[Dict[str, Any]]:
    if not AVATARS_PATH.exists():
        return []
    data = _load_json(AVATARS_PATH)
    if isinstance(data, dict) and isinstance(data.get("avatars"), list):
        return data["avatars"]
    if isinstance(data, list):
        return data
    return []


def _is_known_avatar(avatar_id: str) -> bool:
    return any(a.get("id") == avatar_id for a in _load_avatars_index())


def _default_session() -> Dict[str, Any]:
    created = _now_iso()
    return {
        "version": 1,
        "createdAt": created,
        "updatedAt": created,
        "playersBySlot": [
            {"slot": 0, "avatarId": "", "gamepadIndex": -1, "lockedIn": False},
            {"slot": 1, "avatarId": "", "gamepadIndex": -1, "lockedIn": False},
            {"slot": 2, "avatarId": "", "gamepadIndex": -1, "lockedIn": False},
            {"slot": 3, "avatarId": "", "gamepadIndex": -1, "lockedIn": False},
        ],
        "scoreboardByAvatarId": {},
        "history": [],
    }


def _load_session() -> Dict[str, Any]:
    if not SESSION_PATH.exists():
        sess = _default_session()
        _write_json(SESSION_PATH, sess)
        return sess
    try:
        data = _load_json(SESSION_PATH)
        if isinstance(data, dict) and data.get("version") == 1:
            return data
    except Exception:
        pass
    sess = _default_session()
    _write_json(SESSION_PATH, sess)
    return sess


def _save_session(sess: Dict[str, Any]) -> None:
    sess["updatedAt"] = _now_iso()
    _write_json(SESSION_PATH, sess)


META_RE = re.compile(
    r"<meta\s+[^>]*name\s*=\s*['\"](?P<name>[^'\"]+)['\"][^>]*content\s*=\s*['\"](?P<content>[^'\"]*)['\"][^>]*>",
    re.IGNORECASE,
)


def _extract_meta(html: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for m in META_RE.finditer(html):
        name = (m.group("name") or "").strip()
        content = (m.group("content") or "").strip()
        if not name:
            continue
        meta[name] = content
    return meta


def _get_game_metadata(filename: str, html: str, uploaded_at_iso: Optional[str]) -> Dict[str, Any]:
    meta = _extract_meta(html)

    def pick(keys: List[str], fallback: str = "") -> str:
        for k in keys:
            v = meta.get(k)
            if v:
                return v
        return fallback

    title = pick(["maribro:title", "title"], fallback=Path(filename).stem)
    description = pick(["maribro:description", "description"], fallback="")
    author = pick(["maribro:author", "author"], fallback="")
    creator_avatar_id = pick(["maribro:creatorAvatarId", "creatorAvatarId"], fallback="")
    max_dur_raw = pick(["maribro:maxDurationSec", "maxDurationSec"], fallback="90")
    try:
        max_dur = int(float(max_dur_raw))
    except Exception:
        max_dur = 90

    return {
        "id": Path(filename).stem,
        "filename": filename,
        "title": title,
        "description": description,
        "author": author,
        "creatorAvatarId": creator_avatar_id,
        "maxDurationSec": max(5, min(300, max_dur)),
        "uploadedAt": uploaded_at_iso or _now_iso(),
    }


def _sanitize_filename(filename: str) -> str:
    filename = filename.strip().replace("\\", "/").split("/")[-1]
    if not filename.endswith(".html"):
        raise _err("bad_filename", "filename must end with .html")
    stem = filename[:-5]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", stem):
        raise _err("bad_filename", "filename must be kebab-case (letters/numbers/dashes)")
    return filename


def _validate_game_html_bytes(raw: bytes) -> str:
    if len(raw) > MAX_GAME_BYTES:
        raise _err("too_large", f"game file must be <= {MAX_GAME_BYTES} bytes")
    try:
        html = raw.decode("utf-8")
    except UnicodeDecodeError:
        html = raw.decode("utf-8", errors="replace")

    # Simple external-resource guard rails (trusted friends, but keep it party-safe).
    lower = html.lower()
    if "http://" in lower or "https://" in lower:
        raise _err("external_resource", "external http(s) resources are not allowed")
    if re.search(r"""(?:src|href)\s*=\s*['"]\s*//""", html, flags=re.IGNORECASE):
        raise _err("external_resource", "protocol-relative // resources are not allowed")

    # Allow same-origin SDK include; disallow other non-data src/href.
    attrs = re.findall(r"""(?:src|href)\s*=\s*['"]([^'"]+)['"]""", html, flags=re.IGNORECASE)
    for v in attrs:
        v = v.strip()
        if not v:
            continue
        if v in ("maribro-sdk.js", "/maribro-sdk.js"):
            continue
        # Allow fragment links and in-page references.
        if v.startswith("#"):
            continue
        # Allow data URIs for assets.
        if v.startswith("data:"):
            continue
        # Any other referenced path is considered an external dependency in V1.
        raise _err("external_resource", f"non-inline resource reference not allowed: {v}")

    return html


def _list_games() -> List[Dict[str, Any]]:
    games: List[Dict[str, Any]] = []
    for p in sorted(GAMES_DIR.glob("*.html")):
        if p.name.startswith("_"):
            continue
        try:
            html = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        uploaded_at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
        games.append(_get_game_metadata(p.name, html, uploaded_at))
    # newest first
    games.sort(key=lambda g: g.get("uploadedAt", ""), reverse=True)
    return games


def _clamp_score(x: Any) -> int:
    try:
        v = float(x)
    except Exception:
        return 0
    if v != v:  # NaN
        return 0
    return int(round(max(0.0, min(10.0, v))))


def _creator_bonus_from_ratings(ratings_by_slot: Optional[List[int]]) -> int:
    if not ratings_by_slot:
        return 0
    pos = sum(1 for r in ratings_by_slot if r == 1)
    neg = sum(1 for r in ratings_by_slot if r == -1)
    votes = pos + neg
    if votes <= 0:
        return 0
    return int(round(10 * pos / votes))


_ensure_dirs()
app = FastAPI()

@app.exception_handler(HTTPException)
def http_exception_handler(_request, exc: HTTPException):
    # Return the API's `{ ok:false, error:{...} }` envelope directly (not FastAPI's
    # default `{ detail: ... }`) when our handlers raise `_err(...)`.
    if isinstance(exc.detail, dict) and exc.detail.get("ok") is False:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": {"code": "http_error", "message": str(exc.detail)}},
    )


@app.get("/api/games")
def api_games() -> Dict[str, Any]:
    return _ok({"games": _list_games()})


@app.post("/api/games")
async def api_games_upload(
    file: UploadFile = File(...),
    creator_avatar_id: str = Form(...),
    filename: Optional[str] = Form(None),
    upload_token: Optional[str] = Form(None),
    x_maribro_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    provided_token = (x_maribro_token or upload_token or "").strip()
    if provided_token != _expected_upload_token():
        raise _err("invalid_upload_token", "missing or invalid upload token", status_code=401)

    if not _is_known_avatar(creator_avatar_id):
        raise _err("unknown_avatar", f"unknown creator_avatar_id: {creator_avatar_id}")

    raw = await file.read()
    html = _validate_game_html_bytes(raw)

    out_name = filename or (file.filename or "untitled.html")
    out_name = _sanitize_filename(out_name)

    # Force creator attribution into metadata if missing.
    if "creatoravatarid" not in html.lower():
        inject = f'<meta name="creatorAvatarId" content="{creator_avatar_id}">\n'
        html = re.sub(r"(?i)</head>", inject + "</head>", html, count=1) or (inject + html)

    out_path = GAMES_DIR / out_name
    out_path.write_text(html, encoding="utf-8")

    game = _get_game_metadata(out_name, html, _now_iso())
    game["creatorAvatarId"] = creator_avatar_id
    return _ok({"game": game})


@app.get("/api/session")
def api_session_get() -> Dict[str, Any]:
    return _ok({"session": _load_session()})


@app.post("/api/session/reset")
def api_session_reset() -> Dict[str, Any]:
    sess = _default_session()
    _save_session(sess)
    return _ok({})


@app.post("/api/session/players")
def api_session_players(body: Dict[str, Any]) -> Dict[str, Any]:
    players = body.get("playersBySlot")
    if not isinstance(players, list):
        raise _err("bad_body", "playersBySlot must be a list")
    if len(players) != 4:
        raise _err("bad_body", "playersBySlot must have exactly 4 entries")

    sess = _load_session()
    next_players = []
    for entry in players:
        try:
            slot = int(entry.get("slot"))
            avatar_id = str(entry.get("avatarId") or "")
            gamepad_index = int(entry.get("gamepadIndex"))
        except Exception:
            raise _err("bad_body", "invalid playersBySlot entry")
        if slot not in (0, 1, 2, 3):
            raise _err("bad_body", "slot must be 0..3")
        if avatar_id and not _is_known_avatar(avatar_id):
            raise _err("unknown_avatar", f"unknown avatarId: {avatar_id}")
        next_players.append(
            {
                "slot": slot,
                "avatarId": avatar_id,
                "gamepadIndex": gamepad_index,
                "lockedIn": True if avatar_id and gamepad_index >= 0 else False,
            }
        )
    next_players.sort(key=lambda p: p["slot"])
    sess["playersBySlot"] = next_players
    _save_session(sess)
    return _ok({"session": sess})


@app.post("/api/session/record_game")
def api_session_record_game(body: Dict[str, Any]) -> Dict[str, Any]:
    game_id = body.get("gameId")
    scores = body.get("scoresBySlot")
    ratings = body.get("ratingsBySlot")

    if not isinstance(game_id, str) or not game_id:
        raise _err("bad_body", "gameId is required")
    if not (isinstance(scores, list) and len(scores) == 4):
        raise _err("bad_body", "scoresBySlot must be length-4 array")

    scores_clamped = [_clamp_score(s) for s in scores]
    ratings_norm: Optional[List[int]] = None
    if ratings is not None:
        if not (isinstance(ratings, list) and len(ratings) == 4):
            raise _err("bad_body", "ratingsBySlot must be length-4 array")
        ratings_norm = []
        for r in ratings:
            try:
                ri = int(r)
            except Exception:
                ri = 0
            if ri not in (-1, 0, 1):
                ri = 0
            ratings_norm.append(ri)

    games = {g["id"]: g for g in _list_games()}
    game = games.get(game_id)
    if not game:
        raise _err("unknown_game", f"unknown gameId: {game_id}")

    sess = _load_session()
    players_by_slot = sess.get("playersBySlot") or []
    slot_to_avatar: Dict[int, str] = {int(p.get("slot")): str(p.get("avatarId") or "") for p in players_by_slot}

    scoreboard = sess.get("scoreboardByAvatarId") or {}
    for slot, pts in enumerate(scores_clamped):
        avatar_id = slot_to_avatar.get(slot, "")
        if not avatar_id:
            continue
        entry = scoreboard.get(avatar_id) or {"play": 0, "creator": 0, "total": 0}
        entry["play"] = int(entry.get("play", 0)) + int(pts)
        scoreboard[avatar_id] = entry

    creator_avatar_id = str(game.get("creatorAvatarId") or "")
    creator_bonus = _creator_bonus_from_ratings(ratings_norm)
    if creator_avatar_id:
        entry = scoreboard.get(creator_avatar_id) or {"play": 0, "creator": 0, "total": 0}
        entry["creator"] = int(entry.get("creator", 0)) + int(creator_bonus)
        scoreboard[creator_avatar_id] = entry

    # Recompute totals.
    for aid, entry in scoreboard.items():
        play = int(entry.get("play", 0))
        creator = int(entry.get("creator", 0))
        entry["total"] = play + creator
        scoreboard[aid] = entry

    sess["scoreboardByAvatarId"] = scoreboard
    sess.setdefault("history", []).append(
        {
            "playedAt": _now_iso(),
            "gameId": game_id,
            "creatorAvatarId": creator_avatar_id,
            "scoresBySlot": scores_clamped,
            **({} if ratings_norm is None else {"ratingsBySlot": ratings_norm}),
        }
    )
    _save_session(sess)
    return _ok({"session": sess})


@app.get("/api/avatars")
def api_avatars() -> Dict[str, Any]:
    return _ok({"avatars": _load_avatars_index()})


# Static serving is mounted last so `/api/*` routes win.
app.mount("/games", StaticFiles(directory=str(GAMES_DIR), html=True), name="games")
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
