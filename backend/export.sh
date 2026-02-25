#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./backend/export.sh --host http://HOST:8000 --avatar AVATAR_ID --file games/my-game.html [--filename my-game.html]

What it does:
  1) Verifies the game contract locally (skills/verify-game/scripts/verify.py)
  2) Uploads the HTML file to the host via POST /api/games (multipart)

Notes:
  - Requires: curl, uv (and a local Python via uv)
  - Recommended: run via `uv` (see AGENTS.md)
EOF
}

HOST=""
AVATAR=""
FILE=""
FILENAME=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --avatar) AVATAR="${2:-}"; shift 2 ;;
    --file) FILE="${2:-}"; shift 2 ;;
    --filename) FILENAME="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$HOST" || -z "$AVATAR" || -z "$FILE" ]]; then
  usage
  exit 2
fi

if [[ ! -f "$FILE" ]]; then
  echo "File not found: $FILE" >&2
  exit 2
fi

echo "[1/2] Verifying $FILE"
uv run python3 skills/verify-game/scripts/verify.py "$FILE"

echo "[2/2] Uploading to $HOST/api/games"
args=(
  -sS
  -X POST
  "$HOST/api/games"
  -F "creator_avatar_id=$AVATAR"
  -F "file=@$FILE;type=text/html"
)
if [[ -n "$FILENAME" ]]; then
  args+=(-F "filename=$FILENAME")
fi

curl "${args[@]}" | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))'
echo "Done."
