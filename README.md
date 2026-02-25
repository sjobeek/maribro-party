# Maribro Party

Maribro Party is a *vibe-coded* Mario-Party-like minigame party framework.

One machine (“the host”) runs the lobby + scoreboard on a big screen. Friends (“vibe-coders”) clone this repo and use an AI coding agent to build new minigames as single self-contained HTML files, then upload them into the live session.

## Participants

- **Players (up to 4 at a time)**: sit at the big screen with controllers, pick avatars, choose games, play, accumulate scores.
- **Vibe-coders (any number)**: build new minigames on their laptops and export/upload them to the host while the party is running. (Many people will do both.)

## User workflows (front-and-center)

### Host (the big screen)

1. Clone this repo on the host machine.
2. Start the server:

```bash
uv sync
uv run uvicorn server:app --port 8000
```

3. Open the host UI in Chrome:
   - `http://localhost:8000`
4. Connect controllers (Gamepad API) and assign players/avatars in the UI.
5. Tell vibe-coders the host URL (LAN IP or tunnel) so they can “send it”.

### Vibe-coder (make games during the party)

The vibe-coder loop is intentionally simple:

1. Clone this repo.
2. Tell your AI coding agent: **“make me a minigame”** (describe the vibe/genre in one sentence).
3. **Playtest locally** in your browser (SDK mock mode gives keyboard controls).
4. Say **“iterate / make it fun”** and keep tweaking until it’s good.
5. When you’re happy, say **“send it”** (give the agent the host URL and your avatar id).

Behind the scenes the agent should:

- Scaffold a contract-compliant `games/<name>.html` via `skills/init-game/`
- Run the verify-fix loop via `skills/verify/` until it passes
- Upload to the host via `POST /api/games` (the included `export.sh` is the reference CLI)

After “send it”, the game appears in the host lobby and can be played immediately.

### Player-only (just play, no coding)

1. Sit at the host screen.
2. Pick an avatar and claim a controller slot.
3. Vote on games, play short rounds, watch the leaderboard.
4. If something is too loud/quiet, ask the host to toggle the **Audio** button.

## Quickstart (host)

From the repo root:

```bash
uv sync
uv run uvicorn server:app --port 8000
```

Then open the host UI:

- `http://localhost:8000`

## Technical details (for implementers/agents)

### Hosting assumptions (V1)

- **Host runs a local FastAPI server** (serves `public/`, serves `games/`, exposes `/api/*`).
- **Host browser**: use **Chrome/Chromium** on the host for best Gamepad API consistency.
- **Controllers**: Gamepad API (e.g. DS4 via Bluetooth on the host machine).
- **Network**: vibe-coders push games to the host via HTTP `POST /api/games` (LAN IP or a tunnel URL).
- **Dependency tool**: use **`uv`** (`pyproject.toml` is the source of truth).

### Agent skills (repo-guided workflow)

- Project overview + constraints: `AGENTS.md`
- Technical contract: `docs/design.md`
- Dev workflow skill: `skills/SKILL.md`
- New game scaffolding: `skills/init-game/SKILL.md`
- Verification loop: `skills/verify/SKILL.md`

### Minigame contract (what you can build)

V1 minigames are:

- **Single, self-contained HTML files** in `games/` (inline CSS/JS; assets as `data:` URIs).
- **Shared-screen** (one view; no split-screen).
- **2+ players expected** (host requires at least 2 assigned players to start a game).
- **SDK required**: games must include:

```html
<script src="/maribro-sdk.js"></script>
```

The SDK provides:

- `Maribro.onReady((ctx) => ...)` with `ctx.playersBySlot` and `ctx.activeSlots`
- `Maribro.getInput(slot)` (normalized gamepad input)
- `Maribro.endGame([s0,s1,s2,s3])` (scores 0..10)
- Mock mode keyboard mapping for development
- Optional audio: `Maribro.audio.playNote(...)` (with fallback “bloops” if a game is silent)

Full protocol + schemas live in `docs/design.md`.

## Repo layout

- `server.py`: FastAPI host server
- `public/`: host UI + `maribro-sdk.js` + avatars
- `games/`: minigame HTML files
- `scripts/verify.py`: contract verification (run before export)
- `export.sh`: verify + upload helper
- `data/session.json`: persisted session state (auto-created)

