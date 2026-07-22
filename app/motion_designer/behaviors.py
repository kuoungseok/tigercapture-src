"""Small deterministic behavior library."""
from __future__ import annotations

import math
from typing import Any, MutableMapping

from .curves import clamp01, easing_progress
from .schema import MotionBehaviorRef


def _phase(behavior: MotionBehaviorRef, time_ms: float) -> float:
    span = max(1.0, float(behavior.end_ms - behavior.start_ms))
    return clamp01((float(time_ms) - behavior.start_ms) / span)


def apply_behavior(values: MutableMapping[str, Any], behavior: MotionBehaviorRef, time_ms: float) -> None:
    if not behavior.enabled:
        return
    kind = behavior.kind.lower().strip()
    params = behavior.params
    before = time_ms < behavior.start_ms
    after = time_ms > behavior.end_ms
    if before and not bool(params.get("hold_before", False)):
        return
    if after and not bool(params.get("hold_after", False)):
        return
    t = 0.0 if before else 1.0 if after else _phase(behavior, time_ms)
    t = easing_progress(t, str(params.get("easing") or "linear"))
    if kind == "fade":
        direction = str(params.get("direction", "in"))
        factor = 1.0 - t if direction == "out" else (1.0 if params.get("instant") and not before else t)
        values["opacity"] = float(values.get("opacity", 1.0)) * factor
    elif kind == "slide":
        if before and bool(params.get("hide_before", False)):
            values["opacity"] = 0.0
        distance = params.get("distance", [100.0, 0.0])
        direction = str(params.get("direction", "in"))
        factor = t if direction == "out" else 1.0 - t
        values["position"] = [float(values["position"][0]) + float(distance[0]) * factor,
                              float(values["position"][1]) + float(distance[1]) * factor]
    elif kind in {"scale", "pop"}:
        if before and bool(params.get("hide_before", False)):
            values["opacity"] = 0.0
        start = float(params.get("from", 0.8 if kind == "pop" else 0.0))
        overshoot = float(params.get("overshoot", 0.12 if kind == "pop" else 0.0))
        factor = start + (1.0 - start) * t + math.sin(t * math.pi) * overshoot
        values["scale"] = [float(values["scale"][0]) * factor, float(values["scale"][1]) * factor]
    elif kind == "spring":
        amplitude = float(params.get("amplitude", 20.0))
        frequency = float(params.get("frequency", 3.0))
        damping = float(params.get("damping", 5.0))
        axis = int(params.get("axis", 1))
        offset = amplitude * math.sin(t * frequency * math.tau) * math.exp(-damping * t)
        position = list(values["position"])
        position[max(0, min(1, axis))] += offset
        values["position"] = position
    elif kind == "wiggle":
        amplitude = float(params.get("amplitude", 5.0))
        frequency = float(params.get("frequency", 2.0))
        seed = float(params.get("seed", 0.0))
        seconds = float(time_ms) / 1000.0
        values["rotation"] = float(values.get("rotation", 0.0)) + amplitude * math.sin((seconds * frequency + seed) * math.tau)


def apply_behaviors(values: MutableMapping[str, Any], behaviors: list[MotionBehaviorRef], time_ms: float) -> None:
    for behavior in behaviors:
        apply_behavior(values, behavior, time_ms)
