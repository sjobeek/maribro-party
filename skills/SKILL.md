---
name: maribro-minigame-dev
description: Guides vibe-coders through creating, testing, verifying, and exporting Maribro Party minigames. Use when the user wants to create a new minigame, start a local dev server, test a game with mock controllers, verify a game against the contract, or export/upload a game to the host.
---

# Maribro Party -- Minigame Development

## Context

Read the project design before starting: [docs/design.md](../docs/design.md)

Each minigame is a single self-contained HTML file in `games/`. The full contract (controller input, scoring, player info) is documented in the design doc.

## Quick Start

### 1. Scaffold a new game

Copy the template:

```bash
cp games/_template.html games/<your-game-name>.html
```

If `_template.html` doesn't exist yet, create a minimal game HTML file that:
- Includes `<script src="/maribro-sdk.js"></script>` in the head
- Has a full-viewport canvas or DOM container
- Listens for `maribro.onReady()` to receive player info
- Calls `maribro.endGame(scores)` when finished
- Declares metadata via `<meta name="maribro-*">` tags

### 2. Start local dev server

From the repo root:

```bash
python3 -m http.server 8080 --bind 0.0.0.0
```

Open in browser: `http://localhost:8080/games/<your-game-name>.html`

The SDK enters mock mode automatically (keyboard controls Player 1: WASD + J/K/U/I).

### 3. Iterate

Edit the game file, refresh the browser, repeat. Focus on making it fun in 30-90 seconds.

### 4. Verify

Run the contract verification script:

```bash
python3 scripts/verify.py games/<your-game-name>.html
```

Fix any failures. Warnings are informational but worth addressing.

### 5. Export to host

```bash
./export.sh <host-url> games/<your-game-name>.html <your-avatar-id>
```

The host URL is either a LAN IP (`http://192.168.x.x:8000`) or a tunnel URL (`https://random-words.trycloudflare.com`) provided by whoever is running the host.

The avatar ID identifies you as the game creator (e.g. `knight-red`, `wizard-blue`). Ask the user which avatar they've chosen.

## Agent Instructions

When helping a user create a minigame:

1. Ask what kind of game they want (racing, arena, puzzle, reflex, etc.)
2. Ask which avatar ID they are using (needed for export)
3. Scaffold from the template or create a new single HTML file
4. Implement the game with all 4 players, shared-screen rendering, and controller input
5. Keep it simple -- games should be completable in 30-90 seconds
6. Use the `maribro-sdk.js` helpers where possible
7. Test by starting the local dev server and opening in a browser
8. **Run `python3 scripts/verify.py games/<game>.html` and fix any failures** -- do this proactively during development, not just at export time
9. When the user is happy and verification passes, export to the host

**IMPORTANT:** Never attempt to export a game without running verify first. The export script will also run it, but catching issues early saves time.

## Placeholder Status

This skill is a minimal starting point. Future versions will add:
- Live-reload dev server
- Mock controller UI overlay showing button states
- Virtual AI players for testing multiplayer without 4 controllers
- Score testing harness
