"""Keyframed source-time remapping for Motion Designer layers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .keyframes import evaluate_property
from .schema import AnimatedProperty, Keyframe, MotionLayer

TIME_REMAP_KEY = "time_remap"
TIME_REMAP_CONTRACT = "tigerstudio.motion.time_remap.v1"


def layer_time_remap(layer: MotionLayer) -> AnimatedProperty | None:
    value = layer.metadata.get(TIME_REMAP_KEY)
    if not isinstance(value, Mapping) or not value.get("enabled", True):
        return None
    property_value = value.get("property")
    if not isinstance(property_value, Mapping):
        return None
    return AnimatedProperty.from_dict(property_value, value_type="scalar")


def set_layer_time_remap(
    layer: MotionLayer,
    keyframes: Sequence[Mapping[str, Any] | Keyframe],
    *,
    default: float = 0.0,
) -> AnimatedProperty:
    rows = [
        row if isinstance(row, Keyframe) else Keyframe.from_dict(row)
        for row in keyframes
    ]
    rows.sort(key=lambda row: (row.time_ms, row.id))
    if not rows:
        raise ValueError("Time Remap requires at least one keyframe")
    prop = AnimatedProperty(
        value_type="scalar",
        default=float(default),
        keyframes=rows,
    )
    layer.metadata[TIME_REMAP_KEY] = {
        "contract": TIME_REMAP_CONTRACT,
        "enabled": True,
        "property": prop.to_dict(),
    }
    return prop


def clear_layer_time_remap(layer: MotionLayer) -> bool:
    return layer.metadata.pop(TIME_REMAP_KEY, None) is not None


def apply_time_remap_preset(
    layer: MotionLayer,
    preset: str,
) -> AnimatedProperty:
    duration = max(1, layer.out_ms - layer.in_ms)
    source_start = float(layer.source_in_ms)
    source_end = source_start + duration * max(0.001, abs(layer.time_scale))
    name = str(preset or "linear").lower()
    if name == "freeze":
        rows = [
            Keyframe(time_ms=0, value=source_start, interpolation="hold"),
            Keyframe(time_ms=duration, value=source_start, interpolation="hold"),
        ]
    elif name == "reverse":
        rows = [
            Keyframe(time_ms=0, value=source_end),
            Keyframe(time_ms=duration, value=source_start),
        ]
    elif name == "speed_ramp":
        rows = [
            Keyframe(
                time_ms=0,
                value=source_start,
                out_tangent=(0.15, 0.0),
            ),
            Keyframe(
                time_ms=duration // 2,
                value=source_start + duration * 0.2,
                in_tangent=(0.7, 1.0),
                out_tangent=(0.25, 0.0),
            ),
            Keyframe(
                time_ms=duration,
                value=source_end,
                in_tangent=(0.75, 1.0),
            ),
        ]
    else:
        rows = [
            Keyframe(time_ms=0, value=source_start),
            Keyframe(time_ms=duration, value=source_end),
        ]
    return set_layer_time_remap(layer, rows, default=source_start)


def evaluate_layer_source_time(
    layer: MotionLayer,
    composition_time_ms: float,
) -> float | None:
    prop = layer_time_remap(layer)
    if prop is None:
        return None
    local_time = max(
        0.0,
        min(
            float(max(1, layer.out_ms - layer.in_ms)),
            float(composition_time_ms) - float(layer.in_ms),
        ),
    )
    return max(0.0, float(evaluate_property(prop, local_time) or 0.0))


def time_remap_diagnostics(layer: MotionLayer) -> dict[str, Any]:
    prop = layer_time_remap(layer)
    if prop is None:
        return {"enabled": False, "segments": []}
    segments = []
    rows = prop.keyframes
    for left, right in zip(rows, rows[1:]):
        delta_time = max(1, right.time_ms - left.time_ms)
        delta_source = float(right.value) - float(left.value)
        segments.append({
            "start_ms": left.time_ms,
            "end_ms": right.time_ms,
            "speed": delta_source / delta_time,
            "reverse": delta_source < 0,
            "freeze": abs(delta_source) < 1e-9,
            "hold": left.interpolation == "hold",
        })
    return {
        "enabled": True,
        "contract": TIME_REMAP_CONTRACT,
        "keyframe_count": len(rows),
        "segments": segments,
    }


__all__ = [
    "TIME_REMAP_CONTRACT",
    "TIME_REMAP_KEY",
    "apply_time_remap_preset",
    "clear_layer_time_remap",
    "evaluate_layer_source_time",
    "layer_time_remap",
    "set_layer_time_remap",
    "time_remap_diagnostics",
]
