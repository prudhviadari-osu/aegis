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
from .api import (chat, health, jobs, memory, resources, settings as settings_api,
                  skills, sources, tasks)
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
    # Shutdown: stop the worker with a bounded wait so Ctrl+C never hangs.
    # If a task is mid-model-call (uninterruptible), we wait briefly then let the
    # daemon thread die with the process — its state is already saved in SQLite.
    print("Stopping worker… (up to 3s)")
    worker.stop(join_timeout=3.0)
    print("Aegis stopped. Any in-flight task is saved and will resume on restart.")


app = FastAPI(title="Aegis", version="0.1.0", lifespan=lifespan)
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(tasks.router)
app.include_router(resources.router)
app.include_router(skills.router)
app.include_router(memory.router)
app.include_router(jobs.router)
app.include_router(sources.router)
app.include_router(settings_api.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/jobs")
def jobs_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "jobs.html")


@app.get("/metrics")
def metrics_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "metrics.html")


@app.get("/settings")
def settings_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "settings.html")


def run() -> None:
    import uvicorn
    print(f"Aegis → http://{config.HOST}:{config.PORT}  (local only)")
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    run()
