"""Task + approval endpoints (Milestone 3)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..tasks import repository as repo

router = APIRouter()


class TaskIn(BaseModel):
    title: str
    description: str = ""
    skill: str = ""
    priority: int = 0
    needs_approval: bool = False


class TransitionIn(BaseModel):
    action: str   # "pause" | "resume" | "cancel"


@router.post("/api/tasks")
def create(body: TaskIn) -> dict:
    return repo.create_task(body.title, body.description, body.skill,
                            body.priority, body.needs_approval)


@router.get("/api/tasks")
def list_all(status: str | None = None) -> list[dict]:
    return repo.list_tasks(status=status)


@router.get("/api/tasks/{task_id}")
def detail(task_id: int) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    task["events"] = repo.events(task_id)
    return task


@router.post("/api/tasks/{task_id}/control")
def control(task_id: int, body: TransitionIn) -> dict:
    mapping = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}
    target = mapping.get(body.action)
    if not target:
        raise HTTPException(400, f"unknown action '{body.action}'")
    try:
        return repo.transition(task_id, target, f"user:{body.action}")
    except repo.TransitionError as exc:
        raise HTTPException(409, str(exc))


# --- Approvals ---
@router.get("/api/approvals")
def approvals() -> list[dict]:
    return repo.pending_approvals()


class ApprovalIn(BaseModel):
    approved: bool


@router.post("/api/approvals/{approval_id}")
def resolve(approval_id: int, body: ApprovalIn) -> dict:
    result = repo.resolve_approval(approval_id, body.approved)
    if not result:
        raise HTTPException(404, "approval not found")
    # If approved, move the task from pending_approval into the queue.
    if body.approved and result.get("task_id"):
        try:
            repo.transition(result["task_id"], "queued", "approval granted")
        except repo.TransitionError:
            pass
    elif not body.approved and result.get("task_id"):
        try:
            repo.transition(result["task_id"], "cancelled", "approval rejected")
        except repo.TransitionError:
            pass
    return result
