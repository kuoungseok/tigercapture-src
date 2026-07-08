"""Qt-free runtime helpers for previewing PPT element animations."""
from __future__ import annotations

from dataclasses import dataclass

from app.pptgen.animations import animation_payload
from app.pptgen.schema import SlideElement


@dataclass(frozen=True)
class AnimationRenderState:
    visible: bool = True
    opacity: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale: float = 1.0

    def to_dict(self) -> dict[str, float | bool]:
        return {
            "visible": bool(self.visible),
            "opacity": float(self.opacity),
            "offset_x": float(self.offset_x),
            "offset_y": float(self.offset_y),
            "scale": float(self.scale),
        }


def ease_progress(value: float, easing: str = "ease_out") -> float:
    t = max(0.0, min(1.0, float(value)))
    mode = str(easing or "ease_out").lower()
    if mode == "linear":
        return t
    if mode == "ease_in":
        return t * t
    if mode == "ease_in_out":
        return 3.0 * t * t - 2.0 * t * t * t
    return 1.0 - (1.0 - t) * (1.0 - t)


def static_animation_state(element: SlideElement) -> AnimationRenderState:
    return AnimationRenderState(
        visible=True,
        opacity=max(0.0, min(1.0, float(element.opacity))),
        offset_x=0.0,
        offset_y=0.0,
        scale=1.0,
    )


def element_animation_state(element: SlideElement, local_ms: int | None) -> AnimationRenderState:
    if local_ms is None:
        return static_animation_state(element)
    payload = animation_payload(element.animation)
    effect = str(payload["in_animation"])
    if effect == "none":
        effect = str(payload.get("out_animation") or "none")
    if effect == "none":
        return static_animation_state(element)

    opacity = max(0.0, min(1.0, float(element.opacity)))
    start = int(payload["start_ms"])
    duration = max(1, int(payload["duration_ms"]))
    local = max(0, int(local_ms or 0))
    if local < start:
        if effect in {"appear", "fade_in", "move", "scale"}:
            return AnimationRenderState(visible=False, opacity=0.0)
        return static_animation_state(element)

    progress = ease_progress((local - start) / duration, str(payload["easing"]))
    if effect == "appear":
        return AnimationRenderState(visible=True, opacity=opacity)
    if effect == "fade_in":
        return AnimationRenderState(visible=True, opacity=opacity * progress)
    if effect == "fade_out":
        faded_opacity = opacity * max(0.0, 1.0 - progress)
        return AnimationRenderState(visible=faded_opacity > 0.01, opacity=faded_opacity)
    if effect == "move":
        return AnimationRenderState(
            visible=True,
            opacity=opacity,
            offset_x=float(payload["motion_x"]) * (1.0 - progress),
            offset_y=float(payload["motion_y"]) * (1.0 - progress),
        )
    if effect == "scale":
        start_scale = float(payload["scale"])
        scale = start_scale + (1.0 - start_scale) * progress
        return AnimationRenderState(visible=True, opacity=opacity, scale=max(0.01, scale))
    return static_animation_state(element)


def animated_rect(
    rect: tuple[int, int, int, int],
    slide_size: tuple[int, int],
    state: AnimationRenderState,
) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    slide_w, slide_h = slide_size
    x += int(round(float(state.offset_x) * max(1, slide_w)))
    y += int(round(float(state.offset_y) * max(1, slide_h)))
    scale = float(state.scale)
    if abs(scale - 1.0) > 0.001:
        cx = x + w * 0.5
        cy = y + h * 0.5
        w = max(1, int(round(w * scale)))
        h = max(1, int(round(h * scale)))
        x = int(round(cx - w * 0.5))
        y = int(round(cy - h * 0.5))
    return x, y, max(1, w), max(1, h)


__all__ = [
    "AnimationRenderState",
    "animated_rect",
    "ease_progress",
    "element_animation_state",
    "static_animation_state",
]
