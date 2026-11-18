"""Model layer: the swappable AI backend (PRD §1).

Everything in Aegis talks to the `ModelAdapter` interface — never a specific
backend directly. That's what lets us run Qwen3 today and flip on Hermes later
with a one-line config change.
"""
from .base import ModelAdapter, ModelError, ModelInfo
from .ollama_backend import OllamaBackend
from .hermes_backend import HermesBackend
from .fake_backend import FakeBackend

__all__ = [
    "ModelAdapter", "ModelError", "ModelInfo",
    "OllamaBackend", "HermesBackend", "FakeBackend", "get_adapter",
]


def get_adapter(config):
    """Factory: build the backend named in config.MODEL_BACKEND."""
    backend = getattr(config, "MODEL_BACKEND", "ollama").lower()
    if backend == "fake":
        return FakeBackend()
    if backend == "hermes":
        return HermesBackend(
            host=getattr(config, "HERMES_HOST", "http://localhost:8080"),
            model=getattr(config, "OLLAMA_MODEL", "qwen3:8b"),
        )
    return OllamaBackend(
        host=getattr(config, "OLLAMA_HOST", "http://localhost:11434"),
        model=getattr(config, "OLLAMA_MODEL", "qwen3:8b"),
    )
