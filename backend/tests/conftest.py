"""Shared test setup: every test gets an isolated temp database, so tests never
touch the real ~/.aegis store and don't depend on a writable home directory.

Tests that need a fresh DB per-test still use their own tmp_path fixtures; this
session-level default just guarantees no test writes to the real data dir.
"""
import tempfile
from pathlib import Path

import pytest

from backend.app import config, database


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Point the DB (and data dir) at a per-test temp location and init it.
    autouse=True so EVERY test is isolated, even ones that don't ask for it."""
    data_dir = tmp_path / "aegis-data"
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "DB_PATH", data_dir / "database" / "aegis.db")
    database.init_db(config.DB_PATH)
    yield
