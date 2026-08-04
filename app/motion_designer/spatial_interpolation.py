"""Spatial Bezier path evaluation kept separate from temporal easing."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .schema import Keyframe


SPATIAL_BEZIER_CONTRACT = "spatial_bezier_path_v1"


def property_uses_spatial_bezier(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("spatial_interpolation") or "") == SPATIAL_BEZIER_CONTRACT


def _vector(value: Any, size: int) -> list[float]:
    values = list(value) if isinstance(value, (list, tuple)) else []
    return [float(values[index]) if index < len(values) else 0.0 for index in range(size)]


def evaluate_spatial_segment(left: Keyframe, right: Keyframe, progress: float) -> list[float]:
    start = list(left.value)
    end = list(right.value)
    size = min(len(start), len(end))
    outgoing = _vector(left.metadata.get("spatial_out_tangent"), size)
    incoming = _vector(right.metadata.get("spatial_in_tangent"), size)
    t = max(0.0, min(1.0, float(progress)))
    u = 1.0 - t
    result = []
    for index in range(size):
        p0 = float(start[index])
        p1 = p0 + outgoing[index]
        p3 = float(end[index])
        p2 = p3 + incoming[index]
        result.append(
            u * u * u * p0
            + 3.0 * u * u * t * p1
            + 3.0 * u * t * t * p2
            + t * t * t * p3
        )
    return result


def auto_spatial_tangents(keys: Sequence[Keyframe], index: int) -> tuple[list[float], list[float]]:
    current = list(keys[index].value)
    size = len(current)
    previous = list(keys[index - 1].value) if index > 0 else current
    following = list(keys[index + 1].value) if index + 1 < len(keys) else current
    direction = [
        (float(following[axis]) - float(previous[axis])) / 6.0
        for axis in range(size)
    ]
    return ([-value for value in direction], direction)
