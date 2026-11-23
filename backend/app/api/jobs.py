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


@router.get("/api/jobs/search-status")
def search_status() -> dict:
    """Progress of the most recent public search, so the page can show a live
    indicator instead of looking frozen. (Declared before /{job_id} so the literal
    path isn't captured by the int path param.)"""
    from ..tasks import repository as repo
    tasks = [t for t in repo.list_tasks() if t["skill"] == "job_finder"]
    if not tasks:
        return {"active": False, "status": "none", "detail": "", "result": ""}
    latest = tasks[0]
    detail = ""
    for ev in reversed(repo.events(latest["id"])):
        if ev["type"] == "checkpoint":
            detail = ev["details"]
            break
    active = latest["status"] in ("queued", "running", "paused")
    return {"active": active, "status": latest["status"],
            "detail": detail, "result": latest.get("result") or ""}


@router.get("/api/jobs/search-local")
def search_local(q: str = "") -> dict:
    """LOCAL search: filter jobs already in the DB by keyword. Instant, no network,
    no model. Searches title/company/location/description."""
    from ..jobs import all_jobs
    terms = [t.strip().lower() for t in q.replace(",", " ").split() if t.strip()]
    rows = all_jobs()
    if terms:
        def hit(j):
            hay = f"{j.get('title','')} {j.get('company','')} {j.get('location','')} {j.get('description','')}".lower()
            return any(t in hay for t in terms)
        rows = [j for j in rows if hit(j)]
    table = [{
        "id": j["id"], "company": j["company"], "title": j["title"],
        "location": j["location"], "ring": j["ring"], "fit_score": j["fit_score"],
        "path_score": j["path_score"], "rank": j["rank"], "tier": j["tier"],
        "review_status": j["review_status"], "scored": j["scored"],
    } for j in rows]
    return {"count": len(table), "query": q, "jobs": table,
            "no_model": any(not j["scored"] for j in rows)}


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
    """PUBLIC search: kick off a background job_finder task that fetches NEW jobs
    from the web sources (model-expands the keywords first if a model is running),
    analyzes them, and stores them. Returns immediately; poll /api/jobs/search-status."""
    from ..tasks import repository as repo
    # Don't stack duplicate searches — if one's already running, say so.
    active = [t for t in repo.list_tasks() if t["skill"] == "job_finder"
              and t["status"] in ("queued", "running", "paused")]
    if active:
        return {"ok": True, "task_id": active[0]["id"], "already_running": True,
                "message": "A job search is already running — results will appear as they finish."}
    task = repo.create_task(
        title="Job search", description=body.keywords.strip(), skill="job_finder")
    return {"ok": True, "task_id": task["id"], "already_running": False,
            "message": "Search started. Fetching + analyzing jobs — this can take a few "
                       "minutes. The table updates live as they come in."}


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
