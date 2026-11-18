"""Aegis skills (Milestone 5+).

A skill is a self-contained capability the agent can run as a task. Skills
register a worker handler keyed by name, so new skills plug in without touching
the core (PRD §5). Each skill declares a permission level for the approval gate.
"""
from .registry import Skill, register_skill, all_skills, load_builtin_skills

__all__ = ["Skill", "register_skill", "all_skills", "load_builtin_skills"]
