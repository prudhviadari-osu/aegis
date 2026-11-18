"""Milestone 2 tests: adapter factory, compat check, chat/model endpoints.
Uses the fake backend so no Ollama/Hermes or network is needed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app import config
from backend.app.models import get_adapter, FakeBackend, OllamaBackend, HermesBackend
from backend.app.models.base import ModelInfo
from backend.app.models.compat import check, _params_to_billions


def test_factory_selects_backend():
    class C: pass
    c = C()
    c.MODEL_BACKEND = "fake"; assert isinstance(get_adapter(c), FakeBackend)
    c.MODEL_BACKEND = "ollama"; assert isinstance(get_adapter(c), OllamaBackend)
    c.MODEL_BACKEND = "hermes"; assert isinstance(get_adapter(c), HermesBackend)
    print("  adapter factory picks the right backend: OK")


def test_params_parsing():
    assert _params_to_billions("8.2B") == 8.2
    assert _params_to_billions("270M") == 0.27
    assert _params_to_billions("") == 8.0       # default assumption
    print("  parameter-size parsing: OK")


def test_compat_fits_and_tight():
    # Small model, lots of RAM -> fits.
    info = ModelInfo("ollama", "qwen3:8b", available=True, context_window=131072,
                     parameters="8.2B", quantization="Q4_K_M")
    r = check(info, machine_ram_gb=36, target_context=64000)
    assert r.fits is True
    assert r.meets_hermes_64k is True

    # Same model but a tiny-RAM machine at 64k -> should flag tight.
    r2 = check(info, machine_ram_gb=8, target_context=64000)
    assert r2.fits is False
    assert any("Tight" in m or "tight" in m for m in r2.messages)
    print("  compat check flags fit vs. tight correctly: OK")


def test_compat_hermes_warns_on_small_context():
    info = ModelInfo("ollama", "small", available=True, context_window=32768,
                     parameters="8B")
    r = check(info, machine_ram_gb=18, target_context=64000)
    assert r.meets_hermes_64k is False
    assert any("64,000" in m or "64000" in m for m in r.messages)
    print("  compat warns when context < Hermes 64k: OK")


def test_fake_chat_roundtrip():
    fb = FakeBackend()
    assert fb.available() is True
    reply = fb.chat([{"role": "user", "content": "hello there"}])
    assert "hello there" in reply
    print("  fake backend chat round-trip: OK")


import contextlib


@contextlib.contextmanager
def _client_with_fake():
    """Force the fake backend for endpoint tests, then restore config so the
    change doesn't leak into other tests (test isolation)."""
    original = config.MODEL_BACKEND
    config.MODEL_BACKEND = "fake"
    try:
        from backend.app.main import app
        with TestClient(app) as client:
            yield client
    finally:
        config.MODEL_BACKEND = original


def test_model_endpoint():
    with _client_with_fake() as client:
        r = client.get("/api/model")
        assert r.status_code == 200
        body = r.json()
        assert body["backend"] == "fake"
        assert body["available"] is True
        assert "messages" in body
    print("  /api/model endpoint: OK")


def test_chat_endpoint():
    with _client_with_fake() as client:
        r = client.post("/api/chat", json={"message": "what can you do?", "history": []})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "what can you do?" in body["reply"]
    print("  /api/chat endpoint: OK")


if __name__ == "__main__":
    test_factory_selects_backend()
    test_params_parsing()
    test_compat_fits_and_tight()
    test_compat_hermes_warns_on_small_context()
    test_fake_chat_roundtrip()
    test_model_endpoint()
    test_chat_endpoint()
    print("\nAll Milestone 2 tests passed.")
