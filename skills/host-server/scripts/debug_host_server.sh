#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-8000}"
BASE="http://${HOST}:${PORT}"

is_wsl=false
if grep -qi microsoft /proc/version 2>/dev/null; then
  is_wsl=true
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: curl is required for host checks. Install curl and retry."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: uv is required. Run the setup skill:"
  echo "  uv run python3 skills/setup/scripts/setup_env.py"
  exit 1
fi

echo "Host debug"
echo "- Probe URL: ${BASE}"
if $is_wsl; then
  echo "- Environment: WSL"
fi

echo
if command -v ss >/dev/null 2>&1; then
  echo "== Listener check (ss) =="
  ss -ltn 2>/dev/null | awk -v port=":${PORT}" 'NR==1 || index($4, port)' || true
elif command -v lsof >/dev/null 2>&1; then
  echo "== Listener check (lsof) =="
  lsof -i :"${PORT}" -n -P || true
fi

echo
set +e
HTTP_CODE_ROOT=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE}/")
HTTP_CODE_API=$(curl -sS -o /dev/null -w "%{http_code}" "${BASE}/api/games")
set -e

echo "== HTTP probe =="
echo "- / => ${HTTP_CODE_ROOT}"
echo "- /api/games => ${HTTP_CODE_API}"

if [[ "${HTTP_CODE_ROOT}" == "200" || "${HTTP_CODE_API}" == "200" ]]; then
  echo
  echo "READY: host server is responding."
  if $is_wsl; then
    echo "Windows URL: http://localhost:${PORT}"
    if command -v ip >/dev/null 2>&1; then
      WSL_IP=$(ip -4 addr show eth0 2>/dev/null | awk '/inet / {print $2}' | cut -d/ -f1 | head -n1)
      if [[ -n "${WSL_IP}" ]]; then
        echo "WSL IP fallback: http://${WSL_IP}:${PORT}"
      fi
    fi
  fi
  exit 0
fi

echo
echo "ACTION_REQUIRED: host server is not responding on ${BASE}."
echo "Start it from repo root with:"
echo "  bash skills/host-server/scripts/start_host_server.sh 0.0.0.0 ${PORT}"
if $is_wsl; then
  echo "If Windows can't reach it, keep that server terminal open and use: http://localhost:${PORT}"
fi
exit 1
