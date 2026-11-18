"""The model adapter interface — the single 'socket' every backend plugs into.

Three things every backend must provide:
  - available():  is it reachable right now? (for a friendly status check)
  - info():       what model/params/context is it? (for the compatibility check)
  - chat():       send messages, get a text reply (streaming optional later)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ModelError(Exception):
    """Raised when a backend is unreachable or returns an unusable response."""


@dataclass
class ModelInfo:
    """What a backend reports about itself — feeds the compatibility check."""
    backend: str              # "ollama" | "hermes" | "fake"
    model: str                # e.g. "qwen3:8b"
    available: bool           # reachable right now?
    context_window: int = 0   # tokens, 0 = unknown
    parameters: str = ""      # e.g. "8.2B"
    quantization: str = ""    # e.g. "Q4_K_M"
    note: str = ""            # human-readable status detail


class ModelAdapter(ABC):
    @abstractmethod
    def available(self) -> bool:
        """True if the backend responds. Never raises — returns False on failure."""
        raise NotImplementedError

    @abstractmethod
    def info(self) -> ModelInfo:
        """Report model details (used by the compatibility check)."""
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        """Send a list of {role, content} messages; return the assistant's text.
        Raise ModelError on transport failure."""
        raise NotImplementedError
