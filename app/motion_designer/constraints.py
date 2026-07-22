"""Layer constraint evaluation helpers."""
from __future__ import annotations

import math
from typing import Any, Mapping, MutableMapping


def apply_look_at(values: MutableMapping[str, Any], target: Mapping[str, Any], *, offset_degrees: float = 0.0) -> None:
    position = values.get("position", [0.0, 0.0])
    target_position = target.get("position", [0.0, 0.0])
    dx = float(target_position[0]) - float(position[0])
    dy = float(target_position[1]) - float(position[1])
    values["rotation"] = math.degrees(math.atan2(dy, dx)) + float(offset_degrees)


def point_on_path(points: list[list[float]], progress: float) -> list[float]:
    if not points:
        return [0.0, 0.0]
    if len(points) == 1:
        return list(points[0][:2])
    p = max(0.0, min(1.0, float(progress))) * (len(points) - 1)
    index = min(len(points) - 2, int(p))
    local = p - index
    return [float(points[index][axis]) + (float(points[index + 1][axis]) - float(points[index][axis])) * local for axis in (0, 1)]
