"""Settings API: read defaults, save a value, never echo secrets."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.app import config, database
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


def test_defaults_returned(client):
    data = client.get("/api/settings").json()["settings"]
    model = next(s for s in data if s["key"] == "ollama_model")
    assert model["value"] == "qwen3:8b"


def test_save_plain_setting(client):
    client.post("/api/settings", json={"key": "ollama_model", "value": "qwen3:4b"})
    data = client.get("/api/settings").json()["settings"]
    model = next(s for s in data if s["key"] == "ollama_model")
    assert model["value"] == "qwen3:4b"


def test_secret_never_echoed(client):
    client.post("/api/settings", json={"key": "langsearch_api_key", "value": "super-secret"})
    data = client.get("/api/settings").json()["settings"]
    key = next(s for s in data if s["key"] == "langsearch_api_key")
    assert key["value"] == ""          # never returned
    assert key["is_set"] is True       # but we know it's set


def test_blank_secret_keeps_existing(client):
    client.post("/api/settings", json={"key": "langsearch_api_key", "value": "abc"})
    r = client.post("/api/settings", json={"key": "langsearch_api_key", "value": ""})
    assert r.json().get("unchanged") is True   # blank doesn't wipe it
    print("  settings: defaults, save, secret-hiding, blank-keeps: OK")


def test_unknown_key_rejected(client):
    r = client.post("/api/settings", json={"key": "haxxor", "value": "x"})
    assert r.json()["ok"] is False


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
