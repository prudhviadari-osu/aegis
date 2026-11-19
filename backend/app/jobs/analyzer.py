"""Job analyzer (M5.5 step 2): the model scores a job against the user's profile
and produces everything the /jobs detail page shows.

One model call per job returns structured JSON:
  ring, fit_score, path_score, reasoning, have[], missing[], steps[], draft

- ring/fit/path reuse the priority-ring model (medicine first).
- have   = strengths the user already has that match this role
- missing = gaps the user is missing for this role
- steps  = concrete things to cover gaps / strengthen the application
- draft  = a suggested application paragraph for the user to REVIEW (never auto-sent)

Batch scoring is governor-gated and one-at-a-time (thermal safety): scoring ~30
jobs is several minutes of gentle 8B work, so it runs in the background worker and
the /jobs page shows jobs as they finish.
"""
from __future__ import annotations

from ..models.base import ModelAdapter, ModelError, extract_json
from ..models.prompting import inference_lock, temperature_for

SYSTEM = """You are a career advisor for a pre-med Computer Science student whose
PATH is medicine (he wants to be a doctor); technical roles are welcome only when
they serve that path. Analyze how well he fits a job, grounded ONLY in his profile
and the job text — never invent experience he lacks.

Assign a RING: 1=core medicine/clinical, 2=medical AI/medtech/biomedical (equal top
priority to 1), 3=adjacent technical with no medical angle (allowed, lower), 4=off-path.

Return ONLY JSON with these keys:
  ring (int 1-4),
  fit_score (0-1: can he do the job),
  path_score (0-1: does it serve his pre-med path),
  reasoning (1-2 sentences, cite specific profile facts),
  have (list of short strings: strengths he HAS that match this role),
  missing (list of short strings: gaps he's MISSING for this role),
  steps (list of short strings: concrete actions to cover gaps or strengthen the app),
  draft (a short 'why I'm a fit' paragraph he can review and edit — honest, no fabrication)."""


def _profile_brief(profile: dict) -> str:
    basics = profile.get("basics", {})
    exp = "; ".join(f"{e.get('title','')} @ {e.get('company','')}"
                    for e in profile.get("experience", []))
    skills = profile.get("skills", {})
    flat = []
    if isinstance(skills, dict):
        for v in skills.values():
            flat += v if isinstance(v, list) else [v]
    elif isinstance(skills, list):
        flat = skills
    edu = "; ".join(f"{e.get('degree','')} {e.get('field','')}"
                    for e in profile.get("education", []))
    return (f"Pre-med CS student. Education: {edu}. Experience: {exp}. "
            f"Skills: {', '.join(flat)}. Summary: {profile.get('summary','')}")


def analyze_job(adapter: ModelAdapter, job: dict, profile_brief: str) -> dict:
    user = (
        f"CANDIDATE:\n{profile_brief}\n\n"
        f"JOB:\nTitle: {job.get('title','')}\nCompany: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Description: {(job.get('description') or '')[:1500]}\n\n"
        "Analyze per instructions. JSON only."
    )
    with inference_lock():
        raw = adapter.chat(
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            temperature=temperature_for("analytical"))
    try:
        data = extract_json(raw)
    except ModelError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return _sanitize(data)


def _sanitize(d: dict) -> dict:
    def num(x, default=0.5):
        try:
            return max(0.0, min(1.0, float(x)))
        except (TypeError, ValueError):
            return default
    def strlist(x):
        if isinstance(x, list):
            return [str(i) for i in x][:8]
        if x:
            return [str(x)]
        return []
    try:
        ring = int(d.get("ring", 3))
    except (TypeError, ValueError):
        ring = 3
    ring = ring if ring in (1, 2, 3, 4) else 3
    return {
        "ring": ring,
        "fit_score": num(d.get("fit_score")),
        "path_score": num(d.get("path_score")),
        "reasoning": str(d.get("reasoning", "")),
        "have": strlist(d.get("have")),
        "missing": strlist(d.get("missing")),
        "steps": strlist(d.get("steps")),
        "draft": str(d.get("draft", "")),
    }
