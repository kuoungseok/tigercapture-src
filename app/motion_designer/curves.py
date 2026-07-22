"""Deterministic interpolation curve helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Sequence


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def easing_progress(value: float, easing: str = "ease_out") -> float:
    """Evaluate the named easing shared by PPT and Motion bridge behaviors."""
    t = clamp01(value)
    mode = str(easing or "ease_out").strip().lower()
    if mode == "linear":
        return t
    if mode == "ease_in":
        return t * t
    if mode == "ease_in_out":
        return 3.0 * t * t - 2.0 * t * t * t
    return 1.0 - (1.0 - t) * (1.0 - t)


def cubic_bezier_coordinate(t: float, p1: float, p2: float) -> float:
    u = 1.0 - t
    return 3.0 * u * u * t * p1 + 3.0 * u * t * t * p2 + t * t * t


def cubic_bezier_progress(progress: float, out_tangent: Sequence[float], in_tangent: Sequence[float]) -> float:
    """Solve x(t)=progress and return y(t) for a unit cubic Bezier."""
    x = clamp01(progress)
    x1, y1 = float(out_tangent[0]), float(out_tangent[1])
    x2, y2 = float(in_tangent[0]), float(in_tangent[1])
    low, high, t = 0.0, 1.0, x
    for _ in range(18):
        sampled = cubic_bezier_coordinate(t, x1, x2)
        if abs(sampled - x) < 1e-7:
            break
        if sampled < x:
            low = t
        else:
            high = t
        t = (low + high) * 0.5
    return clamp01(cubic_bezier_coordinate(t, y1, y2))


def interpolate_value(start: Any, end: Any, amount: float) -> Any:
    t = clamp01(amount)
    if isinstance(start, bool) or isinstance(end, bool):
        return start if t < 1.0 else end
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        return float(start) + (float(end) - float(start)) * t
    if isinstance(start, (list, tuple)) and isinstance(end, (list, tuple)):
        size = min(len(start), len(end))
        return [interpolate_value(start[index], end[index], t) for index in range(size)]
    if isinstance(start, Mapping) and isinstance(end, Mapping):
        keys = set(start) | set(end)
        return {
            key: interpolate_value(start.get(key), end.get(key), t)
            if key in start and key in end else start.get(key, end.get(key))
            for key in keys
        }
    return start if t < 1.0 else end
