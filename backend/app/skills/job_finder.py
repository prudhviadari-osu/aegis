"""Job-finder skill (Milestone 5): wraps the standalone `jobify` project.

Design choice: we DON'T copy jobify's code. We import it as an external package
(path from config.JOBIFY_PATH) and call its gather() + scoring. That keeps jobify
independently usable AND makes it an Aegis skill — a thin adapter, not a fork.

Permission level: OBSERVE — it only searches public sources and ranks results.
It never applies or submits anything (that stays a human/EXECUTE action, matching
jobify's own no-auto-submit rule).

A job-finder task's `description` is treated as the search keywords (optional;
falls back to jobify's configured defaults).
"""
from __future__ import annotations

import sys

from .. import config
from .registry import Skill, OBSERVE, register_skill

SKILL_NAME = "job_finder"


def _import_jobify():
    """Put the jobify repo on the import path and import its pieces.
    Raises a clear error if the path is wrong so the registry can report it."""
    path = config.JOBIFY_PATH
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        from finder.run import gather                 # noqa
        from finder import config as jf_config         # noqa
        return gather, jf_config
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import jobify from '{path}'. Set AEGIS_JOBIFY_PATH to the "
            f"jobfinder repo. ({exc})"
        ) from exc


def _handler(task: dict, checkpoint) -> str:
    """Search jobs, store them in Aegis's job table, analyze each with the model
    (have/missing/steps/draft), and assign reveal tiers. Results show on /jobs.

    Only jobs that pass jobify's filters (US + student-level) are stored. Scoring
    is one-at-a-time and governor-gated, so a big batch stays gentle on the Mac.
    """
    from .. import config
    from ..jobs import upsert_job, set_score, assign_tiers
    from ..jobs.analyzer import analyze_job, _profile_brief
    from ..models import get_adapter
    from ..resources import Governor

    gather, jf_config = _import_jobify()

    from .. import config
    from ..models import get_adapter

    desc = (task.get("description") or "").strip()
    keywords = [k.strip() for k in desc.split(",") if k.strip()] or jf_config.KEYWORDS

    # Model-shape the search: if a real model is running, expand the keywords into
    # related medtech terms before fetching (the "interactive search" idea). This
    # is the public-search-uses-the-model step. Falls back to raw keywords.
    adapter = get_adapter(config)
    if adapter.available() and getattr(config, "MODEL_BACKEND", "ollama") != "fake":
        try:
            keywords = _expand_keywords(adapter, keywords)
            checkpoint({"step": "expanded_keywords", "keywords": keywords})
        except Exception:  # noqa: BLE001 - expansion is best-effort; never block the search
            pass

    checkpoint({"step": "searching", "keywords": keywords})
    found = gather(keywords)
    # jobify tags filtered jobs; keep only the ones that passed (status 'new').
    kept = [j for j in found if getattr(j, "status", "new") == "new"]
    checkpoint({"step": "gathered", "found": len(found), "kept": len(kept)})
    if not kept:
        return (f"Searched {len(found)} jobs but none passed your US + student-level "
                "filters. Try broader keywords, or add a job source in jobify config.")

    # Store each kept job in Aegis's job table.
    stored = []
    for j in kept:
        row = upsert_job({
            "job_key": j.job_key, "source": getattr(j, "source", ""),
            "company": getattr(j, "company", ""), "title": getattr(j, "title", ""),
            "location": getattr(j, "location", ""), "url": getattr(j, "url", ""),
            "description": getattr(j, "description", ""),
        })
        stored.append(row)

    # Analyze each with the model — but ONLY if a real model is reachable.
    # No model? The table still fills; jobs stay unscored and flagged "no model
    # used" (we never show fabricated scores). Governor-gated + loads the profile.
    adapter = get_adapter(config)
    backend = getattr(config, "MODEL_BACKEND", "ollama")
    real_model = adapter.available() and backend != "fake"

    analyzed = 0
    if real_model:
        governor = Governor(config)
        brief = _profile_brief(_load_profile(config))
        for row in stored:
            if not governor.evaluate().proceed:
                checkpoint({"step": "paused_by_governor", "analyzed": analyzed})
                break
            a = analyze_job(adapter, row, brief)
            set_score(row["id"], ring=a["ring"], fit_score=a["fit_score"],
                      path_score=a["path_score"], reasoning=a["reasoning"],
                      have=a["have"], missing=a["missing"], steps=a["steps"], draft=a["draft"])
            analyzed += 1
            checkpoint({"step": "scoring", "done": analyzed, "total": len(stored)})
    assign_tiers()

    if not real_model:
        return (f"Found {len(found)} jobs → {len(kept)} passed filters, stored to the "
                "Jobs table. ⚠ No model running, so they're NOT ranked or analyzed — "
                "the table shows the raw matches. Start Ollama (qwen3:8b) and re-run to "
                "get fit ranking, have/missing, and drafts.")
    return (f"Found {len(found)} jobs → {len(kept)} passed filters → analyzed "
            f"{analyzed}. Open the Jobs page to review your ranked matches.")


def _expand_keywords(adapter, keywords: list[str]) -> list[str]:
    """Ask the model to expand seed keywords into related medtech search terms,
    weighted toward medicine + medical-AI (the user's priority). Returns the seeds
    plus the additions, deduped, capped."""
    from ..models.base import extract_json
    from ..models.prompting import inference_lock, temperature_for
    system = ("Expand a pre-med CS student's job-search keywords into related terms, "
              "weighted toward medicine, clinical, and medical-AI/biomedical roles, "
              "with a few general ML/data terms. Return ONLY JSON: "
              '{"keywords": ["term", ...]} with at most 12 short terms.')
    user = f"SEED KEYWORDS: {', '.join(keywords)}\nExpand them. JSON only."
    with inference_lock():
        raw = adapter.chat([{"role": "system", "content": system},
                            {"role": "user", "content": user}],
                           temperature=temperature_for("analytical"))
    data = extract_json(raw)
    extra = data.get("keywords", []) if isinstance(data, dict) else []
    out, seen = [], set()
    for t in list(keywords) + [str(x) for x in extra]:
        k = t.strip().lower()
        if k and k not in seen:
            seen.add(k); out.append(t.strip())
    return out[:15]


def _load_profile(config) -> dict:
    """Reuse Aegis's profile loader so analysis is grounded in the real profile."""
    from ..skills.registry import Skill  # noqa (avoid circular at import time)
    import json, os
    # Aegis profile lives with the finder package (jobify) or the run loader.
    try:
        from ..main import load_profile
        return load_profile()
    except Exception:  # noqa: BLE001
        path = os.path.join(config.JOBIFY_PATH, "finder", "profile.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"basics": {}, "summary": "", "experience": [], "education": [], "skills": {}}


def register() -> None:
    register_skill(Skill(
        name=SKILL_NAME,
        description="Find medtech jobs (incl. Workday) from free public sources and "
                    "rank them against your profile. Read-only; never applies.",
        permission=OBSERVE,
        handler=_handler,
    ))
