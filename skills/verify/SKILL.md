---
name: maribro-verify
description: Validates Maribro Party minigames against the contract before export. Use when verifying a game, checking if a game is ready to export, fixing contract violations, or when the user asks to test/validate their minigame. Compatible with any AI coding agent that reads AGENTS.md and skills/.
---

# Maribro Party -- Game Verification

## Purpose

Validate that a minigame HTML file satisfies the maribro-party contract before it gets exported to the host. The host is where real gameplay happens (controllers, scoring, big monitor) -- verification ensures the game will work there.

## How to Verify

Run the verification script against a game file:

```bash
uv run python3 scripts/verify.py games/<game-name>.html
```

Exit code 0 = pass (ready to export). Exit code 1 = fail (needs fixes).

## Verify-Fix Loop

When verification fails:

1. Run the verify script
2. Read the output -- each check reports PASS, FAIL, or WARN
3. For each FAIL, read the game HTML and apply the appropriate fix
4. Re-run verification
5. Repeat until all required checks pass
6. Report final status to the user

Do not stop after one round of fixes. Keep iterating until verification passes.

## Required Checks (FAIL = must fix)

- **Valid HTML structure** -- Parseable HTML with proper document structure
- **Self-contained** -- No external resource references (relative SDK path is fine)
- **Reasonable file size** -- Under 2MB
- **Has rendering target** -- Canvas element or substantial DOM content
- **Has score reporting** -- Posts scores back to the host via the SDK or postMessage
- **Supports 4 players** -- Handles player indices 0-3
- **Uses the SDK (required)** -- Includes `/maribro-sdk.js` so input/scoring/audio/mock mode are consistent

## Warnings (non-blocking)

- Missing metadata tags (title, description, author)
 - Audio is never required: games may rely on SDK fallback “bloops” or opt-in via `Maribro.audio.playNote(...)`

## When to Run

- **During development**: After implementing core game logic, to catch contract issues early.
- **Before export**: Always. The export process runs it too, but catching issues earlier saves time.
- **After significant changes**: Re-verify after refactoring game structure, scoring, or player handling.
