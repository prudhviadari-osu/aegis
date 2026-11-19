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
        # Some prompts put the instruction in the SYSTEM message, so also scan all
        # message text for routing decisions (but echo the user message by default).
        all_low = " ".join(m.get("content", "") for m in messages).lower()

        # Job-analysis prompt (M5.5) -> return a valid analysis JSON.
        # Route on the job-specific text so ring reflects THIS job, not the system prompt.
        if "assign a ring" in all_low and "job:" in low:
            job_low = low.split("job:", 1)[-1]
            ring = 2 if ("biomedical" in job_low or "clinical" in job_low
                         or "medical" in job_low) else 3
            return (
                '{"ring": %d, "fit_score": 0.8, "path_score": %s, '
                '"reasoning": "(fake) matches ML + biomedical background", '
                '"have": ["Python", "XGBoost", "research experience"], '
                '"missing": ["industry experience", "FDA exposure"], '
                '"steps": ["highlight BraTS/MRI work", "mention hackathon wins"], '
                '"draft": "(fake) I am a pre-med CS student whose research in medical '
                'imaging ML maps directly to this role."}'
            ) % (ring, "0.9" if ring == 2 else "0.4")

        if "grade the answer against these criteria" in low:
            # Isolate just the ANSWER text (between 'ANSWER:' and the next section)
            # as a crude quality proxy for tests: short answers "fail".
            after = last.split("ANSWER:", 1)[-1]
            answer_only = after.split("Grade the answer", 1)[0].strip()
            if len(answer_only) < 40:
                return '{"score": 4, "needs_revision": true, "problems": ["too shallow"]}'
            return '{"score": 9, "needs_revision": false, "problems": []}'
        return f"(fake model) I received: {last!r}. Install Ollama + qwen3:8b for real replies."
