# Maribro Party

## What Is This?

Maribro Party is a collaborative vibe-coded minigame party framework. Think Mario Party, but the games themselves are created in real time by friends using AI-assisted coding.

**The setup:** A group gathers around a big monitor connected to a Mac host PC with 4 PS4 DualShock 4 controllers. Players sit on the couch and play short competitive minigames back-to-back, with scores accumulating across the session. Meanwhile, other participants ("vibe-coders") sit on their own laptops, vibe-coding new minigames and hot-submitting them to the live session. The game library grows in real time as people play.

## Participants

Everyone picks an avatar from the same pool of ~16 premade characters. Whether you're on the couch with a controller, on a laptop vibe-coding, or both -- you're the same avatar everywhere. Many participants will do both.

**Players** (up to 4 at a time) -- Sitting at the big monitor with PS4 controllers. They pick avatars, vote on which game to play next, compete in minigames, and watch scores accumulate on the leaderboard.

**Vibe-Coders** (any number) -- On their own laptops, cloning this repo, using the embedded Cursor skill to scaffold and test minigames locally, then pushing finished games to the host. When exporting, they specify their avatar ID so the host knows who made each game.

**Creating great games earns you kudos.** After each minigame, players do a quick thumbs-up/thumbs-down vote on the game itself. Good ratings give the creator bonus points on the global scoreboard. So if you're both playing well AND making bangers, you climb the leaderboard from both sides.

## The Core Loop

```
Lobby → Vote on next game → Minigame (30-90s) → Results + Scores → Lobby
         ↑                                                          |
         └──── new games appear as vibe-coders submit them ─────────┘
```

## Player Identity

~16 premade avatars, each with a dominant color (red, blue, green, yellow, purple, orange, etc.). Players pick their avatar in the lobby using their controllers. The avatar ID and color are passed to each minigame so games can render players consistently.

## Minigame Format

Each minigame is a **single self-contained HTML file**. Inline CSS, inline JS, no external dependencies. Shared-screen rendering (all 4 players visible on one view -- not split-screen). Games are loaded in an iframe by the host framework.

A minigame must:
- Render into the full viewport
- Support exactly 4 players
- Read controller input via the Gamepad API (or the optional `maribro-sdk.js`)
- Signal completion by posting scores back to the host
- Be completable in 30-90 seconds

Games can end themselves, but the host enforces a max timer as a safety net.

## How Games Reach the Host

Games are verified locally before export. The repo includes a `scripts/verify.py` script that checks the game satisfies the minigame contract (valid HTML, has scoring, supports 4 players, no external deps, etc.). The export script runs verification automatically -- broken games never reach the host.

Once verified, vibe-coders push finished games to the host via HTTP, specifying their avatar ID as creator. The host exposes an upload endpoint and optionally a tunnel URL (via cloudflared, ngrok, or similar) so vibe-coders don't need to fight LAN/WSL2 networking. The tunnel URL can even be shared with remote participants over the internet.

## Network Topology

All devices on the same LAN. The Mac host runs the server and displays on the big monitor. Some vibe-coders may be developing inside WSL2, where inbound connections are painful -- so the system uses outbound HTTP pushes (not inbound SSH/rsync) and optionally a tunnel proxy on the host to make the upload URL universally reachable.

## Project Structure

- `AGENTS.md` -- This file. Concept and background.
- `docs/design.md` -- Technical architecture and framework design.
- `skills/` -- Embedded Cursor skill for vibe-coder workflow.
- `scripts/verify.py` -- Automated game validation (run before export).
- `server.py` -- FastAPI host server (runs on the Mac).
- `export.sh` -- CLI helper: verify + push a game to the host.
- `public/` -- Host SPA (lobby, game frame, results).
- `games/` -- Drop minigame HTML files here. Includes `_template.html`.
- `data/` -- Session state persistence.

## Agent Notes

When working in this repo:
- Read `docs/design.md` for the technical contract (minigame API, scoring protocol, controller mapping).
- Each minigame is a single HTML file in `games/`. No build step, no external deps.
- The host is Python (FastAPI + uvicorn). Keep it simple -- this is a party, not production.
- The embedded skill in `skills/` guides the minigame development workflow.
- Prioritize fun and playability over polish. Games should be quick to build and quick to play.

### Automated Verification (IMPORTANT)

**Before exporting any game to the host, ALWAYS run `python3 scripts/verify.py games/<game>.html` first.** Do not skip this step. The verify script checks that the game satisfies the minigame contract and will catch common issues (missing score reporting, external dependencies, malformed HTML, etc.). Fix any failures before exporting. The `export.sh` script also runs verification automatically, but agents should run it proactively during development -- not just at export time.
