// /jobs page: ranked table + click-through detail + tiered reveal. Vanilla JS.
let selectedId = null;

function ringBadge(ring) {
  const label = { 1: "medicine", 2: "med-AI", 3: "tech", 4: "off-path" }[ring] || "?";
  return `<span class="ring-badge ring-${ring}">${label}</span>`;
}

async function loadTable() {
  const data = await (await fetch("/api/jobs")).json();
  document.getElementById("tier-pill").textContent = "tier " + data.current_tier;
  document.getElementById("tier-pill").className = "pill pill-ok";
  document.getElementById("job-count").textContent = `(${data.count} shown)`;

  // Warning banner when jobs aren't model-analyzed.
  const banner = document.getElementById("no-model-banner");
  if (data.no_model) {
    banner.style.display = "block";
    banner.textContent = "⚠ No model used — these are raw matches, not ranked or analyzed. "
      + "Start Ollama (qwen3:8b) and re-run the job_finder task for fit ranking, "
      + "have/missing, and drafts.";
  } else {
    banner.style.display = "none";
  }

  const body = document.getElementById("job-rows");
  if (!data.jobs.length) {
    body.innerHTML = '<tr><td colspan="5" class="muted">No jobs yet. Run a job_finder task on the dashboard.</td></tr>';
    return;
  }
  body.innerHTML = "";
  for (const j of data.jobs) {
    const tr = document.createElement("tr");
    if (j.id === selectedId) tr.className = "selected";
    const fitCell = j.scored
      ? `<div class="fit-bar"><span style="width:${Math.round((j.fit_score||0)*100)}%"></span></div>`
      : '<span class="muted">—</span>';
    const ringCell = j.scored ? ringBadge(j.ring) : '<span class="muted">unranked</span>';
    tr.innerHTML = `
      <td>${fitCell}</td>
      <td>${ringCell}</td>
      <td>${j.title ?? ""}</td>
      <td>${j.company ?? ""}</td>
      <td class="status-${j.review_status}">${j.review_status}</td>`;
    tr.onclick = () => showDetail(j.id);
    body.appendChild(tr);
  }
}

function list(items) {
  if (!items || !items.length) return '<li class="muted">—</li>';
  return items.map((i) => `<li>${i}</li>`).join("");
}

async function showDetail(id) {
  selectedId = id;
  const j = await (await fetch(`/api/jobs/${id}`)).json();
  const d = document.getElementById("detail");
  d.innerHTML = `
    <h2>${j.title}</h2>
    <p class="muted">${j.company} · ${j.location || "n/a"} · ${ringBadge(j.ring)}
      fit ${Math.round((j.fit_score||0)*100)}% · path ${Math.round((j.path_score||0)*100)}%</p>
    ${j.url ? `<p><a href="${j.url}" target="_blank" rel="noopener">Open the job posting ↗</a></p>` : ""}

    <div class="detail-section"><h3>Why it fits</h3><p>${j.reasoning || "—"}</p></div>
    <div class="detail-section"><h3>Job description</h3>
      <p class="muted">${(j.description || "").slice(0, 600)}${(j.description||"").length>600?"…":""}</p></div>
    <div class="detail-section"><h3>What you have</h3><ul class="have">${list(j.have)}</ul></div>
    <div class="detail-section"><h3>What you're missing</h3><ul class="missing">${list(j.missing)}</ul></div>
    <div class="detail-section"><h3>Steps to strengthen your application</h3><ul class="steps">${list(j.steps)}</ul></div>
    <div class="detail-section"><h3>Suggested submission (review before using)</h3>
      <div class="draft-box">${j.draft || "—"}</div></div>

    <div class="detail-actions">
      <button onclick="review(${j.id}, 'applied')">Mark applied</button>
      <button class="btn-skip" onclick="review(${j.id}, 'skipped')">Skip</button>
    </div>
    <p class="muted" style="margin-top:.5rem">Current status: <strong>${j.review_status}</strong></p>`;
  loadTable();
}

async function review(id, status) {
  await fetch(`/api/jobs/${id}/review`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  await loadTable();      // may reveal a new tier
  showDetail(id);         // refresh the detail with the new status
}

// Run-search form: kicks off a job_finder task; the table polls for results.
document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const kw = document.getElementById("search-input").value.trim();
  const msg = document.getElementById("search-msg");
  const btn = document.getElementById("search-btn");
  btn.disabled = true; msg.textContent = "Starting search…"; msg.className = "msg";
  try {
    const res = await fetch("/api/jobs/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords: kw }),
    });
    const data = await res.json();
    msg.textContent = data.ok
      ? "✓ " + data.message + " (This can take a few minutes — the table updates live.)"
      : "⚠ could not start search";
    msg.className = "msg " + (data.ok ? "msg-ok" : "msg-bad");
  } catch {
    msg.textContent = "⚠ Could not reach the backend.";
    msg.className = "msg msg-bad";
  } finally {
    btn.disabled = false;
  }
});

loadTable();
setInterval(loadTable, 4000);   // live-update as the search + scoring finish
