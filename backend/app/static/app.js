// Minimal vanilla JS: poll status, show model compatibility, and run chat.
// No framework, no build step.

async function refreshStatus() {
  const pill = document.getElementById("status-pill");
  try {
    const health = await (await fetch("/api/health")).json();
    pill.textContent = health.status === "ok" ? "online" : "degraded";
    pill.className = "pill " + (health.status === "ok" ? "pill-ok" : "pill-bad");
    document.getElementById("s-db").textContent = health.database_ok ? "ready" : "error";
    document.getElementById("s-version").textContent = health.version ?? "—";
  } catch (e) {
    pill.textContent = "offline";
    pill.className = "pill pill-bad";
  }

  // Model status + compatibility check.
  try {
    const m = await (await fetch("/api/model")).json();
    document.getElementById("s-backend").textContent = m.backend ?? "—";
    document.getElementById("s-model").textContent =
      m.model + (m.parameters ? ` (${m.parameters})` : "");
    document.getElementById("s-model-ready").textContent = m.available ? "yes" : "no — not running";
    document.getElementById("s-fits").textContent =
      m.available ? (m.fits_memory ? `yes (~${m.estimated_gb} GB)` : `tight (~${m.estimated_gb} GB)`) : "—";
    document.getElementById("model-note").textContent = (m.messages || []).join("  ·  ");
  } catch (e) { /* leave as-is */ }
}

// Append a message bubble to the chat log.
function addBubble(role, text) {
  const log = document.getElementById("chat-log");
  const div = document.createElement("div");
  div.className = "bubble bubble-" + role;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

const history = [];  // [{role, content}] kept in the browser for this session

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  addBubble("user", msg);
  history.push({ role: "user", content: msg });
  input.value = "";
  const thinking = addBubble("assistant", "…");

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history }),
    });
    const data = await res.json();
    if (data.ok) {
      thinking.textContent = data.reply;
      history.push({ role: "assistant", content: data.reply });
    } else {
      thinking.textContent = "⚠ " + data.error;
      thinking.classList.add("bubble-error");
    }
  } catch (err) {
    thinking.textContent = "⚠ Could not reach the backend.";
    thinking.classList.add("bubble-error");
  }
});

refreshStatus();
setInterval(refreshStatus, 8000);
