"""Resource + safety endpoints (Milestone 3.5)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from .. import config
from ..resources import Governor, read_state

router = APIRouter()


@router.get("/api/resources")
def resources() -> dict:
    state = read_state()
    decision = Governor(config).evaluate(state)
    out = asdict(state)
    out["safe_to_proceed"] = decision.proceed
    out["governor_reason"] = decision.reason
    return out
