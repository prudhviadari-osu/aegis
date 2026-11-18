"""Ollama backend — the default. Talks to a local Ollama server (free, offline).

Setup on your Mac:
    1. Install Ollama: https://ollama.com/download
    2. ollama pull qwen3:8b
    3. Ollama serves on http://localhost:11434 automatically.
Nothing leaves your machine; no API key.
"""
from __future__ import annotations

import requests

from .base import ModelAdapter, ModelError, ModelInfo


class OllamaBackend(ModelAdapter):
    def __init__(self, host: str = "http://localhost:11434",
                 model: str = "qwen3:8b", timeout: int = 120,
                 num_ctx: int = 64000, kv_cache_type: str = "q8_0",
                 think: bool = True):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.num_ctx = num_ctx            # context window to request from Ollama
        self.kv_cache_type = kv_cache_type  # q8_0 halves KV memory vs f16
        self.think = think                # chain-of-thought for hard tasks

    def available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=4)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def info(self) -> ModelInfo:
        if not self.available():
            return ModelInfo("ollama", self.model, available=False,
                             note=f"Ollama not reachable at {self.host}. Is it running?")
        # Ask Ollama for the model's real details (params, quant, context).
        ctx, params, quant, note = 0, "", "", ""
        try:
            r = requests.post(f"{self.host}/api/show", json={"model": self.model}, timeout=8)
            if r.status_code == 200:
                data = r.json()
                details = data.get("details", {})
                params = details.get("parameter_size", "")
                quant = details.get("quantization_level", "")
                # The context length key varies by model family; scan model_info.
                for k, v in (data.get("model_info") or {}).items():
                    if k.endswith("context_length") and isinstance(v, int):
                        ctx = v
                        break
            else:
                note = f"model '{self.model}' not pulled yet? (ollama pull {self.model})"
        except requests.RequestException as exc:
            note = f"could not read model info: {exc}"
        return ModelInfo("ollama", self.model, available=True,
                         context_window=ctx, parameters=params,
                         quantization=quant, note=note)

    def chat(self, messages: list[dict], temperature: float = 0.7) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,          # Qwen3 reasons before answering (accuracy win)
            "options": {
                "temperature": temperature,
                "num_ctx": self.num_ctx,              # actually use the big context
                "cache_type_k": self.kv_cache_type,   # 8-bit KV cache: ~half the memory
                "cache_type_v": self.kv_cache_type,
            },
        }
        try:
            r = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
            r.raise_for_status()
            body = r.json()
        except requests.RequestException as exc:
            raise ModelError(
                f"Ollama not reachable at {self.host} ({exc}). "
                f"Is it running? Try: ollama pull {self.model}"
            ) from exc
        except ValueError as exc:
            raise ModelError(f"Ollama returned invalid JSON: {exc}") from exc
        return (body.get("message") or {}).get("content", "")
