"""Geometry helpers for action-authored Painter strokes."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


_CHANNELS = ("pressure", "tilt", "rotation", "load")
_SIGNED_CHANNELS = ("tilt_x", "tilt_y", "tangential_pressure")


def smooth_action_points(
    points: Sequence[Mapping[str, Any]],
    *,
    samples_per_segment: int = 8,
    max_points: int = 512,
) -> list[dict[str, float]]:
    """Return a Catmull-Rom path with interpolated brush dynamics.

    Interactive tablet strokes already contain dense input points. AI/action
    strokes often describe a curve with only a few control points; rendering
    those controls as a polyline produces visible polygons and mechanical
    corners. This helper expands only those action-authored controls.
    """

    rows = [_normalized_point(point) for point in points]
    if len(rows) < 3:
        return rows
    segment_samples = max(2, min(24, int(samples_per_segment)))
    budget = max(len(rows), min(2048, int(max_points)))
    out: list[dict[str, float]] = []
    for index in range(len(rows) - 1):
        p0 = rows[max(0, index - 1)]
        p1 = rows[index]
        p2 = rows[index + 1]
        p3 = rows[min(len(rows) - 1, index + 2)]
        for sample in range(segment_samples):
            if len(out) >= budget - 1:
                break
            t = sample / float(segment_samples)
            row = {
                "x": _clamp01(_catmull(p0["x"], p1["x"], p2["x"], p3["x"], t)),
                "y": _clamp01(_catmull(p0["y"], p1["y"], p2["y"], p3["y"], t)),
            }
            for channel in _CHANNELS:
                row[channel] = _clamp01(
                    _catmull(
                        p0[channel],
                        p1[channel],
                        p2[channel],
                        p3[channel],
                        t,
                    )
                )
            for channel in _SIGNED_CHANNELS:
                row[channel] = _clamp_signed(
                    _catmull(
                        p0[channel],
                        p1[channel],
                        p2[channel],
                        p3[channel],
                        t,
                    )
                )
            if not out or _distance(out[-1], row) > 1e-7:
                out.append(row)
        if len(out) >= budget - 1:
            break
    if not out or _distance(out[-1], rows[-1]) > 1e-7:
        out.append(dict(rows[-1]))
    return out[:budget]


def _normalized_point(point: Mapping[str, Any]) -> dict[str, float]:
    row = {
        "x": _clamp01(float(point.get("x", 0.0))),
        "y": _clamp01(float(point.get("y", 0.0))),
    }
    for channel, default in (
        ("pressure", 0.82),
        ("tilt", 0.5),
        ("rotation", 0.5),
        ("load", 1.0),
    ):
        row[channel] = _clamp01(float(point.get(channel, default)))
    for channel in _SIGNED_CHANNELS:
        row[channel] = _clamp_signed(float(point.get(channel, 0.0)))
    return row


def _catmull(a: float, b: float, c: float, d: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * b)
        + (-a + c) * t
        + (2.0 * a - 5.0 * b + 4.0 * c - d) * t2
        + (-a + 3.0 * b - 3.0 * c + d) * t3
    )


def _distance(first: Mapping[str, float], second: Mapping[str, float]) -> float:
    return math.hypot(first["x"] - second["x"], first["y"] - second["y"])


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _clamp_signed(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


__all__ = ["smooth_action_points"]
