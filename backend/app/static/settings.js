async function loadSettings() {
  const data = await (await fetch("/api/settings")).json();
  const box = document.getElementById("settings-fields");
  box.innerHTML = "";
  for (const s of data.settings) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const setNote = s.secret ? (s.is_set ? ' <span class="muted">(••• set)</span>' : ' <span class="muted">(not set)</span>') : "";
    const placeholder = s.secret && s.is_set ? "leave blank to keep current" : (s.value || "");
    wrap.innerHTML = `
      <label>${s.label}${setNote}</label>
      <div style="display:flex;gap:.5rem">
        <input type="${s.secret ? "password" : "text"}" id="f-${s.key}"
               value="${s.secret ? "" : (s.value ?? "")}" placeholder="${placeholder}">
        <button type="button" onclick="saveOne('${s.key}')">Save</button>
      </div>`;
    box.appendChild(wrap);
  }
}

async function saveOne(key) {
  const val = document.getElementById(`f-${key}`).value;
  const msg = document.getElementById("settings-msg");
  try {
    const res = await fetch("/api/settings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key, value: val }),
    });
    const data = await res.json();
    if (data.ok) {
      msg.textContent = data.unchanged ? `${key}: unchanged (blank secret kept).` : `✓ Saved ${key}.`;
      msg.className = "msg msg-ok";
      loadSettings();
    } else {
      msg.textContent = "⚠ " + (data.error || "could not save");
      msg.className = "msg msg-bad";
    }
  } catch {
    msg.textContent = "⚠ Could not reach the backend.";
    msg.className = "msg msg-bad";
  }
}
loadSettings();
