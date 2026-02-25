#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import argparse
import http.server
import shutil
import socketserver
import re
import sys
import tempfile
import threading
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
RUNTIME_SIM_MS = 9000
RUNTIME_TIMEOUT_MS = 24000


def _print(kind: str, name: str, msg: str = "") -> None:
    tail = f" — {msg}" if msg else ""
    print(f"{kind} {name}{tail}")


def fail(name: str, msg: str = "") -> None:
    _print("FAIL", name, msg)


def warn(name: str, msg: str = "") -> None:
    _print("WARN", name, msg)


def ok(name: str, msg: str = "") -> None:
    _print("PASS", name, msg)


def _supports_multiplayer_markers(lower: str) -> bool:
    checks = (
        "getactiveslots",
        "playersbyslot",
        "[0, 0, 0, 0]",
        "[0,0,0,0]",
        "slot < 4",
        "slot<=3",
    )
    return any(c in lower for c in checks)


def _run_runtime_flow_check(game_path: Path) -> tuple[str, str]:
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except Exception:
        return (
            "unavailable",
            (
                "playwright missing. Install verifier deps "
                "(`uv sync --extra verify`) and browser (`uv run playwright install chromium`)."
            ),
        )

    sdk_src = game_path.parent.parent / "public" / "maribro-sdk.js"
    if not sdk_src.exists():
        return False, f"missing SDK file: {sdk_src}"

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with tempfile.TemporaryDirectory(prefix="maribro-verify-") as td:
        root = Path(td)
        shutil.copy2(game_path, root / "game.html")
        shutil.copy2(sdk_src, root / "maribro-sdk.js")

        handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(root), **kwargs)
        server = ReusableTCPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_address[1]}/game.html"

        async def _check() -> tuple[bool, str]:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_function("() => !!window.Maribro", timeout=6000)

                    await page.evaluate(
                        """(simMs) => {
                          const original = {
                            endGame: window.Maribro.endGame.bind(window.Maribro),
                            getInput: window.Maribro.getInput.bind(window.Maribro),
                          };
                          const startedAt = performance.now();
                          window.__verify_result = { done: false };

                          window.Maribro.getTimeRemainingMs = () =>
                            Math.max(0, simMs - (performance.now() - startedAt));

                          window.Maribro.getInput = (slot) => {
                            const base = original.getInput(slot) || {};
                            const phase = Math.floor((performance.now() + slot * 70) / 170) % 2 === 0;
                            return {
                              buttons: {
                                ...(base.buttons || {}),
                                south: phase,
                                east: false,
                                west: false,
                                north: false,
                              },
                              axes: {
                                ...(base.axes || {}),
                                lx: 0,
                                ly: phase ? -0.7 : 0,
                              },
                            };
                          };

                          window.Maribro.endGame = (scoresBySlot) => {
                            window.__verify_result = {
                              done: true,
                              elapsedMs: performance.now() - startedAt,
                              scoresBySlot,
                            };
                            return original.endGame(scoresBySlot);
                          };
                        }""",
                        RUNTIME_SIM_MS,
                    )

                    await page.wait_for_function(
                        "() => window.__verify_result && window.__verify_result.done === true",
                        timeout=RUNTIME_TIMEOUT_MS,
                    )
                    result = await page.evaluate("() => window.__verify_result")
                    await browser.close()

                    scores = result.get("scoresBySlot")
                    if not isinstance(scores, list):
                        return "failed", "endGame payload is not an array"
                    if len(scores) < 4:
                        return "failed", f"endGame payload too short: {len(scores)} (expected 4)"
                    if not all(isinstance(x, (int, float)) for x in scores[:4]):
                        return "failed", "first 4 endGame scores must be numeric"
                    if not all(0 <= float(x) <= 10 for x in scores[:4]):
                        return "failed", "endGame scores must be within 0..10 (host-effective range)"
                    elapsed = int(result.get("elapsedMs", 0))
                    return "ok", f"endGame observed in {elapsed}ms"
            except PlaywrightTimeoutError:
                return "failed", "game did not call endGame before timeout"
            except Exception as e:
                msg = str(e)
                missing_lib_match = re.search(r"error while loading shared libraries:\s*([^\s:]+)", msg)
                if missing_lib_match:
                    missing_lib = missing_lib_match.group(1)
                    return (
                        "unavailable",
                        (
                            f"browser runtime dependency missing: {missing_lib}. "
                            "On Ubuntu/WSL, run `sudo apt-get install -y libasound2 libgbm1 libnss3 "
                            "libatk-bridge2.0-0 libxkbcommon0`."
                        ),
                    )
                if (
                    "Executable doesn't exist" in msg
                    or "chromium_headless_shell" in msg
                    or "Please run the following command to download new browsers" in msg
                ):
                    return (
                        "unavailable",
                        "chromium binary is missing. Run `uv run playwright install chromium`.",
                    )
                if "libgbm.so.1" in msg or "Host system is missing dependencies" in msg:
                    return (
                        "unavailable",
                        (
                            "browser runtime dependencies are missing. On Ubuntu/WSL: "
                            "`sudo apt-get install -y libasound2 libgbm1 libnss3 libatk-bridge2.0-0 "
                            "libxkbcommon0`."
                        ),
                    )
                first_line = msg.splitlines()[0] if msg else "unknown runtime error"
                return "failed", f"runtime check error: {first_line}"
            finally:
                try:
                    await browser.close()  # type: ignore[name-defined]
                except Exception:
                    pass

        try:
            return asyncio.run(_check())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1.0)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="verify.py",
        description="Verify Maribro minigame contract checks for a single HTML file.",
    )
    parser.add_argument("file", help="Path to game HTML (for example: games/my-game.html)")
    parser.add_argument(
        "--allow-no-runtime",
        action="store_true",
        help="Fallback mode: if runtime tooling is unavailable, keep static checks and emit WARN instead of FAIL.",
    )
    parser.add_argument(
        "--strict-runtime",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    raw = path.read_bytes()

    had_fail = False

    # 1) reasonable size
    if len(raw) > MAX_BYTES:
        had_fail = True
        fail("file_size", f"{len(raw)} bytes > {MAX_BYTES}")
    else:
        ok("file_size", f"{len(raw)} bytes")

    # 2) parseable-ish html (very light)
    try:
        html = raw.decode("utf-8")
        ok("utf8_decode")
    except UnicodeDecodeError:
        html = raw.decode("utf-8", errors="replace")
        warn("utf8_decode", "non-utf8 bytes replaced")

    lower = html.lower()
    if "<!doctype html" in lower and "<html" in lower and "</html>" in lower:
        ok("html_structure")
    else:
        had_fail = True
        fail("html_structure", "missing doctype/html tags")

    # 3) self-contained: no http(s), no protocol-relative, no non-data src/href (except sdk)
    if "http://" in lower or "https://" in lower:
        had_fail = True
        fail("no_external_http", "found http(s)://")
    else:
        ok("no_external_http")

    if re.search(r"""(?:src|href)\s*=\s*['"]\s*//""", html, flags=re.IGNORECASE):
        had_fail = True
        fail("no_protocol_relative", "found src/href=\"//...\"")
    else:
        ok("no_protocol_relative")

    attrs = re.findall(r"""(?:src|href)\s*=\s*['"]([^'"]+)['"]""", html, flags=re.IGNORECASE)
    bad_refs: list[str] = []
    for v in attrs:
        v = v.strip()
        if not v or v.startswith("#"):
            continue
        if v in ("maribro-sdk.js", "/maribro-sdk.js"):
            continue
        if v.startswith("data:"):
            continue
        bad_refs.append(v)
    if bad_refs:
        had_fail = True
        fail("self_contained", "non-inline refs: " + ", ".join(bad_refs[:8]) + (" ..." if len(bad_refs) > 8 else ""))
    else:
        ok("self_contained")

    # 4) rendering target
    if "<canvas" in lower or len(re.sub(r"\s+", "", re.sub(r"(?s)<script.*?</script>", "", lower))) > 200:
        ok("render_target")
    else:
        had_fail = True
        fail("render_target", "missing canvas or substantial DOM")

    # 5) sdk / scoring contract markers (V1 requires SDK)
    uses_sdk = "maribro-sdk.js" in lower
    if uses_sdk:
        ok("uses_sdk")
    else:
        had_fail = True
        fail("uses_sdk", "SDK is required: include <script src=\"/maribro-sdk.js\"></script>")

    has_end = ("maribro.endgame" in lower) or ("maribro:game_end" in lower) or ("postmessage" in lower)
    if has_end:
        ok("score_reporting")
    else:
        had_fail = True
        fail("score_reporting", "missing Maribro.endGame or postMessage game_end")

    # 6) multiplayer markers
    if _supports_multiplayer_markers(lower):
        ok("supports_4_players")
    else:
        had_fail = True
        fail("supports_4_players", "missing obvious 4-player markers")

    # 7) runtime simulation: game must actually finish and report scores
    runtime_status, runtime_msg = _run_runtime_flow_check(path)
    if runtime_status == "ok":
        ok("runtime_end_to_end", runtime_msg)
    elif runtime_status == "unavailable":
        allow_fallback = args.allow_no_runtime
        if args.strict_runtime:
            allow_fallback = False
        if allow_fallback:
            warn("runtime_end_to_end", runtime_msg + " (static checks still ran)")
        else:
            had_fail = True
            fail("runtime_end_to_end", runtime_msg)
    else:
        had_fail = True
        fail("runtime_end_to_end", runtime_msg)

    # 8) metadata (warn only)
    for tag in ("title", "description", "author", "maxDurationSec"):
        if re.search(rf"""<meta\s+[^>]*name\s*=\s*['"]{re.escape(tag)}['"]""", html, flags=re.IGNORECASE):
            ok(f"meta:{tag}")
        else:
            warn(f"meta:{tag}", "missing <meta name=...>")

    return 1 if had_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
