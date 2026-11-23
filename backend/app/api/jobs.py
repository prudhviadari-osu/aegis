"""Jobs API (M5.5): powers the /jobs review page.

- GET  /api/jobs           -> jobs visible now (tiered reveal) + the current tier
- GET  /api/jobs/{id}      -> one job's full detail (have/missing/steps/draft)
- POST /api/jobs/{id}/review {status: applied|skipped} -> mark it, may unlock next tier
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..jobs import visible_jobs, get_job, set_review_status, current_tier, all_jobs

router = APIRouter()


@router.get("/api/jobs")
def list_jobs(show_all: bool = False) -> dict:
    jobs = all_jobs() if show_all else visible_jobs()
    # Trim heavy fields for the table view; the detail endpoint returns everything.
    table = [{
        "id": j["id"], "company": j["company"], "title": j["title"],
        "location": j["location"], "ring": j["ring"], "fit_score": j["fit_score"],
        "path_score": j["path_score"], "rank": j["rank"], "tier": j["tier"],
        "review_status": j["review_status"], "scored": j["scored"],
    } for j in jobs]
    any_unscored = any(not j["scored"] for j in jobs)
    return {"current_tier": current_tier(), "count": len(table),
            "no_model": any_unscored, "jobs": table}


@router.get("/api/jobs/{job_id}")
def job_detail(job_id: int) -> dict:
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


class SearchIn(BaseModel):
    keywords: str = ""   # comma-separated; blank = jobify defaults


@router.post("/api/jobs/search")
def run_search(body: SearchIn) -> dict:
    """Kick off a job search as a task (runs the job_finder skill in the worker).
    Returns immediately with the task id; the page polls /api/jobs for results."""
    from ..tasks import repository as repo
    task = repo.create_task(
        title="Job search", description=body.keywords.strip(), skill="job_finder")
    return {"ok": True, "task_id": task["id"],
            "message": "Search started — results will appear as they're found and analyzed."}


class ReviewIn(BaseModel):
    status: str   # "applied" | "skipped"


@router.post("/api/jobs/{job_id}/review")
def review(job_id: int, body: ReviewIn) -> dict:
    try:
        updated = set_review_status(job_id, body.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not updated:
        raise HTTPException(404, "job not found")
    return {"job": updated, "current_tier": current_tier()}
