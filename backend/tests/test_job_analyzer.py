"""M5.5 step 2 tests: the job analyzer produces all /jobs detail fields,
stored correctly, using the fake backend."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config, database
from backend.app.models import FakeBackend
from backend.app.jobs.analyzer import analyze_job, _profile_brief
from backend.app.jobs import upsert_job, set_score, get_job

PROFILE = {
    "basics": {}, "summary": "pre-med CS student, ML + biomedical research",
    "experience": [{"title": "Research Assistant", "company": "IBRC"}],
    "education": [{"degree": "BS", "field": "Computer Science"}],
    "skills": {"ml": ["XGBoost", "PyTorch"]},
}


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", db)
    database.init_db(db)
    yield


def test_analyzer_returns_all_fields():
    fb = FakeBackend()
    job = {"title": "Biomedical Data Scientist", "company": "MedAICo",
           "location": "Columbus, OH", "description": "medical imaging ML, clinical data"}
    a = analyze_job(fb, job, _profile_brief(PROFILE))
    assert a["ring"] == 2                      # medical -> ring 2
    assert 0 <= a["fit_score"] <= 1 and 0 <= a["path_score"] <= 1
    assert a["have"] and a["missing"] and a["steps"]      # all lists populated
    assert a["draft"]                           # a suggested submission
    assert a["reasoning"]
    print("  analyzer returns ring/scores/have/missing/steps/draft: OK")


def test_adjacent_tech_lower_path():
    fb = FakeBackend()
    job = {"title": "Backend Engineer", "company": "FintechCo",
           "location": "Austin, TX", "description": "build payment APIs in Go"}
    a = analyze_job(fb, job, _profile_brief(PROFILE))
    assert a["ring"] == 3                        # no medical angle
    assert a["path_score"] < a["fit_score"]      # serves the path less than he can do it
    print("  adjacent-tech job gets ring 3 + lower path score: OK")


def test_analysis_persists_to_job():
    fb = FakeBackend()
    j = upsert_job({"job_key": "k1", "title": "Clinical Data Intern",
                    "company": "MedCo", "location": "Columbus, OH",
                    "description": "biomedical clinical data", "source": "workday", "url": "x"})
    a = analyze_job(fb, j, _profile_brief(PROFILE))
    saved = set_score(j["id"], ring=a["ring"], fit_score=a["fit_score"],
                      path_score=a["path_score"], reasoning=a["reasoning"],
                      have=a["have"], missing=a["missing"], steps=a["steps"], draft=a["draft"])
    reloaded = get_job(saved["id"])
    assert reloaded["scored"] == 1
    assert reloaded["have"] == a["have"]         # round-trips through the DB as a list
    assert reloaded["draft"] == a["draft"]
    print("  analysis persists + round-trips through the job table: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
