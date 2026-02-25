---
name: maribro-minigame-dev
description: Guides vibe-coders through creating, testing, verifying, and exporting Maribro Party minigames. Use when the user wants to create a new minigame, start a local dev server, test a game with mock controllers, verify a game against the contract, or export/upload a game to the host. Compatible with any AI coding agent that reads AGENTS.md and skills/.
---

# Maribro Party -- Minigame Development

## Context

Read the project design before starting: [docs/design.md](../../docs/design.md)

Each minigame is a single self-contained HTML file in `games/`. The full contract (controller input, scoring, player info, communication protocol) is documented in the design doc.

## Workflow

### 1. Initialize a new game

Use the init-game skill at `skills/init-game/SKILL.md`. It gathers the game concept and avatar ID from the user, scaffolds a contract-compliant game file, and starts the local dev server.

Skip this step if continuing work on an existing game.

### 2. Develop locally

Start a local dev server from the repo root if not already running. Open the game in a browser -- the SDK enters mock mode automatically (keyboard input, placeholder players). This is for development only -- no real controllers or scoring.

### 3. Iterate

Edit the game file, refresh the browser, repeat. Focus on making it fun in 30-90 seconds with 4 players.

### 4. Verify

Use the verify skill at `skills/verify/SKILL.md`. It validates the game against the minigame contract, interprets failures, fixes issues, and re-verifies in a loop.

### 5. Export to host

Run the export process with the host URL and creator avatar ID. The host URL is provided by whoever is running the host (LAN IP or tunnel URL).

Once exported, the game enters the live rotation on the host -- real controllers, real scoring.

## Agent Instructions

When helping a user create a minigame:

1. **Use the init-game skill** to scaffold the game. It handles gathering the concept, avatar ID, file creation, and dev server.
2. Implement the game with all 4 players, shared-screen rendering, and controller input.
3. Keep it simple -- completable in 30-90 seconds.
4. Use the SDK helpers where possible.
5. Test locally in the browser (mock mode).
6. **Use the verify skill** proactively during development, not just at export time.
7. When the user is happy and verification passes, export to the host.

**IMPORTANT:** Never attempt to export without running the verify skill first.

