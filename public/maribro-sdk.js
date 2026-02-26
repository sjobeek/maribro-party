(() => {
  const SDK_VERSION = "0.1.0";

  const state = {
    ready: false,
    ctx: null,
    lastTick: null,
    mock: false,
    mockKeysDown: new Set(),
    audioConfig: { enabled: true, masterVolume: 0.25 },
    audio: { custom: false, armed: false },
    fallbackBloop: { lastButtonsBySlot: new Map(), lastBloopAtBySlot: new Map() },
  };

  const readyHandlers = [];

  function onReady(fn) {
    if (typeof fn !== "function") return;
    if (state.ready) fn(state.ctx);
    else readyHandlers.push(fn);
  }

  function setReady(ctx) {
    state.ready = true;
    const playersBySlot = Array.isArray(ctx?.playersBySlot) ? ctx.playersBySlot : [];
    const slotToGamepadIndex = Array.isArray(ctx?.slotToGamepadIndex) ? ctx.slotToGamepadIndex : [-1, -1, -1, -1];
    let activeSlots = Array.isArray(ctx?.activeSlots) ? ctx.activeSlots : null;
    if (!activeSlots) {
      activeSlots = playersBySlot
        .filter((p) => p && typeof p.slot === "number")
        .filter((p) => {
          const slot = Number(p.slot);
          const hasAvatar = !!p.avatarId;
          const gpIndex = Number(slotToGamepadIndex?.[slot] ?? -1);
          return slot >= 0 && slot <= 3 && hasAvatar && gpIndex >= 0;
        })
        .map((p) => Number(p.slot));
    }

    state.ctx = { ...ctx, playersBySlot, slotToGamepadIndex, activeSlots };
    for (const fn of readyHandlers.splice(0)) {
      try {
        fn(ctx);
      } catch (e) {
        console.warn(e);
      }
    }
  }

  function isInHostIframe() {
    try {
      return window.parent && window.parent !== window;
    } catch {
      return true;
    }
  }

  function post(type, payload) {
    try {
      window.parent.postMessage({ type, payload }, window.location.origin);
    } catch {
      // ignore
    }
  }

  function clampAxis(v) {
    if (typeof v !== "number" || !isFinite(v)) return 0;
    return Math.max(-1, Math.min(1, v));
  }

  function makeEmptyInput() {
    return {
      axes: { lx: 0, ly: 0, rx: 0, ry: 0 },
      buttons: {
        south: false,
        east: false,
        west: false,
        north: false,
        l1: false,
        r1: false,
        l2: 0,
        r2: 0,
        select: false,
        start: false,
        l3: false,
        r3: false,
        dup: false,
        ddown: false,
        dleft: false,
        dright: false,
      },
    };
  }

  function normalizeGamepad(gp) {
    const out = makeEmptyInput();
    if (!gp) return out;

    const axes = gp.axes || [];
    out.axes.lx = clampAxis(axes[0] || 0);
    out.axes.ly = clampAxis(axes[1] || 0);
    out.axes.rx = clampAxis(axes[2] || 0);
    out.axes.ry = clampAxis(axes[3] || 0);

    const b = gp.buttons || [];
    const pressed = (i) => !!b[i]?.pressed;
    const value = (i) => Number(b[i]?.value || 0);

    out.buttons.south = pressed(0);
    out.buttons.east = pressed(1);
    out.buttons.west = pressed(2);
    out.buttons.north = pressed(3);
    out.buttons.l1 = pressed(4);
    out.buttons.r1 = pressed(5);
    out.buttons.l2 = value(6);
    out.buttons.r2 = value(7);
    out.buttons.select = pressed(8);
    out.buttons.start = pressed(9);
    out.buttons.l3 = pressed(10);
    out.buttons.r3 = pressed(11);
    out.buttons.dup = pressed(12);
    out.buttons.ddown = pressed(13);
    out.buttons.dleft = pressed(14);
    out.buttons.dright = pressed(15);

    return out;
  }

  function keyDown(code) {
    return state.mockKeysDown.has(code);
  }

  function mockInputForSlot(slot) {
    const out = makeEmptyInput();
    const map = [
      // slot 0
      { up: "KeyW", left: "KeyA", down: "KeyS", right: "KeyD", south: "Space", east: "ShiftLeft" },
      // slot 1
      { up: "ArrowUp", left: "ArrowLeft", down: "ArrowDown", right: "ArrowRight", south: "Enter", east: "Slash" },
      // slot 2
      { up: "KeyI", left: "KeyJ", down: "KeyK", right: "KeyL", south: "KeyN", east: "KeyM" },
      // slot 3
      { up: "KeyT", left: "KeyF", down: "KeyG", right: "KeyH", south: "KeyR", east: "KeyY" },
    ][slot] || null;

    if (!map) return out;

    const lx = (keyDown(map.right) ? 1 : 0) + (keyDown(map.left) ? -1 : 0);
    const ly = (keyDown(map.down) ? 1 : 0) + (keyDown(map.up) ? -1 : 0);
    out.axes.lx = lx;
    out.axes.ly = ly;
    out.buttons.south = keyDown(map.south);
    out.buttons.east = keyDown(map.east);
    return out;
  }

  function getInput(slot) {
    const s = Number(slot);
    if (!(s >= 0 && s <= 3)) return makeEmptyInput();

    if (state.mock) return mockInputForSlot(s);

    const gpIndex = state.ctx?.slotToGamepadIndex?.[s];
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    return normalizeGamepad(pads?.[gpIndex]);
  }

  function getActiveSlots() {
    const slots = state.ctx?.activeSlots;
    return Array.isArray(slots) ? slots.slice() : [];
  }

  function getTimeRemainingMs() {
    if (state.lastTick && typeof state.lastTick.timeRemainingMs === "number") return state.lastTick.timeRemainingMs;
    if (state.ctx && typeof state.ctx.maxDurationSec === "number") return state.ctx.maxDurationSec * 1000;
    return 30_000;
  }

  function endGame(scoresBySlot) {
    const scores = Array.isArray(scoresBySlot) ? scoresBySlot.slice(0, 4) : [0, 0, 0, 0];
    while (scores.length < 4) scores.push(0);

    if (state.mock) {
      console.log("[Maribro mock] endGame", scores);
      return;
    }
    post("maribro:game_end", { scoresBySlot: scores, endedAtMs: performance.now() });
  }

  function bootMockMode() {
    state.mock = true;
    const playersBySlot = [
      { slot: 0, avatarId: "mock-0", name: "Mock 1", color: "#E53935" },
      { slot: 1, avatarId: "mock-1", name: "Mock 2", color: "#1E88E5" },
      { slot: 2, avatarId: "mock-2", name: "Mock 3", color: "#43A047" },
      { slot: 3, avatarId: "mock-3", name: "Mock 4", color: "#FDD835" },
    ];
    setReady({ playersBySlot, maxDurationSec: 30, slotToGamepadIndex: [-1, -1, -1, -1], activeSlots: [0, 1, 2, 3] });
  }

  // --- Audio (opt-in) + fallback bloops ---
  const audio = (() => {
    let ctx = null;
    let master = null;
    let comp = null;

    function clamp01(v, def = 0) {
      const n = Number(v);
      if (!isFinite(n)) return def;
      return Math.max(0, Math.min(1, n));
    }

    function ensureGraph() {
      if (ctx) return;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      ctx = new AudioCtx();
      master = ctx.createGain();
      comp = ctx.createDynamicsCompressor();
      comp.threshold.value = -18;
      comp.knee.value = 18;
      comp.ratio.value = 6;
      comp.attack.value = 0.01;
      comp.release.value = 0.15;
      master.gain.value = clamp01(state.audioConfig.masterVolume, 0.25);
      master.connect(comp);
      comp.connect(ctx.destination);
    }

    async function arm() {
      ensureGraph();
      if (!ctx) return;
      try {
        await ctx.resume();
        state.audio.armed = true;
      } catch {
        // ignore; browser may reject without a gesture
      }
    }

    function setEnabled(enabled) {
      state.audioConfig.enabled = !!enabled;
    }

    function setMasterVolume(v) {
      state.audioConfig.masterVolume = clamp01(v, 0.25);
      if (master) master.gain.value = state.audioConfig.masterVolume;
    }

    function noteToHz(note) {
      const n = Number(note);
      if (!isFinite(n)) return 440;
      return 440 * Math.pow(2, (n - 69) / 12);
    }

    function playNote({ note, velocity = 0.5, durationMs = 80, instrument = "sine" } = {}) {
      if (!state.audioConfig.enabled) return;
      state.audio.custom = true; // implicit opt-in
      ensureGraph();
      if (!ctx || !master) return;

      const t0 = ctx.currentTime;
      const dur = Math.max(20, Math.min(800, Number(durationMs) || 80)) / 1000;
      const vel = clamp01(velocity, 0.5);

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, t0);
      gain.gain.exponentialRampToValueAtTime(0.06 * vel, t0 + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      gain.connect(master);

      if (instrument === "noise") {
        const bufferSize = Math.floor(ctx.sampleRate * dur);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) data[i] = (Math.random() * 2 - 1) * 0.7;
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(gain);
        src.start(t0);
        src.stop(t0 + dur + 0.02);
      } else {
        const osc = ctx.createOscillator();
        osc.type = instrument;
        osc.frequency.setValueAtTime(noteToHz(note ?? 60), t0);
        osc.connect(gain);
        osc.start(t0);
        osc.stop(t0 + dur + 0.02);
      }
    }

    return { arm, setEnabled, setMasterVolume, playNote };
  })();

  function fallbackBloopLoop() {
    if (!state.ready) return requestAnimationFrame(fallbackBloopLoop);
    if (!state.audioConfig.enabled) return requestAnimationFrame(fallbackBloopLoop);
    if (state.audio.custom) return requestAnimationFrame(fallbackBloopLoop);

    const slots = getActiveSlots();
    for (const slot of slots) {
      const input = getInput(slot);
      const prev = state.fallbackBloop.lastButtonsBySlot.get(slot) || {};
      const now = input.buttons || {};

      const keys = ["south", "east", "west", "north", "l1", "r1", "select", "start", "dup", "ddown", "dleft", "dright"];
      let edge = null;
      for (const k of keys) {
        const was = !!prev[k];
        const is = !!now[k];
        if (is && !was) {
          edge = k;
          break;
        }
      }

      state.fallbackBloop.lastButtonsBySlot.set(slot, { ...now });

      if (!edge) continue;
      const lastAt = state.fallbackBloop.lastBloopAtBySlot.get(slot) || 0;
      const nowMs = performance.now();
      if (nowMs - lastAt < 100) continue; // ~10 bloops/sec per slot
      state.fallbackBloop.lastBloopAtBySlot.set(slot, nowMs);

      const base = [60, 64, 67, 72][slot] || 60;
      const delta = edge === "east" ? 2 : edge === "west" ? -2 : edge === "north" ? 4 : edge.startsWith("d") ? -5 : 0;
      audio.playNote({ note: base + delta, velocity: 0.25, durationMs: 60, instrument: "triangle" });
    }

    requestAnimationFrame(fallbackBloopLoop);
  }

  requestAnimationFrame(fallbackBloopLoop);

  // Auto-arm on common gestures inside the iframe (helps dev; host also provides an arm button).
  const tryArm = () => audio.arm();
  window.addEventListener("pointerdown", tryArm, { passive: true });
  window.addEventListener("keydown", tryArm);

  window.addEventListener("keydown", (e) => {
    if (!state.mock) return;
    state.mockKeysDown.add(e.code);
  });
  window.addEventListener("keyup", (e) => {
    if (!state.mock) return;
    state.mockKeysDown.delete(e.code);
  });

  window.addEventListener("message", (ev) => {
    if (ev.origin !== window.location.origin) return;
    const msg = ev.data;
    if (!msg || typeof msg.type !== "string") return;
    if (msg.type === "maribro:init") {
      const p = msg.payload || {};
      setReady({
        playersBySlot: p.playersBySlot || [],
        activeSlots: p.activeSlots || null,
        maxDurationSec: Number(p.maxDurationSec || 30),
        slotToGamepadIndex: p.slotToGamepadIndex || [-1, -1, -1, -1],
      });
      post("maribro:ready", { sdkVersion: SDK_VERSION });
    }
    if (msg.type === "maribro:tick") {
      state.lastTick = msg.payload || null;
    }
    if (msg.type === "maribro:force_end") {
      // The SDK doesn't force-end for you; games can optionally listen for this if desired.
    }
    if (msg.type === "maribro:audio_config") {
      const p = msg.payload || {};
      if (typeof p.enabled === "boolean") audio.setEnabled(p.enabled);
      if (typeof p.masterVolume === "number") audio.setMasterVolume(p.masterVolume);
    }
    if (msg.type === "maribro:audio_arm") {
      audio.arm();
    }
  });

  // If no init arrives soon, enter mock mode automatically.
  if (!isInHostIframe()) {
    // Directly opened game file / different origin: always mock.
    setTimeout(bootMockMode, 0);
  } else {
    setTimeout(() => {
      if (!state.ready) bootMockMode();
    }, 500);
  }

  window.Maribro = {
    onReady,
    getInput,
    getActiveSlots,
    getTimeRemainingMs,
    endGame,
    audio,
    __sdkVersion: SDK_VERSION,
  };
})();
