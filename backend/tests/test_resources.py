"""Milestone 3.5 tests: the battery/thermal/memory governor decision logic, and
that the worker defers heavy work when conditions are unsafe. Resource state is
simulated so tests are deterministic on any machine."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config, database
from backend.app.resources import Governor
from backend.app.resources.monitor import ResourceState, read_state


def _gov():
    return Governor(config)


def test_proceeds_when_all_good():
    s = ResourceState(battery_percent=70, on_ac_power=True, thermal_pressure="nominal",
                      memory_percent=50)
    d = _gov().evaluate(s)
    assert d.proceed is True


def test_defers_when_hot():
    # macOS throttling for heat -> strongest protective rule.
    s = ResourceState(battery_percent=70, on_ac_power=True, thermal_pressure="heavy",
                      cpu_speed_limited=True, memory_percent=50)
    d = _gov().evaluate(s)
    assert d.proceed is False
    assert "cool" in d.reason.lower() or "warm" in d.reason.lower()


def test_defers_on_low_battery():
    s = ResourceState(battery_percent=25, on_ac_power=False, thermal_pressure="nominal",
                      memory_percent=50)
    d = _gov().evaluate(s)
    assert d.proceed is False
    assert "battery" in d.reason.lower()


def test_proceeds_on_battery_if_high_enough():
    s = ResourceState(battery_percent=80, on_ac_power=False, thermal_pressure="nominal",
                      memory_percent=50)
    assert _gov().evaluate(s).proceed is True


def test_defers_when_plugged_full_and_warm():
    # Near-full + plugged + warm = classic battery-stress state -> defer.
    s = ResourceState(battery_percent=100, on_ac_power=True, thermal_pressure="moderate",
                      memory_percent=50)
    d = _gov().evaluate(s)
    assert d.proceed is False


def test_full_but_cool_is_fine():
    # Full + plugged but genuinely cool -> allowed (only block when also warm).
    s = ResourceState(battery_percent=100, on_ac_power=True, thermal_pressure="nominal",
                      memory_percent=50)
    assert _gov().evaluate(s).proceed is True


def test_defers_on_memory_pressure():
    s = ResourceState(battery_percent=70, on_ac_power=True, thermal_pressure="nominal",
                      memory_percent=95)
    d = _gov().evaluate(s)
    assert d.proceed is False
    assert "memory" in d.reason.lower()


def test_read_state_never_crashes():
    # On any platform (incl. this Linux sandbox) it must return a state, not raise.
    s = read_state()
    assert isinstance(s, ResourceState)


def test_worker_defers_when_governor_blocks(tmp_path, monkeypatch):
    """With the governor forced to 'unsafe', a queued task must NOT complete —
    the worker holds it off instead of running (the core safety behavior)."""
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "GOVERNOR_BACKOFF_SECONDS", 0.2)
    database.init_db(db)

    from backend.app.tasks import repository as repo
    from backend.app.tasks.worker import Worker
    import backend.app.resources.governor as gov_mod

    # Force every governor decision to 'defer'.
    from backend.app.resources.governor import Decision
    monkeypatch.setattr(gov_mod.Governor, "evaluate",
                        lambda self, state=None: Decision(False, "test: forced unsafe"))

    t = repo.create_task("heavy job")
    w = Worker()
    w.start()
    try:
        time.sleep(1.0)   # give the worker several cycles
        status = repo.get_task(t["id"])["status"]
        # It must be bouncing between paused/queued, never completed.
        assert status in ("queued", "paused"), status
        # And an event should record the governor holding off.
        details = " ".join(e["details"] for e in repo.events(t["id"]))
        assert "governor" in details.lower()
    finally:
        w.stop()
    print("  worker defers under unsafe conditions: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
