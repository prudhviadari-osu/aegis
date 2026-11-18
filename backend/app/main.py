"""Aegis FastAPI application (Milestone 1: the shell).

Run:  python -m backend.app.main        (from the repo root)
or:   ./scripts/start.sh
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import chat, health, resources, skills, tasks
from .database import init_db
from .skills import load_builtin_skills
from .tasks.worker import worker, requeue_interrupted

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure local data dirs + database exist. No cloud, no daemon.
    config.ensure_dirs()
    init_db()
    # Register built-in skills (job_finder, etc.) so the worker can run them.
    load_builtin_skills()
    # Recover any task left 'running' by a previous shutdown, then start the worker.
    recovered = requeue_interrupted()
    if recovered:
        print(f"Recovered {recovered} interrupted task(s) — re-queued.")
    worker.start()
    yield
    # Shutdown: stop the worker cleanly (finishes current task, saves state).
    worker.stop()


app = FastAPI(title="Aegis", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(resources.router)
app.include_router(skills.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


def run() -> None:
    import uvicorn
    print(f"Aegis → http://{config.HOST}:{config.PORT}  (local only)")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    run()
