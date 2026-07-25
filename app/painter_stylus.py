"""Tablet/stylus dynamics shared by Painter input and renderers."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(0.0, min(1.0, float(default)))


def clamp_signed(value: Any, default: float = 0.0) -> float:
    try:
        return max(-1.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(-1.0, min(1.0, float(default)))


def _event_value(event: Any, name: str, default: float) -> float:
    value = getattr(event, name, None)
    if not callable(value):
        return float(default)
    try:
        return float(value())
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class StylusSample:
    pressure: float = 0.82
    tilt: float = 0.0
    tilt_x: float = 0.0
    tilt_y: float = 0.0
    rotation: float = 0.5
    tangential_pressure: float = 0.0
    load: float = 1.0


def mouse_stylus_sample() -> StylusSample:
    """Return stable dynamics for a mouse-authored stroke."""

    return StylusSample(pressure=1.0)


def tablet_stylus_sample(event: Any) -> StylusSample:
    """Normalize a Qt tablet event without depending on a specific device."""

    pressure = clamp01(_event_value(event, "pressure", 0.82), 0.82)
    tilt_x = clamp_signed(_event_value(event, "xTilt", 0.0) / 60.0)
    tilt_y = clamp_signed(_event_value(event, "yTilt", 0.0) / 60.0)
    tilt = clamp01(math.hypot(tilt_x, tilt_y) / math.sqrt(2.0))
    rotation_degrees = _event_value(event, "rotation", 180.0) % 360.0
    rotation = clamp01(rotation_degrees / 360.0, 0.5)
    tangential = clamp_signed(_event_value(event, "tangentialPressure", 0.0))
    return StylusSample(
        pressure=pressure,
        tilt=tilt,
        tilt_x=tilt_x,
        tilt_y=tilt_y,
        rotation=rotation,
        tangential_pressure=tangential,
    )


__all__ = [
    "StylusSample",
    "clamp01",
    "clamp_signed",
    "mouse_stylus_sample",
    "tablet_stylus_sample",
]
