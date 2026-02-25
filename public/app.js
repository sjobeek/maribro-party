const $ = (id) => document.getElementById(id);

const state = {
  avatars: [],
  games: [],
  selectedGameId: null,
  session: null,
  lastPressedGamepadIndex: null,
  lastPressedAtMs: 0,
  claimListeningSlot: null, // 0..3 when waiting for a button press
  claimInFlight: false,
  activeRun: null, // { gameId, startedAtMs, maxDurationSec, tickTimer, hardTimeout }
  audioEnabled: false,
};

function setStatus(text) {
  $("status").textContent = text;
}

async function apiJson(path, opts) {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => null);
  if (!data || data.ok !== true) {
    const msg = data?.error?.message || `${res.status} ${res.statusText}`;
    throw new Error(msg);
  }
  return data;
}

async function apiPostJson(path, body) {
  return apiJson(path, { method: "POST", body: JSON.stringify(body) });
}

function normalizeSession(sess) {
  if (!sess) return null;
  // Ensure playersBySlot is always 4 entries.
  const bySlot = new Map();
  for (const p of sess.playersBySlot || []) bySlot.set(p.slot, p);
  sess.playersBySlot = [0, 1, 2, 3].map((slot) => {
    const p = bySlot.get(slot) || { slot, avatarId: "", gamepadIndex: -1, lockedIn: false };
    return { slot, avatarId: p.avatarId || "", gamepadIndex: Number(p.gamepadIndex ?? -1), lockedIn: !!p.lockedIn };
  });
  return sess;
}

function render() {
  renderPlayers();
  renderGames();
  renderScores();
}

function avatarById(id) {
  return state.avatars.find((a) => a.id === id) || null;
}

function renderPlayers() {
  const wrap = $("players");
  wrap.innerHTML = "";
  const sess = state.session || { playersBySlot: [] };

  for (const slot of [0, 1, 2, 3]) {
    const p = sess.playersBySlot?.find((x) => x.slot === slot) || { slot, avatarId: "", gamepadIndex: -1 };
    const av = avatarById(p.avatarId);
    const color = av?.color || "rgba(255,255,255,0.25)";
    const name = av?.name || "(unassigned)";
    const listening = state.claimListeningSlot === slot;
    const claimBtnText = listening ? "Press button" : "Claim pad";
    const claimBtnClass = listening ? "secondary listening" : "secondary";

    const el = document.createElement("div");
    el.className = "slot";
    el.innerHTML = `
      <div class="badge" style="background:${color}22;border-color:${color}55;color:${color}">${slot + 1}</div>
      <div class="meta">
        <div class="line">
          <div class="chip"><span class="dot" style="background:${color}"></span>${name}</div>
          <div class="chip">pad: ${p.gamepadIndex >= 0 ? p.gamepadIndex : "?"}</div>
        </div>
        <div class="line">
          <select class="select" data-slot="${slot}">
            <option value="">Pick avatar…</option>
            ${state.avatars
              .map((a) => `<option value="${a.id}" ${a.id === p.avatarId ? "selected" : ""}>${a.name} (${a.id})</option>`)
              .join("")}
          </select>
          <button class="${claimBtnClass}" data-claim="${slot}">${claimBtnText}</button>
        </div>
      </div>
    `;
    wrap.appendChild(el);
  }

  wrap.querySelectorAll("select[data-slot]").forEach((sel) => {
    sel.addEventListener("change", async (e) => {
      const slot = Number(e.target.getAttribute("data-slot"));
      const avatarId = e.target.value;
      await updatePlayers({ slot, avatarId });
    });
  });

  wrap.querySelectorAll("button[data-claim]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const slot = Number(e.target.getAttribute("data-claim"));
      if (state.claimInFlight) return;
      const isListening = state.claimListeningSlot === slot;
      state.claimListeningSlot = isListening ? null : slot;
      renderPlayers();
      if (state.claimListeningSlot == null) {
        setStatus("Claim cancelled.");
      } else {
        setStatus(`Slot ${slot + 1}: press any button on the controller you want to claim.`);
      }
    });
  });
}

async function updatePlayers(partial) {
  const sess = state.session;
  const next = sess.playersBySlot.map((p) => ({ ...p }));
  const idx = next.findIndex((p) => p.slot === partial.slot);
  if (idx >= 0) {
    next[idx] = { ...next[idx], ...partial };
  }
  // lockedIn is server-derived; we don't send it.
  const payload = next.map((p) => ({ slot: p.slot, avatarId: p.avatarId || "", gamepadIndex: Number(p.gamepadIndex ?? -1) }));
  const res = await apiPostJson("/api/session/players", { playersBySlot: payload });
  state.session = normalizeSession(res.session);
  render();
}

function renderGames() {
  const wrap = $("games");
  wrap.innerHTML = "";
  for (const g of state.games) {
    const el = document.createElement("div");
    el.className = "game" + (g.id === state.selectedGameId ? " selected" : "");
    const av = avatarById(g.creatorAvatarId);
    const color = av?.color || "rgba(255,255,255,0.25)";
    const creator = g.creatorAvatarId ? `by ${g.creatorAvatarId}` : "by (unknown)";
    el.innerHTML = `
      <div class="title">${escapeHtml(g.title || g.id)}</div>
      <div class="desc">${escapeHtml(g.description || "")}</div>
      <div class="row" style="margin-top:10px;justify-content:space-between;">
        <div class="chip"><span class="dot" style="background:${color}"></span>${escapeHtml(creator)}</div>
        <div class="chip">${g.maxDurationSec}s</div>
      </div>
    `;
    el.addEventListener("click", () => {
      state.selectedGameId = g.id;
      renderGames();
    });
    wrap.appendChild(el);
  }
  if (!state.selectedGameId && state.games.length) {
    state.selectedGameId = state.games[0].id;
    renderGames();
  }
}

function renderScores() {
  const wrap = $("scores");
  const sess = state.session;
  if (!sess) {
    wrap.innerHTML = `<div class="muted">Loading…</div>`;
    return;
  }
  const entries = Object.entries(sess.scoreboardByAvatarId || {});
  entries.sort((a, b) => (b[1]?.total || 0) - (a[1]?.total || 0));
  if (!entries.length) {
    wrap.innerHTML = `<div class="muted">No scores yet.</div>`;
    return;
  }
  wrap.innerHTML = entries
    .map(([aid, s]) => {
      const av = avatarById(aid);
      const color = av?.color || "rgba(255,255,255,0.25)";
      return `
        <div class="slot" style="grid-template-columns: 1fr;">
          <div class="line">
            <div class="chip"><span class="dot" style="background:${color}"></span>${escapeHtml(av?.name || aid)}</div>
            <div class="chip">total: ${Number(s.total || 0)}</div>
          </div>
          <div class="line">
            <div class="chip">play: ${Number(s.play || 0)}</div>
            <div class="chip">creator: ${Number(s.creator || 0)}</div>
          </div>
        </div>
      `;
    })
    .join("");

  const last = (sess.history || [])[sess.history.length - 1];
  if (!last) {
    $("lastResult").textContent = "No games played yet.";
  } else {
    $("lastResult").textContent = `${last.gameId}: [${(last.scoresBySlot || []).join(", ")}]`;
  }
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function slotToGamepadIndex() {
  const sess = state.session;
  const arr = [0, 1, 2, 3].map(() => -1);
  for (const p of sess?.playersBySlot || []) {
    arr[p.slot] = Number(p.gamepadIndex ?? -1);
  }
  return arr;
}

function playersBySlotPayload() {
  const sess = state.session;
  const arr = [];
  for (const p of sess?.playersBySlot || []) {
    const av = avatarById(p.avatarId);
    arr.push({
      slot: p.slot,
      avatarId: p.avatarId || "",
      name: av?.name || p.avatarId || `Player ${p.slot + 1}`,
      color: av?.color || "#888888",
    });
  }
  arr.sort((a, b) => a.slot - b.slot);
  return arr;
}

function postToGame(type, payload) {
  const frame = $("gameFrame");
  if (!frame?.contentWindow) return;
  frame.contentWindow.postMessage({ type, payload }, window.location.origin);
}

function updateAudioButton() {
  const btn = $("audioBtn");
  if (!btn) return;
  btn.textContent = `Audio: ${state.audioEnabled ? "On" : "Off"}`;
  btn.classList.toggle("danger", !state.audioEnabled);
}

function stopActiveRun(reason) {
  const run = state.activeRun;
  if (!run) return;
  clearInterval(run.tickTimer);
  clearTimeout(run.hardTimeout);
  state.activeRun = null;
  if (reason) postToGame("maribro:force_end", { reason });
  postToGame("maribro:audio_config", { enabled: state.audioEnabled, masterVolume: 0.25 });
  $("gameFrameWrap").classList.add("inactive");
  $("gameFrame").src = "about:blank";
  $("timerPill").textContent = "";
  $("timerPill").classList.add("hidden");
  $("endGameBtn").classList.add("hidden");
  setStatus("Back to lobby.");
}

async function recordGame(gameId, scoresBySlot) {
  const res = await apiPostJson("/api/session/record_game", { gameId, scoresBySlot });
  state.session = normalizeSession(res.session);
  render();
}

function startGame(game) {
  if (!game) return;
  stopActiveRun("host");

  const activeSlots = (state.session?.playersBySlot || [])
    .filter((p) => p.avatarId && Number(p.gamepadIndex ?? -1) >= 0)
    .map((p) => p.slot);
  if (activeSlots.length < 2) {
    alert("Assign at least 2 players (avatar + pad) before starting.");
    return;
  }

  $("gameFrameWrap").classList.remove("inactive");
  const frame = $("gameFrame");
  $("timerPill").classList.remove("hidden");
  $("endGameBtn").classList.remove("hidden");

  const startedAtMs = performance.now();
  const maxDurationSec = Number(game.maxDurationSec || 90);

  state.activeRun = {
    gameId: game.id,
    startedAtMs,
    maxDurationSec,
    tickTimer: null,
    hardTimeout: null,
  };

  // Listen for ready/end messages.
  setStatus(`Running ${game.id}…`);
  frame.src = `/games/${encodeURIComponent(game.filename)}`;

  const tick = () => {
    const run = state.activeRun;
    if (!run) return;
    const nowMs = performance.now();
    const elapsedMs = nowMs - run.startedAtMs;
    const timeRemainingMs = Math.max(0, run.maxDurationSec * 1000 - elapsedMs);
    $("timerPill").textContent = `${Math.ceil(timeRemainingMs / 1000)}s`;
    postToGame("maribro:tick", { nowMs, timeRemainingMs });
  };

  state.activeRun.tickTimer = setInterval(tick, 150);
  state.activeRun.hardTimeout = setTimeout(() => {
    // Timeout = force end + record all zeros.
    stopActiveRun("timeout");
    recordGame(game.id, [0, 0, 0, 0]).catch((e) => console.warn(e));
  }, maxDurationSec * 1000 + 250);

  // Send init once iframe is likely alive; retry a couple times.
  const initPayload = {
    sessionId: String(state.session?.createdAt || "session"),
    slotToGamepadIndex: slotToGamepadIndex(),
    playersBySlot: playersBySlotPayload(),
    activeSlots,
    maxDurationSec,
    startedAtMs,
  };
  let tries = 0;
  const initTimer = setInterval(() => {
    tries++;
    postToGame("maribro:init", initPayload);
    postToGame("maribro:audio_config", { enabled: state.audioEnabled, masterVolume: 0.25 });
    if (tries >= 10) clearInterval(initTimer);
  }, 200);
}

function hookGameMessages() {
  window.addEventListener("message", (ev) => {
    if (ev.origin !== window.location.origin) return;
    const msg = ev.data;
    if (!msg || typeof msg.type !== "string") return;
    const run = state.activeRun;
    if (!run) return;

    if (msg.type === "maribro:ready") {
      // no-op; useful for debugging
      return;
    }

    if (msg.type === "maribro:game_end") {
      const scores = msg.payload?.scoresBySlot;
      if (!Array.isArray(scores) || scores.length !== 4) return;
      stopActiveRun("host");
      recordGame(run.gameId, scores).catch((e) => alert(`Failed to record: ${e.message}`));
    }
  });
}

function pollGamepadsForPresses() {
  const pads = navigator.getGamepads ? navigator.getGamepads() : [];
  for (let i = 0; i < pads.length; i++) {
    const gp = pads[i];
    if (!gp) continue;
    for (const b of gp.buttons || []) {
      const pressed = !!b?.pressed;
      const analogPressed = typeof b?.value === "number" && b.value > 0.6;
      if (!(pressed || analogPressed)) continue;

      const now = performance.now();
      if (state.lastPressedGamepadIndex === i && now - state.lastPressedAtMs < 250) return;
      state.lastPressedGamepadIndex = i;
      state.lastPressedAtMs = now;

      if (state.claimListeningSlot != null && !state.claimInFlight) {
        const slot = state.claimListeningSlot;
        state.claimListeningSlot = null;
        state.claimInFlight = true;
        renderPlayers();
        setStatus(`Claiming gamepad ${i} for slot ${slot + 1}…`);
        updatePlayers({ slot, gamepadIndex: i })
          .catch((e) => alert(`Failed to claim pad: ${e.message}`))
          .finally(() => {
            state.claimInFlight = false;
          });
      } else {
        setStatus(`Detected gamepad index ${i}. Click “Claim pad” for a slot.`);
      }
      return;
    }
  }
}

async function refresh() {
  const [avatars, games, session] = await Promise.all([
    apiJson("/api/avatars"),
    apiJson("/api/games"),
    apiJson("/api/session"),
  ]);
  state.avatars = avatars.avatars || [];
  state.games = games.games || [];
  state.session = normalizeSession(session.session);
  render();
}

function hookButtons() {
  $("audioBtn").addEventListener("click", async () => {
    state.audioEnabled = !state.audioEnabled;
    updateAudioButton();
    // A click is a user gesture; request the iframe to arm audio immediately.
    postToGame("maribro:audio_config", { enabled: state.audioEnabled, masterVolume: 0.25 });
    postToGame("maribro:audio_arm", {});
  });
  $("resetSessionBtn").addEventListener("click", async () => {
    if (!confirm("Reset session scores + history?")) return;
    await apiJson("/api/session/reset", { method: "POST" });
    await refresh();
  });
  $("startGameBtn").addEventListener("click", () => {
    const g = state.games.find((x) => x.id === state.selectedGameId);
    if (!g) return;
    startGame(g);
  });
  $("randomGameBtn").addEventListener("click", () => {
    if (!state.games.length) return;
    const g = state.games[Math.floor(Math.random() * state.games.length)];
    state.selectedGameId = g.id;
    renderGames();
  });
  $("endGameBtn").addEventListener("click", () => {
    const run = state.activeRun;
    if (!run) return;
    stopActiveRun("host");
    recordGame(run.gameId, [0, 0, 0, 0]).catch((e) => console.warn(e));
  });
}

async function main() {
  setStatus("Loading…");
  hookButtons();
  hookGameMessages();
  await refresh();
  updateAudioButton();

  // Poll for new games.
  setInterval(() => {
    apiJson("/api/games")
      .then((data) => {
        state.games = data.games || [];
        renderGames();
      })
      .catch(() => {});
  }, 2000);

  // Lightweight gamepad detection loop.
  setInterval(pollGamepadsForPresses, 80);

  setStatus("Ready.");
}

main().catch((e) => {
  console.error(e);
  setStatus(`Error: ${e.message}`);
});

