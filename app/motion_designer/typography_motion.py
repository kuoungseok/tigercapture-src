"""Qt-free selector and stagger evaluation for animated typography."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
import unicodedata
from typing import Any, Mapping

from app.typo_animations import GlyphTransform, get_animation


@dataclass(frozen=True, slots=True)
class TextUnit:
    start: int
    end: int


def grapheme_spans(text: str) -> list[TextUnit]:
    """Return stable approximate grapheme spans without a GUI dependency."""
    spans: list[TextUnit] = []
    start = 0
    join_next = False
    for index, char in enumerate(text):
        combining = bool(unicodedata.combining(char)) or char in {"\ufe0e", "\ufe0f"}
        if index and not combining and not join_next and char != "\u200d":
            spans.append(TextUnit(start, index))
            start = index
        join_next = char == "\u200d"
    if text:
        spans.append(TextUnit(start, len(text)))
    return spans


def selector_units(text: str, unit: str) -> list[TextUnit]:
    mode = str(unit or "character").lower()
    if mode == "line":
        rows: list[TextUnit] = []
        start = 0
        for index, char in enumerate(text):
            if char == "\n":
                rows.append(TextUnit(start, index))
                start = index + 1
        rows.append(TextUnit(start, len(text)))
        return rows
    if mode == "word":
        rows = []
        start: int | None = None
        for index, char in enumerate(text):
            if char.isspace():
                if start is not None:
                    rows.append(TextUnit(start, index))
                    start = None
            elif start is None:
                start = index
        if start is not None:
            rows.append(TextUnit(start, len(text)))
        return rows
    return [span for span in grapheme_spans(text) if text[span.start:span.end] != "\n"]


def _selected_units(units: list[TextUnit], start: float, end: float) -> list[TextUnit]:
    if not units:
        return []
    first = max(0, min(len(units), floor(max(0.0, min(1.0, start)) * len(units))))
    last = max(first, min(len(units), ceil(max(0.0, min(1.0, end)) * len(units))))
    return units[first:last]


def _phase(config: Mapping[str, Any], time_ms: float, duration_ms: float) -> tuple[str, str, float, float]:
    duration = max(1.0, float(duration_ms))
    in_duration = max(0.0, float(config.get("in_duration_ms", 700.0) or 0.0))
    out_duration = max(0.0, float(config.get("out_duration_ms", 500.0) or 0.0))
    if in_duration + out_duration > duration:
        scale = duration / max(1.0, in_duration + out_duration)
        in_duration *= scale
        out_duration *= scale
    time = max(0.0, min(duration, float(time_ms)))
    if time < in_duration:
        return "in", str(config.get("in") or "none"), time, max(1.0, in_duration)
    if time >= duration - out_duration:
        return "out", str(config.get("out") or "none"), time - (duration - out_duration), max(1.0, out_duration)
    animation_id = str(config.get("hold") or "none")
    animation = get_animation(animation_id)
    period = max(1.0, float(config.get("hold_period_ms", animation.loop_period * 1000.0) or 1.0))
    return "hold", animation_id, (time - in_duration) % period, period


def _unit_transform(animation_id: str, progress: float, intensity: float,
                    order: int, count: int) -> GlyphTransform:
    animation = get_animation(animation_id)
    if animation.compute_perglyph is not None:
        values = animation.compute_perglyph(max(0.0, min(1.0, progress)), count, intensity)
        return values[order] if order < len(values) else GlyphTransform.identity()
    if animation.compute_whole is not None:
        value = animation.compute_whole(max(0.0, min(1.0, progress)), intensity)
        return GlyphTransform(
            opacity=value.opacity, scale_x=value.scale_x, scale_y=value.scale_y,
            offset_x=value.offset_x, offset_y=value.offset_y,
            rotation_deg=value.rotation_deg,
        )
    return GlyphTransform.identity()


def evaluate_glyph_motion(
    text: str,
    config: Mapping[str, Any] | None,
    time_ms: float,
    duration_ms: float,
) -> dict[int, GlyphTransform]:
    """Map source character indices to selector-aware glyph transforms."""
    config = config if isinstance(config, Mapping) else {}
    units = selector_units(text, str(config.get("unit") or "character"))
    selected = _selected_units(
        units, float(config.get("selector_start", 0.0) or 0.0),
        float(config.get("selector_end", 1.0) if config.get("selector_end", 1.0) is not None else 1.0),
    )
    if bool(config.get("reverse", False)):
        selected = list(reversed(selected))
    phase, animation_id, phase_time, phase_duration = _phase(config, time_ms, duration_ms)
    if animation_id == "none" or not selected:
        return {}
    stagger_ms = max(0.0, float(config.get("stagger_ms", 35.0) or 0.0))
    maximum_delay = stagger_ms * max(0, len(selected) - 1)
    active_duration = max(1.0, phase_duration - maximum_delay) if phase != "hold" else phase_duration
    intensity = max(0.0, float(config.get("intensity", 1.0) or 0.0))
    result: dict[int, GlyphTransform] = {}
    for order, unit in enumerate(selected):
        unit_time = phase_time - order * stagger_ms
        if phase == "hold":
            unit_time %= phase_duration
        progress = max(0.0, min(1.0, unit_time / active_duration))
        transform = _unit_transform(animation_id, progress, intensity, order, len(selected))
        for index in range(unit.start, unit.end):
            result[index] = transform
    return result
