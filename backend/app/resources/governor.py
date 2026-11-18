"""The governor: decides whether heavy work is safe right now (Milestone 3.5).

Priorities are shaped by WHY the user's battery degraded: sustained heat + high
charge age lithium cells, far more than one-off hard use. So the governor err on
the side of protecting the battery, trading speed for cooler, gentler operation
(the user explicitly prefers this).

Rules (configurable thresholds live in config):
  1. THERMAL — if macOS is throttling for heat (thermal pressure), DEFER. Heat is
     the #1 battery ager, so this is the strongest rule.
  2. ON BATTERY — if unplugged and below a floor %, DEFER (don't burn cycles/heat).
  3. HOT + FULL + PLUGGED — plugged in and near 100% is the classic
     battery-stress state; avoid piling sustained load on top of it.
  4. MEMORY — if RAM is nearly full, DEFER (avoid swap thrash).
Otherwise: PROCEED. The decision carries a human-readable reason.
"""
from __future__ import annotations

from dataclasses import dataclass

from .monitor import ResourceState, read_state


@dataclass
class Decision:
    proceed: bool
    reason: str


class Governor:
    def __init__(self, config):
        self.cfg = config

    def _t(self, name, default):
        return getattr(self.cfg, name, default)

    def evaluate(self, state: ResourceState | None = None) -> Decision:
        s = state or read_state()

        # 1. Thermal pressure — the strongest protective rule (heat ages the battery).
        if s.cpu_speed_limited or s.thermal_pressure in ("moderate", "heavy"):
            return Decision(False,
                f"Deferring — Mac is warm (thermal pressure: {s.thermal_pressure}). "
                "Letting it cool protects your battery.")

        # 2. On battery and low — don't burn cycles.
        floor = self._t("BATTERY_FLOOR_PERCENT", 40)
        if s.on_ac_power is False and s.battery_percent is not None and s.battery_percent < floor:
            return Decision(False,
                f"Deferring — on battery at {s.battery_percent:.0f}% (floor {floor}%). "
                "Plug in to run heavy work.")

        # 3. Plugged in, near full — avoid holding the battery hot at ~100%.
        high = self._t("BATTERY_HIGH_PERCENT", 95)
        if (s.on_ac_power and s.battery_percent is not None and s.battery_percent >= high
                and self._t("AVOID_HOT_FULL_CHARGE", True)):
            # Only block if we're ALSO warm-ish; a cool full battery is fine.
            if s.thermal_pressure != "nominal":
                return Decision(False,
                    f"Deferring — plugged in at {s.battery_percent:.0f}% and warm; "
                    "avoiding sustained load at full charge (battery stress).")

        # 4. Memory pressure — avoid swap thrash.
        mem_ceil = self._t("MEMORY_CEILING_PERCENT", 90)
        if s.memory_percent is not None and s.memory_percent >= mem_ceil:
            return Decision(False,
                f"Deferring — memory {s.memory_percent:.0f}% used (ceiling {mem_ceil}%). "
                "Freeing RAM avoids slowdown.")

        return Decision(True, "Conditions OK — safe to proceed.")
