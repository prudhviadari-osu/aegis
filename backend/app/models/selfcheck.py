"""Self-checking optimization (Milestone 4).

The model answers, then CRITIQUES its own answer against fixed criteria, and if
it falls short, REVISES once using that critique. For a small 8B model this
"measure twice, cut once" loop is one of the biggest quality wins available.

The criteria below come directly from the user's own list (application/job-fit
focus): keyword/semantic coverage, skill match, field-appropriate depth,
parameter fit, and uniqueness.

Cost awareness: each extra pass is more compute, so the loop (a) is capped at a
single revision and (b) asks the M3.5 governor whether it's safe to spend the
extra passes — if the Mac is hot or on low battery, it returns the first answer
rather than burning more cycles.
"""
from __future__ import annotations

import json

from .. import config
from .base import ModelAdapter, ModelError, extract_json
from .prompting import inference_lock, temperature_for

# The user's self-check criteria, phrased as grading instructions to the model.
CRITERIA = """\
1. KEYWORD/SEMANTIC COVERAGE — does the answer address the key terms and themes
   from the job description and the company's mission (not just surface words)?
2. SKILL MATCH — does it clearly connect the candidate's skills to what the role
   asks for, and shape existing experience around those required skills?
3. FIELD-APPROPRIATE DEPTH — is the detail right for the field? Medical answers
   should cite clinical specifics; engineering answers should name tools and how
   they're used. Shallow, generic answers fail this.
4. PARAMETER FIT — does it account for the practical fit: schedule, role type,
   location, eligibility vs. the candidate's constraints?
5. UNIQUENESS / ABOVE-AND-BEYOND — does it make the application stand out rather
   than read like a template?"""

# Score (0-10) at or above which an answer is "good enough" and is NOT revised.
# 7 balances quality against burning extra compute on diminishing returns.
PASS_THRESHOLD = 7


def build_critique_prompt(question: str, answer: str) -> str:
    return (
        "You are a strict reviewer grading a candidate's ANSWER to a QUESTION.\n"
        f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\n"
        f"Grade the answer against these criteria:\n{CRITERIA}\n\n"
        'Return ONLY JSON: {"score": <0-10 int>, "needs_revision": <bool>, '
        '"problems": ["short, specific issue", ...]}. '
        "Set needs_revision true if the answer clearly misses one or more criteria."
    )


def build_revision_prompt(question: str, answer: str, problems: list[str]) -> str:
    issues = "\n".join(f"- {p}" for p in problems) or "- improve overall quality"
    return (
        "Improve the ANSWER below so it fixes these specific problems. Keep what "
        "was good; do not invent experience the candidate doesn't have.\n\n"
        f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nPROBLEMS TO FIX:\n{issues}\n\n"
        "Return only the improved answer text."
    )


def critique(adapter: ModelAdapter, question: str, answer: str) -> dict:
    """Ask the model to grade its own answer. Returns
    {score:int, needs_revision:bool, problems:[...]} — defensively sanitized."""
    prompt = build_critique_prompt(question, answer)
    with inference_lock():
        raw = adapter.chat(
            [{"role": "system", "content": "You grade answers and return only JSON."},
             {"role": "user", "content": prompt}],
            temperature=temperature_for("analytical"),
        )
    try:
        data = extract_json(raw)
    except ModelError:
        # If the critique itself is unparseable, treat as "no revision needed"
        # rather than looping — fail safe toward returning the original answer.
        return {"score": PASS_THRESHOLD, "needs_revision": False, "problems": []}
    if not isinstance(data, dict):
        return {"score": PASS_THRESHOLD, "needs_revision": False, "problems": []}
    try:
        score = int(data.get("score", PASS_THRESHOLD))
    except (TypeError, ValueError):
        score = PASS_THRESHOLD
    score = max(0, min(10, score))
    problems = data.get("problems") or []
    if not isinstance(problems, list):
        problems = [str(problems)]
    needs = bool(data.get("needs_revision", score < PASS_THRESHOLD))
    return {"score": score, "needs_revision": needs, "problems": [str(p) for p in problems]}


def answer_with_selfcheck(adapter: ModelAdapter, question: str, draft: str,
                          governor=None) -> dict:
    """Run the self-check loop on a draft answer.

    Returns {final, revised (bool), score, problems}. Caps revision at ONE pass.
    If a governor is given and says it's not safe to spend extra compute, returns
    the draft unchanged (protects the user's hardware over answer polish).
    """
    # Cost gate: don't spend the extra critique/revision passes if the Mac is
    # under thermal/battery pressure — return the first answer instead.
    if governor is not None:
        decision = governor.evaluate()
        if not decision.proceed:
            return {"final": draft, "revised": False, "score": None,
                    "problems": [], "note": f"self-check skipped — {decision.reason}"}

    review = critique(adapter, question, draft)
    if not review["needs_revision"] and review["score"] >= PASS_THRESHOLD:
        return {"final": draft, "revised": False, "score": review["score"],
                "problems": review["problems"], "note": "passed on first pass"}

    # One revision pass using the critique's specific problems.
    with inference_lock():
        improved = adapter.chat(
            [{"role": "system", "content": config.SYSTEM_PROMPT},
             {"role": "user", "content":
                 build_revision_prompt(question, draft, review["problems"])}],
            temperature=temperature_for("creative"),
        )
    return {"final": improved.strip() or draft, "revised": True,
            "score": review["score"], "problems": review["problems"],
            "note": "revised once from self-critique"}
