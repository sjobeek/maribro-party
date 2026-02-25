#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8000}"
TARGET="http://localhost:${PORT}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "ACTION_REQUIRED: cloudflared is not installed."
  echo "Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
  exit 1
fi

echo "Starting cloudflared tunnel -> ${TARGET}"
exec cloudflared tunnel --url "${TARGET}"
