# Maribro Party

## What Is This?

Maribro Party is a collaborative vibe-coded minigame party framework where the games themselves are created in real time by friends using AI-assisted coding.

**The setup:** A group gathers around a big monitor connected to a Mac host PC with 4 PS4 DualShock 4 controllers. Players sit on the couch and play short competitive minigames back-to-back, with scores accumulating across the session. Meanwhile, other participants ("vibe-coders") sit on their own laptops, vibe-coding new minigames and hot-submitting them to the live session. The game library grows in real time as people play. Some players are probably vibe coding while they compete (sigh).

## Core concept: skills-first, agent-mediated

This repo is designed around a simple assumption:

- Humans mostly talk to **their AI coding agents**.
- Agents use the **embedded skills** in `skills/` to scaffold, verify, and export games (and to run the host).

So user loops look like: **“make me a minigame → playtest → iterate → send it”**, not “run these scripts.”

## Participants

Everyone picks an avatar from the same pool of ~16 premade characters. Whether you're on the couch with a controller, on a laptop vibe-coding, or both -- you're the same avatar everywhere. Many participants will do both.

Participant “types” are hats. One person can be all of these in a single night.

**Host** -- Runs the server + lobby on the big screen. The host should use an agent to start the server and manage setup.

**Players** (up to 4 at a time) -- Sitting at the big monitor with controllers. They pick avatars, vote on which game to play next, compete in minigames, and watch scores accumulate on the leaderboard.

**Vibe-Coders** (any number) -- On their own laptops, cloning this repo, using the embedded agent skill to scaffold and test minigames locally, then pushing finished games to the host. They have specified their avatar ID in their local repo so the host server knows who made each game.

**Creating great games earns you kudos.** After each minigame, players (and optionally watchers! via a client-side skill) do a quick thumbs-up/thumbs-down vote on the game itself. Good ratings give the creator bonus points on the global scoreboard. So if you're both playing well AND making bangers, you climb the leaderboard from both sides.

## The Core Loop

```
Lobby → Vote on next game → Minigame (30-90s) → Results + Scores → Lobby
         ↑                                                          |
         └──── new games appear as vibe-coders submit them ─────────┘
```

## Player Identity

~16 premade avatars, each with a dominant color (red, blue, green, yellow, purple, orange, etc.). Players pick their avatar in the lobby using their controllers. The avatar ID and color are passed to each minigame so games can render players consistently.

## Minigame Format

Each minigame is a **single self-contained HTML file**. Inline CSS, inline JS, no external dependencies. Shared-screen rendering (all 4 players visible on one view -- not split-screen). During development, vibe-coders run games locally in mock mode for testing only -- no real controllers, no score recording. Once exported, the host framework loads the game in an iframe on the big monitor, where all real gameplay and scoring happens.

A minigame must:
- Render into the full viewport
- Support 4 players
- Read controller input (via a shared SDK or the Gamepad API directly)
- Signal completion by posting scores back to the host
- Be completable in 30-90 seconds

Games can end themselves, but the host enforces a max timer as a safety net.

## How Games Reach the Host

A game file is a static artifact. Vibe-coders develop and test it locally in mock mode (no real controllers, no scoring), then push the finished file to the host where it enters the live session. The game only "counts" once it's on the host -- that's where controllers are connected, players compete, and scores are recorded.

Games are verified locally before export. The repo includes a verify skill (`skills/verify-game/`) that agents use to validate games against the minigame contract, interpret failures, fix issues, and re-verify in a loop. The export process also runs verification as a final gate -- broken games never reach the host.

Once verified, vibe-coders push finished games to the host via HTTP, specifying their avatar ID as creator. The host exposes an upload endpoint and optionally a tunnel URL (via cloudflared, ngrok, or similar) so vibe-coders don't need to fight LAN/WSL2 networking. The tunnel URL can even be shared with remote participants over the internet.

## Network Topology

All devices on the same LAN. The Mac host runs the server and displays on the big monitor. Some vibe-coders may be developing inside WSL2, where inbound connections are painful -- so the system uses outbound HTTP pushes (not inbound SSH/rsync) and optionally a tunnel proxy on the host to make the upload URL universally reachable.

## Project Structure

- `AGENTS.md` -- This file. Concept and background.
- `docs/design.md` -- Technical architecture and framework design.
- `skills/` -- Embedded agent skills: `init-game/` to scaffold a new game, `minigame-dev/` for the dev loop, `verify-game/` for game validation, `setup/` for environment setup, and `host-server/` for running/debugging the host server.
- `backend/server.py` -- Host server (runs on the Mac).
- `backend/export.sh` -- CLI helper: verify + push a game to the host.
- `public/` -- Host SPA (lobby, game frame, results).
- `games/` -- Minigame HTML files live here.
- `data/` -- Session state persistence.

## Agent Notes

When working in this repo:
- Read `docs/design.md` for the **authoritative V1 contract** (HTTP API shapes, `postMessage` types, `session.json` schema, scoring formula, controller mapping).
- Each minigame is a single HTML file in `games/`. No build step, no external deps.
- The host is Python (FastAPI + uvicorn). Keep it simple -- this is a party, not production.
- The skills in `skills/` guide the full lifecycle: `init-game/` scaffolds a new game, `minigame-dev/` drives the dev workflow, `verify-game/` validates before export, and `host-server/` helps run/debug hosting.
- Prioritize fun and playability over polish. Games should be quick to build and quick to play.

V1 clarifications (do not deviate unless you update the contract in `docs/design.md`):

- Controller model: **minigames read the Gamepad API directly inside the iframe**; host assigns slot→`gamepadIndex`.
- Host browser: standardize on **Chrome/Chromium** on the host for best Gamepad API consistency.
- Iframe communication: all messages are `{ type, payload }` and use the `maribro:*` types in the design doc.
- SDK requirement: **all minigames must include** `<script src="/maribro-sdk.js"></script>`.
- 2+ players: games should use `ctx.activeSlots` / `Maribro.getActiveSlots()` and “run” with 2+ active slots (inactive slots should be ignored/idle).
- Audio (opt-in): if the user asks for sound, implement it via `Maribro.audio.playNote(...)`. **Implicit opt-in**: the first `playNote` call disables SDK fallback bloops automatically.

### Automated Verification (IMPORTANT)

**Before exporting any game to the host, ALWAYS use the verify skill at `skills/verify-game/SKILL.md`.** The verify skill validates the game against the minigame contract, interprets any failures, fixes common issues, and re-verifies in a loop until the game passes. Agents should invoke this proactively during development -- not just at export time.

## Host Quickstart (V1)

The host is expected to use an AI coding agent. Humans should say “start the host”; the agent executes the commands below.

- Dependency tool: **use `uv`** (assumed available on host + vibe-coder machines).
- Install deps: `uv sync`
- Run server: `uv run uvicorn backend.server:app --port 8000`
- Open host UI in Chrome: `http://localhost:8000`
- Vibe-coder export flow:
  - Verify: `uv run python3 skills/verify-game/scripts/verify.py games/<your-game>.html`
  - If runtime tooling is missing: `uv sync --extra verify && uv run playwright install chromium`
  - Temporary fallback (environment constrained only): `uv run python3 skills/verify-game/scripts/verify.py --allow-no-runtime games/<your-game>.html`
  - Export: `./backend/export.sh --host http://<host-ip>:8000 --avatar <avatar-id> --file games/<your-game>.html`
