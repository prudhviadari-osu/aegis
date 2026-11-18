"""Reads the machine's battery, power, thermal, and memory state.

macOS specifics (no special permissions needed):
  - `pmset -g batt`  -> battery %, charging/discharging, AC vs battery
  - `pmset -g therm` -> thermal pressure / CPU speed limit (a heat signal)
  - psutil           -> memory + CPU load (cross-platform)

Degrades gracefully off macOS (e.g. this Linux sandbox): battery/thermal come
back 'unknown', memory/CPU still work via psutil. Nothing here ever raises.
"""
from __future__ import annotations

import platform
import re
import subprocess
from dataclasses import dataclass

try:
    import psutil
except ImportError:  # psutil optional at import time; monitor still returns partial data
    psutil = None

IS_MAC = platform.system() == "Darwin"


@dataclass
class ResourceState:
    battery_percent: float | None = None    # 0-100, None if unknown/desktop
    on_ac_power: bool | None = None          # True = plugged in
    is_charging: bool | None = None
    thermal_pressure: str = "unknown"        # "nominal" | "moderate" | "heavy" | "unknown"
    cpu_speed_limited: bool = False          # macOS has throttled the CPU (heat signal)
    memory_percent: float | None = None      # % of RAM in use
    available_gb: float | None = None
    cpu_percent: float | None = None


def _read_pmset_batt() -> dict:
    """Parse `pmset -g batt` on macOS."""
    out = {}
    try:
        text = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                              text=True, timeout=4).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return out
    m = re.search(r"(\d+)%", text)
    if m:
        out["battery_percent"] = float(m.group(1))
    low = text.lower()
    if "ac power" in low:
        out["on_ac_power"] = True
    elif "battery power" in low:
        out["on_ac_power"] = False
    out["is_charging"] = "charging" in low and "discharging" not in low
    return out


def _read_pmset_therm() -> dict:
    """Parse `pmset -g therm` for a thermal-pressure / CPU-limit signal."""
    out = {}
    try:
        text = subprocess.run(["pmset", "-g", "therm"], capture_output=True,
                              text=True, timeout=4).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return out
    m = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", text)
    if m:
        limit = int(m.group(1))
        out["cpu_speed_limited"] = limit < 100   # <100% means macOS is throttling for heat
        out["thermal_pressure"] = "nominal" if limit >= 100 else (
            "moderate" if limit >= 70 else "heavy")
    return out


def read_state() -> ResourceState:
    s = ResourceState()

    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            s.memory_percent = vm.percent
            s.available_gb = round(vm.available / (1024 ** 3), 1)
            s.cpu_percent = psutil.cpu_percent(interval=0.1)
            batt = psutil.sensors_battery()
            if batt is not None:
                s.battery_percent = float(batt.percent)
                s.on_ac_power = bool(batt.power_plugged)
        except Exception:  # noqa: BLE001 - never let monitoring crash the app
            pass

    if IS_MAC:
        s_batt = _read_pmset_batt()
        s.battery_percent = s_batt.get("battery_percent", s.battery_percent)
        s.on_ac_power = s_batt.get("on_ac_power", s.on_ac_power)
        s.is_charging = s_batt.get("is_charging", s.is_charging)
        therm = _read_pmset_therm()
        s.thermal_pressure = therm.get("thermal_pressure", s.thermal_pressure)
        s.cpu_speed_limited = therm.get("cpu_speed_limited", s.cpu_speed_limited)

    return s
