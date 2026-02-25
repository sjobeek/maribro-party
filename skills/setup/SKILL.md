---
name: maribro-setup
description: Sets up and validates the full Maribro Party local environment (host, export, and game-runtime verification) on WSL/macOS/Linux. Use when bootstrapping a new machine or when tooling/runtime dependencies are missing.
---

# Maribro Party -- Setup

## Purpose

Get the full local environment working end-to-end:
- host dependencies and imports
- export script readiness
- Playwright runtime verification readiness for game E2E checks
- upload token defaults/override for POST security
- cloudflared quick tunnel readiness (default sharing mode)

Use this skill when the user asks to "set up the environment", "make this machine ready", or when verify/export tooling fails due to missing dependencies.

Role guidance:
- `host`: includes cloudflared tunnel readiness (default sharing mode)
- `vibe-coder`: skips tunnel requirement checks

## Run

From repo root:

```bash
uv run python3 skills/setup/scripts/setup_env.py
```

For a vibe-coder machine:

```bash
uv run python3 skills/setup/scripts/setup_env.py --role vibe-coder
```

Optional probe target:

```bash
uv run python3 skills/setup/scripts/setup_env.py --probe-file games/<game>.html
```

## What It Checks

1. `uv` exists (installs it automatically on Linux/macOS when missing)
2. Core + verify deps install: `uv sync --extra verify`
3. Host import check: `uv run python3 -c "import backend.server"`
4. Export helper check: `./backend/export.sh --help`
5. Browser install: `uv run playwright install chromium`
6. Runtime verify probe: `uv run python3 skills/verify-game/scripts/verify.py <probe-file>`
7. Reports upload token behavior (`maribro-upload` default, `MARIBRO_UPLOAD_TOKEN` override)
8. For `role=host`: checks cloudflared and prints default tunnel command (`cloudflared tunnel --url http://localhost:8000`)

Success ends with `READY: environment setup is working.`

## Agent Loop (required)

1. Run setup script.
2. If output contains `ACTION_REQUIRED`, ask the user to run the specified command(s).
3. Re-run setup script.
4. Stop only at `READY`.

## Common Manual Fixes

Ubuntu/WSL browser libs:

```bash
sudo apt-get install -y libasound2 libgbm1 libnss3 libatk-bridge2.0-0 libxkbcommon0
```

Host cloudflared install (Ubuntu/WSL):

```bash
cd /tmp && curl -fLO https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared-linux-amd64.deb || sudo apt-get -f install -y
```

## After Setup

Verify and export a real game:

```bash
uv run python3 skills/verify-game/scripts/verify.py games/<game>.html
./backend/export.sh --host http://<host-ip>:8000 --avatar <avatar-id> --file games/<game>.html
```
