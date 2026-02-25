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
- **Runtime completion flow** -- Verification must run the game in a browser, simulate inputs, and confirm the game actually reaches completion and calls `endGame` with scores.

## Warnings (non-blocking)

- Missing metadata tags (title, description, author)
 - Audio is never required: games may rely on SDK fallback “bloops” or opt-in via `Maribro.audio.playNote(...)`

## When to Run

- **During development**: After implementing core game logic, to catch contract issues early.
- **Before export**: Always. The export process runs it too, but catching issues earlier saves time.
- **After significant changes**: Re-verify after refactoring game structure, scoring, or player handling.

## Runtime Check Expectations

Verification should include an execution check, not just static HTML checks:

1. Launch the game in a browser (headless is fine).
2. Simulate representative controller input over time.
3. Wait for game completion.
4. Fail if completion never happens (timeouts/frozen states).
5. Fail if no score payload is returned at completion.
6. Verify the returned score payload is host-effective (`scoresBySlot` numeric, length 4, values in `0..10`).
7. Verify score design intent: `scoresBySlot` should represent deliberate round rewards (default guidance: winner `10`, last place `0`, in-between values game-defined), not merely a clamped internal metric.
8. If a game displays "points gained" on a winner/results screen, ensure it reflects that same reported payload.

This catches failure modes like countdown/winner overlays that accidentally freeze on the last frame and never report results.

### Runtime Prerequisites

The verifier's runtime check uses Playwright + Chromium. If runtime checks fail due to missing tooling:

- Install Python deps: `uv sync`
- Install browser binary: `uv run playwright install chromium`
- If needed on Linux/WSL, install missing system browser libs (for example `libgbm1`)
