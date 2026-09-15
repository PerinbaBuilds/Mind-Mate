const log = document.getElementById("log");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");
const status = document.getElementById("status");
const face = document.querySelector(".face");
const moodLabel = document.getElementById("mood-label");
const sosBox = document.getElementById("sos");

const USER_ID = "demo-user";

function addMsg(text, cls, meta) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.textContent = text;
  if (meta) {
    const m = document.createElement("span");
    m.className = "meta";
    m.textContent = meta;
    div.appendChild(m);
  }
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function addRecall(text) {
  const div = document.createElement("div");
  div.className = "msg recall";
  div.textContent = `Mind-Mate is recalling a related memory: "${text}"`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function setMood(label) {
  face.dataset.mood = label || "neutral";
  moodLabel.textContent = label || "neutral";
}

async function refreshStatus() {
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    status.textContent = j.llm_online
      ? `online · ${j.model}`
      : "offline demo mode (set ANTHROPIC_API_KEY to enable Claude)";
  } catch {
    status.textContent = "server unreachable";
  }
}
refreshStatus();

addMsg(
  "Hi, I'm Mind-Mate. I'm here to listen — nothing you say will be judged. What's on your mind today?",
  "bot"
);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMsg(text, "user");
  input.value = "";
  sendBtn.disabled = true;

  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: USER_ID, message: text }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();

    setMood(j.emotion?.label);
    if (j.sos_level >= 2) sosBox.classList.remove("hidden");
    else sosBox.classList.add("hidden");

    if (j.recalled_memory) addRecall(j.recalled_memory);
    const meta = `mood: ${j.emotion.label} · valence ${j.emotion.valence.toFixed(2)} · sos ${j.sos_level}`;
    addMsg(j.reply, "bot", meta);
  } catch (err) {
    addMsg(`Sorry, something went wrong: ${err.message}`, "bot");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});
