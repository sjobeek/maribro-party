#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"

# Intentionally restart only the backend server process.
# Keep cloudflared running in a separate terminal so the tunnel URL stays stable.

if [[ ! -f "backend/server.py" ]]; then
  echo "ERROR: run this from repo root (missing backend/server.py)" >&2
  exit 2
fi

PIDS=""
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti TCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
fi
if [[ -z "${PIDS}" ]]; then
  PIDS="$(pgrep -f "uvicorn backend.server:app.*--port ${PORT}" || true)"
fi

if [[ -n "${PIDS}" ]]; then
  echo "Stopping existing host server process(es): ${PIDS}"
  # shellcheck disable=SC2086
  kill ${PIDS} || true
  for _ in {1..25}; do
    sleep 0.1
    if ! lsof -i :"${PORT}" -n -P >/dev/null 2>&1; then
      break
    fi
  done
fi

echo "Starting host server on ${HOST}:${PORT}"
exec bash skills/host-server/scripts/start_host_server.sh "${HOST}" "${PORT}"
