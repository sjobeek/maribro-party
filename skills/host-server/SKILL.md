---
name: maribro-host-server
description: Starts, checks, and debugs the Maribro host server (backend.server) in local, WSL, and macOS terminal setups. Use when the user asks to start/restart the host, verify reachability, or troubleshoot host URL access.
---

# Maribro Party -- Host Server

## Purpose

Run the host server reliably and expose it through cloudflared by default.

## Setup Host Session (Default)

From repo root:

```bash
bash skills/host-server/scripts/setup_host_tmux.sh 0.0.0.0 8000
```

Notes:
- Creates (or reuses) one tmux session with one window per process: `host`, `tunnel`.
- Session name defaults to `maribro-host` and can be overridden with `MARIBRO_HOST_TMUX_SESSION`.
- If a window already has a live process, setup leaves it running (keeps quick tunnel URL stable).

## Restart Host Session

From repo root:

```bash
bash skills/host-server/scripts/restart_host_tmux.sh 0.0.0.0 8000
```

- Preferred way to apply server updates or re-initialize host backend.
- Restarts only the `host` window; leaves `tunnel` running so quick tunnel URL remains stable.
- Creates the tmux session + windows if missing.

## Stop Host Session

From repo root:

```bash
bash skills/host-server/scripts/stop_host_tmux.sh
```

- Stops all host-related processes by killing the tmux session.
- Safe to run even if the session is already absent.
- Safety gate: stop requires explicit confirmation (`--yes` for non-interactive agent runs).

## Live Visibility

Attach to see logs in real time:

```bash
tmux attach -t maribro-host
```

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

1. Setup/restart host with `setup_host_tmux.sh` or `restart_host_tmux.sh`.
2. Run `debug_host_server.sh` and confirm `READY`.
3. Copy the tunnel URL from setup/restart output or from tmux `tunnel` window logs.
4. If output includes `ACTION_REQUIRED`, apply the suggested fix and retry.

## If Dependencies Are Missing

Run setup skill:

```bash
uv run python3 skills/setup/scripts/setup_env.py
```
