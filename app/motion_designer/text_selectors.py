"""Versioned text range-selector evaluation.

The standard selector contract is intentionally separate from the original
Tiger selector.  Existing projects therefore keep their historical ordering
offset and animation-progress smoothing until an explicit conversion occurs.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import pi, sin
from typing import Any, Callable, Mapping, Sequence, TypeVar


STANDARD_RANGE_SELECTOR_CONTRACT = "standard_range_selector_v1"
LEGACY_TIGER_SELECTOR_CONTRACT = "legacy_tiger_selector_v1"

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SelectorWeight:
    unit: Any
    weight: float


def is_standard_selector(config: Mapping[str, Any] | None) -> bool:
    return str((config or {}).get("selector_contract") or "") == STANDARD_RANGE_SELECTOR_CONTRACT


def convert_legacy_selector(config: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return an explicit, non-mutating legacy-to-standard approximation."""
    converted = dict(config)
    legacy_unit = str(config.get("unit") or "character")
    converted.update({
        "selector_contract": STANDARD_RANGE_SELECTOR_CONTRACT,
        "selector_units": "percentage",
        "selector_based_on": {
            "character": "characters",
            "word": "words",
            "line": "lines",
        }.get(legacy_unit, "characters"),
        "selector_start": float(config.get("selector_start", 0.0) or 0.0) * 100.0,
        "selector_end": float(
            config.get("selector_end", 1.0)
            if config.get("selector_end", 1.0) is not None
            else 1.0
        ) * 100.0,
        "selector_offset": 0.0,
        "selector_smoothness": 0.0,
        "animation_smoothing": float(config.get("smoothness", 0.0) or 0.0),
        "selector_amount": float(config.get("selector_amount", 1.0) or 0.0) * 100.0,
        "selector_ease_high": 0.0,
        "selector_ease_low": 0.0,
        "selector_mode": "add",
    })
    converted.pop("smoothness", None)
    warnings: list[str] = []
    if abs(float(config.get("selector_offset", 0.0) or 0.0)) > 1e-9:
        warnings.append(
            "Legacy Order Offset rotated animation order and cannot be represented "
            "as a standard range offset; the converted offset is 0."
        )
    if float(config.get("smoothness", 0.0) or 0.0) != 0.0:
        warnings.append(
            "Legacy Smoothness affected animation progress; it was preserved as "
            "animation_smoothing rather than range-edge smoothness."
        )
    return converted, warnings


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _smoothstep(value: float) -> float:
    value = _clamp(value)
    return value * value * (3.0 - 2.0 * value)


def _selector_values(config: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    selectors = config.get("selectors")
    if isinstance(selectors, list):
        rows = [row for row in selectors if isinstance(row, Mapping) and row.get("enabled", True)]
        if rows:
            return rows
    return [config]


def _coordinate(index: int, count: int, units: str) -> tuple[float, float]:
    if units == "index":
        return index + 0.5, 1.0
    cell = 100.0 / max(1, count)
    return (index + 0.5) * cell, cell


def _shape_weight(
    coordinate: float,
    cell_width: float,
    selector: Mapping[str, Any],
) -> float:
    start = float(selector.get("selector_start", 0.0) or 0.0)
    end = float(
        selector.get("selector_end", 100.0)
        if selector.get("selector_end", 100.0) is not None
        else 100.0
    )
    offset = float(selector.get("selector_offset", 0.0) or 0.0)
    start += offset
    end += offset
    if end < start:
        start, end = end, start
    span = max(cell_width, end - start)
    shape = str(selector.get("selector_shape") or "square").lower()

    if shape == "square":
        smoothing = _clamp(float(selector.get("selector_smoothness", 100.0) or 0.0) / 100.0)
        if smoothing <= 1e-9:
            value = 1.0 if start <= coordinate <= end else 0.0
        else:
            feather = max(cell_width * 0.5, span * 0.5 * smoothing)
            enter = _smoothstep((coordinate - (start - feather)) / max(1e-9, feather * 2.0))
            leave = 1.0 - _smoothstep((coordinate - (end - feather)) / max(1e-9, feather * 2.0))
            value = min(enter, leave)
    else:
        position = _clamp((coordinate - start) / max(1e-9, end - start))
        inside = start <= coordinate <= end
        if not inside:
            value = 0.0
        elif shape == "ramp_up":
            value = position
        elif shape == "ramp_down":
            value = 1.0 - position
        elif shape == "triangle":
            value = 1.0 - abs(position * 2.0 - 1.0)
        elif shape == "round":
            value = sin(pi * position)
        elif shape == "smooth":
            value = sin(pi * position) ** 2
        else:
            value = 1.0

    ease_low = _clamp(float(selector.get("selector_ease_low", 0.0) or 0.0) / 100.0, -1.0, 1.0)
    ease_high = _clamp(float(selector.get("selector_ease_high", 0.0) or 0.0) / 100.0, -1.0, 1.0)
    value = _clamp(value)
    if value < 0.5:
        local = value * 2.0
        exponent = 2.0 ** ease_low
        value = 0.5 * (local ** exponent)
    else:
        local = (value - 0.5) * 2.0
        exponent = 2.0 ** (-ease_high)
        value = 0.5 + 0.5 * (local ** exponent)
    amount = _clamp(float(selector.get("selector_amount", 100.0) or 0.0) / 100.0)
    return _clamp(value * amount)


def _combine(current: float | None, value: float, mode: str) -> float:
    if current is None:
        return _clamp(1.0 - value) if mode == "subtract" else _clamp(value)
    if mode == "subtract":
        return _clamp(current - value)
    if mode == "intersect":
        return _clamp(current * value)
    return _clamp(current + value)


def evaluate_selector_weights(
    units: Sequence[T],
    config: Mapping[str, Any],
) -> list[tuple[T, float]]:
    """Evaluate ordered Add/Subtract/Intersect range selectors per text unit."""
    count = len(units)
    if count == 0:
        return []
    selectors = _selector_values(config)
    result: list[tuple[T, float]] = []
    for index, unit in enumerate(units):
        combined: float | None = None
        for selector in selectors:
            selector_units = str(selector.get("selector_units") or config.get("selector_units") or "percentage").lower()
            coordinate, cell_width = _coordinate(index, count, selector_units)
            value = _shape_weight(coordinate, cell_width, selector)
            mode = str(selector.get("selector_mode") or "add").lower()
            combined = _combine(combined, value, mode)
        result.append((unit, _clamp(combined or 0.0)))
    return result


def standard_units(
    text: str,
    based_on: str,
    *,
    grapheme_factory: Callable[[str], Sequence[T]],
    word_factory: Callable[[str], Sequence[T]],
    line_factory: Callable[[str], Sequence[T]],
) -> list[T]:
    mode = str(based_on or "characters").lower()
    if mode == "words":
        return list(word_factory(text))
    if mode == "lines":
        return list(line_factory(text))
    units = list(grapheme_factory(text))
    if mode == "characters_excluding_spaces":
        return [
            unit for unit in units
            if not text[int(getattr(unit, "start")):int(getattr(unit, "end"))].isspace()
        ]
    return units
