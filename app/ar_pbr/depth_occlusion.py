"""Depth-matte occlusion helpers for AR/PBR compositing."""
from __future__ import annotations

from typing import Any, Mapping

DEFAULT_DEPTH_EDGE_GLOW_COLOR = [0.38, 0.82, 1.0]
DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX = 3.0
DEFAULT_DEPTH_EDGE_GLOW_STRENGTH = 0.0


def _setting_float(settings: Mapping[str, Any] | None, keys: tuple[str, ...], default: float) -> float:
    source = settings or {}
    for key in keys:
        if key not in source:
            continue
        try:
            return float(source.get(key))
        except Exception:
            return float(default)
    return float(default)


def depth_occlusion_tolerance(settings: Mapping[str, Any] | None = None, default: float = 0.02) -> float:
    return max(
        0.0,
        min(
            0.25,
            _setting_float(
                settings,
                ("depth_occlusion_tolerance", "occlusion_tolerance"),
                default,
            ),
        ),
    )


def depth_occlusion_softness(settings: Mapping[str, Any] | None = None, default: float = 0.0) -> float:
    return max(
        0.0,
        min(
            0.25,
            _setting_float(
                settings,
                ("depth_occlusion_softness", "occlusion_softness"),
                default,
            ),
        ),
    )


def normalize_depth_frame(depth_frame: Any, width: int, height: int):
    if depth_frame is None:
        return None
    try:
        import numpy as np
        from PIL import Image

        arr = np.asarray(depth_frame, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
        if arr.ndim != 2 or arr.size <= 0:
            return None
        if arr.shape != (int(height), int(width)):
            arr = np.asarray(
                Image.fromarray(arr.astype(np.float32), mode="F").resize(
                    (int(width), int(height)),
                    Image.Resampling.BILINEAR,
                ),
                dtype=np.float32,
            )
        arr = np.nan_to_num(arr, nan=1.0, posinf=1.0, neginf=0.0)
        if float(np.max(arr)) > 1.5:
            arr = arr / 255.0
        return np.clip(arr, 0.0, 1.0)
    except Exception:
        return None


def _setting_bool(settings: Mapping[str, Any] | None, keys: tuple[str, ...], default: bool) -> bool:
    source = settings or {}
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if isinstance(value, bool):
            return value
        text = str(value).strip().casefold()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
    return bool(default)


def _setting_color(settings: Mapping[str, Any] | None, keys: tuple[str, ...], default: list[float]) -> list[float]:
    source = settings or {}
    for key in keys:
        if key not in source:
            continue
        raw = source.get(key)
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            out: list[float] = []
            for value, fallback in zip(raw[:3], default):
                try:
                    out.append(max(0.0, min(1.0, float(value))))
                except Exception:
                    out.append(float(fallback))
            return out
    return [float(v) for v in default[:3]]


def normalize_depth_edge_glow_settings(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    strength = max(
        0.0,
        min(
            1.0,
            _setting_float(
                settings,
                ("depth_edge_glow_strength", "depth_occlusion_glow_strength", "edge_glow_strength"),
                DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
            ),
        ),
    )
    enabled = _setting_bool(
        settings,
        ("depth_edge_glow_enabled", "depth_occlusion_glow_enabled", "edge_glow_enabled"),
        strength > 1.0e-6,
    )
    radius_px = max(
        0.5,
        min(
            18.0,
            _setting_float(
                settings,
                ("depth_edge_glow_radius_px", "depth_occlusion_glow_radius_px", "edge_glow_radius_px"),
                DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
            ),
        ),
    )
    return {
        "schema": "tigerstudio.ar_pbr.depth_edge_glow.v1",
        "enabled": bool(enabled and strength > 1.0e-6),
        "strength": float(strength),
        "radius_px": float(radius_px),
        "color": _setting_color(
            settings,
            ("depth_edge_glow_color", "depth_occlusion_glow_color", "edge_glow_color"),
            DEFAULT_DEPTH_EDGE_GLOW_COLOR,
        ),
        "mode": "depth_boundary_visible_rim",
    }


def flatten_depth_edge_glow_settings(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cfg = normalize_depth_edge_glow_settings(settings)
    return {
        "depth_edge_glow_enabled": bool(cfg["enabled"]),
        "depth_edge_glow_strength": float(cfg["strength"]),
        "depth_edge_glow_radius_px": float(cfg["radius_px"]),
        "depth_edge_glow_color": list(cfg["color"]),
    }


def depth_visibility(
    depth_patch: Any,
    *,
    object_depth: float,
    tolerance: float,
    softness: float = 0.0,
):
    import numpy as np

    depth = np.asarray(depth_patch, dtype=np.float32)
    threshold = max(0.0, min(1.0, float(object_depth) - max(0.0, float(tolerance))))
    soft = max(0.0, float(softness))
    if soft <= 1.0e-6:
        return depth >= threshold
    lo = max(0.0, threshold - soft)
    hi = min(1.0, threshold + soft)
    span = max(1.0e-6, hi - lo)
    t = np.clip((depth - lo) / span, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def apply_depth_occlusion_to_alpha(
    alpha: Any,
    depth_patch: Any,
    *,
    object_depth: float,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    import numpy as np

    alpha_arr = np.asarray(alpha)
    tolerance = depth_occlusion_tolerance(settings)
    softness = depth_occlusion_softness(settings)
    visibility = depth_visibility(
        depth_patch,
        object_depth=float(object_depth),
        tolerance=tolerance,
        softness=softness,
    )
    visible_threshold = 0.5 if alpha_arr.dtype.kind in {"u", "i"} else 0.001
    before = int((alpha_arr > visible_threshold).sum())
    if visibility.dtype == np.bool_:
        out = np.where(visibility, alpha_arr, 0)
    else:
        out = alpha_arr.astype(np.float32) * visibility.astype(np.float32)
    after = int((out > visible_threshold).sum())
    if alpha_arr.dtype.kind in {"u", "i"}:
        out = np.clip(out, 0, 255).astype(alpha_arr.dtype)
    else:
        out = np.clip(out, 0.0, 1.0).astype(alpha_arr.dtype, copy=False)
    return out, {
        "enabled": True,
        "applied": before > after,
        "occluded_pixels": max(0, before - after),
        "visible_pixels": after,
        "object_depth": max(0.0, min(1.0, float(object_depth))),
        "tolerance": tolerance,
        "softness": softness,
    }


def apply_depth_edge_glow_to_rgb(
    rgb: Any,
    alpha: Any,
    depth_patch: Any,
    *,
    object_depth: float,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    import numpy as np

    cfg = normalize_depth_edge_glow_settings(settings)
    if not bool(cfg["enabled"]):
        return rgb, {"enabled": False, "applied": False, "changed_pixels": 0}
    out = np.asarray(rgb, dtype=np.float32)
    if out.ndim != 3 or out.shape[2] < 3:
        return rgb, {"enabled": True, "applied": False, "changed_pixels": 0, "reason": "invalid_rgb"}
    alpha_arr = np.asarray(alpha, dtype=np.float32)
    if alpha_arr.shape != out.shape[:2]:
        return rgb, {"enabled": True, "applied": False, "changed_pixels": 0, "reason": "invalid_alpha"}
    depth = np.asarray(depth_patch, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    if depth.shape != out.shape[:2]:
        return rgb, {"enabled": True, "applied": False, "changed_pixels": 0, "reason": "invalid_depth"}

    tolerance = depth_occlusion_tolerance(settings)
    softness = max(depth_occlusion_softness(settings), 0.002)
    visibility = depth_visibility(
        depth,
        object_depth=float(object_depth),
        tolerance=tolerance,
        softness=softness,
    ).astype(np.float32)
    active = (alpha_arr > 0.001).astype(np.float32)
    visible = active * np.clip(visibility, 0.0, 1.0)
    hidden = active * (1.0 - np.clip(visibility, 0.0, 1.0))
    neighbor_hidden = hidden.copy()
    depth_edge = np.zeros_like(hidden)
    radius = max(1, int(round(float(cfg["radius_px"]))))
    for offset in range(1, radius + 1):
        weight = 1.0 - (float(offset - 1) / max(1.0, float(radius)))
        shifted = np.zeros_like(hidden)
        shifted[:, offset:] = hidden[:, :-offset]
        neighbor_hidden = np.maximum(neighbor_hidden, shifted * weight)
        depth_shift = np.zeros_like(depth)
        depth_shift[:, offset:] = depth[:, :-offset]
        depth_edge = np.maximum(depth_edge, np.abs(depth - depth_shift) * weight)
        shifted = np.zeros_like(hidden)
        shifted[:, :-offset] = hidden[:, offset:]
        neighbor_hidden = np.maximum(neighbor_hidden, shifted * weight)
        depth_shift = np.zeros_like(depth)
        depth_shift[:, :-offset] = depth[:, offset:]
        depth_edge = np.maximum(depth_edge, np.abs(depth - depth_shift) * weight)
        shifted = np.zeros_like(hidden)
        shifted[offset:, :] = hidden[:-offset, :]
        neighbor_hidden = np.maximum(neighbor_hidden, shifted * weight)
        depth_shift = np.zeros_like(depth)
        depth_shift[offset:, :] = depth[:-offset, :]
        depth_edge = np.maximum(depth_edge, np.abs(depth - depth_shift) * weight)
        shifted = np.zeros_like(hidden)
        shifted[:-offset, :] = hidden[offset:, :]
        neighbor_hidden = np.maximum(neighbor_hidden, shifted * weight)
        depth_shift = np.zeros_like(depth)
        depth_shift[:-offset, :] = depth[offset:, :]
        depth_edge = np.maximum(depth_edge, np.abs(depth - depth_shift) * weight)
    transition = np.clip(visibility * (1.0 - visibility) * 4.0, 0.0, 1.0) * active
    scene_edge = np.clip(depth_edge * visible, 0.0, 1.0)
    edge = np.clip((neighbor_hidden * visible) + transition + scene_edge, 0.0, 1.0)
    glow = edge[:, :, None] * np.asarray(cfg["color"], dtype=np.float32)[None, None, :3] * float(cfg["strength"])
    changed = int((edge > 0.01).sum())
    if changed <= 0:
        return rgb, {
            "enabled": True,
            "applied": False,
            "changed_pixels": 0,
            "object_depth": max(0.0, min(1.0, float(object_depth))),
            "tolerance": tolerance,
            "radius_px": float(cfg["radius_px"]),
        }
    return np.clip(out[:, :, :3] + glow, 0.0, 1.0), {
        "enabled": True,
        "applied": True,
        "changed_pixels": changed,
        "object_depth": max(0.0, min(1.0, float(object_depth))),
        "tolerance": tolerance,
        "radius_px": float(cfg["radius_px"]),
        "strength": float(cfg["strength"]),
    }
