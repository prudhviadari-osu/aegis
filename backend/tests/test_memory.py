"""Milestone 6 tests: persistent memory — store, dedupe, search, recall,
context injection, and that chat includes memory. Temp DB, fake model."""
import sys
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


def test_remember_and_list():
    from backend.app.memory import remember, all_memories
    remember("Prudhvi is pre-med at OSU", category="profile")
    remember("Targeting summer 2027 internships", category="profile")
    mems = all_memories("profile")
    assert len(mems) == 2
    assert any("pre-med" in m["content"] for m in mems)


def test_dedupe_exact_repeat():
    from backend.app.memory import remember, all_memories
    remember("Likes medtech roles", category="profile")
    remember("Likes medtech roles", category="profile")   # exact repeat
    assert len(all_memories("profile")) == 1               # not duplicated


def test_search_ranks_by_relevance():
    from backend.app.memory import remember, search_memories
    remember("Experienced with XGBoost and PyTorch for medical imaging", category="reference")
    remember("Enjoys hiking on weekends", category="reference")
    hits = search_memories("medical imaging model")
    assert hits
    assert "XGBoost" in hits[0]["content"]      # most relevant first
    assert "hiking" not in hits[0]["content"]


def test_invalid_category_falls_back():
    from backend.app.memory import remember
    m = remember("something", category="nonsense")
    assert m["category"] == "reference"          # safe fallback


def test_forget():
    from backend.app.memory import remember, forget, all_memories
    m = remember("temporary note")
    assert forget(m["id"]) is True
    assert all_memories() == []
    assert forget(99999) is False                # missing id


def test_build_context_includes_profile_and_relevant():
    from backend.app.memory import remember, build_memory_context
    remember("Prudhvi is a US permanent resident", category="profile")
    remember("Prefers clinical roles for hours", category="profile")
    remember("Won the HackOHI/O hackathon in 2026", category="reference")
    # Keyword search matches on shared words, so the query must share one
    # ("hackathon"). This reflects how the current (non-semantic) recall works.
    ctx = build_memory_context(query="tell me about my hackathon wins")
    assert "permanent resident" in ctx            # profile always included
    assert "HackOHI/O" in ctx                      # query-relevant added


def test_chat_injects_memory(monkeypatch):
    """The chat endpoint must fold remembered profile facts into the system prompt
    so the model 'knows' the user. We capture what the fake backend receives."""
    monkeypatch.setattr(config, "MODEL_BACKEND", "fake")
    from backend.app.memory import remember
    remember("Prudhvi is pre-med and wants to be a doctor", category="profile")

    captured = {}
    from backend.app.models import fake_backend
    orig = fake_backend.FakeBackend.chat
    def spy(self, messages, temperature=0.7):
        captured["system"] = messages[0]["content"]
        return orig(self, messages, temperature)
    monkeypatch.setattr(fake_backend.FakeBackend, "chat", spy)

    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as client:
        r = client.post("/api/chat", json={"message": "what should I focus on?", "history": []})
        assert r.status_code == 200
    assert "pre-med" in captured["system"]        # memory reached the model
    print("  chat injects remembered profile into the system prompt: OK")


if __name__ == "__main__":
    raise SystemExit(__import__("subprocess").call(
        ["python", "-m", "pytest", __file__, "-v"]))
