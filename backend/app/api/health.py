"""Health endpoint — reports app, DB, and (from M2) model status."""
from __future__ import annotations

from fastapi import APIRouter

from .. import config
from ..database import connect

router = APIRouter()


def _db_ok() -> bool:
    try:
        conn = connect()
        try:
            conn.execute("SELECT 1 FROM task LIMIT 1;")
            return True
        finally:
            conn.close()
    except Exception:
        return False


@router.get("/api/health")
def health() -> dict:
    from .. import __version__
    return {
        "status": "ok" if _db_ok() else "degraded",
        "version": __version__,
        "database_ok": _db_ok(),
        "model_backend": config.MODEL_BACKEND,
        "model": config.OLLAMA_MODEL,  # placeholder until M2 verifies availability
    }
