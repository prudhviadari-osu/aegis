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
    """Run a job search and return a short human-readable summary. Full results
    go to jobify's own sink (CSV/Sheet); here we surface a digest for the task."""
    gather, jf_config = _import_jobify()

    # Keywords: use the task description if given, else jobify's configured defaults.
    desc = (task.get("description") or "").strip()
    keywords = [k.strip() for k in desc.split(",") if k.strip()] or jf_config.KEYWORDS

    checkpoint({"step": "searching", "keywords": keywords})
    jobs = gather(keywords)

    checkpoint({"step": "gathered", "count": len(jobs)})
    if not jobs:
        return ("No jobs found. Check that a source is configured (Workday seed "
                "companies, or Arbeitnow is on) in the jobfinder config.")

    # Rank preview: jobs jobify didn't filter out, newest-ish first.
    kept = [j for j in jobs if getattr(j, "status", "new") != "location_filtered"]
    lines = [f"Found {len(jobs)} jobs ({len(kept)} within your location rules). Top:"]
    for j in kept[:10]:
        lines.append(f"  • {j.title} @ {j.company} — {j.location or 'n/a'}  [{j.source}]")
    lines.append("\nFull, deduped results were written to jobify's sink (CSV/Sheet).")
    return "\n".join(lines)


def register() -> None:
    register_skill(Skill(
        name=SKILL_NAME,
        description="Find medtech jobs (incl. Workday) from free public sources and "
                    "rank them against your profile. Read-only; never applies.",
        permission=OBSERVE,
        handler=_handler,
    ))
