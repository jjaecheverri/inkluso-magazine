/* XT:RELAY — logic puzzle (Mastermind-like), daily seeded, local-only storage. */
(() => {
  const $ = (id) => document.getElementById(id);
  const DEFAULT = { len: 4, symbols: 6, attempts: 10 };
  const SYMBOLS = ["A","B","C","D","E","F","G","H","J","K","L","M"];
  const LS = { stats: "xt_relay_stats_v1", state: "xt_relay_state_v1" };

  const elPalette = $("palette"), elSlots = $("slots"), elBoard = $("board");
  const elStatus = $("status"), elDailyTag = $("dailyTag"), elBuildTag = $("buildTag");
  const elModeDaily = $("modeDaily"), elModeHard = $("modeHard"), elBtnNew = $("btnNew");
  const elBtnReset = $("btnReset"), elBtnHelp = $("btnHelp"), elDlgHelp = $("dlgHelp");
  const elBtnBack = $("btnBack"), elBtnClear = $("btnClear"), elBtnSubmit = $("btnSubmit");
  const elBtnShare = $("btnShare"), elBtnCopy = $("btnCopy");
  const elCodeLen = $("codeLen"), elSymbolCount = $("symbolCount"), elMaxAttempts = $("maxAttempts");
  const elStreak = $("streak"), elWins = $("wins"), elLosses = $("losses"), elBest = $("best");

  const todayISO = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  };

  const mulberry32 = (seed) => () => {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const strSeed = (s) => {
    let h = 2166136261;
    for (let i=0; i<s.length; i++){ h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  };

  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));

  const loadStats = () => {
    try { return JSON.parse(localStorage.getItem(LS.stats)) || { wins:0, losses:0, best:null, dailyStreak:0, lastDailyWin:null }; }
    catch { return { wins:0, losses:0, best:null, dailyStreak:0, lastDailyWin:null }; }
  };

  const saveStats = (s) => localStorage.setItem(LS.stats, JSON.stringify(s));

  const renderStats = (stats) => {
    elWins.textContent = String(stats.wins);
    elLosses.textContent = String(stats.losses);
    elBest.textContent = stats.best ? String(stats.best) : "—";
    elStreak.textContent = String(stats.dailyStreak);
  };

  const blankState = () => ({ date: todayISO(), daily: true, hard: false, cfg: { ...DEFAULT }, secret: [], current: [], history: [], over: false, win: false });

  const loadState = () => { try { return JSON.parse(localStorage.getItem(LS.state)) || null; } catch { return null; } };
  const saveState = (s) => localStorage.setItem(LS.state, JSON.stringify(s));

  const evaluate = (guess, secret) => {
    let hit = 0; const gLeft = [], sLeft = [];
    for (let i=0; i<guess.length; i++){
      if (guess[i] === secret[i]) hit++;
      else { gLeft.push(guess[i]); sLeft.push(secret[i]); }
    }
    let near = 0; const freq = new Map();
    for (const x of sLeft) freq.set(x, (freq.get(x)||0)+1);
    for (const x of gLeft){ const c = freq.get(x)||0; if (c > 0){ near++; freq.set(x, c-1); } }
    return { hit, near, miss: guess.length - hit - near };
  };

  const makeSecret = ({ daily, hard, cfg }) => {
    const pool = SYMBOLS.slice(0, clamp(cfg.symbols, 4, SYMBOLS.length));
    const seedBase = daily ? `XT:RELAY|${todayISO()}|${cfg.len}|${cfg.symbols}|${hard?1:0}` : `XT:RELAY|RND|${Date.now()}|${Math.random()}`;
    const rng = mulberry32(strSeed(seedBase));
    const out = [], used = new Set();
    while (out.length < cfg.len){
      const sym = pool[Math.floor(rng() * pool.length)];
      if (hard){ if (used.has(sym)) continue; used.add(sym); }
      out.push(sym);
    }
    return out;
  };

  const renderConfig = (s) => {
    elCodeLen.textContent = String(s.cfg.len);
    elSymbolCount.textContent = String(s.cfg.symbols);
    elMaxAttempts.textContent = String(s.cfg.attempts);
    elDailyTag.textContent = s.daily ? `Daily • ${s.date}` : "Random";
  };

  const renderPalette = (s) => {
    elPalette.innerHTML = "";
    const pool = SYMBOLS.slice(0, clamp(s.cfg.symbols, 4, SYMBOLS.length));
    pool.forEach(sym => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "sym"; b.textContent = sym; b.title = `Add ${sym}`;
      b.addEventListener("click", () => {
        if (s.over || s.current.length >= s.cfg.len) return;
        s.current.push(sym); saveState(s); renderCurrent(s);
      });
      elPalette.appendChild(b);
    });
  };

  const renderCurrent = (s) => {
    elSlots.innerHTML = "";
    for (let i=0; i<s.cfg.len; i++){
      const d = document.createElement("div"); d.className = "slot"; d.textContent = s.current[i] || "·"; elSlots.appendChild(d);
    }
    elBtnSubmit.disabled = s.over || s.current.length !== s.cfg.len;
  };

  const renderBoard = (s) => {
    elBoard.innerHTML = "";
    s.history.forEach((h, idx) => {
      const line = document.createElement("div"); line.className = "line";
      const seq = document.createElement("div"); seq.className = "seq";
      h.guess.forEach(x => { const p = document.createElement("div"); p.className = "peb"; p.textContent = x; seq.appendChild(p); });
      const fb = document.createElement("div"); fb.className = "fb";
      const dots = [...Array(h.fb.hit).fill("hit"), ...Array(h.fb.near).fill("near"), ...Array(h.fb.miss).fill("miss")];
      const rng = mulberry32(strSeed(`fb|${s.date}|${idx}|${s.daily?1:0}`));
      for (let i=dots.length-1; i>0; i--){ const j = Math.floor(rng()*(i+1)); [dots[i],dots[j]]=[dots[j],dots[i]]; }
      dots.forEach(kind => { const dot = document.createElement("span"); dot.className = `dot ${kind}`; fb.appendChild(dot); });
      const label = document.createElement("span");
      label.style.cssText = "font-family:var(--mono);color:var(--muted)";
      label.textContent = `#${idx+1}`; fb.appendChild(label);
      line.appendChild(seq); line.appendChild(fb); elBoard.appendChild(line);
    });
  };

  const setStatus = (msg) => { elStatus.textContent = msg; };
  const resultSummary = (s) => [`XT:RELAY ${s.daily ? s.date : "RND"} ${s.win ? "✓" : "✗"} ${s.history.length}/${s.cfg.attempts}`, ...s.history.map(h => "●".repeat(h.fb.hit) + "◐".repeat(h.fb.near) + "○".repeat(h.fb.miss))].join("\n");
  const enableShare = (s) => { elBtnShare.disabled = !s.over; elBtnCopy.disabled = !s.over; };

  const renderAll = (s) => { renderConfig(s); renderPalette(s); renderCurrent(s); renderBoard(s); elModeDaily.checked = s.daily; elModeHard.checked = s.hard; elBuildTag.textContent = `XT:RELAY build v1 • local-only • ${s.daily ? "daily seed" : "random seed"}`; };

  const newRun = (opts = {}) => {
    const s = blankState();
    s.daily = opts.daily ?? elModeDaily.checked; s.hard = opts.hard ?? elModeHard.checked;
    s.secret = makeSecret({ daily: s.daily, hard: s.hard, cfg: s.cfg });
    saveState(s); renderAll(s); setStatus("New run initialized. Deduce the signal."); enableShare(s); return s;
  };

  const resetRun = (s) => {
    s.current = []; s.history = []; s.over = false; s.win = false;
    s.secret = makeSecret({ daily: s.daily, hard: s.hard, cfg: s.cfg });
    saveState(s); renderAll(s); setStatus("Run reset. Same rules, fresh deductions."); enableShare(s);
  };

  const backspace = (s) => { if (s.over) return; s.current.pop(); saveState(s); renderCurrent(s); };
  const clearGuess = (s) => { if (s.over) return; s.current = []; saveState(s); renderCurrent(s); };

  const submit = (s, stats) => {
    if (s.over || s.current.length !== s.cfg.len){ setStatus(`Need ${s.cfg.len} symbols.`); return; }
    const fb = evaluate(s.current, s.secret);
    s.history.push({ guess: [...s.current], fb }); s.current = [];
    if (fb.hit === s.cfg.len){
      s.over = true; s.win = true; stats.wins += 1;
      stats.best = stats.best ? Math.min(stats.best, s.history.length) : s.history.length;
      if (s.daily){
        const today = todayISO(), last = stats.lastDailyWin;
        if (!last){ stats.dailyStreak = 1; }
        else { const diff = Math.round((new Date(today+"T00:00:00") - new Date(last+"T00:00:00")) / 86400000); stats.dailyStreak = diff === 1 ? stats.dailyStreak + 1 : 1; }
        stats.lastDailyWin = today;
      }
      saveStats(stats); setStatus(`Signal cracked in ${s.history.length}/${s.cfg.attempts}.`);
    } else if (s.history.length >= s.cfg.attempts){
      s.over = true; s.win = false; stats.losses += 1;
      if (s.daily) stats.dailyStreak = 0;
      saveStats(stats); setStatus(`Out of attempts. Code was ${s.secret.join("")}.`);
    } else {
      setStatus(`${s.cfg.attempts - s.history.length} attempt(s) left. Tighten the hypothesis.`);
    }
    saveState(s); renderBoard(s); renderCurrent(s); renderStats(stats); enableShare(s);
  };

  const boot = () => {
    const stats = loadStats(); renderStats(stats);
    let s = loadState();
    const iso = todayISO();
    if (!s){ s = newRun({ daily: true, hard: false }); }
    else {
      if (s.daily && s.date !== iso){ s = newRun({ daily: true, hard: s.hard }); }
      else { renderAll(s); enableShare(s); setStatus(s.over ? (s.win ? "You already solved this run." : "This run is finished.") : "Continue your run."); }
    }

    elBtnHelp.addEventListener("click", () => elDlgHelp.showModal());
    elBtnNew.addEventListener("click", () => { newRun({ daily: elModeDaily.checked, hard: elModeHard.checked }); renderStats(loadStats()); });
    elBtnReset.addEventListener("click", () => { resetRun(loadState() || s); renderStats(loadStats()); });

    const modeChange = () => {
      const cur = loadState() || s;
      cur.daily = elModeDaily.checked; cur.hard = elModeHard.checked; cur.date = todayISO();
      cur.secret = makeSecret({ daily: cur.daily, hard: cur.hard, cfg: cur.cfg });
      cur.current = []; cur.history = []; cur.over = false; cur.win = false;
      saveState(cur); renderAll(cur); setStatus("Mode changed. New run started."); enableShare(cur);
    };
    elModeDaily.addEventListener("change", modeChange);
    elModeHard.addEventListener("change", modeChange);

    elBtnBack.addEventListener("click", () => backspace(loadState() || s));
    elBtnClear.addEventListener("click", () => clearGuess(loadState() || s));
    elBtnSubmit.addEventListener("click", () => submit(loadState() || s, loadStats()));

    window.addEventListener("keydown", (e) => {
      const cur = loadState() || s;
      if (e.key === "Backspace"){ e.preventDefault(); backspace(cur); }
      if (e.key === "Escape"){ e.preventDefault(); clearGuess(cur); }
      if (e.key === "Enter"){ e.preventDefault(); submit(cur, loadStats()); }
      const k = e.key.toUpperCase();
      const pool = SYMBOLS.slice(0, clamp(cur.cfg.symbols, 4, SYMBOLS.length));
      if (pool.includes(k) && !cur.over && cur.current.length < cur.cfg.len){ cur.current.push(k); saveState(cur); renderCurrent(cur); }
    });

    elBtnCopy.addEventListener("click", async () => {
      const cur = loadState() || s;
      try { await navigator.clipboard.writeText(resultSummary(cur)); setStatus("Summary copied."); }
      catch { setStatus("Clipboard blocked by browser settings."); }
    });

    elBtnShare.addEventListener("click", async () => {
      const cur = loadState() || s; const txt = resultSummary(cur);
      if (navigator.share){ try { await navigator.share({ title: "XT:RELAY", text: txt }); setStatus("Shared."); } catch { setStatus("Share canceled."); } }
      else { try { await navigator.clipboard.writeText(txt); setStatus("Share not supported — copied instead."); } catch { setStatus("Share not supported and clipboard blocked."); } }
    });
  };

  boot();
})();