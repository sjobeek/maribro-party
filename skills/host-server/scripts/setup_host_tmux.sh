#!/usr/bin/env bash
set -euo pipefail

SESSION="${MARIBRO_HOST_TMUX_SESSION:-maribro-host}"
HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ ! -f "${ROOT_DIR}/backend/server.py" ]]; then
  echo "ERROR: repo root not found at ${ROOT_DIR}" >&2
  exit 2
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: tmux is not installed."
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: uv is not installed."
  exit 1
fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: cloudflared is not installed."
  exit 1
fi

window_exists() {
  local name="$1"
  tmux list-windows -t "${SESSION}" -F "#{window_name}" | grep -Fxq "${name}"
}

pane_dead() {
  local name="$1"
  tmux display-message -p -t "${SESSION}:${name}.0" "#{pane_dead}"
}

host_cmd="cd '${ROOT_DIR}' && exec bash skills/host-server/scripts/start_host_server.sh '${HOST}' '${PORT}'"
tunnel_cmd="cd '${ROOT_DIR}' && exec bash skills/host-server/scripts/start_tunnel.sh '${PORT}'"

if ! tmux has-session -t "${SESSION}" 2>/dev/null; then
  tmux new-session -d -s "${SESSION}" -n host "${host_cmd}"
  tmux new-window -d -t "${SESSION}" -n tunnel "${tunnel_cmd}"
else
  if window_exists host; then
    if [[ "$(pane_dead host)" == "1" ]]; then
      tmux respawn-window -k -t "${SESSION}:host" "${host_cmd}"
    fi
  else
    tmux new-window -d -t "${SESSION}" -n host "${host_cmd}"
  fi

  if window_exists tunnel; then
    if [[ "$(pane_dead tunnel)" == "1" ]]; then
      tmux respawn-window -k -t "${SESSION}:tunnel" "${tunnel_cmd}"
    fi
  else
    tmux new-window -d -t "${SESSION}" -n tunnel "${tunnel_cmd}"
  fi
fi

sleep 1
TUNNEL_URL="$(tmux capture-pane -pt "${SESSION}:tunnel" -S -200 | sed -n 's#.*\(https://[a-zA-Z0-9.-]*\.trycloudflare\.com\).*#\1#p' | tail -n1)"

echo "READY: tmux session '${SESSION}'"
echo "Attach: tmux attach -t ${SESSION}"
echo "Host URL: http://localhost:${PORT}"
if [[ -n "${TUNNEL_URL}" ]]; then
  echo "Tunnel URL: ${TUNNEL_URL}"
else
  echo "Tunnel URL: pending; check logs in window '${SESSION}:tunnel'"
fi
