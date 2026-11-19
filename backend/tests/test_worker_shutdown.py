"""Regression test: the worker must stop promptly even if a handler is slow,
so Ctrl+C never hangs on 'waiting for background tasks'."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config, database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    yield


def test_stop_is_bounded_even_with_slow_handler(monkeypatch):
    """A handler that sleeps a long time must not make stop() hang forever —
    stop() joins with a timeout and returns bounded."""
    from backend.app.tasks import repository as repo
    from backend.app.tasks import worker as worker_mod
    from backend.app.tasks.worker import Worker, register_handler

    # Register a slow handler (simulates a stuck model call).
    def slow_handler(task, checkpoint):
        time.sleep(30)        # would block shutdown if stop() didn't bound the wait
        return "done"
    register_handler("slow", slow_handler)

    # Force governor to always-OK so the task actually runs. (The worker imports
    # Governor lazily from resources.governor, so patch it there.)
    import backend.app.resources.governor as gov_mod
    from backend.app.resources.governor import Decision
    monkeypatch.setattr(gov_mod.Governor, "evaluate",
                        lambda self, state=None: Decision(True, "ok"))

    repo.create_task("slow one", skill="slow")
    w = Worker()
    w.start()
    time.sleep(0.5)                 # let it pick up the task and enter the sleep

    t0 = time.time()
    w.stop(join_timeout=2.0)        # must return within ~2s, not 30s
    elapsed = time.time() - t0
    assert elapsed < 4.0, f"stop() took {elapsed:.1f}s — it hung on the slow handler"
    print(f"  stop() bounded at {elapsed:.1f}s despite a 30s handler: OK")


def test_idle_worker_stops_fast():
    from backend.app.tasks.worker import Worker
    w = Worker()
    w.start()
    time.sleep(0.3)
    t0 = time.time()
    w.stop()
    assert time.time() - t0 < 2.0
    print("  idle worker stops fast: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
