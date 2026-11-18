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
from ..models.prompting import inference_lock, temperature_for

router = APIRouter()


class ChatIn(BaseModel):
    message: str
    history: list[dict] = []     # prior [{role, content}] turns (optional)
    kind: str = "conversational"  # "analytical" | "conversational" | "creative"


@router.get("/api/model")
def model_status() -> dict:
    adapter = get_adapter(config)
    info = adapter.info()
    report = check(info, machine_ram_gb=config.MACHINE_RAM_GB,
                   target_context=config.TARGET_CONTEXT,
                   kv_cache_type=getattr(config, "KV_CACHE_TYPE", "f16"))
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


class AnswerIn(BaseModel):
    question: str
    kind: str = "creative"   # answers (e.g. "why this company") are usually prose


@router.post("/api/answer")
def answer_checked(body: AnswerIn) -> dict:
    """Draft an answer, then self-check + revise it once (Milestone 4).
    Skips the extra passes if the device governor says conditions are unsafe."""
    from ..models.selfcheck import answer_with_selfcheck
    from ..models.prompting import inference_lock, temperature_for
    from ..resources import Governor

    adapter = get_adapter(config)
    if not adapter.available():
        return {"ok": False, "error": f"model backend '{config.MODEL_BACKEND}' not reachable"}

    # First draft.
    with inference_lock():
        draft = adapter.chat(
            [{"role": "system", "content": config.SYSTEM_PROMPT},
             {"role": "user", "content": body.question}],
            temperature=temperature_for(body.kind))
    # Self-check loop (governor-gated so it won't burn compute on a hot Mac).
    result = answer_with_selfcheck(adapter, body.question, draft, governor=Governor(config))
    result["ok"] = True
    return result


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
    # Build the system prompt, augmented with relevant long-term memories so Aegis
    # "remembers" the user across sessions (M6).
    from ..memory import build_memory_context
    system = config.SYSTEM_PROMPT
    mem = build_memory_context(query=body.message)
    if mem:
        system = f"{system}\n\n{mem}"

    messages = [{"role": "system", "content": system}]
    messages += [m for m in body.history if m.get("role") in ("user", "assistant")]
    messages.append({"role": "user", "content": body.message})
    temperature = temperature_for(body.kind)
    try:
        # The lock guarantees only one inference runs at a time (thermal safeguard).
        with inference_lock():
            reply = adapter.chat(messages, temperature=temperature)
        return {"ok": True, "reply": reply, "error": None}
    except ModelError as exc:
        return {"ok": False, "reply": "", "error": str(exc)}
