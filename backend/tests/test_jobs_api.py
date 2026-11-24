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
    # Two search modes present on the page.
    assert "Search my jobs" in r.text and "Find new jobs" in r.text


def test_local_search_filters_db(client):
    _seed(3)                                   # 3 jobs titled "Role 0/1/2" at MedCo
    # Local search for a term that matches.
    r = client.get("/api/jobs/search-local?q=Role")
    assert r.json()["count"] == 3
    # A term that matches nothing.
    r2 = client.get("/api/jobs/search-local?q=nonexistentterm")
    assert r2.json()["count"] == 0


def test_search_status_not_shadowed(client):
    # The literal path must resolve to the status endpoint, not /{job_id} (422).
    r = client.get("/api/jobs/search-status")
    assert r.status_code == 200
    assert "active" in r.json()


def test_clear_jobs_keeps_applied(client):
    from backend.app.jobs import upsert_job, set_review_status
    a = upsert_job({"job_key": "a", "company": "X", "title": "t", "location": "l",
                    "url": "u", "description": "d", "source": "s"})
    upsert_job({"job_key": "b", "company": "X", "title": "t2", "location": "l",
                "url": "u", "description": "d", "source": "s"})
    set_review_status(a["id"], "applied")           # mark one applied
    r = client.post("/api/jobs/clear")               # default: keep applied
    assert r.json()["removed"] == 1                  # only the non-applied one
    from backend.app.jobs import all_jobs
    remaining = all_jobs()
    assert len(remaining) == 1 and remaining[0]["review_status"] == "applied"


def test_search_endpoint_creates_task(client):
    r = client.post("/api/jobs/search", json={"keywords": "intern, biomedical"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # A job_finder task should now exist.
    from backend.app.tasks import repository as repo
    tasks = repo.list_tasks()
    assert any(t["skill"] == "job_finder" for t in tasks)


def test_subpages_served(client):
    for path, marker in [("/metrics", "Device safety"), ("/settings", "Settings")]:
        r = client.get(path)
        assert r.status_code == 200 and marker in r.text


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
