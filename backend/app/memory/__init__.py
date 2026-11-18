"""Persistent memory (Milestone 6): lets Aegis remember you across sessions.

A model is stateless — each chat starts blank. Memory works by (1) storing facts
in SQLite and (2) retrieving the relevant ones and injecting them into the system
prompt before each reply. So 'remembering' = store + retrieve + inject.

This is the lightweight, local version that works on plain Ollama (no Hermes, no
64K strain). Categories (PRD §5.4) are tags: profile|project|task|reference|procedural.
"""
from .store import (
    remember, recall, search_memories, forget, all_memories, build_memory_context,
)

__all__ = [
    "remember", "recall", "search_memories", "forget", "all_memories",
    "build_memory_context",
]
