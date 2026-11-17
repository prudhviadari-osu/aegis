// Minimal vanilla JS: poll health, fill the status card. No framework, no build.
async function refreshStatus() {
  const pill = document.getElementById("status-pill");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    pill.textContent = data.status === "ok" ? "online" : "degraded";
    pill.className = "pill " + (data.status === "ok" ? "pill-ok" : "pill-bad");
    document.getElementById("s-backend").textContent = data.model_backend ?? "—";
    document.getElementById("s-model").textContent = data.model ?? "—";
    document.getElementById("s-db").textContent = data.database_ok ? "ready" : "error";
    document.getElementById("s-version").textContent = data.version ?? "—";
  } catch (e) {
    pill.textContent = "offline";
    pill.className = "pill pill-bad";
  }
}
refreshStatus();
setInterval(refreshStatus, 5000);
