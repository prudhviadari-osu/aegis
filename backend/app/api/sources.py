"""Job-source management (M7 polish): add a Workday company from the dashboard,
so you don't have to edit jobify's Python config by hand.

It parses a careers URL into tenant/dc/site (reusing jobify's parser) and appends
it to jobify's discovered_companies.json — the file jobify already merges into its
Workday search. Safer than rewriting config.py from a web form.
"""
from __future__ import annotations

import json
import os
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config

router = APIRouter()


def _jobify_on_path():
    if config.JOBIFY_PATH not in sys.path:
        sys.path.insert(0, config.JOBIFY_PATH)


class SourceIn(BaseModel):
    url: str          # a *.myworkdayjobs.com careers URL


@router.get("/api/sources")
def list_sources() -> dict:
    """Seed companies (from jobify config) + discovered ones (the file we append to)."""
    _jobify_on_path()
    try:
        from finder import config as jf
        from finder.discovery import load_discovered
    except ImportError as exc:
        raise HTTPException(500, f"jobify not importable from {config.JOBIFY_PATH}: {exc}")
    seeded = [c.get("name", c.get("tenant")) for c in getattr(jf, "WORKDAY_COMPANIES", [])]
    discovered = [c.get("name", c.get("tenant")) for c in load_discovered()]
    return {"seeded": seeded, "discovered": discovered}


@router.post("/api/sources")
def add_source(body: SourceIn) -> dict:
    _jobify_on_path()
    try:
        from finder.workday_tenant import parse_workday_url, is_workday_url
        from finder.discovery import register_from_url, load_discovered
    except ImportError as exc:
        raise HTTPException(500, f"jobify not importable from {config.JOBIFY_PATH}: {exc}")

    if not is_workday_url(body.url):
        raise HTTPException(400, "Not a *.myworkdayjobs.com URL. Paste a company's "
                                 "Workday careers page URL.")
    parsed = parse_workday_url(body.url)
    if not parsed:
        raise HTTPException(400, "Couldn't parse that Workday URL. Expected "
                                 "https://COMPANY.wdN.myworkdayjobs.com/SiteSlug")
    added = register_from_url(body.url)
    if added is None:
        return {"ok": True, "added": False, "company": parsed,
                "message": f"{parsed['name']} is already a known source."}
    return {"ok": True, "added": True, "company": added,
            "message": f"Added {added['name']}. It'll be searched on the next job_finder run."}
