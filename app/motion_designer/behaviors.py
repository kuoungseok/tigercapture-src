"""Small deterministic behavior library."""
from __future__ import annotations

import math
from typing import Any, MutableMapping

from .curves import clamp01, easing_progress
from .schema import MotionBehaviorRef


BEHAVIOR_CONTRACT = "tiger_parameter_behavior_v1"
BEHAVIOR_CONTRACTS = {
    "fade": {"channels": ["opacity"], "time_model": "bounded"},
    "slide": {"channels": ["position"], "time_model": "bounded"},
    "scale": {"channels": ["scale"], "time_model": "bounded"},
    "pop": {"channels": ["scale"], "time_model": "bounded"},
    "spring": {"channels": ["position"], "time_model": "bounded"},
    "wiggle": {"channels": ["rotation"], "time_model": "continuous"},
    "impact": {"channels": ["position", "scale", "rotation"], "time_model": "bounded"},
    "spin": {"channels": ["rotation"], "time_model": "integrated"},
    "drift": {"channels": ["position"], "time_model": "integrated"},
    "grow_shrink": {"channels": ["scale"], "time_model": "oscillating"},
    "oscillate": {"channels": ["parameter"], "time_model": "oscillating"},
    "random_motion": {"channels": ["position", "rotation"], "time_model": "seeded_noise"},
}


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
    elif kind == "impact":
        overshoot = float(params.get("scale_overshoot", 0.14))
        rotation_kick = float(params.get("rotation_kick", 4.0))
        shake = float(params.get("shake", 8.0))
        frequency = float(params.get("frequency", 4.0))
        damping = max(0.0, float(params.get("damping", 6.0)))
        envelope = math.exp(-damping * t)
        pulse = math.sin(t * math.pi) * overshoot
        settle = math.sin(t * frequency * math.tau) * envelope
        values["scale"] = [
            float(values["scale"][0]) * (1.0 + pulse),
            float(values["scale"][1]) * (1.0 + pulse),
        ]
        values["rotation"] = float(values.get("rotation", 0.0)) + rotation_kick * settle
        position = list(values["position"])
        position[0] += shake * settle
        position[1] += shake * 0.45 * math.sin(t * (frequency + 0.5) * math.tau) * envelope
        values["position"] = position
    elif kind == "spin":
        elapsed = max(0.0, min(float(time_ms), float(behavior.end_ms)) - behavior.start_ms) / 1000.0
        values["rotation"] = float(values.get("rotation", 0.0)) + float(params.get("rate", 90.0)) * elapsed
    elif kind == "drift":
        elapsed = max(0.0, min(float(time_ms), float(behavior.end_ms)) - behavior.start_ms) / 1000.0
        velocity = list(params.get("velocity") or [40.0, 0.0])
        position = list(values["position"])
        position[0] += float(velocity[0]) * elapsed
        position[1] += float(velocity[1] if len(velocity) > 1 else 0.0) * elapsed
        values["position"] = position
    elif kind == "grow_shrink":
        cycles = float(params.get("cycles", 2.0))
        phase = math.radians(float(params.get("phase", 0.0)))
        amount = float(params.get("amount", 0.12)) * math.sin(t * cycles * math.tau + phase)
        values["scale"] = [
            float(values["scale"][0]) * (1.0 + amount),
            float(values["scale"][1]) * (1.0 + amount),
        ]
    elif kind == "oscillate":
        target = str(params.get("target") or "rotation")
        amount = float(params.get("amplitude", 10.0))
        cycles = float(params.get("cycles", 2.0))
        phase = math.radians(float(params.get("phase", 0.0)))
        value = amount * math.sin(t * cycles * math.tau + phase)
        if target == "position_x":
            values["position"][0] += value
        elif target == "position_y":
            values["position"][1] += value
        elif target == "scale":
            values["scale"] = [axis * (1.0 + value) for axis in values["scale"]]
        elif target == "opacity":
            values["opacity"] = max(0.0, min(1.0, float(values["opacity"]) + value))
        else:
            values["rotation"] = float(values.get("rotation", 0.0)) + value
    elif kind == "random_motion":
        frequency = max(0.001, float(params.get("frequency", 4.0)))
        seed = float(params.get("seed", 1.0))
        seconds = max(0.0, float(time_ms - behavior.start_ms)) / 1000.0
        cell = math.floor(seconds * frequency)
        fraction = seconds * frequency - cell
        fraction = fraction * fraction * (3.0 - 2.0 * fraction)

        def noise(index: int, channel: float) -> float:
            first = math.sin((index + seed * 19.19 + channel) * 12.9898) * 43758.5453
            second = math.sin((index + 1 + seed * 19.19 + channel) * 12.9898) * 43758.5453
            a = (first - math.floor(first)) * 2.0 - 1.0
            b = (second - math.floor(second)) * 2.0 - 1.0
            return a + (b - a) * fraction

        position_amount = float(params.get("position_amount", 8.0))
        rotation_amount = float(params.get("rotation_amount", 2.0))
        values["position"][0] += noise(cell, 3.1) * position_amount
        values["position"][1] += noise(cell, 7.7) * position_amount
        values["rotation"] = float(values.get("rotation", 0.0)) + noise(cell, 11.3) * rotation_amount


def apply_behaviors(values: MutableMapping[str, Any], behaviors: list[MotionBehaviorRef], time_ms: float) -> None:
    for behavior in behaviors:
        apply_behavior(values, behavior, time_ms)


def behavior_contract(kind: str) -> dict[str, Any]:
    normalized = str(kind or "").strip().lower()
    details = BEHAVIOR_CONTRACTS.get(normalized)
    return {
        "contract": BEHAVIOR_CONTRACT,
        "kind": normalized,
        "supported": details is not None,
        **(details or {}),
        "stack_order": "top_to_bottom_additive_transform",
        "deterministic": True,
    }
