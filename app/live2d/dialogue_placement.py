"""Live2D placement helpers for AI dialogue takes.

The dialogue-take path needs a broadcast-friendly default: a character anchored
near the lower corner without assuming the model shows a full body.  The helper
measures the visible alpha bounds of a rendered frame when possible, then maps
that measured rectangle into a preset safe area.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


DIALOGUE_PLACEMENT_SCHEMA = "tigerstudio.live2d.dialogue_placement.v1"


PLACEMENT_PRESETS: dict[str, dict[str, Any]] = {
    "bottom_right": {
        "id": "bottom_right",
        "label": "Bottom Right",
        "recommended": True,
        "anchor_x": "right",
        "anchor_y": "bottom",
        "center_x": 0.84,
        "bottom_y": 0.998,
        "target_width": 0.30,
        "target_height": 0.72,
        "safe_margin_x": 0.015,
        "safe_margin_y": 0.000,
    },
    "bottom_left": {
        "id": "bottom_left",
        "label": "Bottom Left",
        "anchor_x": "left",
        "anchor_y": "bottom",
        "center_x": 0.22,
        "bottom_y": 0.998,
        "target_width": 0.30,
        "target_height": 0.72,
        "safe_margin_x": 0.035,
        "safe_margin_y": 0.000,
    },
    "center_bottom": {
        "id": "center_bottom",
        "label": "Center Bottom",
        "anchor_x": "center",
        "anchor_y": "bottom",
        "center_x": 0.50,
        "bottom_y": 0.998,
        "target_width": 0.34,
        "target_height": 0.76,
        "safe_margin_x": 0.035,
        "safe_margin_y": 0.000,
    },
    "talking_head": {
        "id": "talking_head",
        "label": "Talking Head",
        "anchor_x": "right",
        "anchor_y": "bottom",
        "center_x": 0.80,
        "bottom_y": 1.000,
        "target_width": 0.38,
        "target_height": 0.86,
        "safe_margin_x": 0.025,
        "safe_margin_y": 0.000,
    },
    "large_reaction": {
        "id": "large_reaction",
        "label": "Large Reaction",
        "anchor_x": "right",
        "anchor_y": "bottom",
        "center_x": 0.74,
        "bottom_y": 1.015,
        "target_width": 0.44,
        "target_height": 0.98,
        "safe_margin_x": 0.020,
        "safe_margin_y": -0.015,
    },
}


SIZE_PRESETS: dict[str, dict[str, Any]] = {
    "auto_fit": {"id": "auto_fit", "label": "Auto Fit", "width_mul": 1.0, "height_mul": 1.0, "recommended": True},
    "bust_up": {"id": "bust_up", "label": "Bust Up", "width_mul": 1.20, "height_mul": 1.18},
    "half_body": {"id": "half_body", "label": "Half Body", "width_mul": 1.05, "height_mul": 1.05},
    "full_body": {"id": "full_body", "label": "Full Body", "width_mul": 0.88, "height_mul": 0.95},
    "custom": {"id": "custom", "label": "Custom", "width_mul": 1.0, "height_mul": 1.0},
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def placement_preset_options() -> list[dict[str, Any]]:
    return [dict(row) for row in PLACEMENT_PRESETS.values()]


def size_preset_options() -> list[dict[str, Any]]:
    return [dict(row) for row in SIZE_PRESETS.values()]


def normalize_placement_preset(value: str | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        raw_id = str(value.get("id") or value.get("preset") or "bottom_right").strip().casefold()
        base = dict(PLACEMENT_PRESETS.get(raw_id) or PLACEMENT_PRESETS["bottom_right"])
        base.update(dict(value))
        base["id"] = raw_id if raw_id in PLACEMENT_PRESETS else str(base.get("id") or "custom")
        return base
    key = str(value or "bottom_right").strip().casefold()
    return dict(PLACEMENT_PRESETS.get(key) or PLACEMENT_PRESETS["bottom_right"])


def normalize_size_preset(value: str | Mapping[str, Any] | None) -> dict[str, Any]:
    if isinstance(value, Mapping):
        raw_id = str(value.get("id") or value.get("preset") or "auto_fit").strip().casefold()
        base = dict(SIZE_PRESETS.get(raw_id) or SIZE_PRESETS["auto_fit"])
        base.update(dict(value))
        base["id"] = raw_id if raw_id in SIZE_PRESETS else str(base.get("id") or "custom")
        return base
    key = str(value or "auto_fit").strip().casefold()
    return dict(SIZE_PRESETS.get(key) or SIZE_PRESETS["auto_fit"])


def alpha_bounds(image: Any) -> dict[str, Any]:
    """Return visible alpha bounds for a PIL-like RGBA image."""
    if image is None:
        return {"ok": False, "reason": "no_image"}
    try:
        width = int(image.width)
        height = int(image.height)
        alpha = image.getchannel("A") if getattr(image, "mode", "") == "RGBA" else image.convert("RGBA").getchannel("A")
        bbox = alpha.getbbox()
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    if bbox is None:
        return {"ok": False, "reason": "blank_alpha", "image_size": [width, height]}
    left, top, right, bottom = [int(v) for v in bbox]
    return {
        "ok": True,
        "bbox": [left, top, right, bottom],
        "image_size": [width, height],
        "width": max(1, right - left),
        "height": max(1, bottom - top),
        "center": [(left + right) / 2.0, (top + bottom) / 2.0],
        "bottom": bottom,
        "right": right,
    }


def fallback_transform_for_preset(
    *,
    preset: str | Mapping[str, Any] | None = "bottom_right",
    size_preset: str | Mapping[str, Any] | None = "auto_fit",
) -> dict[str, float]:
    """Predictable fallback when a Live2D frame cannot be measured."""
    p = normalize_placement_preset(preset)
    s = normalize_size_preset(size_preset)
    scale = 1.0 * _float(s.get("height_mul"), 1.0)
    return {
        "pos_x": _clamp(_float(p.get("center_x"), 0.78), -0.25, 1.25),
        "pos_y": _clamp(_float(p.get("bottom_y"), 0.965) - 0.30 / max(0.1, scale), -0.25, 1.25),
        "scale": _clamp(scale, 0.05, 8.0),
    }


def fit_transform_from_bounds(
    bounds: Mapping[str, Any],
    *,
    current_pos_x: float = 0.5,
    current_pos_y: float = 0.5,
    current_scale: float = 1.0,
    preset: str | Mapping[str, Any] | None = "bottom_right",
    size_preset: str | Mapping[str, Any] | None = "auto_fit",
    canvas_width: int = 1920,
    canvas_height: int = 1080,
) -> dict[str, Any]:
    """Calculate a Live2D transform that places measured bounds into a preset."""
    p = normalize_placement_preset(preset)
    s = normalize_size_preset(size_preset)
    width = max(1, _int(canvas_width, 1920))
    height = max(1, _int(canvas_height, 1080))
    if not bool(bounds.get("ok")):
        transform = fallback_transform_for_preset(preset=p, size_preset=s)
        return {
            "schema": DIALOGUE_PLACEMENT_SCHEMA,
            "measured": False,
            "reason": str(bounds.get("reason") or "unavailable_bounds"),
            "preset": p,
            "size_preset": s,
            "transform": transform,
        }

    bbox = list(bounds.get("bbox") or [0, 0, width, height])
    bbox_w = max(1.0, _float(bounds.get("width"), bbox[2] - bbox[0]))
    bbox_h = max(1.0, _float(bounds.get("height"), bbox[3] - bbox[1]))
    center = list(bounds.get("center") or [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0])

    target_w = width * _float(p.get("target_width"), 0.30) * _float(s.get("width_mul"), 1.0)
    target_h = height * _float(p.get("target_height"), 0.72) * _float(s.get("height_mul"), 1.0)
    scale_factor = min(target_w / bbox_w, target_h / bbox_h)
    new_scale = _clamp(_float(current_scale, 1.0) * scale_factor, 0.05, 8.0)
    scaled_w = bbox_w * scale_factor
    scaled_h = bbox_h * scale_factor

    margin_x = width * _float(p.get("safe_margin_x"), 0.035)
    margin_y = height * _float(p.get("safe_margin_y"), 0.025)
    anchor_x = str(p.get("anchor_x") or "right").casefold()
    if anchor_x == "left":
        desired_center_x = margin_x + scaled_w / 2.0
    elif anchor_x == "center":
        desired_center_x = width * _float(p.get("center_x"), 0.5)
    else:
        desired_center_x = width - margin_x - scaled_w / 2.0
    desired_bottom = height * _float(p.get("bottom_y"), 0.965) - margin_y
    desired_center_y = desired_bottom - scaled_h / 2.0

    current_center_x = _float(center[0], width / 2.0)
    current_center_y = _float(center[1], height / 2.0)
    new_pos_x = _clamp(_float(current_pos_x, 0.5) + (desired_center_x - current_center_x) / width, -0.25, 1.25)
    new_pos_y = _clamp(_float(current_pos_y, 0.5) + (desired_center_y - current_center_y) / height, -0.25, 1.25)
    transform = {
        "pos_x": round(new_pos_x, 6),
        "pos_y": round(new_pos_y, 6),
        "scale": round(new_scale, 6),
    }
    return {
        "schema": DIALOGUE_PLACEMENT_SCHEMA,
        "measured": True,
        "preset": p,
        "size_preset": s,
        "bounds": dict(bounds),
        "canvas": {"width": width, "height": height},
        "target": {
            "visible_width_px": round(scaled_w, 3),
            "visible_height_px": round(scaled_h, 3),
            "center_px": [round(desired_center_x, 3), round(desired_center_y, 3)],
            "bottom_px": round(desired_bottom, 3),
        },
        "transform": transform,
    }


def apply_dialogue_placement_to_clip(
    clip: Any,
    *,
    preset: str | Mapping[str, Any] | None = "bottom_right",
    size_preset: str | Mapping[str, Any] | None = "auto_fit",
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    sample_ms: int | None = None,
    render_func: Callable[[Any, int, int, int], Any] | None = None,
    replace_transform_keyframes: bool = True,
) -> dict[str, Any]:
    """Measure a Live2D clip and apply a preset transform."""
    width = max(1, _int(canvas_width, 1920))
    height = max(1, _int(canvas_height, 1080))
    pos_ms = int(getattr(clip, "start_ms", 0) or 0) + max(0, _int(sample_ms, 0))
    image = None
    reason = ""
    try:
        if render_func is not None:
            image = render_func(clip, width, height, pos_ms)
        else:
            render = getattr(clip, "render_frame", None)
            if callable(render):
                image = render(width, height, pos_ms)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
    bounds = alpha_bounds(image)
    if reason and not bool(bounds.get("ok")):
        bounds["reason"] = reason
    result = fit_transform_from_bounds(
        bounds,
        current_pos_x=_float(getattr(clip, "pos_x", 0.5), 0.5),
        current_pos_y=_float(getattr(clip, "pos_y", 0.5), 0.5),
        current_scale=_float(getattr(clip, "scale", 1.0), 1.0),
        preset=preset,
        size_preset=size_preset,
        canvas_width=width,
        canvas_height=height,
    )
    transform = dict(result.get("transform") or {})
    for key in ("pos_x", "pos_y", "scale"):
        if key in transform:
            setattr(clip, key, float(transform[key]))
    if bool(replace_transform_keyframes):
        try:
            from app.live2d.actor_track import Live2DKeyframe

            clip.kf_pos_x = [Live2DKeyframe(0, float(transform.get("pos_x", getattr(clip, "pos_x", 0.5))), "smoothstep")]
            clip.kf_pos_y = [Live2DKeyframe(0, float(transform.get("pos_y", getattr(clip, "pos_y", 0.5))), "smoothstep")]
            clip.kf_scale = [Live2DKeyframe(0, float(transform.get("scale", getattr(clip, "scale", 1.0))), "smoothstep")]
        except Exception:
            pass
    try:
        clip.dialogue_placement_payload = dict(result)
    except Exception:
        pass
    reset = getattr(clip, "reset", None)
    if callable(reset):
        try:
            reset()
        except Exception:
            pass
    return result


__all__ = [
    "DIALOGUE_PLACEMENT_SCHEMA",
    "PLACEMENT_PRESETS",
    "SIZE_PRESETS",
    "alpha_bounds",
    "apply_dialogue_placement_to_clip",
    "fallback_transform_for_preset",
    "fit_transform_from_bounds",
    "normalize_placement_preset",
    "normalize_size_preset",
    "placement_preset_options",
    "size_preset_options",
]
