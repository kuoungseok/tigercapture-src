"""Neighbor-derived temporal interpolation for standard Auto tangents."""
from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from typing import Any

from .schema import Keyframe


TEMPORAL_AUTO_CONTRACT = "temporal_auto_monotone_v1"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _secant(left: Keyframe, right: Keyframe, component: int | None = None) -> float:
    duration = max(1.0, float(right.time_ms - left.time_ms))
    a = left.value if component is None else left.value[component]
    b = right.value if component is None else right.value[component]
    return (float(b) - float(a)) / duration


def _monotone_slope(keys: Sequence[Keyframe], index: int, component: int | None = None) -> float:
    if index <= 0:
        return _secant(keys[0], keys[1], component)
    if index >= len(keys) - 1:
        return _secant(keys[-2], keys[-1], component)
    previous = _secant(keys[index - 1], keys[index], component)
    following = _secant(keys[index], keys[index + 1], component)
    if previous == 0.0 or following == 0.0 or previous * following <= 0.0:
        return 0.0
    before = max(1.0, float(keys[index].time_ms - keys[index - 1].time_ms))
    after = max(1.0, float(keys[index + 1].time_ms - keys[index].time_ms))
    first_weight = 2.0 * after + before
    second_weight = after + 2.0 * before
    return (first_weight + second_weight) / (
        first_weight / previous + second_weight / following
    )


def _uses_auto(key: Keyframe) -> bool:
    return (
        str(key.metadata.get("tangent_contract") or "") == TEMPORAL_AUTO_CONTRACT
        or str(key.metadata.get("tangent_mode") or "") == "standard_auto"
    )


def _component_value(
    keys: Sequence[Keyframe],
    segment_index: int,
    progress: float,
    component: int | None = None,
) -> float:
    left = keys[segment_index]
    right = keys[segment_index + 1]
    a = left.value if component is None else left.value[component]
    b = right.value if component is None else right.value[component]
    duration = max(1.0, float(right.time_ms - left.time_ms))
    secant = _secant(left, right, component)
    left_slope = _monotone_slope(keys, segment_index, component) if _uses_auto(left) else secant
    right_slope = _monotone_slope(keys, segment_index + 1, component) if _uses_auto(right) else secant
    t = max(0.0, min(1.0, float(progress)))
    t2 = t * t
    t3 = t2 * t
    return (
        (2.0 * t3 - 3.0 * t2 + 1.0) * float(a)
        + (t3 - 2.0 * t2 + t) * duration * left_slope
        + (-2.0 * t3 + 3.0 * t2) * float(b)
        + (t3 - t2) * duration * right_slope
    )


def evaluate_auto_segment(
    keys: Sequence[Keyframe],
    segment_index: int,
    progress: float,
) -> Any:
    left = keys[segment_index].value
    right = keys[segment_index + 1].value
    if _is_number(left) and _is_number(right):
        return _component_value(keys, segment_index, progress)
    if (
        isinstance(left, (list, tuple))
        and isinstance(right, (list, tuple))
        and len(left) == len(right)
        and all(_is_number(value) for value in [*left, *right])
    ):
        return [
            _component_value(keys, segment_index, progress, component)
            for component in range(len(left))
        ]
    return None


def segment_uses_auto(left: Keyframe, right: Keyframe) -> bool:
    return _uses_auto(left) or _uses_auto(right)


def evaluate_auto_progress(
    keys: Sequence[Keyframe],
    segment_index: int,
    progress: float,
) -> float:
    """Evaluate temporal Auto against cumulative spatial distance."""
    distances = [0.0]
    for left, right in zip(keys, keys[1:]):
        if isinstance(left.value, (list, tuple)) and isinstance(right.value, (list, tuple)):
            size = min(len(left.value), len(right.value))
            distance = sqrt(sum(
                (float(right.value[index]) - float(left.value[index])) ** 2
                for index in range(size)
            ))
        else:
            distance = abs(float(right.value) - float(left.value))
        distances.append(distances[-1] + max(1e-9, distance))
    proxy = [
        Keyframe(
            id=key.id,
            time_ms=key.time_ms,
            value=distances[index],
            interpolation=key.interpolation,
            metadata=dict(key.metadata),
        )
        for index, key in enumerate(keys)
    ]
    value = float(evaluate_auto_segment(proxy, segment_index, progress))
    start = distances[segment_index]
    end = distances[segment_index + 1]
    return max(0.0, min(1.0, (value - start) / max(1e-9, end - start)))
