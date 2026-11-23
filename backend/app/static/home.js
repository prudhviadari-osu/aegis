// Home page: status summary + chat. Vanilla JS.
async function refresh() {
  const pill = document.getElementById("status-pill");
  try {
    const h = await (await fetch("/api/health")).json();
    pill.textContent = h.status === "ok" ? "online" : "degraded";
    pill.className = "pill " + (h.status === "ok" ? "pill-ok" : "pill-bad");
  } catch { pill.textContent = "offline"; pill.className = "pill pill-bad"; }

  try {
    const m = await (await fetch("/api/model")).json();
    document.getElementById("h-model").textContent =
      m.available ? `${m.model} — ready` : `${m.model} — not running`;
  } catch {}

  try {
    const r = await (await fetch("/api/resources")).json();
    const batt = r.battery_percent != null ? `${r.battery_percent}%` : "n/a";
    const power = r.on_ac_power == null ? "" : (r.on_ac_power ? ", plugged in" : ", on battery");
    document.getElementById("h-device").textContent =
      `battery ${batt}${power} · ${r.safe_to_proceed ? "OK to work" : "holding off"}`;
  } catch {}

  try {
    const j = await (await fetch("/api/jobs?show_all=true")).json();
    const applied = j.jobs.filter((x) => x.review_status === "applied").length;
    document.getElementById("h-jobs").textContent =
      j.count ? `${j.count} found · ${applied} applied` : "none yet — run a search";
  } catch {}

  try {
    const tasks = await (await fetch("/api/tasks?status=running")).json();
    document.getElementById("h-tasks").textContent = tasks.length;
  } catch {}

  // Show what the worker is doing right now + how long (so nothing's a mystery).
  try {
    const r = await (await fetch("/api/tasks/running")).json();
    const el = document.getElementById("h-running");
    if (r.running) {
      const mins = r.elapsed_seconds != null ? ` · ${Math.floor(r.elapsed_seconds / 60)}m ${r.elapsed_seconds % 60}s` : "";
      el.textContent = `#${r.task_id} ${r.title}${mins}${r.step ? " · " + r.step : ""}`;
    } else {
      el.textContent = "idle";
    }
  } catch {}
}

const history = [];
function bubble(role, text) {
  const log = document.getElementById("chat-log");
  const d = document.createElement("div");
  d.className = "bubble bubble-" + role;
  d.textContent = text;
  log.appendChild(d); log.scrollTop = log.scrollHeight;
  return d;
}
document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  bubble("user", msg); history.push({ role: "user", content: msg });
  input.value = "";
  const thinking = bubble("assistant", "…");
  try {
    const res = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg, history }),
    });
    const data = await res.json();
    if (data.ok) { thinking.textContent = data.reply; history.push({ role: "assistant", content: data.reply }); }
    else { thinking.textContent = "⚠ " + data.error; thinking.classList.add("bubble-error"); }
  } catch { thinking.textContent = "⚠ Could not reach the backend."; thinking.classList.add("bubble-error"); }
});

refresh();
setInterval(refresh, 6000);
