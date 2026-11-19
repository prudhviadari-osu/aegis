"""Milestone 5 tests: skill registry + job_finder skill wiring.

jobify's gather() hits the network, so we mock it: a fake 'finder' package is
injected on sys.path, proving the skill imports jobify, runs its handler, and
formats results — without any live sources."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.skills import registry
from backend.app.skills.registry import Skill, OBSERVE, register_skill, all_skills
from backend.app.tasks import worker


def test_register_skill_wires_worker():
    called = {}
    def h(task, cp):
        called["ran"] = True
        return "ok"
    register_skill(Skill("dummy", "a test skill", OBSERVE, h))
    assert any(s.name == "dummy" for s in all_skills())
    # The worker should now have a handler under that skill name.
    assert "dummy" in worker._handlers
    result = worker._handlers["dummy"]({"title": "x", "description": ""}, lambda cp: None)
    assert result == "ok" and called["ran"]
    print("  register_skill wires a worker handler: OK")


@pytest.fixture
def fake_jobify(monkeypatch, tmp_path):
    """Inject a fake 'finder' package + temp DB so the job_finder handler runs
    offline. The handler now stores+analyzes jobs, so it needs the DB and model."""
    from backend.app import config, database
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    monkeypatch.setattr(config, "MODEL_BACKEND", "fake")
    database.init_db(db)

    finder_pkg = types.ModuleType("finder")
    run_mod = types.ModuleType("finder.run")
    config_mod = types.ModuleType("finder.config")
    config_mod.KEYWORDS = ["biomedical", "clinical"]

    class FakeJob:
        _n = 0
        def __init__(self, title, company, location, source="workday", status="new"):
            self.title, self.company, self.location = title, company, location
            self.source, self.status = source, status
            self.description = "biomedical clinical research"
            FakeJob._n += 1
            self.job_key = f"workday:{FakeJob._n}"

    def fake_gather(keywords):
        return [
            FakeJob("Clinical Research Assistant", "HospitalX", "Columbus, OH"),
            FakeJob("ML Engineer", "FintechCo", "NYC", status="location_filtered"),
        ]

    run_mod.gather = fake_gather
    finder_pkg.run = run_mod
    finder_pkg.config = config_mod
    monkeypatch.setitem(sys.modules, "finder", finder_pkg)
    monkeypatch.setitem(sys.modules, "finder.run", run_mod)
    monkeypatch.setitem(sys.modules, "finder.config", config_mod)
    yield


def test_job_finder_handler_runs(fake_jobify):
    from backend.app.skills import job_finder
    from backend.app.jobs import all_jobs
    checkpoints = []
    result = job_finder._handler(
        {"title": "find jobs", "description": "biomedical, imaging"},
        lambda cp: checkpoints.append(cp),
    )
    # Only the 'new'-status job is kept + stored (the filtered one is dropped).
    stored = all_jobs()
    assert len(stored) == 1
    assert stored[0]["company"] == "HospitalX"
    assert stored[0]["scored"] == 1              # analyzed by the fake model
    assert "analyzed 1" in result
    steps = [c.get("step") for c in checkpoints]
    assert "searching" in steps and "gathered" in steps and "scoring" in steps
    print("  job_finder stores + analyzes kept jobs: OK")


def test_job_finder_empty(fake_jobify, monkeypatch):
    import finder.run as run_mod
    monkeypatch.setattr(run_mod, "gather", lambda kw: [])
    from backend.app.skills import job_finder
    result = job_finder._handler({"title": "x", "description": ""}, lambda cp: None)
    assert "none passed" in result or "Searched 0" in result
    print("  job_finder handles no-results gracefully: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
