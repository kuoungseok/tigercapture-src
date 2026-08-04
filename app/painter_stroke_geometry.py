"""Geometry helpers for action-authored Painter strokes."""
from __future__ import annotations

import math
import operator
from typing import Any, Mapping, Sequence


_CHANNELS = ("pressure", "tilt", "rotation", "load")
_SIGNED_CHANNELS = ("tilt_x", "tilt_y", "tangential_pressure")

ACTION_STROKE_SAMPLING_MODEL_CONTRACT = {
    "schema": "tigerstudio.painter.action_stroke_sampling_model.v1",
    "model": "tiger_authored_catmull_rom_action_path_v1",
    "defaults": {"samples_per_segment": 8, "max_points": 512},
    "caller_requested_point_budget_preserved": True,
    "source_control_points_preserved": True,
    "interior_samples_distributed_across_complete_path": True,
    "tablet_input_model_claim": False,
    "external_brush_path_parity_claim": False,
}


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

    try:
        segment_samples = operator.index(samples_per_segment)
        requested_budget = operator.index(max_points)
    except TypeError as exc:
        raise ValueError("samples_per_segment and max_points must be integers") from exc
    rows = [_normalized_point(point) for point in points]
    if len(rows) < 3:
        return rows
    segment_samples = max(2, min(24, segment_samples))
    budget = max(len(rows), requested_budget)
    segment_count = len(rows) - 1
    interior_budget = min(
        budget - len(rows),
        segment_count * (segment_samples - 1),
    )
    out: list[dict[str, float]] = [dict(rows[0])]
    for index in range(segment_count):
        p0 = rows[max(0, index - 1)]
        p1 = rows[index]
        p2 = rows[index + 1]
        p3 = rows[min(len(rows) - 1, index + 2)]
        previous_quota = (index * interior_budget) // segment_count
        current_quota = ((index + 1) * interior_budget) // segment_count
        segment_interior_count = current_quota - previous_quota
        for sample in range(1, segment_interior_count + 1):
            t = sample / float(segment_interior_count + 1)
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
        out.append(dict(p2))
    return out[:budget]


def _normalized_point(point: Mapping[str, Any]) -> dict[str, float]:
    def finite(channel: str, default: float) -> float:
        value = float(point.get(channel, default))
        if not math.isfinite(value):
            raise ValueError(f"{channel} must be finite")
        return value

    row = {
        "x": _clamp01(finite("x", 0.0)),
        "y": _clamp01(finite("y", 0.0)),
    }
    for channel, default in (
        ("pressure", 1.0),
        ("tilt", 0.5),
        ("rotation", 0.5),
        ("load", 1.0),
    ):
        row[channel] = _clamp01(finite(channel, default))
    for channel in _SIGNED_CHANNELS:
        row[channel] = _clamp_signed(finite(channel, 0.0))
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
