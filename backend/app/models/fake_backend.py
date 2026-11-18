"""Fake backend — deterministic, offline. For tests and for seeing the UI work
before you install Ollama. It does NOT understand language; it echoes a canned
reply so the plumbing can be exercised end to end."""
from __future__ import annotations

from .base import ModelAdapter, ModelInfo


class FakeBackend(ModelAdapter):
    def available(self) -> bool:
        return True

    def info(self) -> ModelInfo:
        return ModelInfo("fake", "fake-model", available=True,
                         context_window=128_000, parameters="0B", quantization="none",
                         note="deterministic stub — no real model")

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        last = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        low = last.lower()
        # If this is a self-check critique prompt, return a valid critique JSON.
        # Deterministic rule: short answers "fail" (needs revision), longer ones pass.
        if "grade the answer against these criteria" in low:
            # Isolate just the ANSWER text (between 'ANSWER:' and the next section)
            # as a crude quality proxy for tests: short answers "fail".
            after = last.split("ANSWER:", 1)[-1]
            answer_only = after.split("Grade the answer", 1)[0].strip()
            if len(answer_only) < 40:
                return '{"score": 4, "needs_revision": true, "problems": ["too shallow"]}'
            return '{"score": 9, "needs_revision": false, "problems": []}'
        return f"(fake model) I received: {last!r}. Install Ollama + qwen3:8b for real replies."
