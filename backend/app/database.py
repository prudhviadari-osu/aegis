"""SQLite database: the single source of truth (PRD §3).

Plain stdlib sqlite3 for now (SQLAlchemy only if the models grow). WAL mode +
foreign keys on. Schema self-initializes on first connect.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS task (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    description   TEXT DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'created',
    priority      INTEGER NOT NULL DEFAULT 0,
    skill         TEXT DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    started_at    TEXT,
    completed_at  TEXT,
    checkpoint    TEXT,
    result        TEXT,
    error         TEXT
);

CREATE TABLE IF NOT EXISTS task_event (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id    INTEGER NOT NULL REFERENCES task(id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now')),
    details    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS approval (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER REFERENCES task(id) ON DELETE CASCADE,
    action       TEXT NOT NULL,
    description  TEXT DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at  TEXT
);

CREATE TABLE IF NOT EXISTS memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,            -- profile|project|task|reference|procedural
    content     TEXT NOT NULL,
    source      TEXT DEFAULT '',
    confidence  REAL DEFAULT 1.0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    path        TEXT DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1,
    version     TEXT DEFAULT '0.1.0'
);

CREATE TABLE IF NOT EXISTS setting (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_task_status   ON task(status);
CREATE INDEX IF NOT EXISTS idx_event_task    ON task_event(task_id);
CREATE INDEX IF NOT EXISTS idx_approval_task ON approval(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_cat    ON memory(category);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | None = None) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
