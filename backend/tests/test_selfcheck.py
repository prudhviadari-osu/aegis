"""Milestone 4 tests: self-check critique parsing, the pass/revise decision,
and the governor cost-gate. Uses the fake backend (critique-aware)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models import FakeBackend
from backend.app.models.selfcheck import (
    critique, answer_with_selfcheck, build_critique_prompt, PASS_THRESHOLD,
)
from backend.app.resources.governor import Decision


def test_critique_prompt_contains_criteria():
    p = build_critique_prompt("Why this company?", "Because I like it.")
    assert "KEYWORD/SEMANTIC COVERAGE" in p
    assert "SKILL MATCH" in p
    assert "Why this company?" in p and "Because I like it." in p
    print("  critique prompt includes the user's criteria: OK")


def test_critique_flags_shallow_answer():
    fb = FakeBackend()
    # Short answer -> fake grader returns needs_revision=true.
    review = critique(fb, "Why this role?", "I want it.")
    assert review["needs_revision"] is True
    assert review["score"] < PASS_THRESHOLD
    print(f"  shallow answer flagged for revision (score {review['score']}): OK")


def test_critique_passes_rich_answer():
    fb = FakeBackend()
    rich = ("I built a calibrated XGBoost donor-risk classifier at >95.5% precision "
            "for kidney assessment, matching this role's clinical-ML and imaging needs.")
    review = critique(fb, "Why this role?", rich)
    assert review["needs_revision"] is False
    assert review["score"] >= PASS_THRESHOLD
    print(f"  rich answer passes (score {review['score']}): OK")


def test_selfcheck_revises_shallow():
    fb = FakeBackend()
    result = answer_with_selfcheck(fb, "Why this role?", "I want it.")
    assert result["revised"] is True
    assert result["final"]               # produced an improved answer
    print("  self-check revises a shallow draft once: OK")


def test_selfcheck_keeps_good_draft():
    fb = FakeBackend()
    rich = ("I built a calibrated XGBoost donor-risk classifier at >95.5% precision, "
            "directly matching this clinical-ML role's imaging and data needs.")
    result = answer_with_selfcheck(fb, "Why this role?", rich)
    assert result["revised"] is False
    assert result["final"] == rich       # unchanged — already good enough
    print("  self-check leaves a good draft alone: OK")


def test_selfcheck_skips_when_device_unsafe():
    """If the governor says conditions are unsafe, self-check must NOT spend the
    extra passes — it returns the draft unchanged (hardware protection wins)."""
    fb = FakeBackend()

    class BlockingGov:
        def evaluate(self, state=None):
            return Decision(False, "test: hot, defer")

    result = answer_with_selfcheck(fb, "Why this role?", "I want it.",
                                   governor=BlockingGov())
    assert result["revised"] is False
    assert result["final"] == "I want it."       # untouched
    assert "skipped" in result["note"].lower()
    print("  self-check skips extra passes when device unsafe: OK")


if __name__ == "__main__":
    test_critique_prompt_contains_criteria()
    test_critique_flags_shallow_answer()
    test_critique_passes_rich_answer()
    test_selfcheck_revises_shallow()
    test_selfcheck_keeps_good_draft()
    test_selfcheck_skips_when_device_unsafe()
    print("\nAll Milestone 4 self-check tests passed.")
