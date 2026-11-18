"""Milestone 3 tests: task state machine, checkpoints, approvals, worker,
and interrupted-task recovery. Uses a temp DB and the fake model backend."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config, database
from backend.app.tasks import repository as repo


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point the DB at a temp file for each test (isolation)."""
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    yield


def test_create_and_queue():
    t = repo.create_task("Find biomedical internships", "medtech focus")
    assert t["status"] == "queued"
    assert t["title"].startswith("Find")


def test_needs_approval_starts_pending():
    t = repo.create_task("Submit application", needs_approval=True)
    assert t["status"] == "pending_approval"


def test_legal_transition_and_event_log():
    t = repo.create_task("x")
    repo.transition(t["id"], "running")
    done = repo.transition(t["id"], "completed", "all good")
    assert done["status"] == "completed"
    assert done["completed_at"] is not None
    kinds = [e["type"] for e in repo.events(t["id"])]
    assert "created" in kinds and "status:running" in kinds and "status:completed" in kinds


def test_illegal_transition_blocked():
    t = repo.create_task("x")                     # queued
    repo.transition(t["id"], "running")
    repo.transition(t["id"], "completed")
    with pytest.raises(repo.TransitionError):     # terminal -> anything is illegal
        repo.transition(t["id"], "running")


def test_illegal_skip_blocked():
    t = repo.create_task("x", needs_approval=True)   # pending_approval
    with pytest.raises(repo.TransitionError):        # can't jump straight to running
        repo.transition(t["id"], "running")


def test_checkpoint_roundtrip():
    t = repo.create_task("x")
    repo.save_checkpoint(t["id"], {"step": 2, "found": 7})
    import json
    saved = json.loads(repo.get_task(t["id"])["checkpoint"])
    assert saved == {"step": 2, "found": 7}


def test_approval_gate_flow():
    t = repo.create_task("Send email", needs_approval=True)
    ap = repo.request_approval(t["id"], "send_email", "to professor")
    assert ap["status"] == "pending"
    resolved = repo.resolve_approval(ap["id"], approved=True)
    assert resolved["status"] == "approved"
    assert len(repo.pending_approvals()) == 0


def test_requeue_interrupted_recovers():
    from backend.app.tasks.worker import requeue_interrupted
    t = repo.create_task("long job")
    repo.transition(t["id"], "running")          # simulate mid-flight
    n = requeue_interrupted()                     # simulate restart recovery
    assert n == 1
    assert repo.get_task(t["id"])["status"] == "queued"   # recovered, not lost


def test_worker_runs_a_task_with_fake_model(monkeypatch):
    monkeypatch.setattr(config, "MODEL_BACKEND", "fake")
    from backend.app.tasks.worker import Worker
    t = repo.create_task("plan my week")
    w = Worker()
    w.start()
    try:
        # Wait for the worker to pick it up and finish (fake model is instant).
        deadline = time.time() + 5
        while time.time() < deadline:
            if repo.get_task(t["id"])["status"] == "completed":
                break
            time.sleep(0.1)
    finally:
        w.stop()
    task = repo.get_task(t["id"])
    assert task["status"] == "completed", task
    assert task["result"]              # the fake model produced a result


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python", "-m", "pytest", __file__, "-v"]))
