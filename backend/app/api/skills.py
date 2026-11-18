"""Skills endpoint (Milestone 5): list what the agent can do."""
from __future__ import annotations

from fastapi import APIRouter

from ..skills import all_skills

router = APIRouter()


@router.get("/api/skills")
def list_skills() -> list[dict]:
    return [
        {"name": s.name, "description": s.description, "permission": s.permission}
        for s in all_skills()
    ]
