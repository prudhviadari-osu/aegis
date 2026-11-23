"""Settings endpoints (Settings page): read/write user-facing config.

Stored in the SQLite `setting` table so changes persist across restarts. These
are *display/convenience* settings; secrets like API keys are written here too
but the API never returns their full value (only whether one is set).
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..database import connect

router = APIRouter()

# Keys the Settings page manages. "secret": True means never echo the value back.
SETTINGS_SCHEMA = [
    {"key": "ollama_model", "label": "Model", "secret": False, "default": "qwen3:8b"},
    {"key": "target_context", "label": "Context window", "secret": False, "default": "16000"},
    {"key": "machine_ram_gb", "label": "Mac RAM (GB)", "secret": False, "default": "18"},
    {"key": "kv_cache_type", "label": "KV cache", "secret": False, "default": "q8_0"},
    {"key": "langsearch_api_key", "label": "LangSearch API key", "secret": True, "default": ""},
    {"key": "adzuna_app_id", "label": "Adzuna App ID", "secret": True, "default": ""},
    {"key": "adzuna_app_key", "label": "Adzuna App Key", "secret": True, "default": ""},
]
_SECRET = {s["key"] for s in SETTINGS_SCHEMA if s["secret"]}


def _get(key: str) -> str | None:
    conn = connect()
    try:
        row = conn.execute("SELECT value FROM setting WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def _set(key: str, value: str) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO setting(key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (key, value))
        conn.commit()
    finally:
        conn.close()


@router.get("/api/settings")
def get_settings() -> dict:
    out = []
    for s in SETTINGS_SCHEMA:
        stored = _get(s["key"])
        if s["secret"]:
            # Never return the actual secret — only whether one is set.
            out.append({**s, "value": "", "is_set": bool(stored)})
        else:
            out.append({**s, "value": stored if stored is not None else s["default"], "is_set": stored is not None})
    return {"settings": out}


class SettingIn(BaseModel):
    key: str
    value: str


@router.post("/api/settings")
def update_setting(body: SettingIn) -> dict:
    valid = {s["key"] for s in SETTINGS_SCHEMA}
    if body.key not in valid:
        return {"ok": False, "error": f"unknown setting '{body.key}'"}
    # Empty value for a secret means "leave unchanged" (don't wipe it by accident).
    if body.key in _SECRET and body.value == "":
        return {"ok": True, "unchanged": True}
    _set(body.key, body.value)
    return {"ok": True, "key": body.key, "is_set": True}
