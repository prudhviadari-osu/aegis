"""Tests for the prompting/sampling helpers and the single-inference lock
(the thermal safeguard). No model needed."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import config
from backend.app.models.prompting import temperature_for, build_system, inference_lock


def test_temperature_by_kind():
    assert temperature_for("analytical") == config.TEMP_ANALYTICAL
    assert temperature_for("conversational") == config.TEMP_CONVERSATIONAL
    assert temperature_for("creative") == config.TEMP_CREATIVE
    # analytical should be the lowest (steadiest) of the three
    assert config.TEMP_ANALYTICAL < config.TEMP_CREATIVE
    assert temperature_for("unknown") == config.TEMP_CONVERSATIONAL  # safe default
    print("  per-task temperature mapping: OK")


def test_build_system_few_shot_and_json():
    sys_prompt = build_system(
        "You are a classifier.",
        examples=[{"input": "sunny day", "output": "positive"}],
        json_only=True,
    )
    assert "You are a classifier." in sys_prompt
    assert "sunny day" in sys_prompt and "positive" in sys_prompt
    assert "ONLY valid JSON" in sys_prompt
    print("  build_system few-shot + json-only: OK")


def test_inference_lock_serializes():
    """Prove the lock actually prevents two inferences overlapping — the core
    thermal safeguard (never two model calls at once)."""
    lock = inference_lock()
    order = []

    def worker(name):
        with lock:
            order.append(f"{name}-start")
            time.sleep(0.05)
            order.append(f"{name}-end")

    t1 = threading.Thread(target=worker, args=("A",))
    t2 = threading.Thread(target=worker, args=("B",))
    t1.start(); t2.start(); t1.join(); t2.join()

    # Whichever ran first must fully finish before the other starts — no overlap.
    assert order[0].endswith("-start")
    assert order[1].endswith("-end")
    assert order[0][0] == order[1][0], f"interleaved! {order}"
    print(f"  inference lock serializes calls (order={order}): OK")


if __name__ == "__main__":
    test_temperature_by_kind()
    test_build_system_few_shot_and_json()
    test_inference_lock_serializes()
    print("\nAll prompting/thermal tests passed.")
