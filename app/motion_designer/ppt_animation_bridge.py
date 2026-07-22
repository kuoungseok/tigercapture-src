"""Loss-aware conversion between PPT animations and Motion behaviors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.pptgen.animations import animation_payload
from app.pptgen.schema import AnimationSpec

from .schema import MotionBehaviorRef, MotionLayer


_PPT_EFFECTS = {"appear", "fade_in", "fade_out", "move", "scale"}


def _effective_effect(payload: Mapping[str, Any]) -> tuple[str, str]:
    entrance = str(payload.get("in_animation") or "none")
    if entrance != "none":
        return entrance, "in"
    exit_effect = str(payload.get("out_animation") or "none")
    return (exit_effect, "out") if exit_effect != "none" else ("none", "in")


def behavior_from_ppt_animation(
    animation: AnimationSpec,
    *,
    width: int,
    height: int,
) -> tuple[MotionBehaviorRef | None, dict[str, Any]]:
    """Create one Motion preview behavior using the PPT runtime's effective effect."""
    payload = animation_payload(animation)
    effect, slot = _effective_effect(payload)
    if effect not in _PPT_EFFECTS:
        return None, payload

    start = max(0, int(payload["start_ms"]))
    duration = max(1, int(payload["duration_ms"]))
    common = {
        "easing": str(payload["easing"]),
        "ppt_effect": effect,
        "ppt_trigger": str(payload["trigger"]),
        "ppt_click_index": max(0, int(payload["click_index"])),
        "hold_before": True,
        "hold_after": True,
    }
    if effect in {"appear", "fade_in", "fade_out"}:
        behavior = MotionBehaviorRef(
            kind="fade",
            start_ms=start,
            end_ms=start + duration,
            params={
                **common,
                "direction": "out" if effect == "fade_out" else "in",
                "instant": effect == "appear",
            },
        )
    elif effect == "move":
        behavior = MotionBehaviorRef(
            kind="slide",
            start_ms=start,
            end_ms=start + duration,
            params={
                **common,
                "direction": "in",
                "distance": [
                    float(payload["motion_x"]) * max(1, int(width)),
                    float(payload["motion_y"]) * max(1, int(height)),
                ],
                "hide_before": True,
            },
        )
    else:
        behavior = MotionBehaviorRef(
            kind="scale",
            start_ms=start,
            end_ms=start + duration,
            params={**common, "from": float(payload["scale"]), "hide_before": True},
        )
    behavior.metadata = {
        "bridge": "ppt_animation",
        "ppt_effect_slot": slot,
        "ppt_animation": dict(payload),
    }
    return behavior, payload


def _effect_from_behavior(behavior: MotionBehaviorRef) -> str | None:
    kind = str(behavior.kind or "").strip().lower()
    params = behavior.params
    hinted = str(params.get("ppt_effect") or "").strip().lower()
    if kind == "fade":
        if hinted == "appear" and bool(params.get("instant", False)):
            return "appear"
        return "fade_out" if str(params.get("direction") or "in") == "out" else "fade_in"
    if kind == "slide" and str(params.get("direction") or "in") == "in":
        return "move"
    if kind == "scale":
        return "scale"
    return None


def animation_from_motion_layer(
    layer: MotionLayer,
    *,
    width: int,
    height: int,
) -> tuple[AnimationSpec, list[str]]:
    """Return a native PPT animation when the Motion behavior is representable."""
    enabled = [behavior for behavior in layer.behaviors if behavior.enabled]
    if not enabled:
        return AnimationSpec(), []
    if len(enabled) != 1:
        return AnimationSpec(), ["multiple motion behaviors require video bake for PPT export"]

    behavior = enabled[0]
    effect = _effect_from_behavior(behavior)
    if effect is None:
        return AnimationSpec(), [f"motion behavior '{behavior.kind}' requires video bake for PPT export"]

    original: dict[str, Any] = {}
    if behavior.metadata.get("bridge") == "ppt_animation":
        raw = behavior.metadata.get("ppt_animation")
        if isinstance(raw, Mapping):
            original = animation_payload(AnimationSpec.from_dict(dict(raw)))
    payload = animation_payload(AnimationSpec.from_dict(original)) if original else animation_payload(AnimationSpec())
    slot = str(behavior.metadata.get("ppt_effect_slot") or "in") if original else "in"
    if slot == "out":
        payload["out_animation"] = effect
        if not original:
            payload["in_animation"] = "none"
    else:
        payload["in_animation"] = effect

    payload["start_ms"] = max(0, int(behavior.start_ms))
    payload["duration_ms"] = max(1, int(behavior.end_ms) - int(behavior.start_ms))
    payload["end_ms"] = payload["start_ms"] + payload["duration_ms"]
    payload["trigger"] = str(behavior.params.get("ppt_trigger") or payload["trigger"])
    payload["click_index"] = max(0, int(behavior.params.get("ppt_click_index", payload["click_index"]) or 0))
    payload["easing"] = str(behavior.params.get("easing") or payload["easing"])
    if effect == "move":
        distance = list(behavior.params.get("distance") or [0.0, 0.0])
        distance.extend([0.0] * (2 - len(distance)))
        payload["motion_x"] = float(distance[0]) / max(1, int(width))
        payload["motion_y"] = float(distance[1]) / max(1, int(height))
    elif effect == "scale":
        payload["scale"] = float(behavior.params.get("from", payload["scale"]))
    return AnimationSpec.from_dict(payload), []


__all__ = ["animation_from_motion_layer", "behavior_from_ppt_animation"]
