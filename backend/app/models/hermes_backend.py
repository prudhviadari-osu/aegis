"""Hermes backend — optional "smart mode" (Nous Research self-improving agent).

Hermes Agent runs as a local service and exposes an OpenAI-compatible chat
endpoint. Aegis talks to it the same way it talks to any chat model, but Hermes
adds its learning loop, skills, and cross-session memory on top.

Hard requirement (checked by Hermes at startup): the underlying model must expose
a context window of at least 64,000 tokens. We surface that in info() so the
compatibility check can warn before you rely on it.

Setup (on your Mac, when you're ready — M5 wires the UI toggle):
    1. Install Hermes Agent per Nous Research's docs.
    2. Point it at your local Ollama model configured for >= 64K context.
    3. Set AEGIS_MODEL_BACKEND=hermes (and AEGIS_HERMES_HOST if non-default).
"""
from __future__ import annotations

import requests

from .base import ModelAdapter, ModelError, ModelInfo

HERMES_MIN_CONTEXT = 64_000   # Hermes Agent's hard-coded minimum


class HermesBackend(ModelAdapter):
    def __init__(self, host: str = "http://localhost:8080",
                 model: str = "qwen3:8b", timeout: int = 180):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        # Try the OpenAI-compatible models listing most local agent servers expose.
        for path in ("/v1/models", "/health", "/"):
            try:
                r = requests.get(f"{self.host}{path}", timeout=4)
                if r.status_code < 500:
                    return True
            except requests.RequestException:
                continue
        return False

    def info(self) -> ModelInfo:
        if not self.available():
            return ModelInfo("hermes", self.model, available=False,
                             note=f"Hermes not reachable at {self.host}. Is the Hermes "
                                  f"service running?")
        return ModelInfo("hermes", self.model, available=True,
                         context_window=HERMES_MIN_CONTEXT,
                         note=f"Hermes requires >= {HERMES_MIN_CONTEXT:,} token context; "
                              "verify your underlying model provides it.")

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        payload = {"model": self.model, "messages": messages, "temperature": temperature}
        try:
            r = requests.post(f"{self.host}/v1/chat/completions",
                              json=payload, timeout=self.timeout)
            r.raise_for_status()
            body = r.json()
        except requests.RequestException as exc:
            raise ModelError(
                f"Hermes not reachable at {self.host} ({exc}). Is the Hermes service "
                "running, and is your model configured for >= 64K context?"
            ) from exc
        except ValueError as exc:
            raise ModelError(f"Hermes returned invalid JSON: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelError(f"unexpected Hermes response shape: {exc}") from exc
