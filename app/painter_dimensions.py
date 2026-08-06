"""Strict shared numeric boundaries for Painter raster and physical dimensions."""
from __future__ import annotations

import math
import numbers
import operator


def positive_integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Painter {field} must be an integer, not bool")
    try:
        resolved = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter {field} must be an integer") from exc
    if resolved <= 0:
        raise ValueError(f"Painter {field} must be positive")
    return resolved


def finite_real(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise TypeError(f"Painter {field} must be a real number, not bool")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"Painter {field} must be finite")
    return resolved


def positive_real(value: object, *, field: str) -> float:
    resolved = finite_real(value, field=field)
    if resolved <= 0.0:
        raise ValueError(f"Painter {field} must be positive")
    return resolved


def nonnegative_real(value: object, *, field: str) -> float:
    resolved = finite_real(value, field=field)
    if resolved < 0.0:
        raise ValueError(f"Painter {field} must be nonnegative")
    return resolved


__all__ = ["finite_real", "nonnegative_real", "positive_integer", "positive_real"]
