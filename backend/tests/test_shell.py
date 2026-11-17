"""Milestone 1 tests: DB init, schema, and the shell's HTTP surface.

These use a temp DB and FastAPI's TestClient — no model, no network needed.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app import config, database


def test_db_init_creates_tables(tmp_path):
    db = tmp_path / "t.db"
    database.init_db(db)
    conn = database.connect(db)
    try:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    for expected in ("task", "task_event", "approval", "memory", "skill", "setting"):
        assert expected in names, f"missing table {expected}; got {names}"


def test_db_pragmas(tmp_path):
    db = tmp_path / "t.db"
    conn = database.connect(db)
    try:
        assert conn.execute("PRAGMA journal_mode;").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys;").fetchone()[0] == 1
    finally:
        conn.close()


def test_foreign_key_cascade(tmp_path):
    db = tmp_path / "t.db"
    database.init_db(db)
    conn = database.connect(db)
    try:
        cur = conn.execute("INSERT INTO task(title) VALUES ('x')")
        tid = cur.lastrowid
        conn.execute("INSERT INTO task_event(task_id, type) VALUES (?, 'created')", (tid,))
        conn.commit()
        conn.execute("DELETE FROM task WHERE id=?", (tid,))
        conn.commit()
        remaining = conn.execute("SELECT COUNT(*) FROM task_event WHERE task_id=?", (tid,)).fetchone()[0]
        assert remaining == 0, "cascade delete should remove child task_event rows"
    finally:
        conn.close()


def _client(tmp_path):
    # Point the app at a temp DB before importing the app module's db usage.
    config.DB_PATH = tmp_path / "database" / "aegis.db"
    config.DATA_DIR = tmp_path
    from backend.app.main import app
    return TestClient(app)


def test_health_endpoint(tmp_path):
    client = _client(tmp_path)
    with client:  # triggers lifespan (ensure_dirs + init_db)
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["database_ok"] is True
        assert body["model_backend"] == "ollama"
        assert "version" in body


def test_dashboard_served(tmp_path):
    client = _client(tmp_path)
    with client:
        r = client.get("/")
        assert r.status_code == 200
        assert "Aegis" in r.text
        r2 = client.get("/static/style.css")
        assert r2.status_code == 200
