"""Memory endpoints (Milestone 6): view, add, search, and delete what Aegis
remembers about you (PRD §5.4 — user can inspect and edit stored memory)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..memory import all_memories, remember, search_memories, forget

router = APIRouter()


class MemoryIn(BaseModel):
    content: str
    category: str = "profile"
    source: str = "user"


@router.get("/api/memory")
def list_memory(category: str | None = None) -> list[dict]:
    return all_memories(category)


@router.post("/api/memory")
def add_memory(body: MemoryIn) -> dict:
    return remember(body.content, body.category, body.source)


@router.get("/api/memory/search")
def search(q: str) -> list[dict]:
    return search_memories(q)


@router.delete("/api/memory/{memory_id}")
def delete_memory(memory_id: int) -> dict:
    if not forget(memory_id):
        raise HTTPException(404, "memory not found")
    return {"deleted": memory_id}
