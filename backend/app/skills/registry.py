"""Skill registry: discover, describe, and enable skills (PRD §5.3).

Kept deliberately simple — a dict of registered skills, each with a worker
handler and a permission level. The DB `skill` table records which are enabled;
this registry is the in-memory source of truth for what a skill *does*.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..tasks.worker import register_handler

# Permission levels mirror PRD §7.2 / the approval gate.
OBSERVE = "observe"    # read/search/analyze — no approval needed
PREPARE = "prepare"    # draft/populate for review — no approval to prepare
EXECUTE = "execute"    # consequential action — requires approval


@dataclass
class Skill:
    name: str
    description: str
    permission: str                       # observe | prepare | execute
    handler: Callable                     # (task, checkpoint) -> result str


_skills: dict[str, Skill] = {}


def register_skill(skill: Skill) -> None:
    _skills[skill.name] = skill
    register_handler(skill.name, skill.handler)   # wire it into the worker


def all_skills() -> list[Skill]:
    return list(_skills.values())


def get_skill(name: str) -> Skill | None:
    return _skills.get(name)


def load_builtin_skills() -> None:
    """Import built-in skills so they self-register. Called once at startup.
    Import errors (e.g. a skill's optional dependency missing) are reported but
    don't stop the app — a broken skill shouldn't take down Aegis."""
    from . import job_finder  # noqa: F401  (import triggers registration)
    try:
        job_finder.register()
    except Exception as exc:  # noqa: BLE001
        print(f"[skills] job_finder unavailable: {exc}")
