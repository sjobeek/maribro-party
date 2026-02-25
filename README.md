# Maribro Party

Maribro Party is a *vibe-coded* Mario-Party-like minigame party framework.

One machine (“the host”) runs the lobby + scoreboard on a big screen. Friends (“vibe-coders”) clone this repo and use an AI coding agent to build new minigames as single self-contained HTML files, then upload them into the live session.

## Participants

- **Players (up to 4 at a time)**: sit at the big screen with controllers, pick avatars, choose games, play, accumulate scores.
- **Vibe-coders (any number)**: build new minigames on their laptops and export/upload them to the host while the party is running. (Many people will do both.)

## Hosting assumptions (V1)

- **Host runs a local FastAPI server** (serves `public/`, serves `games/`, exposes `/api/*`).
- **Host browser**: use **Chrome/Chromium** on the host for best Gamepad API consistency.
- **Controllers**: Gamepad API (e.g. DS4 via Bluetooth on the host machine).
- **Network**: vibe-coders push games to the host via HTTP `POST /api/games` (LAN IP or a tunnel URL).
- **Dependency tool**: use **`uv`** (`pyproject.toml` is the source of truth).

## Quickstart (host)

From the repo root:

```bash
uv sync
uv run uvicorn server:app --port 8000
```

Then open the host UI:

- `http://localhost:8000`

## Vibe-coder workflow (recommended)

The repo includes agent “skills” so the **user loop stays simple** and the agent handles the guardrails.

- Project overview + constraints: `AGENTS.md`
- Technical contract: `docs/design.md`
- Dev workflow skill: `skills/SKILL.md`
- New game scaffolding: `skills/init-game/SKILL.md`
- Verification loop: `skills/verify/SKILL.md`

Typical loop (from the user’s perspective):

1. **Clone** this repo.
2. In your AI coding agent, say: **“make me a minigame”** (describe the vibe/genre in one sentence).
3. **Playtest locally** in your browser (SDK mock mode gives keyboard controls).
4. Say **“iterate”** / “make it fun” and keep tweaking until it’s good.
5. When you’re happy, say **“send it”** (provide the host URL and your avatar id).

What the agent should do behind the scenes:

- Scaffold a contract-compliant `games/<name>.html` via `skills/init-game/`
- Run the **verify-fix loop** via `skills/verify/` until the game passes
- Upload via `POST /api/games` (the included `export.sh` is the reference CLI)

After “send it”, the game appears in the host lobby and can be played immediately.

## Minigame contract (what you can build)

V1 minigames are:

- **Single, self-contained HTML files** in `games/` (inline CSS/JS; assets as `data:` URIs).
- **Shared-screen** (one view; no split-screen).
- **2+ players expected** (host requires at least 2 assigned players to start a game).
- **SDK required**: games must include:

```html
<script src="/maribro-sdk.js"></script>
```

The SDK provides:

- `Maribro.onReady((ctx) => ...)` with `ctx.playersBySlot` and `ctx.activeSlots`
- `Maribro.getInput(slot)` (normalized gamepad input)
- `Maribro.endGame([s0,s1,s2,s3])` (scores 0..10)
- Mock mode keyboard mapping for development
- Optional audio: `Maribro.audio.playNote(...)` (with fallback “bloops” if a game is silent)

Full protocol + schemas live in `docs/design.md`.

## Repo layout

- `server.py`: FastAPI host server
- `public/`: host UI + `maribro-sdk.js` + avatars
- `games/`: minigame HTML files
- `scripts/verify.py`: contract verification (run before export)
- `export.sh`: verify + upload helper
- `data/session.json`: persisted session state (auto-created)

