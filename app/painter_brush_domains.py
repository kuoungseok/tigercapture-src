from __future__ import annotations

import math
import numbers
import operator
from collections.abc import Mapping

from app.painter_palette import MAX_BRUSH_PRESET_WIDTH_PX


BRUSH_HARDNESS_RANGE = (1, 100)
BRUSH_SPACING_RANGE = (1, 200)
BRUSH_ANGLE_RANGE = (-180, 180)
BRUSH_ROUNDNESS_RANGE = (10, 100)
BRUSH_PRESSURE_RESPONSE_RANGE = (25, 250)
BRUSH_WIDTH_RANGE_PX = (1.0, float(MAX_BRUSH_PRESET_WIDTH_PX))
BRUSH_WIDTH_DEFAULT_PX = 6.0
BRUSH_DETAIL_DEFAULTS = {
    "hardness": 100,
    "spacing": 25,
    "angle": 0,
    "roundness": 100,
    "pressure_response": 100,
    "flip_x": False,
    "flip_y": False,
}


def normalize_brush_detail_integer(value: object, *, field: str) -> int:
    domains = {
        "hardness": BRUSH_HARDNESS_RANGE,
        "spacing": BRUSH_SPACING_RANGE,
        "angle": BRUSH_ANGLE_RANGE,
        "roundness": BRUSH_ROUNDNESS_RANGE,
        "pressure_response": BRUSH_PRESSURE_RESPONSE_RANGE,
    }
    if field not in domains:
        raise KeyError(f"Unknown Painter brush detail field: {field}")
    if isinstance(value, bool):
        raise TypeError(f"Painter brush {field} must be an integer, not bool")
    try:
        integer = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter brush {field} must be an integer") from exc
    minimum, maximum = domains[field]
    return max(minimum, min(maximum, integer))


def normalize_brush_width_px(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError("Painter brush width must be a real number")
    width = float(value)
    if not math.isfinite(width):
        raise ValueError("Painter brush width must be finite")
    return max(BRUSH_WIDTH_RANGE_PX[0], min(BRUSH_WIDTH_RANGE_PX[1], width))


def normalize_brush_detail_settings(
    value: object,
    *,
    base: Mapping[str, object] | None = None,
) -> dict[str, int | bool]:
    if not isinstance(value, Mapping):
        raise TypeError("Painter brush detail settings must be an object")
    source = dict(BRUSH_DETAIL_DEFAULTS if base is None else base)
    source.update(value)
    result: dict[str, int | bool] = {}
    for field in (
        "hardness", "spacing", "angle", "roundness", "pressure_response"
    ):
        result[field] = normalize_brush_detail_integer(source[field], field=field)
    for field in ("flip_x", "flip_y"):
        if not isinstance(source[field], bool):
            raise TypeError(f"Painter brush {field} must be boolean")
        result[field] = source[field]
    return result
