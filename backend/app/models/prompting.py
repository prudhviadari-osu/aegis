"""Prompting + sampling helpers that make an 8B model punch above its weight,
tuned to run gently (cool & quiet) rather than fast.

Keepers from the inference-time playbook:
  - per-task temperature (low for analysis, higher for prose)
  - few-shot examples baked into the system message
  - structured-output instruction
Deferred on purpose (heat/RAM cost, speed we don't need): self-consistency,
speculative decoding, Best-of-N.
"""
from __future__ import annotations

import threading

from .. import config

# A single global lock: only ONE model inference runs at a time, regardless of how
# many tasks are queued. This is the main thermal safeguard — the chip stays busy
# but never pegged by parallel inference (what spins the fans up).
_inference_lock = threading.Lock()


def inference_lock() -> threading.Lock:
    return _inference_lock


# --- Task kinds -> temperature (PRD: low temp for analysis, higher for prose) ---
def temperature_for(task_kind: str) -> float:
    return {
        "analytical": config.TEMP_ANALYTICAL,     # scoring, classification, JSON, logic
        "conversational": config.TEMP_CONVERSATIONAL,
        "creative": config.TEMP_CREATIVE,          # drafting paragraphs
    }.get(task_kind, config.TEMP_CONVERSATIONAL)


def build_system(base: str, examples: list[dict] | None = None,
                 json_only: bool = False) -> str:
    """Compose a system prompt with optional few-shot examples and a
    structured-output instruction. Few-shot examples strongly stabilize a small
    model's formatting and edge-case handling for ~free.

    examples: list of {"input": str, "output": str}
    """
    parts = [base]
    if examples:
        parts.append("\nExamples of the expected input → output:")
        for ex in examples:
            parts.append(f"\nInput: {ex['input']}\nOutput: {ex['output']}")
    if json_only:
        parts.append(
            "\nRespond with ONLY valid JSON matching the requested shape — no prose, "
            "no code fences.")
    return "\n".join(parts)
