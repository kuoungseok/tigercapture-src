"""Qt-free selector and stagger evaluation for animated typography."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, pi, sin
import random
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
                    order: int, count: int, smoothness: float = 0.0) -> GlyphTransform:
    amount = max(0.0, min(1.0, float(progress)))
    smooth = max(0.0, min(1.0, float(smoothness)))
    eased = amount * amount * (3.0 - 2.0 * amount)
    progress = amount + (eased - amount) * smooth
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


def _ordered_units(
    units: list[TextUnit],
    config: Mapping[str, Any],
) -> list[TextUnit]:
    rows = list(units)
    offset = float(config.get("selector_offset", 0.0) or 0.0)
    if rows and abs(offset) > 1e-9:
        shift = int(round(offset * len(rows))) % len(rows)
        rows = [*rows[shift:], *rows[:shift]]
    if bool(config.get("randomize_order", False)):
        random.Random(int(config.get("random_seed", 0) or 0)).shuffle(rows)
    elif bool(config.get("ping_pong", False)) and len(rows) > 2:
        rows = [
            rows[index // 2] if index % 2 == 0 else rows[-(index // 2) - 1]
            for index in range(len(rows))
        ]
    if bool(config.get("reverse", False)):
        rows.reverse()
    return rows


def _property_transform(config: Mapping[str, Any]) -> GlyphTransform:
    properties = config.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    position = list(properties.get("position") or [0.0, 0.0])
    scale = list(properties.get("scale") or [1.0, 1.0])
    while len(position) < 2:
        position.append(0.0)
    while len(scale) < 2:
        scale.append(scale[0] if scale else 1.0)
    if max(abs(float(scale[0])), abs(float(scale[1]))) > 10.0:
        scale = [float(scale[0]) / 100.0, float(scale[1]) / 100.0]
    fill = properties.get("fill")
    return GlyphTransform(
        opacity=max(0.0, min(1.0, float(properties.get("opacity", 1.0) or 0.0))),
        scale_x=float(scale[0]),
        scale_y=float(scale[1]),
        offset_x=float(position[0]),
        offset_y=float(position[1]),
        rotation_deg=float(properties.get("rotation", 0.0) or 0.0),
        tracking=float(properties.get("tracking", 0.0) or 0.0),
        blur_px=max(0.0, float(properties.get("blur", 0.0) or 0.0)),
        color_override=str(fill) if fill else None,
    )


def _merge_transform(left: GlyphTransform, right: GlyphTransform) -> GlyphTransform:
    return GlyphTransform(
        opacity=left.opacity * right.opacity,
        scale_x=left.scale_x * right.scale_x,
        scale_y=left.scale_y * right.scale_y,
        offset_x=left.offset_x + right.offset_x,
        offset_y=left.offset_y + right.offset_y,
        rotation_deg=left.rotation_deg + right.rotation_deg,
        tracking=left.tracking + right.tracking,
        blur_px=max(left.blur_px, right.blur_px),
        pivot_x=right.pivot_x if right.pivot_x != 0.5 else left.pivot_x,
        pivot_y=right.pivot_y if right.pivot_y != 0.5 else left.pivot_y,
        color_override=right.color_override or left.color_override,
    )


def _selector_influence(
    order: int,
    count: int,
    config: Mapping[str, Any],
) -> float:
    position = (order + 0.5) / max(1, count)
    shape = str(config.get("selector_shape") or "square").lower()
    if shape == "ramp_up":
        value = position
    elif shape == "ramp_down":
        value = 1.0 - position
    elif shape == "triangle":
        value = 1.0 - abs(position * 2.0 - 1.0)
    elif shape == "round":
        value = sin(pi * position)
    else:
        value = 1.0
    amount = max(0.0, min(1.0, float(config.get("selector_amount", 1.0) or 0.0)))
    return max(0.0, min(1.0, value * amount))


def _weighted_transform(transform: GlyphTransform, weight: float) -> GlyphTransform:
    amount = max(0.0, min(1.0, float(weight)))
    return GlyphTransform(
        opacity=1.0 + (transform.opacity - 1.0) * amount,
        scale_x=1.0 + (transform.scale_x - 1.0) * amount,
        scale_y=1.0 + (transform.scale_y - 1.0) * amount,
        offset_x=transform.offset_x * amount,
        offset_y=transform.offset_y * amount,
        rotation_deg=transform.rotation_deg * amount,
        tracking=transform.tracking * amount,
        blur_px=transform.blur_px * amount,
        pivot_x=transform.pivot_x,
        pivot_y=transform.pivot_y,
        color_override=transform.color_override if amount > 1e-6 else None,
    )


def _evaluate_single_animator(
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
    selected = _ordered_units(selected, config)
    phase, animation_id, phase_time, phase_duration = _phase(config, time_ms, duration_ms)
    properties = config.get("properties")
    has_properties = isinstance(properties, Mapping) and bool(properties)
    if (animation_id == "none" and not has_properties) or not selected:
        return {}
    stagger_ms = max(0.0, float(config.get("stagger_ms", 35.0) or 0.0))
    maximum_delay = stagger_ms * max(0, len(selected) - 1)
    active_duration = max(1.0, phase_duration - maximum_delay) if phase != "hold" else phase_duration
    intensity = max(0.0, float(config.get("intensity", 1.0) or 0.0))
    smoothness = max(0.0, min(1.0, float(config.get("smoothness", 0.0) or 0.0)))
    property_transform = _property_transform(config)
    result: dict[int, GlyphTransform] = {}
    for order, unit in enumerate(selected):
        unit_time = phase_time - order * stagger_ms
        if phase == "hold":
            unit_time %= phase_duration
        progress = max(0.0, min(1.0, unit_time / active_duration))
        transform = (
            _unit_transform(
                animation_id,
                progress,
                intensity,
                order,
                len(selected),
                smoothness,
            )
            if animation_id != "none"
            else GlyphTransform.identity()
        )
        if has_properties:
            transform = _merge_transform(transform, property_transform)
        transform = _weighted_transform(
            transform,
            _selector_influence(order, len(selected), config),
        )
        for index in range(unit.start, unit.end):
            result[index] = transform
    return result


def evaluate_glyph_motion(
    text: str,
    config: Mapping[str, Any] | None,
    time_ms: float,
    duration_ms: float,
) -> dict[int, GlyphTransform]:
    """Evaluate a legacy animator or a composited animator stack."""
    config = config if isinstance(config, Mapping) else {}
    animators = config.get("animators")
    if not isinstance(animators, list):
        return _evaluate_single_animator(text, config, time_ms, duration_ms)
    result: dict[int, GlyphTransform] = {}
    for animator in animators:
        if not isinstance(animator, Mapping) or not animator.get("enabled", True):
            continue
        current = _evaluate_single_animator(text, animator, time_ms, duration_ms)
        for index, transform in current.items():
            result[index] = _merge_transform(
                result.get(index, GlyphTransform.identity()),
                transform,
            )
    return result
