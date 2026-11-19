"""M5.5 step 1 tests: job storage, scoring fields, and the tiered-reveal logic."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config, database
from backend.app.jobs import (
    upsert_job, get_job, set_score, set_review_status,
    current_tier, visible_jobs, assign_tiers,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    yield


def _job(key, title="Intern", company="MedCo"):
    return {"job_key": key, "source": "workday", "company": company,
            "title": title, "location": "Columbus, OH", "url": "http://x", "description": "d"}


def test_upsert_and_dedupe():
    upsert_job(_job("k1"))
    upsert_job(_job("k1", title="Intern (updated)"))   # same key -> update, not dupe
    from backend.app.jobs import all_jobs
    jobs = all_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Intern (updated)"


def test_set_score_stores_structured_fields():
    j = upsert_job(_job("k1"))
    scored = set_score(j["id"], ring=2, fit_score=0.8, path_score=0.9,
                       reasoning="strong medical-AI fit",
                       have=["XGBoost", "MRI ML"], missing=["FDA exposure"],
                       steps=["mention BraTS work"], draft="Dear team, ...")
    assert scored["ring"] == 2
    assert scored["rank"] == round(0.8 * 0.9, 4)
    assert scored["have"] == ["XGBoost", "MRI ML"]       # JSON parsed back to list
    assert scored["missing"] == ["FDA exposure"]
    assert scored["draft"].startswith("Dear team")
    assert scored["scored"] == 1


def _scored(key, ring, fit, path):
    j = upsert_job(_job(key))
    return set_score(j["id"], ring=ring, fit_score=fit, path_score=path,
                     reasoning="r", have=[], missing=[], steps=[], draft="")


def test_tiered_reveal_hides_later_tiers():
    # 12 scored jobs -> tier size 5 -> tiers 1,2,3.
    for i in range(12):
        _scored(f"k{i}", ring=2, fit=0.9, path=0.9)
    assign_tiers()

    # Initially: current tier = 1, only tier-1 jobs visible (5 of them).
    assert current_tier() == 1
    vis = visible_jobs()
    assert all(j["tier"] == 1 for j in vis)
    assert len(vis) == 5

    # Review 4 of tier 1 -> still tier 1 (one left unreviewed).
    tier1 = [j for j in vis]
    for j in tier1[:4]:
        set_review_status(j["id"], "applied")
    assert current_tier() == 1

    # Review the last tier-1 job -> tier 2 unlocks.
    set_review_status(tier1[4]["id"], "skipped")
    assert current_tier() == 2
    vis2 = visible_jobs()
    tiers_shown = {j["tier"] for j in vis2}
    assert tiers_shown == {1, 2}            # reviewed tier 1 stays visible + tier 2 revealed
    assert 3 not in tiers_shown             # tier 3 still hidden
    print("  tiered reveal: tier 2 unlocks only after tier 1 fully reviewed: OK")


def test_rings_1_2_favored_into_early_tiers():
    # A ring-3 high-rank job should still tier AFTER ring-1/2 jobs.
    _scored("med", ring=1, fit=0.6, path=0.9)
    for i in range(5):
        _scored(f"tech{i}", ring=3, fit=0.95, path=0.95)
    assign_tiers()
    med = next(j for j in visible_jobs() if j["job_key"] == "med")
    assert med["tier"] == 1                 # medicine job is in the first tier
    print("  rings 1-2 favored into early tiers: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
