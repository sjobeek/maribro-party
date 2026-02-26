# Maribro Party

Maribro Party is an agentic meta-game: compete with friends in your own vibe-coded minigames while your agents build the next round.

One machine (“the host”) runs the lobby + scoreboard on a big screen. Friends (“vibe-coders”) clone this repo and use an AI coding agent to build new minigames as single self-contained HTML files, then upload them into the live session.

## Core concept: skills-first, agent-mediated

This repo assumes participants have AI coding agents and that most interactions with the codebase are **mediated by agents using skills**.

- Humans say: **“start the host”**, **“make me a minigame”**, **“iterate”**, **“send it”**.
- Agents do: scaffold → run locally (mock mode) → verify/fix → upload → repeat.

## Participants

Participant “types” are hats. One person can be all of these in a single night.

- **Host**: runs the lobby + server on the big screen (can also vibe-code and/or play).
- **Players (up to 4 at a time)**: sit at the big screen with controllers, pick avatars, choose games, play, accumulate scores.
- **Vibe-coders (any number)**: build new minigames on their laptops and export/upload them to the host while the party is running.

## User workflows (front-and-center)

### Host (the big screen)

**Core assumption:** the host uses an AI coding agent too. Humans mostly say what they want; agents use the repo’s skills/contract to make it happen.

1. Clone this repo on the host machine.
2. Open the repo in your AI coding agent and say something like:
   - **“Start the Maribro Party host”**
   - **“Run the host server and tell me what URL to open”**
3. The agent should install/run using `uv`, then tell you what to open in Chrome:
   - usually `http://localhost:8000`
4. Start the durable host tmux session (server + tunnel windows) and share the printed tunnel URL:
   - `bash skills/host-server/scripts/setup_host_tmux.sh 0.0.0.0 8000`
5. Connect controllers and assign players/avatars in the UI.
6. Tell vibe-coders the host URL (prefer tunnel URL) so they can say **“send it”**.

### Vibe-coder (make games during the party)

The vibe-coder loop is intentionally simple:

1. Clone this repo.
2. Open it in your AI coding agent.
3. Tell your agent: **“make me a minigame”** (describe the vibe/genre in one sentence).
4. **Playtest locally** in your browser (SDK mock mode gives keyboard controls).
5. Say **“iterate / make it fun”** and keep tweaking until it’s good.
6. When you’re happy, say **“send it”** (give the agent the host URL and your avatar id).

Behind the scenes the agent should:

- Scaffold a contract-compliant `games/<name>.html` via `skills/init-game/`
- Run the verify-fix loop via `skills/verify-game/` until it passes
- Upload to the host via `POST /api/games` (the included `backend/export.sh` is the reference CLI)

After “send it”, the game appears in the host lobby and can be played immediately.

### Player-only (just play, no coding)

1. Sit at the host screen.
2. Pick an avatar and claim a controller slot.
3. Vote on games, play short rounds, watch the leaderboard.
4. If something is too loud/quiet, ask the host to toggle the **Audio** button.

## Technical details (for implementers/agents)

### Hosting assumptions (V1)

- **Host runs a local FastAPI server** (serves `public/`, serves `games/`, exposes `/api/*`).
- **Host browser**: use **Chrome/Chromium** on the host for best Gamepad API consistency.
- **Controllers**: Gamepad API (e.g. DS4 via Bluetooth on the host machine).
- **Network**: vibe-coders push games to the host via HTTP `POST /api/games` (LAN IP or a tunnel URL).
- **Default share URL**: use cloudflared quick tunnel URL for phones/remote devices.
- **Dependency tool**: use **`uv`** (`pyproject.toml` is the source of truth).
- **Upload auth (lightweight)**: `POST /api/games` requires token `maribro-upload` by default (override with `MARIBRO_UPLOAD_TOKEN` on host + vibe-coder envs).

### Host run commands (what the host agent executes)

From the repo root (durable default):

```bash
uv sync
bash skills/host-server/scripts/setup_host_tmux.sh 0.0.0.0 8000
```

Then open: `http://localhost:8000`

Useful host lifecycle commands:

```bash
bash skills/host-server/scripts/restart_host_tmux.sh 0.0.0.0 8000
bash skills/host-server/scripts/stop_host_tmux.sh --yes
tmux attach -t maribro-host
```

If host token is customized:

```bash
export MARIBRO_UPLOAD_TOKEN=<your-token>
```

### Agent skills (repo-guided workflow)

- Project overview + constraints: `AGENTS.md`
- Technical contract: `docs/design.md`
- Dev workflow skill: `skills/minigame-dev/SKILL.md`
- New game scaffolding: `skills/init-game/SKILL.md`
- Verification loop: `skills/verify-game/SKILL.md`
- Environment setup (WSL/macOS/Linux): `skills/setup/SKILL.md`
- Host run/debug workflow: `skills/host-server/SKILL.md`

### Minigame contract (what you can build)

V1 minigames are:

- **Single, self-contained HTML files** in `games/` (inline CSS/JS; assets as `data:` URIs).
- **Shared-screen** (one view; no split-screen).
- **2+ players expected** (host requires at least 2 assigned players to start a game).
- **SDK required**: games must include:

```html
<script src="/public/maribro-sdk.js"></script>
```

The SDK provides:

- `Maribro.onReady((ctx) => ...)` with `ctx.playersBySlot` and `ctx.activeSlots`
- `Maribro.getInput(slot)` (normalized gamepad input)
- `Maribro.endGame([s0,s1,s2,s3])` (scores 0..10)
- Mock mode keyboard mapping for development
- Optional audio: `Maribro.audio.playNote(...)` (with fallback “bloops” if a game is silent)

Full protocol + schemas live in `docs/design.md`.

## Repo layout

- `backend/server.py`: FastAPI host server
- `public/`: host UI + `maribro-sdk.js` + avatars
- `games/`: minigame HTML files
- `skills/verify-game/scripts/verify.py`: contract verification (run before export)
- `backend/export.sh`: verify + upload helper
- `data/session.json`: persisted session state (auto-created)

## Verification runtime deps

Default verification requires runtime E2E checks:

```bash
uv sync --extra verify
uv run playwright install chromium
uv run python3 skills/verify-game/scripts/verify.py games/<game>.html
```

Fallback only when environment constraints block runtime:

```bash
uv run python3 skills/verify-game/scripts/verify.py --allow-no-runtime games/<game>.html
```
