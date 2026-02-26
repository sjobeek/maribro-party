#!/usr/bin/env bash
set -euo pipefail

SESSION="${MARIBRO_HOST_TMUX_SESSION:-maribro-host}"
ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=true ;;
    *)
      echo "ERROR: unknown argument '${arg}'. Supported: --yes"
      exit 2
      ;;
  esac
done

if ! command -v tmux >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: tmux is not installed."
  exit 1
fi

if ! tmux has-session -t "${SESSION}" 2>/dev/null; then
  echo "No tmux host session found: ${SESSION}"
  exit 0
fi

if [[ "${ASSUME_YES}" != "true" ]]; then
  if [[ ! -t 0 ]]; then
    echo "ACTION_REQUIRED: stopping will drop the active quick tunnel URL."
    echo "Rerun with --yes to confirm: bash skills/host-server/scripts/stop_host_tmux.sh --yes"
    exit 1
  fi
  printf "Stop host session '%s'? This will drop the quick tunnel URL. [y/N] " "${SESSION}"
  read -r reply
  case "${reply}" in
    y|Y|yes|YES) ;;
    *) echo "Canceled."; exit 1 ;;
  esac
fi

tmux kill-session -t "${SESSION}"
echo "Stopped tmux host session '${SESSION}'."
