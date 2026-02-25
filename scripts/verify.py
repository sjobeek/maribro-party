#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024


def _print(kind: str, name: str, msg: str = "") -> None:
    tail = f" — {msg}" if msg else ""
    print(f"{kind} {name}{tail}")


def fail(name: str, msg: str = "") -> None:
    _print("FAIL", name, msg)


def warn(name: str, msg: str = "") -> None:
    _print("WARN", name, msg)


def ok(name: str, msg: str = "") -> None:
    _print("PASS", name, msg)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python3 scripts/verify.py games/<game>.html")
        return 1

    path = Path(argv[1])
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

    # 6) metadata (warn only)
    for tag in ("title", "description", "author", "maxDurationSec"):
        if re.search(rf"""<meta\s+[^>]*name\s*=\s*['"]{re.escape(tag)}['"]""", html, flags=re.IGNORECASE):
            ok(f"meta:{tag}")
        else:
            warn(f"meta:{tag}", "missing <meta name=...>")

    return 1 if had_fail else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

