"""Ephemeral interactive drivers for Tiger Glass preview rendering."""
from __future__ import annotations

from collections.abc import Mapping
from .keyframes import evaluate_property
from .schema import MotionEffectRef


GLASS_DRIVER_SOURCES = frozenset({"manual", "pointer", "velocity", "scroll"})


def _animated_value(effect: MotionEffectRef, name: str, time_ms: float) -> float:
    value = effect.params.get(name)
    try:
        return float(evaluate_property(value, time_ms) if value is not None else 0.0)
    except (TypeError, ValueError):
        return 0.0


def resolve_glass_driver(
    effect: MotionEffectRef,
    runtime_inputs: Mapping[str, tuple[float, float]] | None = None,
    *,
    time_ms: float = 0.0,
) -> tuple[float, float] | None:
    """Resolve a preview-only driver without mutating the serialized effect."""
    driver = effect.metadata.get("driver")
    if not isinstance(driver, Mapping):
        return None
    source = str(driver.get("source") or "manual").strip().lower()
    if source not in GLASS_DRIVER_SOURCES:
        source = "manual"
    try:
        strength = max(0.0, min(10.0, float(driver.get("strength", 1.0))))
    except (TypeError, ValueError):
        strength = 1.0
    base_x = _animated_value(effect, "driver_x", time_ms)
    base_y = _animated_value(effect, "driver_y", time_ms)
    live_x = live_y = 0.0
    if source != "manual" and runtime_inputs is not None:
        raw = runtime_inputs.get(source, (0.0, 0.0))
        if isinstance(raw, (tuple, list)) and len(raw) >= 2:
            try:
                live_x, live_y = float(raw[0]), float(raw[1])
            except (TypeError, ValueError):
                live_x = live_y = 0.0
    return (
        max(-10.0, min(10.0, base_x + live_x * strength)),
        max(-10.0, min(10.0, base_y + live_y * strength)),
    )


__all__ = ["GLASS_DRIVER_SOURCES", "resolve_glass_driver"]
