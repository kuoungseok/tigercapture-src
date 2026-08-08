from __future__ import annotations

import math
import numbers
import operator


def positive_preview_dimension(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Painter preview {field} must be an integer, not bool")
    try:
        dimension = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter preview {field} must be an integer") from exc
    if dimension <= 0:
        raise ValueError(f"Painter preview {field} must be positive")
    return dimension


def scaled_preview_stroke_width(width_px: object, scale: object) -> float:
    if (
        isinstance(width_px, bool)
        or isinstance(scale, bool)
        or not isinstance(width_px, numbers.Real)
        or not isinstance(scale, numbers.Real)
    ):
        raise TypeError("Painter preview stroke width and scale must be real numbers")
    width = float(width_px)
    factor = float(scale)
    if not math.isfinite(width) or not math.isfinite(factor):
        raise ValueError("Painter preview stroke width and scale must be finite")
    if width <= 0.0 or factor <= 0.0:
        raise ValueError("Painter preview stroke width and scale must be positive")
    return width * factor
