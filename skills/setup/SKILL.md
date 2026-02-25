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

Use this skill when the user asks to "set up the environment", "make this machine ready", or when verify/export tooling fails due to missing dependencies.

## Run

From repo root:

```bash
uv run python3 skills/setup/scripts/setup_env.py
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

## After Setup

Verify and export a real game:

```bash
uv run python3 skills/verify-game/scripts/verify.py games/<game>.html
./backend/export.sh --host http://<host-ip>:8000 --avatar <avatar-id> --file games/<game>.html
```
