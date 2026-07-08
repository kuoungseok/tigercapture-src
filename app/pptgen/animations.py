"""Animation helpers for user PPT elements."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.pptgen.editing import find_element
from app.pptgen.schema import AnimationSpec, DeckSpec, SlideElement, SlideSpec


ANIMATION_TYPES = ("none", "appear", "fade_in", "fade_out", "move", "scale")
ANIMATION_TRIGGERS = ("on_slide_start", "on_click", "after_previous", "with_previous")
ANIMATION_EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out")


def clamp_ms(value: Any, *, default: int = 0, minimum: int = 0, maximum: int = 600_000) -> int:
    try:
        number = int(round(float(value)))
    except Exception:
        number = int(default)
    return max(int(minimum), min(int(maximum), number))


def normalize_animation_type(value: Any) -> str:
    raw = str(value or "none").strip().lower().replace("-", "_")
    aliases = {
        "fade": "fade_in",
        "fadein": "fade_in",
        "fade_out": "fade_out",
        "fadeout": "fade_out",
        "fly": "move",
        "fly_in": "move",
        "zoom": "scale",
        "zoom_in": "scale",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in ANIMATION_TYPES else "none"


def normalize_trigger(value: Any) -> str:
    raw = str(value or "on_slide_start").strip().lower().replace("-", "_")
    aliases = {
        "start": "on_slide_start",
        "with": "with_previous",
        "after": "after_previous",
        "click": "on_click",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in ANIMATION_TRIGGERS else "on_slide_start"


def normalize_easing(value: Any) -> str:
    raw = str(value or "ease_out").strip().lower().replace("-", "_")
    return raw if raw in ANIMATION_EASINGS else "ease_out"


def animation_duration_ms(animation: AnimationSpec) -> int:
    duration = clamp_ms(getattr(animation, "duration_ms", 0), default=0, minimum=0, maximum=60_000)
    if duration > 0:
        return duration
    start = clamp_ms(getattr(animation, "start_ms", 0), default=0)
    end = clamp_ms(getattr(animation, "end_ms", 0), default=0)
    return max(1, end - start) if end > start else 450


def animation_is_active(animation: AnimationSpec | None) -> bool:
    if animation is None:
        return False
    return normalize_animation_type(getattr(animation, "in_animation", "none")) != "none" or normalize_animation_type(
        getattr(animation, "out_animation", "none")
    ) != "none"


def animation_payload(animation: AnimationSpec) -> dict[str, Any]:
    duration = animation_duration_ms(animation)
    start = clamp_ms(animation.start_ms, default=0)
    try:
        click_index = max(0, int(getattr(animation, "click_index", 0) or 0))
    except Exception:
        click_index = 0
    return {
        "in_animation": normalize_animation_type(animation.in_animation),
        "out_animation": normalize_animation_type(animation.out_animation),
        "trigger": normalize_trigger(animation.trigger),
        "click_index": click_index,
        "start_ms": start,
        "duration_ms": duration,
        "end_ms": max(start + duration, clamp_ms(animation.end_ms, default=start + duration)),
        "easing": normalize_easing(animation.easing),
        "motion_x": float(animation.motion_x or 0.0),
        "motion_y": float(animation.motion_y or 0.0),
        "scale": float(animation.scale or 1.0),
    }


def animation_sequence_sort_key(element: SlideElement) -> tuple[int, int, int, str]:
    payload = animation_payload(element.animation)
    trigger = str(payload.get("trigger") or "on_slide_start")
    click_index = int(payload.get("click_index") or 0)
    return (
        0 if trigger == "on_click" else 1,
        click_index if trigger == "on_click" and click_index > 0 else 9999,
        int(payload.get("start_ms") or 0),
        element.id,
    )


def set_element_animation(
    deck: DeckSpec,
    element_id: str,
    *,
    slide_id: str = "",
    in_animation: Any = None,
    out_animation: Any = None,
    trigger: Any = None,
    start_ms: Any = None,
    duration_ms: Any = None,
    click_index: Any = None,
    easing: Any = None,
    motion_x: Any = None,
    motion_y: Any = None,
    scale: Any = None,
) -> tuple[SlideSpec, SlideElement]:
    slide, element = find_element(deck, element_id, slide_id=slide_id)
    if element.locked:
        raise RuntimeError(f"element is locked: {element.id}")
    current = animation_payload(element.animation)
    payload = dict(current)
    if in_animation is not None:
        payload["in_animation"] = normalize_animation_type(in_animation)
    if out_animation is not None:
        payload["out_animation"] = normalize_animation_type(out_animation)
    if trigger is not None:
        payload["trigger"] = normalize_trigger(trigger)
    if start_ms is not None:
        payload["start_ms"] = clamp_ms(start_ms, default=current["start_ms"])
    if duration_ms is not None:
        payload["duration_ms"] = clamp_ms(duration_ms, default=current["duration_ms"], minimum=1, maximum=60_000)
    if click_index is not None:
        payload["click_index"] = clamp_ms(click_index, default=current["click_index"], minimum=0, maximum=999)
    if easing is not None:
        payload["easing"] = normalize_easing(easing)
    if motion_x is not None:
        payload["motion_x"] = max(-1.0, min(1.0, float(motion_x)))
    if motion_y is not None:
        payload["motion_y"] = max(-1.0, min(1.0, float(motion_y)))
    if scale is not None:
        payload["scale"] = max(0.1, min(4.0, float(scale)))
    payload["end_ms"] = int(payload["start_ms"]) + int(payload["duration_ms"])
    element.animation = AnimationSpec.from_dict(payload)
    return slide, element


def update_element_animation_from_mapping(
    deck: DeckSpec,
    element_id: str,
    animation: Mapping[str, Any],
    *,
    slide_id: str = "",
) -> tuple[SlideSpec, SlideElement]:
    return set_element_animation(
        deck,
        element_id,
        slide_id=slide_id,
        in_animation=animation.get("in_animation"),
        out_animation=animation.get("out_animation"),
        trigger=animation.get("trigger"),
        start_ms=animation.get("start_ms"),
        duration_ms=animation.get("duration_ms"),
        click_index=animation.get("click_index"),
        easing=animation.get("easing"),
        motion_x=animation.get("motion_x"),
        motion_y=animation.get("motion_y"),
        scale=animation.get("scale"),
    )


__all__ = [
    "ANIMATION_EASINGS",
    "ANIMATION_TRIGGERS",
    "ANIMATION_TYPES",
    "animation_duration_ms",
    "animation_is_active",
    "animation_payload",
    "animation_sequence_sort_key",
    "normalize_animation_type",
    "set_element_animation",
    "update_element_animation_from_mapping",
]
