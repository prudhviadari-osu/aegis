let consecutiveDown = 0;   // debounce: don't show "not running" on a single blip

async function refresh() {
  try {
    const m = await (await fetch("/api/model")).json();
    document.getElementById("m-backend").textContent = m.backend ?? "—";
    document.getElementById("m-model").textContent = m.model ?? "—";
    document.getElementById("m-mem").textContent =
      m.estimated_gb != null ? `~${m.estimated_gb} / ${m.machine_ram_gb} GB` : "—";
    document.getElementById("m-notes").textContent = (m.messages || []).join("  ·  ");

    const statusEl = document.getElementById("m-status");
    if (m.available) {
      consecutiveDown = 0;
      statusEl.textContent = "ready";
      statusEl.style.color = "var(--ok)";
    } else {
      consecutiveDown += 1;
      // Only declare it down after 2 consecutive failed checks (≈10s), so a single
      // slow/busy moment shows "busy…" instead of a scary "not running".
      if (consecutiveDown >= 2) {
        statusEl.textContent = "not running";
        statusEl.style.color = "var(--bad)";
      } else {
        statusEl.textContent = "busy… (rechecking)";
        statusEl.style.color = "var(--warn)";
      }
    }
  } catch {
    consecutiveDown += 1;   // network blip to our own backend counts too
  }

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
