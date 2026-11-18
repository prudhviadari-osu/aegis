"""Model compatibility check (PRD §6).

Estimates whether a model fits your Mac's unified memory at a target context
window, and whether it meets Hermes' 64K requirement. Estimates are rough but
honest — the goal is to warn BEFORE you run, never to silently drop context or
reach for a paid cloud model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .base import ModelInfo

# Rough per-Mac budgeting (Q4). Sources vary; these are conservative.
SYSTEM_RESERVE_GB = 5.0          # macOS + your apps (Chrome, etc.)
WEIGHTS_GB_PER_B = 0.6           # ~0.5-0.7 GB per billion params at 4-bit
KV_GB_PER_1K_TOKENS_8B = 0.125   # ~ for an 8B model; scales with model size


@dataclass
class CompatReport:
    model: str
    backend: str
    available: bool
    context_window: int
    target_context: int
    est_weights_gb: float
    est_kv_gb: float
    est_total_gb: float
    machine_ram_gb: int
    fits: bool
    meets_hermes_64k: bool
    messages: list[str]


def _params_to_billions(params: str) -> float:
    """'8.2B' -> 8.2 ; '270M' -> 0.27 ; '' -> 8.0 (assume 8B)."""
    if not params:
        return 8.0
    m = re.match(r"([\d.]+)\s*([BM])", params.strip(), re.IGNORECASE)
    if not m:
        return 8.0
    val = float(m.group(1))
    return val if m.group(2).upper() == "B" else val / 1000.0


# KV cache memory multiplier by cache precision (relative to 16-bit default).
KV_CACHE_MULTIPLIER = {"f16": 1.0, "q8_0": 0.5, "q4_0": 0.25}


def check(info: ModelInfo, machine_ram_gb: int = 18,
          target_context: int = 64_000, kv_cache_type: str = "f16") -> CompatReport:
    billions = _params_to_billions(info.parameters)
    weights = billions * WEIGHTS_GB_PER_B
    # KV scales with context length and model size, reduced by cache quantization.
    kv_mult = KV_CACHE_MULTIPLIER.get(kv_cache_type, 1.0)
    kv = (target_context / 1000.0) * KV_GB_PER_1K_TOKENS_8B * (billions / 8.0) * kv_mult
    total = weights + kv + SYSTEM_RESERVE_GB
    fits = total <= machine_ram_gb

    # Does the model's real window cover the target? (0 = unknown)
    known_ctx = info.context_window or 0
    meets_hermes = known_ctx >= 64_000 if known_ctx else None

    msgs: list[str] = []
    if not info.available:
        msgs.append(f"Backend '{info.backend}' not reachable — can't verify. {info.note}")
    if not fits:
        msgs.append(
            f"Estimated {total:.1f} GB needed at {target_context:,} ctx, but you have "
            f"{machine_ram_gb} GB. Tight — close apps, try a smaller model (phi4-mini), "
            "or an 8-bit KV cache.")
    else:
        msgs.append(
            f"Estimated {total:.1f} GB of {machine_ram_gb} GB at {target_context:,} ctx "
            f"(~{weights:.1f} weights + ~{kv:.1f} KV + {SYSTEM_RESERVE_GB:.0f} system). OK.")
    if known_ctx and known_ctx < target_context:
        msgs.append(
            f"Model's context window is {known_ctx:,}, below the target {target_context:,}. "
            "Hermes needs >= 64,000 and will refuse smaller — raise the model's context.")
    if info.note:
        msgs.append(info.note)

    return CompatReport(
        model=info.model, backend=info.backend, available=info.available,
        context_window=known_ctx, target_context=target_context,
        est_weights_gb=round(weights, 1), est_kv_gb=round(kv, 1),
        est_total_gb=round(total, 1), machine_ram_gb=machine_ram_gb,
        fits=fits, meets_hermes_64k=bool(meets_hermes), messages=msgs,
    )
