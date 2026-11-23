async function refresh() {
  try {
    const m = await (await fetch("/api/model")).json();
    document.getElementById("m-backend").textContent = m.backend ?? "—";
    document.getElementById("m-model").textContent = m.model ?? "—";
    document.getElementById("m-status").textContent = m.available ? "ready" : "not running";
    document.getElementById("m-status").style.color = m.available ? "var(--ok)" : "var(--bad)";
    document.getElementById("m-mem").textContent =
      m.estimated_gb != null ? `~${m.estimated_gb} / ${m.machine_ram_gb} GB` : "—";
    document.getElementById("m-notes").textContent = (m.messages || []).join("  ·  ");
  } catch {}

  try {
    const r = await (await fetch("/api/resources")).json();
    document.getElementById("d-battery").textContent =
      r.battery_percent != null ? `${r.battery_percent}%` : "n/a";
    document.getElementById("d-power").textContent =
      r.on_ac_power == null ? "—" : (r.on_ac_power ? "plugged in" : "on battery");
    document.getElementById("d-thermal").textContent = r.thermal_pressure ?? "—";
    document.getElementById("d-mem").textContent =
      r.memory_percent != null ? `${r.memory_percent}%` : "—";
    const safe = document.getElementById("d-safe");
    safe.textContent = (r.safe_to_proceed ? "✓ " : "⚠ ") + (r.governor_reason || "");
    safe.className = "msg " + (r.safe_to_proceed ? "msg-ok" : "msg-bad");
  } catch {}
}
refresh();
setInterval(refresh, 5000);
