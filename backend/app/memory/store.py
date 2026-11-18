"""Memory store: save, search, retrieve, and inject memories (M6).

Search is keyword-based for now (SQLite LIKE) — simple, local, no vector DB, per
the PRD's 'don't add a vector database in the MVP' rule. Semantic search (e.g.
EmbeddingGemma) is a future upgrade if keyword recall proves too blunt.
"""
from __future__ import annotations

import re

from ..database import connect

VALID_CATEGORIES = {"profile", "project", "task", "reference", "procedural"}
_WORD = re.compile(r"[a-zA-Z0-9]+")


def remember(content: str, category: str = "reference", source: str = "user",
             confidence: float = 1.0) -> dict:
    """Store a fact. De-dupes exact repeats so memory doesn't bloat."""
    if category not in VALID_CATEGORIES:
        category = "reference"
    conn = connect()
    try:
        existing = conn.execute(
            "SELECT id FROM memory WHERE category=? AND content=?",
            (category, content)).fetchone()
        if existing:
            return dict(conn.execute("SELECT * FROM memory WHERE id=?",
                                     (existing["id"],)).fetchone())
        cur = conn.execute(
            "INSERT INTO memory(category, content, source, confidence) VALUES (?,?,?,?)",
            (category, content, source, confidence))
        conn.commit()
        return dict(conn.execute("SELECT * FROM memory WHERE id=?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


def all_memories(category: str | None = None) -> list[dict]:
    conn = connect()
    try:
        if category:
            rows = conn.execute("SELECT * FROM memory WHERE category=? ORDER BY id DESC",
                                (category,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM memory ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def search_memories(query: str, limit: int = 5) -> list[dict]:
    """Keyword search: rank memories by how many query words they contain.
    Blunt but effective and fully local."""
    words = [w.lower() for w in _WORD.findall(query)]
    if not words:
        return []
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM memory").fetchall()
    finally:
        conn.close()
    scored = []
    for r in rows:
        text = r["content"].lower()
        hits = sum(1 for w in words if w in text)
        if hits:
            scored.append((hits, dict(r)))
    scored.sort(key=lambda t: (t[0], t[1]["id"]), reverse=True)
    return [m for _, m in scored[:limit]]


def recall(limit: int = 10) -> list[dict]:
    """The most important always-on memories: the user's profile facts first."""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM memory WHERE category='profile' ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def forget(memory_id: int) -> bool:
    conn = connect()
    try:
        cur = conn.execute("DELETE FROM memory WHERE id=?", (memory_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def build_memory_context(query: str = "", max_items: int = 8) -> str:
    """Produce a short text block of relevant memories to inject into the system
    prompt. Always includes profile facts; adds query-relevant ones on top."""
    items: list[dict] = recall(limit=5)
    seen = {m["id"] for m in items}
    for m in search_memories(query, limit=max_items):
        if m["id"] not in seen:
            items.append(m)
            seen.add(m["id"])
    if not items:
        return ""
    lines = ["What you remember about the user:"]
    for m in items[:max_items]:
        lines.append(f"- ({m['category']}) {m['content']}")
    return "\n".join(lines)
