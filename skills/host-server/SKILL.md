---
name: maribro-host-server
description: Starts, checks, and debugs the Maribro host server (backend.server) in local, WSL, and macOS terminal setups. Use when the user asks to start/restart the host, verify reachability, or troubleshoot host URL access.
---

# Maribro Party -- Host Server

## Purpose

Run the host server reliably and quickly diagnose why it is not reachable.

## Start Server

From repo root:

```bash
bash skills/host-server/scripts/start_host_server.sh 0.0.0.0 8000
```

Notes:
- Keep this terminal open while hosting.
- On WSL, this is the most reliable bind mode for Windows browser access.

## Restart Server

From repo root:

```bash
bash skills/host-server/scripts/restart_host_server.sh 0.0.0.0 8000
```

This stops any existing host process on the port, then starts a fresh one.

## Debug / Health Check

From repo root:

```bash
bash skills/host-server/scripts/debug_host_server.sh 127.0.0.1 8000
```

The debug script checks:
1. required tools (`uv`, `curl`)
2. listener state (`ss`/`lsof` if available)
3. HTTP responses for `/` and `/api/games`
4. WSL access hints (`http://localhost:8000`, plus WSL IP fallback)

## Agent Loop

1. Start server with `start_host_server.sh`.
2. Run `debug_host_server.sh`.
3. If output includes `ACTION_REQUIRED`, apply the suggested fix.
4. Repeat until output includes `READY`.

## If Dependencies Are Missing

Run setup skill:

```bash
uv run python3 skills/setup/scripts/setup_env.py
```
