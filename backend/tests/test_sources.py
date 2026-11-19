"""M7 polish: the add-job-source endpoint parses a Workday URL and registers it."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend.app import config, database
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "MODEL_BACKEND", "fake")
    database.init_db(db)
    # The registry writes to jobify's discovered file; point THAT at a temp path
    # (it's a jobify config setting, not an Aegis one).
    sys.path.insert(0, config.JOBIFY_PATH)
    from finder import config as jf_config
    monkeypatch.setattr(jf_config, "DISCOVERED_COMPANIES_PATH", str(tmp_path / "discovered.json"))
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


def test_add_valid_workday_source(client):
    r = client.post("/api/sources",
                    json={"url": "https://medtronic.wd1.myworkdayjobs.com/MedtronicCareers"})
    assert r.status_code == 200
    body = r.json()
    assert body["added"] is True
    assert body["company"]["tenant"] == "medtronic"


def test_add_duplicate_is_idempotent(client):
    url = "https://iqvia.wd1.myworkdayjobs.com/IQVIA"
    client.post("/api/sources", json={"url": url})
    r2 = client.post("/api/sources", json={"url": url})
    assert r2.json()["added"] is False
    assert "already" in r2.json()["message"].lower()


def test_reject_non_workday_url(client):
    r = client.post("/api/sources", json={"url": "https://example.com/careers"})
    assert r.status_code == 400
    print("  add-source endpoint: valid/dup/invalid all handled: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
