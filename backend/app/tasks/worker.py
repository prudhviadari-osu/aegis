"""Background worker (Milestone 3).

Pulls queued tasks and runs them ONE AT A TIME, with a gentle rest between tasks
(cool-and-quiet execution). Each task is handled by a registered handler keyed by
its `skill`; the default handler just asks the model, so M3 is testable before any
real skill exists (the job-finder registers its handler in M5).

Resumability: state lives in SQLite (repository), so if Aegis stops mid-task, the
task is left in a recoverable state and re-queued on next start.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from .. import config
from . import repository as repo

# A handler takes a task dict + a checkpoint-saver, and returns a result string.
Handler = Callable[[dict, Callable[[dict], None]], str]

_handlers: dict[str, Handler] = {}


def register_handler(skill: str, handler: Handler) -> None:
    """Skills register how their tasks actually run. M5 uses this for job-finder."""
    _handlers[skill] = handler


def _default_handler(task: dict, checkpoint) -> str:
    """M3 placeholder: ask the model to acknowledge/plan the objective.
    Runs through the single-inference lock so it stays gentle on the chip."""
    from ..models import get_adapter
    from ..models.prompting import inference_lock, temperature_for

    adapter = get_adapter(config)
    if not adapter.available():
        raise RuntimeError(f"model backend '{config.MODEL_BACKEND}' not reachable")
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content":
            f"Objective: {task['title']}\n{task['description']}\n\n"
            "Briefly outline how you'd approach this in 2-4 steps."},
    ]
    with inference_lock():
        return adapter.chat(messages, temperature=temperature_for("analytical"))


class Worker:
    """Single-threaded task runner. One task at a time, by design (thermal safety)."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="aegis-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the loop to finish the current task and exit cleanly."""
        self._stop.set()

    def _next_queued(self) -> dict | None:
        queued = repo.list_tasks(status="queued")
        # Highest priority first, then oldest (FIFO within a priority).
        queued.sort(key=lambda t: (-t["priority"], t["id"]))
        return queued[0] if queued else None

    def _run_one(self, task: dict) -> None:
        tid = task["id"]
        repo.transition(tid, "running")
        handler = _handlers.get(task["skill"], _default_handler)
        try:
            result = handler(task, lambda cp: repo.save_checkpoint(tid, cp))
            repo.set_result(tid, result)
            repo.transition(tid, "completed", "handler finished")
        except Exception as exc:   # noqa: BLE001 - record any failure, don't crash the worker
            repo.set_error(tid, str(exc))
            repo.transition(tid, "failed", str(exc))

    def _loop(self) -> None:
        rest = config.GENTLE_REST_SECONDS if config.EXECUTION_INTENSITY == "gentle" else 0.0
        while not self._stop.is_set():
            task = self._next_queued()
            if task is None:
                # Nothing to do — idle poll (cheap, keeps the chip cool).
                self._stop.wait(timeout=1.0)
                continue
            self._run_one(task)
            # Gentle pacing: rest between tasks so work happens in relaxed bursts.
            if rest:
                self._stop.wait(timeout=rest)


# Module-level singleton the app starts/stops in its lifespan.
worker = Worker()


def requeue_interrupted() -> int:
    """On startup, recover tasks left 'running' by a previous shutdown — move them
    back to 'queued' so they resume (nothing is lost, nothing double-completes)."""
    stuck = repo.list_tasks(status="running")
    for t in stuck:
        try:
            repo.transition(t["id"], "paused", "interrupted by shutdown")
            repo.transition(t["id"], "queued", "re-queued on restart")
        except repo.TransitionError:
            pass
    return len(stuck)
