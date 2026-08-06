from __future__ import annotations

import math
import numbers
import operator


PAINTER_ZOOM_MIN_PERCENT = 25
PAINTER_ZOOM_MAX_PERCENT = 800
PAINTER_ZOOM_DEFAULT_PERCENT = 100
PAINTER_ZOOM_MIN_FACTOR = PAINTER_ZOOM_MIN_PERCENT / 100.0
PAINTER_ZOOM_MAX_FACTOR = PAINTER_ZOOM_MAX_PERCENT / 100.0
PAINTER_ZOOM_DEFAULT_FACTOR = PAINTER_ZOOM_DEFAULT_PERCENT / 100.0


def normalize_painter_zoom_percent(value: object) -> int:
    """Return a strict integer Painter zoom clamped to the product domain."""

    if isinstance(value, bool):
        raise TypeError("Painter zoom percent must be an integer, not bool")
    try:
        percent = operator.index(value)
    except TypeError as exc:
        raise TypeError("Painter zoom percent must be an integer") from exc
    return max(PAINTER_ZOOM_MIN_PERCENT, min(PAINTER_ZOOM_MAX_PERCENT, percent))


def normalize_painter_zoom_factor(value: object) -> float:
    """Return a finite Painter zoom factor clamped to the product domain."""

    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError("Painter zoom factor must be a real number, not bool")
    try:
        factor = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError("Painter zoom factor must be a real number") from exc
    if not math.isfinite(factor):
        raise ValueError("Painter zoom factor must be finite")
    return max(PAINTER_ZOOM_MIN_FACTOR, min(PAINTER_ZOOM_MAX_FACTOR, factor))
