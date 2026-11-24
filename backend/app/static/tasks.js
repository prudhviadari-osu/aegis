function fmtDuration(s) {
  if (s == null) return "—";
  const m = Math.floor(s / 60), sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

async function refresh() {
  let data;
  try { data = await (await fetch("/api/tasks/overview")).json(); }
  catch { return; }

  document.getElementById("q-pill").textContent = `queue ${data.queue_length}`;
  document.getElementById("q-pill").className = "pill " + (data.queue_length ? "pill-warn" : "pill-ok");

  // Running
  const run = document.getElementById("running");
  if (data.running) {
    const r = data.running;
    const progress = (r.done != null && r.total != null)
      ? `<div class="fit-bar" style="width:100%;height:8px"><span style="width:${Math.round(100*r.done/r.total)}%"></span></div>
         <p class="muted">${r.done} / ${r.total} done</p>` : "";
    const eta = r.eta_seconds != null ? `~${fmtDuration(r.eta_seconds)} left (estimate)`
              : (r.total == null ? "estimating…" : "almost done");
    run.innerHTML = `
      <p><strong>#${r.task_id} ${r.title}</strong></p>
      <p class="muted">step: ${r.step || "working"} · running ${fmtDuration(r.elapsed_seconds)} · ${eta}</p>
      ${progress}
      <div style="margin-top:.6rem">
        <button class="btn-mini btn-secondary" onclick="control(${r.task_id}, 'pause')">⏸ Pause</button>
        <button class="btn-mini btn-secondary" onclick="control(${r.task_id}, 'cancel')">✕ Cancel</button>
      </div>
      <p class="muted" style="font-size:.8rem;margin-top:.4rem">Pausing takes effect after the current step (a model call can't be interrupted mid-way).</p>`;
  } else {
    run.innerHTML = '<p class="muted">Nothing running — the worker is idle.</p>';
  }

  // Queue
  const q = document.getElementById("queue-list");
  document.getElementById("queue-count").textContent = `(${data.queue_length})`;
  if (!data.queued.length) {
    q.innerHTML = '<li class="muted">Queue is empty.</li>';
  } else {
    q.innerHTML = "";
    data.queued.forEach((t, i) => {
      const li = document.createElement("li");
      // Controls depend on state: a paused task can resume; a queued one can pause.
      const controls = t.status === "paused"
        ? `<button class="btn-mini" onclick="control(${t.task_id}, 'resume')">▶ Resume</button>`
        : `<button class="btn-mini btn-secondary" onclick="control(${t.task_id}, 'pause')">⏸ Pause</button>`;
      li.innerHTML = `<strong>#${t.task_id}</strong> ${t.title}
        <span class="muted">[${t.status}]${i === 0 ? " · next up" : ""}</span> `;
      const span = document.createElement("span");
      span.innerHTML = controls +
        ` <button class="btn-mini btn-secondary" onclick="control(${t.task_id}, 'cancel')">✕ Cancel</button>`;
      li.appendChild(span);
      q.appendChild(li);
    });
  }

  // Recent
  const rec = document.getElementById("recent-list");
  if (!data.recent.length) {
    rec.innerHTML = '<li class="muted">No finished tasks yet.</li>';
  } else {
    rec.innerHTML = "";
    for (const t of data.recent) {
      const li = document.createElement("li");
      const color = t.status === "completed" ? "var(--ok)" : t.status === "failed" ? "var(--bad)" : "var(--muted)";
      li.innerHTML = `<strong>#${t.task_id}</strong> ${t.title}
        <span style="color:${color}">[${t.status}]</span>
        ${t.result ? `<br><span class="muted">${t.result}</span>` : ""}`;
      rec.appendChild(li);
    }
  }
}

// Pause / resume / cancel a task via the control endpoint, then refresh.
async function control(taskId, action) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/control`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Couldn't ${action} task #${taskId}: ${err.detail || res.status}`);
    }
  } catch {
    alert("Couldn't reach the backend.");
  }
  refresh();
}

refresh();
setInterval(refresh, 3000);
