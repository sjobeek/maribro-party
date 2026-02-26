---
name: maribro-init-game
description: Initializes a new Maribro Party minigame from scratch. Use when the user wants to start a new game, begin a new minigame, or says something like "let's make a game" or "new game". This is the first skill invoked at the start of a vibe-coding session. Compatible with any AI coding agent that reads AGENTS.md and skills/.
---

# Maribro Party -- Initialize New Game

## When to Use

This skill runs at the start of every new minigame creation session. The user says something like "make me a game" or "let's build a minigame" and the agent handles everything below automatically.

## Steps

### 1. Gather game concept

Ask the user:

- **What kind of game?** -- A brief description or genre (racing, arena brawl, reflex test, puzzle, rhythm, etc.). A single sentence is enough.
- **What's your avatar ID?** -- Needed for creator attribution on export. Show the avatar list if they haven't picked one. Skip if already configured from a previous session.

### 2. Generate a game filename

Derive a short kebab-case filename from the game concept and place it in `games/`. Confirm with the user if ambiguous.

### 3. Scaffold the game file

Create `games/<name>.html`. If `games/_template.html` exists, copy it and fill in the metadata. Otherwise, create a minimal HTML file that:

- Has proper HTML document structure
- Includes the SDK (**required**) (`/public/maribro-sdk.js`)
- Has a canvas or DOM rendering target
- Wires up the `onReady` callback to receive player info
- Has a game loop (update + draw)
- Reads controller input for all 4 players via the SDK
- Has a score reporting call (`endGame`) that fires when the game concludes
- Declares metadata via `<meta>` tags (title, description, author, max duration)

The scaffold should pass the verification script out of the box.

Required presentation flow:

- Include a start countdown screen (3 seconds) before gameplay begins.
- Include a winner/results screen (about 2-4 seconds) after gameplay ends, showing per-player points gained for that round before reporting completion.
- Scaffold overlays so they cannot deadlock the game loop and so completion still reaches `Maribro.endGame(...)` (timer and/or skip path).
- If the game shows "points gained" on its winner/results screen, those values should match the exact `scoresBySlot` payload sent via `Maribro.endGame(...)` (host-effective values), not a separate internal score metric.
- Treat `scoresBySlot` as intentional round rewards in `0..10` decided by game logic. Default recommendation: winner gets `10`, last place gets `0`, and middle placements get game-defined values in between (ties allowed). Do not rely on last-second clamping of a raw internal score.

Optional (only if user asks for sound):

- Use `Maribro.audio.playNote(...)` for simple SFX.
- Remember: calling `playNote` **implicitly opts into custom audio** and disables SDK fallback bloops automatically.

### 4. Start the local dev server

If not already running, start a Python HTTP server from the repo root. Tell the user to open the game in their browser. The SDK runs in mock mode locally (keyboard input, placeholder players, no real scoring).

### 5. Hand off to the dev workflow

The game is scaffolded and serving. From here, the main dev skill (`skills/minigame-dev/SKILL.md`) takes over for the iterate-verify-export loop. Ask the user what gameplay they want to build first.

## Agent Notes

- This skill is purely about initialization. Do not build the full game here -- scaffold and hand off.
- The scaffold must pass verification out of the box so the verify-fix loop starts clean.
- Prefer copying `games/_template.html` if it exists -- it may have project-specific conventions.
- Skip starting the dev server if one is already running.
- New game scaffolds must include this flow: 3s countdown -> gameplay -> short winner/results screen.
