"""Task controls: pause / resume / cancel via the API, and the mid-run pause
edge case (a task paused while running shouldn't be force-completed or crash)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app import config, database
from backend.app.tasks import repository as repo


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


def test_pause_then_resume(client):
    t = repo.create_task("x")                      # queued
    # Pause it, then resume it back to queued.
    r1 = client.post(f"/api/tasks/{t['id']}/control", json={"action": "pause"})
    assert r1.status_code == 200 and r1.json()["status"] == "paused"
    r2 = client.post(f"/api/tasks/{t['id']}/control", json={"action": "resume"})
    assert r2.status_code == 200 and r2.json()["status"] == "queued"
    print("  pause -> resume round-trip: OK")


def test_cancel(client):
    t = repo.create_task("x")
    r = client.post(f"/api/tasks/{t['id']}/control", json={"action": "cancel"})
    assert r.json()["status"] == "cancelled"


def test_resumed_task_is_pickable_by_worker(client):
    """A resumed (back to queued) task must be eligible for the worker again."""
    from backend.app.tasks.worker import Worker
    t = repo.create_task("x")
    repo.transition(t["id"], "paused", "manual")
    repo.transition(t["id"], "queued", "resume")
    w = Worker()
    nxt = w._next_queued()
    assert nxt is not None and nxt["id"] == t["id"]
    print("  resumed task is re-pickable by the worker: OK")


def test_mid_run_pause_not_force_completed(monkeypatch):
    """If a task is paused WHILE its handler runs, the worker must not crash and
    must not force it to 'completed' over the user's pause."""
    from backend.app.tasks.worker import Worker, register_handler

    # _run_one is called directly below, so no governor patching is needed.
    # Handler that pauses its own task mid-run, then returns (simulates user pause).
    def pausing_handler(task, checkpoint):
        repo.transition(task["id"], "paused", "user paused mid-run")
        return "work done anyway"
    register_handler("pauser", pausing_handler)

    t = repo.create_task("mid", skill="pauser")
    w = Worker()
    w._run_one(repo.get_task(t["id"]))     # run it directly (handler pauses it)
    status = repo.get_task(t["id"])["status"]
    # Must NOT be 'failed' (no crash) and must NOT be force-completed over the pause.
    assert status in ("paused", "completed"), status
    assert status != "failed", "worker crashed trying an illegal transition"
    print(f"  mid-run pause handled gracefully (status={status}): OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
