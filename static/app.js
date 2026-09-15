// ------- Mind-Mate front end -------
const log = document.getElementById("log");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const resetBtn = document.getElementById("reset");
const statusPill = document.getElementById("status");
const statusLabel = document.getElementById("status-label");
const sosBox = document.getElementById("sos");
const moodLabel = document.getElementById("mood-label");
const moodDot = document.querySelector(".mood-dot");
const barVal = document.getElementById("bar-val");
const barAro = document.getElementById("bar-aro");
const faceEl = document.querySelector(".face");

const USER_ID = "demo-user";

// ---------- Face rendering ----------
// SVG paths for each mood. Coordinates match the viewBoxes in index.html.
// Eyes viewBox: 300x130. Mouth viewBox: 300x80.
const EYE_SHAPES = {
  neutral:  { l: "M40 65 Q90 24 140 65 Q90 104 40 65 Z", r: "M160 65 Q210 24 260 65 Q210 104 160 65 Z" },
  joy:      { l: "M40 75 Q90 30 140 75 Q90 60 40 75 Z", r: "M160 75 Q210 30 260 75 Q210 60 160 75 Z" }, // squint-happy
  sadness:  { l: "M40 55 Q90 30 140 55 Q90 95 40 55 Z", r: "M160 55 Q210 30 260 55 Q210 95 160 55 Z" }, // droopy
  anger:    { l: "M40 80 L140 50 L140 80 L40 90 Z",      r: "M160 50 L260 80 L260 90 L160 80 Z" },      // slanted
  fear:     { l: "M35 65 Q90 5 145 65 Q90 125 35 65 Z", r: "M155 65 Q210 5 265 65 Q210 125 155 65 Z" }, // wide
  surprise: { l: "M40 65 Q90 15 140 65 Q90 115 40 65 Z", r: "M160 65 Q210 15 260 65 Q210 115 160 65 Z" },
};
const PUPIL = {
  neutral:  { r: 18, dy: 0,  color: "#7bd7c8" },
  joy:      { r: 16, dy: -3, color: "#a5f0e0" },
  sadness:  { r: 14, dy: 6,  color: "#7bd7c8" },
  anger:    { r: 14, dy: 0,  color: "#ff8b78" },
  fear:     { r: 22, dy: 0,  color: "#c9f7ee" },
  surprise: { r: 22, dy: 0,  color: "#a78bfa" },
};
const MOUTH = {
  // resting face keeps a soft, friendly curve — never a dead flat line
  neutral:  "M70 38 Q150 54 230 38",
  joy:      "M60 30 Q150 75 240 30",
  sadness:  "M60 55 Q150 15 240 55",
  anger:    "M60 45 L110 30 L150 45 L190 30 L240 45",
  fear:     "M130 30 Q150 60 170 30 Q150 15 130 30 Z",
  surprise: "M130 30 Q150 65 170 30 Q150 5 130 30 Z",
};
// Talking wiggle keyframes
const TALK_FRAMES = [
  "M70 38 Q150 46 230 38",
  "M70 38 Q150 62 230 38",
  "M70 38 Q150 42 230 38",
  "M70 38 Q150 56 230 38",
];

const eyeL = document.getElementById("eye-left-lid");
const eyeR = document.getElementById("eye-right-lid");
const pupL = document.getElementById("pupil-left");
const pupR = document.getElementById("pupil-right");
const mouthPath = document.getElementById("mouth-path");

let currentMood = "neutral";
let talkTimer = null;

function setMood(mood) {
  if (!EYE_SHAPES[mood]) mood = "neutral";
  currentMood = mood;
  moodLabel.textContent = mood;
  const shape = EYE_SHAPES[mood];
  const pupil = PUPIL[mood];
  eyeL.setAttribute("d", shape.l);
  eyeR.setAttribute("d", shape.r);
  pupL.setAttribute("r", pupil.r);
  pupR.setAttribute("r", pupil.r);
  pupL.setAttribute("cy", 65 + pupil.dy);
  pupR.setAttribute("cy", 65 + pupil.dy);
  pupL.style.fill = pupil.color;
  pupR.style.fill = pupil.color;
  moodDot.style.background = pupil.color;
  mouthPath.setAttribute("d", MOUTH[mood]);
  mouthPath.style.stroke = pupil.color;
  faceEl.dataset.mood = mood;
}

// Blinking
function blink() {
  const restoreL = eyeL.getAttribute("d");
  const restoreR = eyeR.getAttribute("d");
  const closedL = "M40 68 Q90 68 140 68 Q90 68 40 68 Z";
  const closedR = "M160 68 Q210 68 260 68 Q210 68 160 68 Z";
  eyeL.setAttribute("d", closedL);
  eyeR.setAttribute("d", closedR);
  setTimeout(() => {
    eyeL.setAttribute("d", restoreL);
    eyeR.setAttribute("d", restoreR);
  }, 130);
}
setInterval(() => { if (Math.random() < 0.7) blink(); }, 3800);

// Talking animation while assistant is "speaking"
function startTalking() {
  stopTalking();
  let i = 0;
  talkTimer = setInterval(() => {
    mouthPath.setAttribute("d", TALK_FRAMES[i % TALK_FRAMES.length]);
    i++;
  }, 140);
}
function stopTalking() {
  if (talkTimer) { clearInterval(talkTimer); talkTimer = null; }
  mouthPath.setAttribute("d", MOUTH[currentMood]);
}

// Idle eye wander
setInterval(() => {
  const dx = (Math.random() - 0.5) * 6;
  const dy = (Math.random() - 0.5) * 4;
  pupL.setAttribute("cx", 90 + dx);
  pupR.setAttribute("cx", 210 + dx);
  const baseDy = PUPIL[currentMood].dy;
  pupL.setAttribute("cy", 65 + baseDy + dy);
  pupR.setAttribute("cy", 65 + baseDy + dy);
}, 2400);

// ---------- Chat rendering ----------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function addUserMsg(text) {
  const m = el("div", "msg user", text);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
}

function addBotMsg(text, meta) {
  const m = el("div", "msg bot", text);
  if (meta) m.appendChild(el("span", "meta", meta));
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
}

// Reveal the reply the way a person types it — the mouth animates while the
// words land, then settles. Far more alive than a block of text appearing.
function addBotMsgTyped(text, meta) {
  return new Promise((resolve) => {
    const m = el("div", "msg bot");
    const body = el("span");
    m.appendChild(body);
    log.appendChild(m);

    const perChar = Math.max(9, Math.min(28, 1100 / Math.max(text.length, 1)));
    let i = 0;
    startTalking();
    const tick = setInterval(() => {
      // reveal in small chunks so long replies don't crawl
      i = Math.min(text.length, i + (text.length > 160 ? 3 : 1));
      body.textContent = text.slice(0, i);
      log.scrollTop = log.scrollHeight;
      if (i >= text.length) {
        clearInterval(tick);
        stopTalking();
        if (meta) m.appendChild(el("span", "meta", meta));
        log.scrollTop = log.scrollHeight;
        resolve();
      }
    }, perChar);
  });
}

function addRecall(text) {
  log.appendChild(el("div", "msg recall", `remembering: "${text}"`));
  log.scrollTop = log.scrollHeight;
}

function showTyping() {
  const t = el("div", "typing");
  t.id = "typing";
  t.appendChild(el("span"));
  t.appendChild(el("span"));
  t.appendChild(el("span"));
  log.appendChild(t);
  log.scrollTop = log.scrollHeight;
}
function hideTyping() {
  const t = document.getElementById("typing");
  if (t) t.remove();
}

function setBars(valence, arousal) {
  // valence -1..1 -> 0..100%
  barVal.style.width = `${Math.round(((valence + 1) / 2) * 100)}%`;
  barAro.style.width = `${Math.round(arousal * 100)}%`;
  if (valence > 0.2) {
    barVal.style.background = "linear-gradient(90deg, #7bd7c8, #a5f0e0)";
  } else if (valence < -0.2) {
    barVal.style.background = "linear-gradient(90deg, #ffb26b, #ff8b78)";
  } else {
    barVal.style.background = "linear-gradient(90deg, #7bd7c8, #a78bfa)";
  }
}

// ---------- Networking ----------
async function refreshStatus() {
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    statusPill.classList.toggle("offline", !j.llm_online);
    statusLabel.textContent = j.llm_online
      ? j.provider
      : `offline · ${j.reason || "add GROQ_API_KEY"}`;
  } catch {
    statusPill.classList.add("offline");
    statusLabel.textContent = "server unreachable";
  }
}
refreshStatus();

// ---------- Long-term memory panel ----------
const rememberBody = document.getElementById("remember-body");
const forgetBtn = document.getElementById("forget");

function renderMemory(m) {
  if (!m) return;
  const bits = [];
  if (m.name) bits.push(`<div class="mem-name">${esc(m.name)}</div>`);
  (m.facts || []).forEach((f) => {
    bits.push(
      `<div class="mem-fact"><span class="mem-k">${esc(f.key.replace(/_/g, " "))}</span>${esc(f.value)}</div>`
    );
  });
  (m.sessions || []).forEach((s) => {
    bits.push(`<div class="mem-session">${esc(s.summary)}</div>`);
  });
  rememberBody.innerHTML = bits.length
    ? bits.join("")
    : '<span class="remember-empty">We haven\'t met properly yet.</span>';
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

// ---------- Opening the conversation ----------
setMood("neutral");

async function openConversation() {
  showTyping();
  try {
    const r = await fetch(`/api/greeting?user_id=${encodeURIComponent(USER_ID)}`);
    const j = await r.json();
    hideTyping();
    await addBotMsgTyped(j.reply);
    renderMemory(j.remembers);
  } catch {
    hideTyping();
    addBotMsg("Hey, I'm Mind-Mate. I'm here to listen — what's going on with you today?");
  }
}
openConversation();

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addUserMsg(text);
  input.value = "";
  sendBtn.disabled = true;
  showTyping();

  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, message: text }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    hideTyping();

    setMood(j.display_mood || j.emotion?.label);
    setBars(j.emotion.valence, j.emotion.arousal);
    sosBox.classList.toggle("hidden", j.sos_level < 2);
    if (j.recalled_memory) addRecall(j.recalled_memory);

    const meta = `${j.provider} · ${j.display_mood} · valence ${j.emotion.valence.toFixed(2)}${
      j.sos_level ? ` · sos ${j.sos_level}` : ""
    }`;
    await addBotMsgTyped(j.reply, meta);
  } catch (err) {
    hideTyping();
    addBotMsg(`Couldn't reach the server: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

resetBtn.addEventListener("click", async () => {
  resetBtn.disabled = true;
  log.innerHTML = "";
  sosBox.classList.add("hidden");
  setMood("neutral");
  setBars(0, 0);
  showTyping();
  try {
    const r = await fetch(`/api/new_session?user_id=${encodeURIComponent(USER_ID)}`, {
      method: "POST",
    });
    const j = await r.json();
    hideTyping();
    await addBotMsgTyped(j.reply);
    renderMemory(j.remembers);
  } catch (e) {
    hideTyping();
    addBotMsg(`Couldn't start a new session: ${e.message}`);
  } finally {
    resetBtn.disabled = false;
    input.focus();
  }
});

// ---------- History drawer ----------
const drawer = document.getElementById("drawer");
const scrim = document.getElementById("drawer-scrim");
const drawerBody = document.getElementById("drawer-body");

function fmtWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  const time = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return sameDay
    ? `Today, ${time}`
    : `${d.toLocaleDateString([], { day: "numeric", month: "short" })}, ${time}`;
}

async function openDrawer() {
  drawer.classList.remove("hidden");
  scrim.classList.remove("hidden");
  drawerBody.innerHTML = '<div class="drawer-empty">Loading…</div>';
  try {
    const r = await fetch(`/api/sessions?user_id=${encodeURIComponent(USER_ID)}`);
    const { sessions } = await r.json();
    if (!sessions.length) {
      drawerBody.innerHTML = '<div class="drawer-empty">No conversations yet.</div>';
      return;
    }
    drawerBody.innerHTML = "";
    sessions.forEach((s) => drawerBody.appendChild(sessionCard(s)));
  } catch (e) {
    drawerBody.innerHTML = `<div class="drawer-empty">Couldn't load history: ${esc(e.message)}</div>`;
  }
}

function sessionCard(s) {
  const card = el("div", "sess");
  const head = el("div", "sess-head");

  const left = el("div");
  left.appendChild(el("div", "sess-when", fmtWhen(s.started_at)));
  const bits = [`${s.turns} message${s.turns === 1 ? "" : "s"}`];
  if (s.summary) bits.push(s.summary);
  left.appendChild(el("div", "sess-meta", bits.join(" · ")));
  head.appendChild(left);

  if (s.is_current) head.appendChild(el("span", "sess-badge", "current"));
  const chev = document.createElement("span");
  chev.className = "sess-chev";
  chev.innerHTML =
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>';
  head.appendChild(chev);
  card.appendChild(head);

  let loaded = false;
  head.addEventListener("click", async () => {
    const isOpen = card.classList.toggle("open");
    if (!isOpen) {
      const t = card.querySelector(".sess-turns");
      if (t) t.remove();
      return;
    }
    const box = el("div", "sess-turns");
    box.appendChild(el("div", "t-who", "loading…"));
    card.appendChild(box);
    if (loaded) return;
    try {
      const r = await fetch(
        `/api/sessions/${s.session_id}?user_id=${encodeURIComponent(USER_ID)}`
      );
      const { turns } = await r.json();
      box.innerHTML = "";
      turns.forEach((t) => {
        const row = el("div", `t-row ${t.role}`);
        row.appendChild(el("div", "t-who", t.role === "user" ? "You" : "Mind-Mate"));
        row.appendChild(el("div", "t-text", t.text));
        box.appendChild(row);
      });
      loaded = true;
    } catch (e) {
      box.innerHTML = "";
      box.appendChild(el("div", "t-who", `couldn't load: ${e.message}`));
    }
  });

  return card;
}

function closeDrawer() {
  drawer.classList.add("hidden");
  scrim.classList.add("hidden");
}

document.getElementById("history-btn").addEventListener("click", openDrawer);
document.getElementById("drawer-close").addEventListener("click", closeDrawer);
scrim.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !drawer.classList.contains("hidden")) closeDrawer();
});

forgetBtn.addEventListener("click", async () => {
  if (!confirm("Erase everything Mind-Mate remembers about you? This can't be undone.")) return;
  try {
    const r = await fetch(`/api/forget?user_id=${encodeURIComponent(USER_ID)}`, { method: "POST" });
    const j = await r.json();
    log.innerHTML = "";
    sosBox.classList.add("hidden");
    setMood("neutral");
    setBars(0, 0);
    addBotMsg(j.reply);
    renderMemory(j.remembers);
  } catch (e) {
    addBotMsg(`Couldn't clear memory: ${e.message}`);
  }
});
