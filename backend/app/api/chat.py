"""Chat + model-status endpoints (Milestone 2).

/api/model      -> which backend, is it up, and does it fit your Mac (compat check)
/api/chat       -> send a message, get the local model's reply
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config
from ..models import get_adapter
from ..models.base import ModelError
from ..models.compat import check

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []     # prior [{role, content}] turns (optional)


@router.get("/api/model")
def model_status() -> dict:
    adapter = get_adapter(config)
    info = adapter.info()
    report = check(info, machine_ram_gb=config.MACHINE_RAM_GB,
                   target_context=config.TARGET_CONTEXT)
    return {
        "backend": info.backend,
        "model": info.model,
        "available": info.available,
        "context_window": info.context_window,
        "parameters": info.parameters,
        "quantization": info.quantization,
        "fits_memory": report.fits,
        "meets_hermes_64k": report.meets_hermes_64k,
        "estimated_gb": report.est_total_gb,
        "machine_ram_gb": report.machine_ram_gb,
        "messages": report.messages,
    }


@router.post("/api/chat")
def chat(body: ChatIn) -> dict:
    adapter = get_adapter(config)
    if not adapter.available():
        return {
            "ok": False,
            "reply": "",
            "error": f"The '{config.MODEL_BACKEND}' model backend isn't reachable. "
                     f"Start Ollama and run `ollama pull {config.OLLAMA_MODEL}`, "
                     "or set AEGIS_MODEL_BACKEND=fake to try the UI without a model.",
        }
    # Build the message list: system prompt + prior history + the new message.
    messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    messages += [m for m in body.history if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": body.message})
    try:
        reply = adapter.chat(messages, temperature=0.7)
        return {"ok": True, "reply": reply, "error": None}
    except ModelError as exc:
        return {"ok": False, "reply": "", "error": str(exc)}
