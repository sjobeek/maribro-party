# Maribro Party -- Technical Design

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
│  Vibe-Coder Laptop (any number)                         │
│                                                         │
│  Clone repo ──▶ Cursor + Skill ──▶ Local dev server    │
│  Edit games/_template.html ──▶ Test in browser          │
│  ./export.sh <host-url> my-game.html ──▶ HTTP POST     │
└─────────────────────────────────────────────────────────┘
```

## Host Server

### Stack

- **Backend**: Python 3.10+, FastAPI, uvicorn
- **Frontend**: Vanilla HTML/CSS/JS SPA served from `public/`
- **Persistence**: JSON file at `data/session.json`

### API Endpoints

**`GET /api/games`** -- List available minigames.

Returns an array of game metadata objects, scanned from HTML files in `games/`:
```json
[
  {
    "id": "bumper-balls",
    "filename": "bumper-balls.html",
    "title": "Bumper Balls",
    "description": "Knock opponents off the platform!",
    "author": "Erik",
    "max_duration": 60
  }
]
```

Metadata is extracted from `<meta>` tags in the HTML file (see Minigame Contract below).

**`POST /api/games`** -- Upload a new minigame.

Accepts multipart form data with a single `.html` file and a `creator` field (avatar ID of the vibe-coder). Saves the file to `games/`, records creator attribution, and returns the extracted metadata. The game appears in the lobby immediately.

```bash
curl -F "game=@my-game.html" -F "creator=knight-red" http://<host>:8000/api/games
```

The server also runs server-side validation on upload and rejects games that fail basic contract checks.

**`GET /api/session`** -- Current session state.

Returns player info, cumulative scores, game history, and available games.

**`POST /api/session/reset`** -- Reset scores and start a new session.

### File Watching

The server watches `games/` for filesystem changes (new files, modifications, deletions) using `watchfiles` or polling. The game list in the lobby updates automatically.

## Tunnel / Proxy

The host can optionally run a tunnel proxy to make the upload endpoint reachable without LAN/WSL2 headaches.

### Recommended: cloudflared (Cloudflare Tunnel)

```bash
# On the host Mac, after starting the server:
cloudflared tunnel --url http://localhost:8000
```

This prints a public URL like `https://random-words.trycloudflare.com`. Vibe-coders use this URL to upload games -- works from WSL2, other LANs, or anywhere on the internet. No account required for quick tunnels.

### Alternative: ngrok

```bash
ngrok http 8000
```

### Workflow

1. Host starts the server: `python server.py`
2. Host starts the tunnel: `cloudflared tunnel --url http://localhost:8000`
3. Host shares the tunnel URL with vibe-coders (Slack, whiteboard, QR code, etc.)
4. Vibe-coders export games: `./export.sh https://random-words.trycloudflare.com my-game.html`

No SSH keys, no port forwarding, no WSL2 networking gymnastics.

The tunnel URL also serves as a simple identifier vibe-coders can give to their AI agents: "export my game to this URL".

## Minigame Contract

### File Format

Each minigame is a single `.html` file in `games/`. Everything is inlined -- no external CSS, JS, or assets (base64-encode images if needed).

### Metadata

Games declare metadata via `<meta>` tags in `<head>`:

```html
<meta name="maribro-title" content="Bumper Balls">
<meta name="maribro-description" content="Knock opponents off the platform!">
<meta name="maribro-author" content="Erik">
<meta name="maribro-max-duration" content="60">
```

All optional. The host uses filename as fallback for title, and 90s as default max duration.

### Receiving Player Info

On load, the host sends player info to the iframe via `postMessage`:

```js
// The host sends this when the game iframe loads:
window.postMessage({
  type: 'maribro:init',
  players: [
    { index: 0, name: 'Player 1', avatarId: 'knight-red', color: '#e74c3c' },
    { index: 1, name: 'Player 2', avatarId: 'wizard-blue', color: '#3498db' },
    { index: 2, name: 'Player 3', avatarId: 'rogue-green', color: '#2ecc71' },
    { index: 3, name: 'Player 4', avatarId: 'bard-yellow', color: '#f1c40f' }
  ]
}, '*');
```

Games listen for this to know who's playing and what colors/avatars to use.

### Controller Input

Games read controller input directly via the standard Gamepad API:

```js
function readInput(playerIndex) {
  const gamepads = navigator.getGamepads();
  const gp = gamepads[playerIndex];
  if (!gp) return null;
  return {
    leftStickX: gp.axes[0],   // -1 to 1
    leftStickY: gp.axes[1],   // -1 to 1
    cross: gp.buttons[0].pressed,      // X / action
    circle: gp.buttons[1].pressed,     // O / cancel
    square: gp.buttons[2].pressed,
    triangle: gp.buttons[3].pressed,
    l1: gp.buttons[4].pressed,
    r1: gp.buttons[5].pressed,
    l2: gp.buttons[6].pressed,
    r2: gp.buttons[7].pressed,
    dpadUp: gp.buttons[12].pressed,
    dpadDown: gp.buttons[13].pressed,
    dpadLeft: gp.buttons[14].pressed,
    dpadRight: gp.buttons[15].pressed,
  };
}
```

The optional `maribro-sdk.js` wraps this into a cleaner API (see below).

### Reporting Scores

When the game ends, post scores back to the host:

```js
window.parent.postMessage({
  type: 'maribro:gameOver',
  scores: [
    { playerIndex: 0, points: 10 },
    { playerIndex: 1, points: 5 },
    { playerIndex: 2, points: 7 },
    { playerIndex: 3, points: 3 }
  ]
}, '*');
```

Points are integers, 0-10. The host adds these to the cumulative session totals.

If the game doesn't report scores before the max timer, the host awards 0 to everyone.

### Rendering

- Shared screen: all 4 players render on a single full-viewport canvas/DOM
- Target resolution: 1920x1080 (the big monitor)
- The iframe gets the full viewport -- games should fill it
- Use Canvas 2D, WebGL, or DOM -- whatever suits the game

## Optional SDK: maribro-sdk.js

Games can include a `<script>` tag pointing to the host-served SDK for convenience:

```html
<script src="/maribro-sdk.js"></script>
```

The SDK provides:

- `maribro.players` -- Array of player objects (set after init message received)
- `maribro.getInput(playerIndex)` -- Returns normalized input state
- `maribro.endGame(scores)` -- Posts scores to host and signals game over
- `maribro.onReady(callback)` -- Fires when player info is received from host
- `maribro.timeRemaining` -- Seconds left (synced from host timer)
- `maribro.mock` -- Boolean, true when running outside the host (local dev). In mock mode, keyboard keys are mapped to controller input for testing.

### Mock Mode (Local Development)

When loaded outside the host iframe (e.g. opening the HTML file directly or via local dev server), the SDK enters mock mode:

- Generates 4 placeholder players with default colors
- Maps keyboard to Player 1 input: WASD = left stick, J = cross, K = circle, U = square, I = triangle
- Players 2-4 get simple AI or are idle
- `maribro.endGame()` logs scores to console instead of posting

This lets vibe-coders test games locally without the full host setup.

## Controller System

### Hardware

4x PS4 DualShock 4 controllers connected to the Mac via Bluetooth. Pairing: hold Share + PS button until the light bar flashes, then pair in macOS Bluetooth settings.

### Gamepad API Mapping

The browser's Gamepad API with `mapping: "standard"` provides consistent button indices for DualShock 4:

| Button | Index | Usage |
|--------|-------|-------|
| Cross (X) | 0 | Primary action, confirm |
| Circle (O) | 1 | Secondary action, cancel |
| Square | 2 | Game-specific |
| Triangle | 3 | Game-specific |
| L1 | 4 | Game-specific |
| R1 | 5 | Game-specific |
| L2 | 6 | Game-specific |
| R2 | 7 | Game-specific |
| Share | 8 | (reserved) |
| Options | 9 | Pause (handled by host) |
| L3 | 10 | Game-specific |
| R3 | 11 | Game-specific |
| D-pad Up | 12 | Menu navigation |
| D-pad Down | 13 | Menu navigation |
| D-pad Left | 14 | Menu navigation |
| D-pad Right | 15 | Menu navigation |
| PS Button | 16 | (reserved) |

Axes 0-1: Left stick (X, Y). Axes 2-3: Right stick (X, Y).

### Lobby Controller Assignment

The lobby includes a controller test screen where each player presses a button to claim a slot and pick their avatar. The host maps gamepad indices to player indices (0-3) based on join order.

## Player Avatars

~16 premade avatars, each with a dominant color and a short name. Examples:

- `knight-red` (#e74c3c), `wizard-blue` (#3498db), `rogue-green` (#2ecc71), `bard-yellow` (#f1c40f)
- `archer-purple` (#9b59b6), `monk-orange` (#e67e22), `pirate-teal` (#1abc9c), `ninja-pink` (#e91e8f)
- `viking-brown` (#8B4513), `samurai-indigo` (#4b0082), `robot-silver` (#95a5a6), `alien-lime` (#7fff00)
- `dragon-crimson` (#dc143c), `ghost-white` (#ecf0f1), `demon-black` (#2c3e50), `phoenix-gold` (#ffd700)

Avatar images are stored in `public/avatars/` (simple pixel art or vector SVGs). Minigames receive the avatar ID and hex color so they can render players however they like.

## Scoring

### Player Scores (from playing)

- Points per game: 0-10 per player (game decides distribution)
- Cumulative: host adds each game's points to session totals
- Persisted to `data/session.json` (survives server restart)

### Creator Scores (from making games)

After each minigame's results screen, the 4 players do a quick rating -- Cross for thumbs-up, Circle for thumbs-down. This takes ~3 seconds and doesn't break the flow. The creator earns bonus points based on the rating:

- 4 thumbs up: +5 creator points
- 3 thumbs up: +3 creator points
- 2 thumbs up: +1 creator point
- 1 or 0 thumbs up: +0 creator points

Creator points are added to the same global scoreboard as player points. The lobby leaderboard shows a combined total, with a breakdown of "play score" vs "creator score" visible on hover or in the detail view.

### Session JSON Schema

```json
{
  "started_at": "2026-02-25T19:00:00Z",
  "participants": [
    {
      "avatarId": "knight-red",
      "color": "#e74c3c",
      "playScore": 42,
      "creatorScore": 8,
      "totalScore": 50
    },
    {
      "avatarId": "wizard-blue",
      "color": "#3498db",
      "playScore": 38,
      "creatorScore": 3,
      "totalScore": 41
    }
  ],
  "games_played": [
    {
      "game_id": "bumper-balls",
      "creator_avatar": "knight-red",
      "played_at": "2026-02-25T19:05:00Z",
      "scores": [10, 5, 7, 3],
      "rating": { "up": 3, "down": 1, "creator_bonus": 3 }
    }
  ],
  "games_available": [
    {
      "id": "bumper-balls",
      "filename": "bumper-balls.html",
      "title": "Bumper Balls",
      "creator_avatar": "knight-red",
      "uploaded_at": "2026-02-25T18:50:00Z"
    }
  ]
}
```

## Lobby and Game Selection

Players browse and vote using their controllers:

1. Game list displayed on screen (scrollable with D-pad), showing title, creator avatar, and rating history
2. Each player highlights a game with their cursor (color-coded)
3. Cross (X) button to cast vote
4. Game with most votes wins (random tiebreaker)
5. Countdown, then game loads in iframe

Alternatively, the lobby can auto-pick a random unplayed game if configured.

## Post-Game Rating Flow

After the results screen for each minigame:

1. "Rate this game!" prompt appears with the creator's avatar displayed
2. Each player presses Cross (thumbs up) or Circle (thumbs down) -- 5 second window
3. No input counts as abstain (not counted either way)
4. Rating is displayed briefly, creator bonus points awarded
5. Transition back to lobby

## Game Verification

### Purpose

Automated validation ensures games satisfy the minigame contract before they reach the host. This prevents broken or incomplete games from disrupting the live session.

### Verification Script: `scripts/verify.py`

A standalone Python script (stdlib only, no pip deps) that checks a game HTML file against the contract. Run it locally during development and it runs automatically as part of `export.sh`.

```bash
python3 scripts/verify.py games/my-game.html
```

### Checks

**Structural (must pass):**
- File is valid HTML (parseable, has `<html>`, `<head>`, `<body>`)
- File is self-contained (no external `<script src="http...">` or `<link href="http...">` tags -- `maribro-sdk.js` relative path is allowed)
- File size is under 2MB
- Has a `<canvas>` element or substantial DOM content for rendering

**Contract (must pass):**
- Contains a `gameOver` or `maribro:gameOver` postMessage call (score reporting)
- References all 4 player indices (0-3) or uses a loop/array pattern for players
- Contains Gamepad API usage (`navigator.getGamepads`) or `maribro-sdk.js` include

**Metadata (warnings, non-blocking):**
- Has `<meta name="maribro-title">` tag
- Has `<meta name="maribro-description">` tag
- Has `<meta name="maribro-author">` tag

### Output Format

```
$ python3 scripts/verify.py games/bumper-balls.html

Verifying: bumper-balls.html
  [PASS] Valid HTML structure
  [PASS] Self-contained (no external resources)
  [PASS] File size OK (48KB < 2MB)
  [PASS] Has rendering target (canvas)
  [PASS] Has score reporting (maribro:gameOver)
  [PASS] Supports 4 players
  [PASS] Has controller input (Gamepad API)
  [WARN] Missing <meta name="maribro-description">

Result: PASS (1 warning)
Ready to export!
```

Exit code 0 = pass, exit code 1 = fail (with details on what to fix).

### Integration Points

1. **`export.sh`** -- Runs verify before uploading. Aborts on failure.
2. **Host server** -- Also runs basic server-side validation on `POST /api/games` as a second gate.
3. **Agent hook** -- AGENTS.md instructs agents to run verify proactively during development, not just at export time.

## Directory Structure

```
maribro-party/
├── AGENTS.md                 # Project concept and agent background
├── requirements.txt          # Python deps (fastapi, uvicorn, watchfiles)
├── server.py                 # FastAPI host server
├── export.sh                 # CLI helper: verify + push a game to the host
├── scripts/
│   └── verify.py             # Game contract validation
├── public/
│   ├── index.html            # Host SPA (lobby, game frame, results)
│   ├── style.css
│   ├── app.js                # Host frontend logic
│   ├── maribro-sdk.js        # Optional SDK for minigames
│   └── avatars/              # ~16 avatar images
├── games/
│   ├── _template.html        # Starter template for vibe-coders
│   └── (submitted games go here)
├── skills/
│   └── SKILL.md              # Cursor skill for vibe-coder workflow
├── docs/
│   └── design.md             # This file
└── data/
    └── session.json          # Session state (auto-created)
```

## Vibe-Coder Workflow

1. Clone the `maribro-party` repo on your laptop
2. Open in Cursor -- the embedded skill guides you
3. Copy `games/_template.html` to `games/my-game.html`
4. Vibe-code your minigame (the template has the full contract wired up)
5. Start local dev server: `python -m http.server 8080` in the repo root
6. Open `http://localhost:8080/games/my-game.html` -- SDK enters mock mode, keyboard controls Player 1
7. Iterate until fun
8. Verify: `python3 scripts/verify.py games/my-game.html` (agents do this automatically)
9. Export: `./export.sh <host-url> games/my-game.html <your-avatar-id>`
10. Game appears in the lobby on the big monitor, attributed to your avatar

## Export Script

`export.sh` runs verification, then uploads with creator attribution:

```bash
#!/usr/bin/env bash
set -euo pipefail
HOST_URL="${1:?Usage: ./export.sh <host-url> <game-file> <creator-avatar-id>}"
GAME_FILE="${2:?Usage: ./export.sh <host-url> <game-file> <creator-avatar-id>}"
CREATOR="${3:?Usage: ./export.sh <host-url> <game-file> <creator-avatar-id>}"

echo "=== Verifying $(basename "$GAME_FILE")... ==="
python3 scripts/verify.py "$GAME_FILE"
if [ $? -ne 0 ]; then
  echo "Verification failed. Fix the issues above before exporting."
  exit 1
fi

echo ""
echo "=== Uploading to $HOST_URL as $CREATOR... ==="
curl -f -F "game=@$GAME_FILE" -F "creator=$CREATOR" "$HOST_URL/api/games"
echo ""
echo "Done! Game is now available in the lobby."
```

## WSL2 Notes

Vibe-coders developing inside WSL2:
- **Outbound HTTP works fine** -- `curl` and `export.sh` can reach the host Mac or tunnel URL without any special config
- **Inbound connections are the problem** -- this is why we use HTTP push (not rsync/SSH) and optionally a tunnel
- **Local testing**: `python -m http.server 8080` inside WSL2 is reachable at `localhost:8080` from the Windows browser (WSL2 localhost forwarding)

## Future Considerations

- WebSocket for real-time lobby updates (game list, player joins)
- Spectator mode: other browsers can watch the big screen via a stream endpoint
- Tournament mode: bracket-style elimination across games
- Sound system: host plays lobby music, games handle their own audio
- Game versioning: allow re-uploading updated versions of the same game
- Creator dashboard: web page showing your games, ratings, and creator score
