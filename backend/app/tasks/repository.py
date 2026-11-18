"""Data access for tasks, events, and approvals (PRD §3).

Thin typed wrappers over SQLite so the rest of the task system never writes raw
SQL. Every state change also writes a task_event, giving a full audit trail.
"""
from __future__ import annotations

import json
from typing import Any

from ..database import connect

# Valid task states and the allowed transitions between them (the state machine).
STATES = {
    "created", "pending_approval", "queued", "running",
    "waiting_input", "paused", "completed", "failed", "cancelled",
}
TERMINAL = {"completed", "failed", "cancelled"}

ALLOWED = {
    "created": {"pending_approval", "queued", "cancelled"},
    "pending_approval": {"queued", "cancelled"},
    "queued": {"running", "paused", "cancelled"},
    "running": {"waiting_input", "paused", "completed", "failed", "cancelled"},
    "waiting_input": {"running", "paused", "cancelled"},
    "paused": {"queued", "running", "cancelled"},
    # terminal states go nowhere
}


class TransitionError(Exception):
    """Raised on an illegal state transition — guards the lifecycle."""


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


def create_task(title: str, description: str = "", skill: str = "",
                priority: int = 0, needs_approval: bool = False) -> dict:
    status = "pending_approval" if needs_approval else "queued"
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO task(title, description, skill, priority, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, description, skill, priority, status),
        )
        tid = cur.lastrowid
        conn.execute("INSERT INTO task_event(task_id, type, details) VALUES (?, 'created', ?)",
                     (tid, f"status={status}"))
        conn.commit()
        return get_task(tid)
    finally:
        conn.close()


def get_task(task_id: int) -> dict | None:
    conn = connect()
    try:
        return _row_to_dict(conn.execute("SELECT * FROM task WHERE id=?", (task_id,)).fetchone())
    finally:
        conn.close()


def list_tasks(status: str | None = None, limit: int = 100) -> list[dict]:
    conn = connect()
    try:
        if status:
            rows = conn.execute("SELECT * FROM task WHERE status=? ORDER BY id DESC LIMIT ?",
                                (status, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM task ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def transition(task_id: int, new_status: str, detail: str = "") -> dict:
    """Move a task to new_status if the transition is allowed; log an event."""
    if new_status not in STATES:
        raise TransitionError(f"unknown status '{new_status}'")
    task = get_task(task_id)
    if not task:
        raise TransitionError(f"task {task_id} not found")
    current = task["status"]
    if current in TERMINAL:
        raise TransitionError(f"task {task_id} is terminal ({current}); cannot change")
    if new_status not in ALLOWED.get(current, set()):
        raise TransitionError(f"illegal transition {current} -> {new_status}")

    conn = connect()
    try:
        sets = ["status=?", "updated_at=datetime('now')"]
        vals: list[Any] = [new_status]
        if new_status == "running" and not task["started_at"]:
            sets.append("started_at=datetime('now')")
        if new_status in TERMINAL:
            sets.append("completed_at=datetime('now')")
        conn.execute(f"UPDATE task SET {', '.join(sets)} WHERE id=?", (*vals, task_id))
        conn.execute("INSERT INTO task_event(task_id, type, details) VALUES (?, ?, ?)",
                     (task_id, f"status:{new_status}", detail))
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def transition_safe(task_id: int, new_status: str, detail: str = "") -> dict | None:
    """Like transition() but never raises on an illegal/terminal move — returns
    None instead. Used by the worker's governor loop, where a task may have been
    cancelled by the user between checks and we don't want to crash the worker."""
    try:
        return transition(task_id, new_status, detail)
    except TransitionError:
        return None


def save_checkpoint(task_id: int, checkpoint: dict) -> None:
    """Persist resumable progress so an interrupted task can continue safely."""
    conn = connect()
    try:
        conn.execute("UPDATE task SET checkpoint=?, updated_at=datetime('now') WHERE id=?",
                     (json.dumps(checkpoint), task_id))
        conn.execute("INSERT INTO task_event(task_id, type, details) VALUES (?, 'checkpoint', ?)",
                     (task_id, f"keys={list(checkpoint)}"))
        conn.commit()
    finally:
        conn.close()


def set_result(task_id: int, result: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE task SET result=? WHERE id=?", (result, task_id))
        conn.commit()
    finally:
        conn.close()


def set_error(task_id: int, error: str) -> None:
    conn = connect()
    try:
        conn.execute("UPDATE task SET error=? WHERE id=?", (error, task_id))
        conn.commit()
    finally:
        conn.close()


def events(task_id: int) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM task_event WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# --- Approvals (the propose -> approve -> act gate) ---
def request_approval(task_id: int, action: str, description: str = "") -> dict:
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO approval(task_id, action, description, status) VALUES (?, ?, ?, 'pending')",
            (task_id, action, description))
        aid = cur.lastrowid
        conn.commit()
        return dict(conn.execute("SELECT * FROM approval WHERE id=?", (aid,)).fetchone())
    finally:
        conn.close()


def resolve_approval(approval_id: int, approved: bool) -> dict | None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE approval SET status=?, resolved_at=datetime('now') WHERE id=?",
            ("approved" if approved else "rejected", approval_id))
        conn.commit()
        row = conn.execute("SELECT * FROM approval WHERE id=?", (approval_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def pending_approvals() -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM approval WHERE status='pending' ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
