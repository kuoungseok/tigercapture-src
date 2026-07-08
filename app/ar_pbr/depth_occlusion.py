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


def _shift_zero(arr: Any, dx: int, dy: int):
    import numpy as np

    src = np.asarray(arr, dtype=np.float32)
    out = np.zeros_like(src)
    h, w = src.shape[:2]
    if h <= 0 or w <= 0:
        return out
    src_x0 = max(0, -int(dx))
    src_x1 = min(w, w - int(dx)) if int(dx) >= 0 else w
    dst_x0 = max(0, int(dx))
    dst_x1 = min(w, w + int(dx)) if int(dx) < 0 else w
    src_y0 = max(0, -int(dy))
    src_y1 = min(h, h - int(dy)) if int(dy) >= 0 else h
    dst_y0 = max(0, int(dy))
    dst_y1 = min(h, h + int(dy)) if int(dy) < 0 else h
    if src_x1 <= src_x0 or src_y1 <= src_y0 or dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return out
    out[dst_y0:dst_y1, dst_x0:dst_x1] = src[src_y0:src_y1, src_x0:src_x1]
    return out


def _shift_edge(arr: Any, dx: int, dy: int):
    import numpy as np

    src = np.asarray(arr, dtype=np.float32)
    h, w = src.shape[:2]
    pad = max(1, abs(int(dx)), abs(int(dy)))
    padded = np.pad(src, ((pad, pad), (pad, pad)), mode="edge")
    y0 = pad - int(dy)
    x0 = pad - int(dx)
    return padded[y0:y0 + h, x0:x0 + w]


def _box_blur_mask(mask: Any, radius: int):
    import numpy as np

    src = np.asarray(mask, dtype=np.float32)
    r = max(0, int(radius))
    if r <= 0:
        return src
    acc = src.copy()
    count = 1.0
    for offset in range(1, r + 1):
        for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
            acc += _shift_zero(src, dx, dy)
            count += 1.0
    return np.clip(acc / max(1.0, count), 0.0, 1.0)


def build_depth_effect_masks(
    alpha: Any,
    depth_patch: Any,
    *,
    object_depth: float,
    settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build reusable depth masks for occlusion, glow, and future effects.

    The returned masks are display-space float32 arrays in the same size as the
    object alpha patch. They intentionally separate raw depth logic from the
    visible glow color pass so other effects can consume the same information.
    """
    import numpy as np

    alpha_arr = np.asarray(alpha, dtype=np.float32)
    if alpha_arr.ndim == 3:
        alpha_arr = alpha_arr[:, :, 0]
    depth = np.asarray(depth_patch, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[:, :, 0]
    if alpha_arr.shape != depth.shape:
        raise ValueError("alpha and depth_patch must have matching 2D shapes")
    if alpha_arr.size <= 0:
        raise ValueError("empty depth effect mask")
    if float(np.nanmax(alpha_arr)) > 1.5:
        alpha_arr = alpha_arr / 255.0
    alpha_arr = np.clip(np.nan_to_num(alpha_arr, nan=0.0, posinf=1.0, neginf=0.0), 0.0, 1.0)
    depth = np.clip(np.nan_to_num(depth, nan=1.0, posinf=1.0, neginf=0.0), 0.0, 1.0)

    tolerance = depth_occlusion_tolerance(settings)
    softness = max(depth_occlusion_softness(settings), 0.002)
    radius = max(
        1,
        int(round(_setting_float(
            settings,
            ("depth_effect_radius_px", "depth_edge_glow_radius_px", "depth_occlusion_glow_radius_px"),
            DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
        ))),
    )
    blur_radius = max(
        0,
        min(
            4,
            int(round(_setting_float(
                settings,
                ("depth_effect_blur_px", "depth_edge_glow_blur_px"),
                min(2.0, max(0.0, float(radius) * 0.28)),
            ))),
        ),
    )
    scene_edge_strength = max(
        0.0,
        min(
            1.0,
            _setting_float(
                settings,
                ("depth_effect_scene_edge_strength", "depth_edge_glow_scene_edge_strength"),
                0.55,
            ),
        ),
    )

    visibility = depth_visibility(
        depth,
        object_depth=float(object_depth),
        tolerance=tolerance,
        softness=softness,
    ).astype(np.float32)
    visibility = np.clip(visibility, 0.0, 1.0)
    visible_mask = alpha_arr * visibility
    hidden_mask = alpha_arr * (1.0 - visibility)

    neighbor_hidden = np.zeros_like(hidden_mask)
    depth_edge = np.zeros_like(hidden_mask)
    for offset in range(1, radius + 1):
        weight = 1.0 - (float(offset - 1) / max(1.0, float(radius)))
        for dx, dy in ((offset, 0), (-offset, 0), (0, offset), (0, -offset)):
            neighbor_hidden = np.maximum(neighbor_hidden, _shift_zero(hidden_mask, dx, dy) * weight)
            shifted_depth = _shift_edge(depth, dx, dy)
            depth_edge = np.maximum(depth_edge, np.abs(depth - shifted_depth) * weight)

    transition_mask = np.clip(visibility * (1.0 - visibility) * 4.0, 0.0, 1.0) * alpha_arr
    scene_depth_edge = np.clip(depth_edge * visible_mask * scene_edge_strength, 0.0, 1.0)
    object_boundary = np.clip(neighbor_hidden * visible_mask, 0.0, 1.0)
    edge_mask = np.clip(object_boundary + transition_mask + scene_depth_edge, 0.0, 1.0)
    if blur_radius > 0:
        edge_mask = np.clip(edge_mask * 0.72 + _box_blur_mask(edge_mask, blur_radius) * 0.28, 0.0, 1.0)
    edge_mask = np.where(edge_mask > 0.012, edge_mask, 0.0).astype(np.float32)

    masks = {
        "visible_mask": visible_mask.astype(np.float32),
        "hidden_mask": hidden_mask.astype(np.float32),
        "transition_mask": transition_mask.astype(np.float32),
        "scene_depth_edge": scene_depth_edge.astype(np.float32),
        "object_boundary": object_boundary.astype(np.float32),
        "edge_mask": edge_mask,
    }
    diagnostics = {
        "schema": "tigerstudio.ar_pbr.depth_effect_masks.v1",
        "ok": True,
        "object_depth": max(0.0, min(1.0, float(object_depth))),
        "tolerance": tolerance,
        "softness": softness,
        "radius_px": float(radius),
        "blur_px": float(blur_radius),
        "visible_pixels": int((visible_mask > 0.001).sum()),
        "hidden_pixels": int((hidden_mask > 0.001).sum()),
        "edge_pixels": int((edge_mask > 0.001).sum()),
        "scene_edge_strength": float(scene_edge_strength),
    }
    return masks, diagnostics


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
    try:
        masks, mask_diag = build_depth_effect_masks(
            alpha,
            depth_patch,
            object_depth=object_depth,
            settings=settings,
        )
    except Exception as exc:
        return rgb, {
            "enabled": True,
            "applied": False,
            "changed_pixels": 0,
            "reason": f"mask_build_failed:{type(exc).__name__}",
        }
    edge = masks["edge_mask"]
    if edge.shape != out.shape[:2]:
        return rgb, {"enabled": True, "applied": False, "changed_pixels": 0, "reason": "invalid_mask_shape"}
    glow = edge[:, :, None] * np.asarray(cfg["color"], dtype=np.float32)[None, None, :3] * float(cfg["strength"])
    changed = int((edge > 0.01).sum())
    if changed <= 0:
        return rgb, {
            "enabled": True,
            "applied": False,
            "changed_pixels": 0,
            "object_depth": max(0.0, min(1.0, float(object_depth))),
            "tolerance": float(mask_diag.get("tolerance", 0.0) or 0.0),
            "radius_px": float(cfg["radius_px"]),
            "rendering": cfg,
            "masks": mask_diag,
        }
    return np.clip(out[:, :, :3] + glow, 0.0, 1.0), {
        "enabled": True,
        "applied": True,
        "changed_pixels": changed,
        "object_depth": max(0.0, min(1.0, float(object_depth))),
        "tolerance": float(mask_diag.get("tolerance", 0.0) or 0.0),
        "radius_px": float(cfg["radius_px"]),
        "strength": float(cfg["strength"]),
        "rendering": cfg,
        "masks": mask_diag,
    }
