"""M5.5 step 3 tests: the /jobs API — visible jobs follow the tiered reveal,
detail returns full fields, and reviewing unlocks the next tier. Fake model."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app import config, database
from backend.app.jobs import upsert_job, set_score, assign_tiers


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "MODEL_BACKEND", "fake")
    database.init_db(db)
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


def _seed(n, ring=2):
    for i in range(n):
        j = upsert_job({"job_key": f"k{i}", "company": "MedCo", "title": f"Role {i}",
                        "location": "Columbus, OH", "url": "x", "description": "biomedical"})
        set_score(j["id"], ring=ring, fit_score=0.9, path_score=0.9,
                  reasoning="fits", have=["Python"], missing=["FDA"],
                  steps=["mention research"], draft="I'm a strong fit because...")
    assign_tiers()


def test_jobs_list_shows_only_current_tier(client):
    _seed(12)                                  # tiers 1,2,3 (size 5)
    data = client.get("/api/jobs").json()
    assert data["current_tier"] == 1
    assert all(j["tier"] == 1 for j in data["jobs"])
    assert data["count"] == 5                  # only tier 1 shown


def test_detail_returns_full_fields(client):
    _seed(1)
    jid = client.get("/api/jobs").json()["jobs"][0]["id"]
    j = client.get(f"/api/jobs/{jid}").json()
    assert j["have"] == ["Python"]
    assert j["missing"] == ["FDA"]
    assert j["steps"] == ["mention research"]
    assert j["draft"].startswith("I'm a strong fit")


def test_review_unlocks_next_tier(client):
    _seed(10)                                  # tiers 1,2
    data = client.get("/api/jobs").json()
    assert data["current_tier"] == 1
    tier1_ids = [j["id"] for j in data["jobs"]]
    # Review all but one -> still tier 1.
    for jid in tier1_ids[:-1]:
        client.post(f"/api/jobs/{jid}/review", json={"status": "applied"})
    assert client.get("/api/jobs").json()["current_tier"] == 1
    # Review the last -> tier 2 unlocks and becomes visible.
    r = client.post(f"/api/jobs/{tier1_ids[-1]}/review", json={"status": "skipped"})
    assert r.json()["current_tier"] == 2
    shown = client.get("/api/jobs").json()
    assert 2 in {j["tier"] for j in shown["jobs"]}
    print("  /api review flow unlocks the next tier: OK")


def test_bad_review_status_rejected(client):
    _seed(1)
    jid = client.get("/api/jobs").json()["jobs"][0]["id"]
    r = client.post(f"/api/jobs/{jid}/review", json={"status": "nonsense"})
    assert r.status_code == 400


def test_jobs_page_served(client):
    r = client.get("/jobs")
    assert r.status_code == 200
    assert "Your matches" in r.text


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
