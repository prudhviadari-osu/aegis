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

  // Device safety (battery / thermal / memory governor).
  try {
    const r = await (await fetch("/api/resources")).json();
    document.getElementById("r-battery").textContent =
      r.battery_percent != null ? `${r.battery_percent}%` : "n/a (desktop?)";
    document.getElementById("r-power").textContent =
      r.on_ac_power == null ? "—" : (r.on_ac_power ? "plugged in" : "on battery");
    document.getElementById("r-thermal").textContent = r.thermal_pressure ?? "—";
    document.getElementById("r-mem").textContent =
      r.memory_percent != null ? `${r.memory_percent}% used` : "—";
    const safe = document.getElementById("r-safe");
    safe.textContent = r.safe_to_proceed ? "yes" : "holding off";
    safe.style.color = r.safe_to_proceed ? "var(--ok)" : "var(--bad)";
    document.getElementById("r-reason").textContent = r.governor_reason ?? "";
  } catch (e) { /* ignore */ }

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

// --- Tasks ---
async function refreshTasks() {
  try {
    const tasks = await (await fetch("/api/tasks")).json();
    const list = document.getElementById("task-list");
    list.innerHTML = "";
    if (!tasks.length) { list.innerHTML = '<li class="muted">No tasks yet.</li>'; return; }
    for (const t of tasks) {
      const li = document.createElement("li");
      li.textContent = `#${t.id} [${t.status}] ${t.title}`;
      list.appendChild(li);
    }
  } catch (e) { /* ignore */ }

  try {
    const aps = await (await fetch("/api/approvals")).json();
    const list = document.getElementById("approval-list");
    list.innerHTML = "";
    if (!aps.length) { list.innerHTML = '<li class="muted">Nothing waiting.</li>'; return; }
    for (const a of aps) {
      const li = document.createElement("li");
      li.textContent = `${a.action}: ${a.description} `;
      const yes = document.createElement("button");
      yes.textContent = "Approve";
      yes.onclick = () => resolveApproval(a.id, true);
      const no = document.createElement("button");
      no.textContent = "Reject";
      no.onclick = () => resolveApproval(a.id, false);
      li.append(yes, no);
      list.appendChild(li);
    }
  } catch (e) { /* ignore */ }
}

async function resolveApproval(id, approved) {
  await fetch(`/api/approvals/${id}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  refreshTasks();
}

document.getElementById("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("task-title");
  const title = input.value.trim();
  if (!title) return;
  await fetch("/api/tasks", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  input.value = "";
  refreshTasks();
});

async function loadSkills() {
  try {
    const skills = await (await fetch("/api/skills")).json();
    const list = document.getElementById("skill-list");
    list.innerHTML = "";
    if (!skills.length) { list.innerHTML = '<li class="muted">No skills loaded.</li>'; return; }
    for (const s of skills) {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${s.name}</strong> <span class="muted">[${s.permission}]</span> — ${s.description}`;
      list.appendChild(li);
    }
  } catch (e) { /* ignore */ }
}

async function refreshMemory() {
  try {
    const mems = await (await fetch("/api/memory")).json();
    const list = document.getElementById("memory-list");
    list.innerHTML = "";
    if (!mems.length) { list.innerHTML = '<li class="muted">Nothing remembered yet.</li>'; return; }
    for (const m of mems) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="muted">[${m.category}]</span> ${m.content} `;
      const del = document.createElement("button");
      del.textContent = "Forget";
      del.onclick = async () => {
        await fetch(`/api/memory/${m.id}`, { method: "DELETE" });
        refreshMemory();
      };
      li.appendChild(del);
      list.appendChild(li);
    }
  } catch (e) { /* ignore */ }
}

document.getElementById("memory-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("memory-input");
  const content = input.value.trim();
  if (!content) return;
  await fetch("/api/memory", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, category: "profile" }),
  });
  input.value = "";
  refreshMemory();
});

refreshStatus();
refreshTasks();
loadSkills();
refreshMemory();
setInterval(refreshStatus, 8000);
setInterval(refreshTasks, 4000);
