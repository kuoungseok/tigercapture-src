"""Geometry for snapping Painter strokes to editable perspective rulers."""
from __future__ import annotations

import math
from typing import Iterable, Mapping


def _unit(vector: tuple[float, float]) -> tuple[float, float] | None:
    length = math.hypot(float(vector[0]), float(vector[1]))
    if length == 0.0:
        return None
    return float(vector[0]) / length, float(vector[1]) / length


def perspective_directions(
    anchor: tuple[float, float],
    width: int,
    height: int,
    state: Mapping[str, object],
) -> list[tuple[str, tuple[float, float]]]:
    """Return ruler directions in document-pixel space for 1/2/3-point modes."""
    mode = max(1, min(3, int(state.get("mode", 2) or 2)))
    ax, ay = float(anchor[0]), float(anchor[1])

    def toward(name: str, key: str) -> tuple[str, tuple[float, float]] | None:
        raw = list(state.get(key) or [])
        if len(raw) < 2:
            return None
        direction = _unit((float(raw[0]) * width - ax, float(raw[1]) * height - ay))
        return (name, direction) if direction is not None else None

    candidates: list[tuple[str, tuple[float, float]] | None]
    if mode == 1:
        candidates = [
            toward("center_vp", "center_vp"),
            ("horizontal", (1.0, 0.0)),
            ("vertical", (0.0, 1.0)),
        ]
    elif mode == 2:
        candidates = [
            toward("left_vp", "left_vp"),
            toward("right_vp", "right_vp"),
            ("vertical", (0.0, 1.0)),
        ]
    else:
        candidates = [
            toward("left_vp", "left_vp"),
            toward("right_vp", "right_vp"),
            toward("vertical_vp", "vertical_vp"),
        ]
    return [row for row in candidates if row is not None]


def choose_perspective_direction(
    anchor: tuple[float, float],
    point: tuple[float, float],
    directions: Iterable[tuple[str, tuple[float, float]]],
) -> tuple[str, tuple[float, float]] | None:
    motion = _unit((float(point[0]) - float(anchor[0]), float(point[1]) - float(anchor[1])))
    if motion is None:
        return None
    rows = list(directions)
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: abs(motion[0] * row[1][0] + motion[1] * row[1][1]),
    )


def project_to_direction(
    anchor: tuple[float, float],
    point: tuple[float, float],
    direction: tuple[float, float],
) -> tuple[float, float]:
    unit = _unit(direction)
    if unit is None:
        return float(anchor[0]), float(anchor[1])
    dx = float(point[0]) - float(anchor[0])
    dy = float(point[1]) - float(anchor[1])
    distance = dx * unit[0] + dy * unit[1]
    return (
        float(anchor[0]) + distance * unit[0],
        float(anchor[1]) + distance * unit[1],
    )


__all__ = [
    "choose_perspective_direction",
    "perspective_directions",
    "project_to_direction",
]
