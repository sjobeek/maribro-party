# Maribro Party -- Technical Design

## Skills-first, agent-mediated (V1)

This repo is meant to be used through AI coding agents that read `AGENTS.md` and execute the embedded skills in `skills/`.

- Humans say: “start the host”, “make me a minigame”, “iterate”, “send it”.
- Agents do: scaffold → run locally (mock mode) → verify/fix → upload → repeat.

Participant “types” are hats:

- **Host**: runs the lobby + server on the big screen (can also vibe-code and/or play).
- **Vibe-coder**: builds and submits games.
- **Player**: plays on the couch with a controller.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  Host Mac (Big Monitor, Full-Screen Browser)            │
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │  Lobby   │──▶│ Minigame │──▶│ Results  │──┐         │
│  │  (vote)  │   │ (iframe) │   │ (scores) │  │         │
│  └──────────┘   └──────────┘   └──────────┘  │         │
│       ▲                                       │         │
│       └───────────────────────────────────────┘         │
│                                                         │
│  FastAPI Server (port 8000)                             │
│  ├── Serves public/ SPA                                 │
│  ├── GET  /api/games      (list available games)        │
│  ├── POST /api/games      (upload a new game)           │
│  ├── GET  /api/session    (current scores + state)      │
│  ├── POST /api/session    (reset / manage session)      │
│  └── Watches games/ dir for new files                   │
│                                                         │
│  Optional: Tunnel proxy (cloudflared / ngrok)           │
│  └── Exposes upload endpoint to LAN + internet          │
│                                                         │
│  4x PS4 DualShock 4 ──(Bluetooth)──▶ Gamepad API       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Vibe-Coder Laptop (dev + test only, no real gameplay)  │
│                                                         │
│  Clone repo ──▶ Agent + Skill ──▶ Local dev server     │
│  Edit game ──▶ Test in browser (mock mode, no scoring)  │
│  Verify skill ──▶ export ──▶ HTTP POST to host          │
│                                                         │
│  Games are static artifacts until they reach the host.  │
│  No controllers, no real scoring -- just dev iteration. │
└─────────────────────────────────────────────────────────┘
```

## Host Server

### Stack

- **Backend**: Python 3.10+, FastAPI, uvicorn
- **Frontend**: Vanilla HTML/CSS/JS SPA served from `public/`
- **Persistence**: JSON file at `data/session.json`

Dependency management convention (V1): use **`uv`** for installing/running Python tooling across host + vibe-coder environments.

### API Endpoints

All JSON responses use this envelope:

- Success: `{ "ok": true, ... }`
- Failure: `{ "ok": false, "error": { "code": string, "message": string } }`

**`GET /api/games`** -- List available minigames.

- Response: `{ "ok": true, "games": GameSummary[] }`
- `GameSummary`:
  - `id: string` (stable id, usually the filename stem)
  - `filename: string` (e.g. `button-masher.html`)
  - `title: string`
  - `description: string`
  - `author: string`
  - `creatorAvatarId: string`
  - `maxDurationSec: number` (default 30)
  - `uploadedAt: string` (ISO)

**`POST /api/games`** -- Upload a new minigame (multipart).

- Form fields:
  - `file`: the `.html` file
  - `creator_avatar_id`: string (must be a known avatar id)
  - `upload_token`: required unless sent via `X-Maribro-Token` header
  - optional `filename`: string (kebab-case + `.html`); otherwise derived from upload name
- Header alternative:
  - `X-Maribro-Token`: upload token
- Token behavior:
  - default token: `maribro-upload`
  - override via host env: `MARIBRO_UPLOAD_TOKEN`
- Response: `{ "ok": true, "game": GameSummary }`
- V1 server-side validation:
  - Enforce `.html` extension, size limit (20MB)
  - Parseable HTML (best-effort)
  - **No external resources**:
    - Disallow any `http://`, `https://`, or protocol-relative `//...` in `src=` / `href=`
    - Allow the canonical same-origin SDK script reference: `/public/maribro-sdk.js`
    - For other `src=` (images/audio/video), require `data:` URIs (single-file artifact)

**`GET /api/session`** -- Current session state.

- Response: `{ "ok": true, "session": SessionState }`

**`POST /api/session/reset`** -- Reset scores/history and start a new session.

- Response: `{ "ok": true }`

**`POST /api/session/players`** -- Set which avatars + controllers occupy slots.

- Body:
  - `{ "playersBySlot": Array<{ "slot":0|1|2|3, "avatarId":string, "gamepadIndex":number }> }`
- Response: `{ "ok": true, "session": SessionState }`

**`POST /api/session/record_game`** -- Record a finished game (scores + optional ratings).

- Body:
  - `{ "gameId":string, "scoresBySlot":[number,number,number,number], "ratingsBySlot"?:[-1|0|1,-1|0|1,-1|0|1,-1|0|1] }`
- Response: `{ "ok": true, "session": SessionState }`

### Session persistence (`data/session.json`)

The host persists session state as JSON so scores and history survive restarts.

`SessionState` schema (V1):

- `version: 1`
- `createdAt: string` (ISO)
- `updatedAt: string` (ISO)
- `playersBySlot: Array<{ slot:0|1|2|3, avatarId:string, gamepadIndex:number, lockedIn:boolean }>`
- `scoreboardByAvatarId: Record<string, { play:number, creator:number, total:number }>`
- `history: Array<{ playedAt:string, gameId:string, creatorAvatarId:string, scoresBySlot:[number,number,number,number], ratingsBySlot?:[-1|0|1,-1|0|1,-1|0|1,-1|0|1] }>`

### File Watching

The server watches `games/` for filesystem changes and automatically updates the game list in the lobby.
V1 implementation note: this can be implemented as **frontend polling** (`GET /api/games` every ~2s) instead of true filesystem watching.

## Tunnel / Proxy

The host can optionally run a tunnel proxy to make the upload endpoint reachable without LAN/WSL2 headaches.

**Recommended: cloudflared** -- Run `cloudflared tunnel --url http://localhost:8000` to get a public URL. Works from WSL2, other LANs, or anywhere on the internet. No account required for quick tunnels.

**Alternative: ngrok** -- `ngrok http 8000`.

The tunnel URL is a simple identifier vibe-coders can give to their AI agents: "export my game to this URL".

## Minigame Contract

### File Format

Each minigame is a single `.html` file in `games/`. Everything is inlined -- no external CSS, JS, or assets (base64-encode images if needed). During actual gameplay, the host serves the game in an iframe on the big monitor.

**V1 controller model (authoritative):** the minigame reads the **Gamepad API directly inside the iframe**. The host SPA is responsible for mapping player slots (`0..3`) to `navigator.getGamepads()[gamepadIndex]` indices during the controller-assignment step.

The host enforces timer and records scores. Vibe-coder laptops only run games locally in mock mode for development.

**V1 SDK requirement (authoritative):** minigames MUST include the SDK:

`<script src="/public/maribro-sdk.js"></script>`

This is required so gameplay, scoring, timer, audio, and mock mode behave consistently across games.

**V1 round flow requirement (authoritative):**

- Games must show a 3-second start countdown before live gameplay input begins.
- Games must show a winner/results screen with scores before calling `Maribro.endGame(...)`.

### Metadata

Games declare metadata via `<meta>` tags in `<head>` (title, description, author, max duration). All optional -- the host uses filename as fallback for title, and 30s as default max duration.

### Communication Protocol

The host and minigame iframe communicate via `postMessage`:

All messages are JSON: `{ "type": string, "payload": object }`.

**Host → Game**

- `maribro:init`
  - payload:
    - `sessionId: string`
    - `slotToGamepadIndex: [number,number,number,number]`
    - `playersBySlot: Array<{ slot:0|1|2|3, avatarId:string, name:string, color:string }>`
    - `maxDurationSec: number`
    - `startedAtMs: number` (from `performance.now()` on the host)
- `maribro:tick`
  - payload: `{ nowMs:number, timeRemainingMs:number }` (sent ~5–10Hz)
- `maribro:force_end`
  - payload: `{ reason:"timeout"|"host" }`

**Game → Host**

- `maribro:ready`
  - payload: `{ sdkVersion:string }`
- `maribro:game_end`
  - payload: `{ scoresBySlot:[number,number,number,number], endedAtMs:number }`

Validation rules:

- Host only accepts messages from the iframe it created and from same-origin.
- Host clamps scores to `[0,10]` and treats NaN as 0.
If a game doesn't report scores before max duration, the host awards 0 to everyone.

### Rendering

- Shared screen: all players visible on a single full-viewport canvas or DOM
- Target resolution: 1920x1080 (the big monitor)
- The iframe gets the full viewport -- games should fill it
- Canvas 2D, WebGL, or DOM-based -- whatever suits the game

## SDK (required): maribro-sdk.js

V1 requires the SDK. It wraps the postMessage protocol and Gamepad API into a cleaner interface:

- Player info (avatars, colors)
- Normalized controller input per player
- Score reporting helper
- Ready callback (fires when player info arrives from host)
- Time remaining (synced from host timer)
- **Mock mode**: When loaded outside the host iframe (local dev), the SDK generates placeholder players and maps keyboard input so vibe-coders can test without controllers. No scores are recorded locally -- the game file is a static artifact until exported to the host.

### SDK API (authoritative for V1)

Games can use `/public/maribro-sdk.js`, which exposes `window.Maribro`:

- `Maribro.onReady((ctx)=>void)`
  - `ctx.playersBySlot`
  - `ctx.activeSlots` (array of slots with assigned avatar + controller; minimum expected is 2)
  - `ctx.maxDurationSec`
  - `ctx.slotToGamepadIndex`
- `Maribro.getInput(slot:number)` → normalized:
  - `{ axes:{lx,ly,rx,ry}, buttons:{south,east,west,north,l1,r1,l2,r2,select,start,l3,r3,dup,ddown,dleft,dright} }`
- `Maribro.getActiveSlots(): number[]`
- `Maribro.getTimeRemainingMs(): number`
- `Maribro.endGame(scoresBySlot:[number,number,number,number])` (posts `maribro:game_end`)

### Mock mode keyboard mapping (deterministic)

Mock mode activates when the SDK does not receive `maribro:init` shortly after load. It creates 4 placeholder players and maps keyboard input:

- Slot 0: `W/A/S/D` (move), `Space` (south), `LeftShift` (east)
- Slot 1: Arrow keys (move), `Enter` (south), `/` (east)
- Slot 2: `I/J/K/L` (move), `N` (south), `M` (east)
- Slot 3: `T/F/G/H` (move), `R` (south), `Y` (east)

### Audio (V1): opt-in with safe fallback

Audio is optional for games, but we want consistent “party-safe” sound defaults.

- **Default (fallback)**: if the game never plays sound, the SDK emits quiet, rate-limited “bloops” on **button-edge presses** (not analog sticks/axes).
- **Opt-in (implicit)**: the first call to `Maribro.audio.playNote(...)` disables fallback bloops for the remainder of the run (prevents double audio).
- **Autoplay note**: browsers may require a user gesture to start audio. The host UI provides an “Audio” button that arms audio for the active iframe.

SDK audio API (minimal, MIDI-ish note events rendered via WebAudio):

- `Maribro.audio.arm(): Promise<void>`
- `Maribro.audio.setEnabled(enabled: boolean)` (host may force-mute)
- `Maribro.audio.setMasterVolume(v: number)` (0..1, default low)
- `Maribro.audio.playNote({ note:number, velocity?:number, durationMs?:number, instrument?: "sine"|"triangle"|"square"|"noise" })`

## Controller System

PS4 DualShock 4 controllers connect to the Mac via Bluetooth. The browser's Gamepad API with standard mapping provides consistent button indices. The SDK (or direct Gamepad API usage) gives games access to sticks, face buttons (Cross, Circle, Square, Triangle), shoulder buttons, and D-pad.

The lobby includes a controller test/assignment screen where each player presses a button to claim a slot and pick their avatar.

## Player Avatars

~16 premade avatars, each with a dominant color and a short name (e.g. `knight-red`, `wizard-blue`). Avatar images stored in `public/avatars/`. Minigames receive the avatar ID and hex color so they can render players however they like.

The avatar list and color palette will be defined during implementation.

## Scoring

### Player Scores (from playing)

- Points per game: 0-10 per player (game decides distribution)
- Cumulative across the session
- Persisted to `data/session.json` (survives server restart)

### Creator Scores (from making games)

After each minigame, players do a quick thumbs-up/thumbs-down rating via controller. The creator earns bonus points based on the ratio of positive votes. Creator points are added to the same global scoreboard as player points.

V1 concrete formula:

- `pos = count(rating == 1)`, `neg = count(rating == -1)`, `votes = pos + neg`
- If `votes == 0`: creator bonus = `0`
- Else: creator bonus = `round(10 * pos / votes)` (0..10)

The lobby leaderboard shows a combined total with a breakdown of play score vs creator score.

## Lobby and Game Selection

Players browse and vote on the next game using their controllers. The game list shows title, creator avatar, and past ratings. Voting is quick -- a few seconds, then the winning game loads. Ties broken randomly. Can also auto-pick a random unplayed game.

## Post-Game Rating Flow

After the results screen: a brief "rate this game" prompt, players press a button for thumbs up or down (few seconds), rating displayed, creator bonus awarded, transition back to lobby.

## Game Verification

Automated validation ensures games satisfy the minigame contract before they reach the host. A verification script checks:

**Required (must pass):**
- Valid HTML structure
- Self-contained (no external resource references)
- Reasonable file size
- Has a rendering target (canvas or DOM)
- Has score reporting (postMessage or SDK call)
- Uses the SDK (required)
- Runtime completion flow (game reaches `endGame` with host-effective scores)

**Warnings (non-blocking):**
- Missing metadata tags (title, description, author)

The verify skill (`skills/verify-game/`) wraps the script with agent-level intelligence: interpret failures, apply fixes, and re-verify in a loop.
The script lives at `skills/verify-game/scripts/verify.py`. By default it requires runtime E2E checks and fails if tooling is missing. Use `--allow-no-runtime` only as a temporary fallback when environment constraints block runtime checks.

Integration points:
1. **Export process** -- Runs verification before uploading. Aborts on failure.
2. **Host server** -- Also runs basic validation on upload as a second gate.
3. **Agent skill** -- Agents invoke the verify skill proactively during development.

## Directory Structure

```
maribro-party/
├── AGENTS.md                 # Project concept and agent background
├── pyproject.toml            # Python deps (uv-first)
├── backend/
│   ├── server.py             # FastAPI host server
│   └── export.sh             # CLI helper: verify + push a game to the host
├── public/
│   ├── index.html            # Host SPA (lobby, game frame, results)
│   ├── style.css
│   ├── app.js                # Host frontend logic
│   ├── maribro-sdk.js        # Required SDK for minigames
│   └── avatars/              # Avatar images
├── games/
│   ├── _template.html        # Starter template
│   └── (submitted games)
├── skills/
│   ├── init-game/
│   │   └── SKILL.md          # Agent skill: scaffold a new game
│   ├── minigame-dev/
│   │   └── SKILL.md          # Agent skill: dev workflow
│   ├── verify-game/
│       ├── SKILL.md          # Agent skill: game contract verification
│       └── scripts/
│           └── verify.py     # Verifier used by the skill/export flow
│   ├── setup/
│       ├── SKILL.md          # Agent skill: sets up local environment deps
│       └── scripts/
│           └── setup_env.py
│   └── host-server/
│       ├── SKILL.md          # Agent skill: run/debug host server
│       └── scripts/
│           ├── start_host_server.sh
│           └── debug_host_server.sh
├── docs/
│   └── design.md             # This file
└── data/
    └── session.json          # Session state (auto-created)
```

## Vibe-Coder Workflow

The human-facing loop is intentionally simple and agent-driven:

1. Clone the repo on your laptop
2. Open it in your AI coding agent of choice (this repo includes embedded skills in `skills/`)
3. Tell your agent: **“make me a minigame”** (one-sentence concept + your avatar id)
4. Playtest locally (SDK mock mode: keyboard controls)
5. Tell your agent: **“iterate / make it fun”** until it’s ready
6. Tell your agent: **“send it”** (provide the host URL)

What the agent should do behind the scenes:

- Scaffold via `skills/init-game/`
- Verify/fix via `skills/verify-game/` until required checks pass
- Upload to the host via `POST /api/games`

Once uploaded, the game appears in the lobby on the big monitor — now it's real: controllers, scoring, and ratings happen on the host.

## Export

The export process: run verification locally, then HTTP POST the game file and creator avatar ID to the host's upload endpoint. A CLI helper script wraps this.

## WSL2 Notes

- **Outbound HTTP works fine** -- export can reach the host or tunnel URL without special config
- **Inbound connections are the problem** -- this is why we use HTTP push and optionally a tunnel
- **Local testing** -- a local dev server inside WSL2 is reachable at localhost from the Windows browser

## Future Considerations / Backlog

- **"Set up local agent session" skill** -- A guided skill that walks a semi-technical participant through cloning the repo, picking an avatar, configuring their AI coding agent, and connecting to the host. Goal: one git-savvy friend can get everyone else set up.
- WebSocket for real-time lobby updates (game list, player joins)
- Spectator mode via stream endpoint
- Tournament mode: bracket-style elimination
- Sound system: host lobby music, per-game audio
- Game versioning: re-uploading updated versions
- Creator dashboard: web page showing your games, ratings, and creator score
- Single-file session export/import (portable “party save” bundle containing `games/` + `session.json` + manifest)
