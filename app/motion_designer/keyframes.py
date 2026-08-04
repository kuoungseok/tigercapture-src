"""Animated property evaluation."""
from __future__ import annotations

from .curves import cubic_bezier_progress, interpolate_value
from .schema import AnimatedProperty, Keyframe
from .spatial_interpolation import evaluate_spatial_segment, property_uses_spatial_bezier
from .temporal_interpolation import (
    evaluate_auto_progress,
    evaluate_auto_segment,
    segment_uses_auto,
)


DISCRETE_TYPES = {"bool", "enum", "string"}


def sorted_keyframes(prop: AnimatedProperty) -> list[Keyframe]:
    return sorted(prop.keyframes, key=lambda key: (key.time_ms, key.id))


def evaluate_property(prop: AnimatedProperty, time_ms: float):
    if not prop.enabled or not prop.keyframes:
        return prop.default
    keys = sorted_keyframes(prop)
    if time_ms <= keys[0].time_ms:
        return keys[0].value
    if time_ms >= keys[-1].time_ms:
        return keys[-1].value
    for segment_index, (left, right) in enumerate(zip(keys, keys[1:])):
        if left.time_ms <= time_ms <= right.time_ms:
            span = max(1.0, float(right.time_ms - left.time_ms))
            progress = (float(time_ms) - left.time_ms) / span
            interpolation = str(left.interpolation or "linear").lower()
            if interpolation == "hold" or prop.value_type in DISCRETE_TYPES:
                return left.value
            if (
                property_uses_spatial_bezier(prop.metadata)
                and isinstance(left.value, (list, tuple))
                and isinstance(right.value, (list, tuple))
            ):
                if segment_uses_auto(left, right):
                    progress = evaluate_auto_progress(keys, segment_index, progress)
                elif interpolation in {"bezier", "cubic", "cubic_bezier"}:
                    progress = cubic_bezier_progress(progress, left.out_tangent, right.in_tangent)
                return evaluate_spatial_segment(left, right, progress)
            if segment_uses_auto(left, right):
                value = evaluate_auto_segment(keys, segment_index, progress)
                if value is not None:
                    return value
            if interpolation in {"bezier", "cubic", "cubic_bezier"}:
                progress = cubic_bezier_progress(progress, left.out_tangent, right.in_tangent)
            return interpolate_value(left.value, right.value, progress)
    return keys[-1].value
