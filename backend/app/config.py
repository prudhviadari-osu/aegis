"""Application configuration. Local-first; override via environment variables.

Nothing here points at a paid service or the public internet by default.
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root = two levels up from this file's package (backend/app -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("AEGIS_DATA_DIR", REPO_ROOT / "data"))
DB_PATH = DATA_DIR / "database" / "aegis.db"

# Dashboard / API bind address — localhost only (never public). See PRD §9.
HOST = os.environ.get("AEGIS_HOST", "127.0.0.1")
PORT = int(os.environ.get("AEGIS_PORT", "8777"))

# Model backend. "ollama" default; "hermes" optional smart mode; "fake" for a
# no-model dry run (useful before you install Ollama).
MODEL_BACKEND = os.environ.get("AEGIS_MODEL_BACKEND", "ollama")
OLLAMA_HOST = os.environ.get("AEGIS_OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("AEGIS_OLLAMA_MODEL", "qwen3:8b")
HERMES_HOST = os.environ.get("AEGIS_HERMES_HOST", "http://localhost:8080")

# Your Mac's unified memory (GB) — used by the model compatibility check.
MACHINE_RAM_GB = int(os.environ.get("AEGIS_RAM_GB", "18"))
# Context window Aegis targets (Hermes needs >= 64000).
TARGET_CONTEXT = int(os.environ.get("AEGIS_TARGET_CONTEXT", "64000"))

# --- Tuning that makes an 8B model punch above its weight on 18GB ---
# 8-bit KV cache roughly halves context memory, so 8B @ 64K fits comfortably.
# Options: "f16" (default, safest), "q8_0" (recommended here), "q4_0" (smallest).
KV_CACHE_TYPE = os.environ.get("AEGIS_KV_CACHE", "q8_0")
# Thinking / chain-of-thought mode: let the model reason before answering on hard
# tasks (big accuracy win for small models). Qwen3 supports this natively.
THINKING_MODE = os.environ.get("AEGIS_THINKING", "true").lower() == "true"

# --- Gentle execution: prioritize a cool, quiet Mac over speed ---
# "gentle" (default): one model call at a time, pause between queued tasks so the
#   chip runs in relaxed bursts instead of a sustained grind (fans stay quiet).
# "normal": no artificial pacing.
EXECUTION_INTENSITY = os.environ.get("AEGIS_INTENSITY", "gentle")
# Seconds to rest between queued background tasks when intensity is "gentle".
GENTLE_REST_SECONDS = float(os.environ.get("AEGIS_GENTLE_REST", "3.0"))
# Hard rule regardless of intensity: never run two model inferences at once
# (keeps the chip from maxing out — the main driver of heat).
MAX_CONCURRENT_INFERENCE = 1

# --- Battery / thermal / resource governor (M3.5): protect the hardware ---
# The user saw real battery wear from sustained training load. These rules make
# Aegis back off before adding to the heat/high-charge conditions that age cells.
# Don't run heavy work on battery below this % (plug in instead).
BATTERY_FLOOR_PERCENT = int(os.environ.get("AEGIS_BATTERY_FLOOR", "40"))
# Treat this % and up as "near full" for the plugged-in-and-hot rule.
BATTERY_HIGH_PERCENT = int(os.environ.get("AEGIS_BATTERY_HIGH", "95"))
# Avoid sustained load while plugged in, near full, and warm (battery stress).
AVOID_HOT_FULL_CHARGE = os.environ.get("AEGIS_AVOID_HOT_FULL", "true").lower() == "true"
# Defer if RAM usage is at/above this %.
MEMORY_CEILING_PERCENT = int(os.environ.get("AEGIS_MEM_CEILING", "90"))
# How long to rest before re-checking when the governor says "defer" (seconds).
GOVERNOR_BACKOFF_SECONDS = float(os.environ.get("AEGIS_GOVERNOR_BACKOFF", "30"))

# --- Skills (M5+) ---
# Path to the jobify ('jobfinder') repo so the job_finder skill can import it.
# Defaults to a sibling directory next to the aegis repo. Override if elsewhere.
JOBIFY_PATH = os.environ.get(
    "AEGIS_JOBIFY_PATH",
    str(Path(__file__).resolve().parents[3] / "jobfinder"),
)

# Per-task sampling temperatures (lower = steadier/more stable, also a bit cooler).
TEMP_ANALYTICAL = float(os.environ.get("AEGIS_TEMP_ANALYTICAL", "0.2"))  # scoring, logic, JSON
TEMP_CONVERSATIONAL = float(os.environ.get("AEGIS_TEMP_CHAT", "0.6"))     # chat
TEMP_CREATIVE = float(os.environ.get("AEGIS_TEMP_CREATIVE", "0.8"))       # drafting prose

# The assistant's standing instructions (the "system" message).
SYSTEM_PROMPT = (
    "You are Aegis, a local-first personal assistant for Prudhvi, a pre-med "
    "Computer Science student. Be concise and practical. You never take "
    "consequential actions without explicit approval."
)


def ensure_dirs() -> None:
    """Create the local data directories if they don't exist."""
    for sub in ("database", "browser", "documents", "logs", "checkpoints"):
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)
