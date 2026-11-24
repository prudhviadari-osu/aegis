"""Data access for jobs + the tiered-reveal logic (M5.5).

Tiered reveal (the user's spec): the page shows only the CURRENT tier — the lowest
tier that still has unreviewed ('new') jobs. When every job in that tier is marked
(applied/skipped), the next tier becomes current and reveals. So you work through
the best matches first; the rest appear as you clear them.
"""
from __future__ import annotations

import json

from ..database import connect


def _row(r) -> dict | None:
    if not r:
        return None
    d = dict(r)
    for k in ("have_json", "missing_json", "steps_json"):
        if d.get(k):
            try:
                d[k.replace("_json", "")] = json.loads(d[k])
            except (ValueError, TypeError):
                d[k.replace("_json", "")] = []
        else:
            d[k.replace("_json", "")] = []
    return d


def upsert_job(job: dict) -> dict:
    """Insert a found job (from jobify) or update it if the job_key already exists.
    `job` has at least: job_key, source, company, title, location, url, description."""
    conn = connect()
    try:
        existing = conn.execute("SELECT id FROM job WHERE job_key=?", (job["job_key"],)).fetchone()
        if existing:
            conn.execute(
                "UPDATE job SET source=?, company=?, title=?, location=?, url=?, "
                "description=? WHERE job_key=?",
                (job.get("source"), job.get("company"), job.get("title"),
                 job.get("location"), job.get("url"), job.get("description"),
                 job["job_key"]))
            jid = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO job(job_key, source, company, title, location, url, description) "
                "VALUES (?,?,?,?,?,?,?)",
                (job["job_key"], job.get("source"), job.get("company"), job.get("title"),
                 job.get("location"), job.get("url"), job.get("description")))
            jid = cur.lastrowid
        conn.commit()
        return _row(conn.execute("SELECT * FROM job WHERE id=?", (jid,)).fetchone())
    finally:
        conn.close()


def get_job(job_id: int) -> dict | None:
    conn = connect()
    try:
        return _row(conn.execute("SELECT * FROM job WHERE id=?", (job_id,)).fetchone())
    finally:
        conn.close()


def set_score(job_id: int, *, ring: int, fit_score: float, path_score: float,
              reasoning: str, have: list, missing: list, steps: list, draft: str) -> dict:
    """Store the model's full analysis of a job (step 2 fills these)."""
    rank = round((fit_score or 0) * (path_score or 0), 4)
    conn = connect()
    try:
        conn.execute(
            "UPDATE job SET ring=?, fit_score=?, path_score=?, rank=?, reasoning=?, "
            "have_json=?, missing_json=?, steps_json=?, draft=?, scored=1 WHERE id=?",
            (ring, fit_score, path_score, rank, reasoning,
             json.dumps(have), json.dumps(missing), json.dumps(steps), draft, job_id))
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def set_review_status(job_id: int, status: str) -> dict | None:
    if status not in ("new", "applied", "skipped"):
        raise ValueError(f"bad review status '{status}'")
    conn = connect()
    try:
        conn.execute("UPDATE job SET review_status=? WHERE id=?", (status, job_id))
        conn.commit()
        return get_job(job_id)
    finally:
        conn.close()


def assign_tiers() -> None:
    """Assign reveal tiers. Scored jobs rank by ring + fit (best first). Unscored
    jobs (no model was run) all go to tier 1 so the raw table is fully visible —
    there's no ranking to gate on, so nothing is hidden."""
    conn = connect()
    try:
        scored = conn.execute(
            "SELECT id FROM job WHERE scored=1 "
            "ORDER BY (CASE WHEN ring IN (1,2) THEN 0 ELSE 1 END), rank DESC, id"
        ).fetchall()
        tier_size = 5
        for i, r in enumerate(scored):
            conn.execute("UPDATE job SET tier=? WHERE id=?", ((i // tier_size) + 1, r["id"]))
        # Unscored jobs: all tier 1 (no ranking exists to tier them by).
        conn.execute("UPDATE job SET tier=1 WHERE scored=0")
        conn.commit()
    finally:
        conn.close()


def current_tier() -> int:
    """The lowest tier that still has unreviewed jobs. That's the tier to show."""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT MIN(tier) AS t FROM job WHERE review_status='new'"
        ).fetchone()
        return row["t"] if row and row["t"] is not None else 1
    finally:
        conn.close()


def visible_jobs() -> list[dict]:
    """Jobs the user should see now: everything up to and including the current
    tier. Includes unscored jobs (no model run) so the table fills regardless —
    scored jobs sort first by fit, unscored jobs follow."""
    tier = current_tier()
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM job WHERE tier<=? "
            "ORDER BY scored DESC, (CASE WHEN ring IN (1,2) THEN 0 ELSE 1 END), "
            "rank DESC, id",
            (tier,)).fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def all_jobs() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM job ORDER BY rank DESC, id").fetchall()
        return [_row(r) for r in rows]
    finally:
        conn.close()


def clear_jobs(only_status: str | None = None) -> int:
    """Delete stored jobs. With only_status, delete just those with that review
    status (e.g. keep 'applied' ones, clear the rest). Returns count deleted.
    Used to wipe stale results (e.g. a DB full of international jobs from before a
    filter fix) so a fresh search repopulates cleanly."""
    conn = connect()
    try:
        if only_status:
            cur = conn.execute("DELETE FROM job WHERE review_status=?", (only_status,))
        else:
            cur = conn.execute("DELETE FROM job")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
