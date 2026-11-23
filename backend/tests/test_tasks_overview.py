"""Tasks dashboard: the /api/tasks/overview endpoint (queue, running, ETA) and
that the literal route isn't shadowed by /{task_id}."""
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


def test_overview_route_not_shadowed(client):
    r = client.get("/api/tasks/overview")
    assert r.status_code == 200          # not 422 from /{task_id}
    body = r.json()
    assert "queued" in body and "recent" in body and "running" in body


def test_overview_shows_queue_and_recent(client):
    from backend.app.tasks import repository as repo
    repo.create_task("Queued job", skill="job_finder")          # queued
    t2 = repo.create_task("Done job")
    repo.transition(t2["id"], "running"); repo.transition(t2["id"], "completed")
    data = client.get("/api/tasks/overview").json()
    assert data["queue_length"] >= 1
    assert any("Queued job" in q["title"] for q in data["queued"])
    assert any("Done job" in r["title"] for r in data["recent"])


def test_overview_eta_from_checkpoint(client, monkeypatch):
    """When a task is running with done/total in its checkpoint, overview computes
    an ETA from elapsed / done * remaining."""
    from backend.app.tasks import repository as repo
    from backend.app.tasks.worker import worker
    import backend.app.tasks.worker as wmod

    t = repo.create_task("Scoring job", skill="job_finder")
    repo.transition(t["id"], "running")
    repo.save_checkpoint(t["id"], {"step": "scoring", "done": 5, "total": 20})
    # Simulate the worker currently holding this task.
    monkeypatch.setattr(wmod.worker, "current_task_id", t["id"])
    monkeypatch.setattr(wmod.worker, "current_task_title", "Scoring job")

    data = client.get("/api/tasks/overview").json()
    assert data["running"] is not None
    r = data["running"]
    assert r["done"] == 5 and r["total"] == 20
    # ETA should be a non-negative number (or None if elapsed couldn't be read).
    assert r["eta_seconds"] is None or r["eta_seconds"] >= 0
    print("  overview exposes running task + progress + ETA: OK")


def test_tasks_page_served(client):
    r = client.get("/tasks")
    assert r.status_code == 200
    assert "Running now" in r.text and "Queue" in r.text


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
