#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [[ $# -ge 1 ]]; then
  HOST="$1"
fi
if [[ $# -ge 2 ]]; then
  PORT="$2"
fi

if [[ ! -f "backend/server.py" ]]; then
  echo "ERROR: run this from repo root (missing backend/server.py)" >&2
  exit 2
fi

exec uv run uvicorn backend.server:app --host "$HOST" --port "$PORT"
