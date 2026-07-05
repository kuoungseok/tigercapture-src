"""Depth-of-field controls and packet-export post blur for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_DEPTH_OF_FIELD_MODE = "off"
DEFAULT_DEPTH_OF_FIELD_STRENGTH = 0.0
DEFAULT_DOF_FOCUS_DEPTH = 0.50
DEFAULT_DOF_FOCUS_RANGE = 0.08
DEFAULT_DOF_MAX_BLUR_PX = 5.0
DEFAULT_DOF_NEAR_BLUR = 0.70
DEFAULT_DOF_FAR_BLUR = 1.0
DEFAULT_DOF_BOKEH_SHAPE = "soft"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "dof", "depth", "lens"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "none"}:
        return False
    return bool(default)


def _float_value(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "depth_of_field_rendering",
        "depth_of_field",
        "camera_depth_of_field",
        "camera_dof",
        "lens_dof",
        "dof",
        "lens",
    ):
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def normalize_depth_of_field_settings(value: Any) -> dict[str, Any]:
    """Normalize optional camera/lens depth-of-field controls.

    This is a deterministic screen-space post blur for AR/PBR overlay pixels.
    It does not model aperture blades, cat-eye bokeh, occlusion-aware background
    gathering, stochastic lens sampling, or true path-traced camera optics.
    """
    data = _as_mapping(value)
    dof_raw = data.get("depth_of_field", data.get("dof", data.get("camera_dof")))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("depth_of_field_mode"),
        data.get("dof_mode"),
        DEFAULT_DEPTH_OF_FIELD_MODE,
    )
    mode = str(raw_mode or DEFAULT_DEPTH_OF_FIELD_MODE).strip().casefold().replace("-", "_")
    if mode in {"lens", "camera", "camera_lens", "blur", "bokeh"}:
        mode = "depth_of_field"
    if mode not in {"off", "depth_of_field"}:
        mode = DEFAULT_DEPTH_OF_FIELD_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("depth_of_field_enabled"),
        data.get("dof_enabled"),
        dof_raw if isinstance(dof_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "depth_of_field")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "blur"),
            data.get("depth_of_field_strength"),
            data.get("dof_strength"),
            dof_raw if not isinstance(dof_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_DEPTH_OF_FIELD_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "depth_of_field"

    focus_depth = _float_value(
        _first_value(
            _nested(data, "focus_depth", "focus", "focus_distance"),
            data.get("dof_focus_depth"),
            data.get("depth_of_field_focus_depth"),
            data.get("focus_depth"),
        ),
        DEFAULT_DOF_FOCUS_DEPTH,
        0.0,
        1.0,
    )
    focus_range = _float_value(
        _first_value(
            _nested(data, "focus_range", "focus_width", "in_focus_range"),
            data.get("dof_focus_range"),
            data.get("depth_of_field_focus_range"),
        ),
        DEFAULT_DOF_FOCUS_RANGE,
        0.0,
        0.75,
    )
    max_blur_px = _float_value(
        _first_value(
            _nested(data, "max_blur_px", "max_radius_px", "radius_px", "blur_px"),
            data.get("dof_max_blur_px"),
            data.get("depth_of_field_max_blur_px"),
        ),
        DEFAULT_DOF_MAX_BLUR_PX,
        0.0,
        24.0,
    )
    near_blur = _float_value(
        _first_value(
            _nested(data, "near_blur", "foreground_blur"),
            data.get("dof_near_blur"),
            data.get("depth_of_field_near_blur"),
        ),
        DEFAULT_DOF_NEAR_BLUR,
        0.0,
        2.0,
    )
    far_blur = _float_value(
        _first_value(
            _nested(data, "far_blur", "background_blur"),
            data.get("dof_far_blur"),
            data.get("depth_of_field_far_blur"),
        ),
        DEFAULT_DOF_FAR_BLUR,
        0.0,
        2.0,
    )
    bokeh_shape = str(
        _first_value(
            _nested(data, "bokeh_shape", "shape"),
            data.get("dof_bokeh_shape"),
            DEFAULT_DOF_BOKEH_SHAPE,
        )
        or DEFAULT_DOF_BOKEH_SHAPE
    ).strip().casefold().replace("-", "_")
    if bokeh_shape not in {"soft", "round"}:
        bokeh_shape = DEFAULT_DOF_BOKEH_SHAPE

    if not enabled or max_blur_px <= 0.0:
        mode = "off"
        enabled = False
        strength = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.depth_of_field.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "focus_depth": float(focus_depth),
        "focus_range": float(focus_range),
        "max_blur_px": float(max_blur_px),
        "near_blur": float(near_blur),
        "far_blur": float(far_blur),
        "bokeh_shape": bokeh_shape,
        "blur_model": "depth_banded_premultiplied_alpha_gaussian_overlay_blur",
        "sampling_policy": "deterministic_no_stochastic_lens_sampling",
        "scope_policy": "ar_overlay_pixels_only_background_preserved",
        "optics_policy": "no_aperture_blades_cat_eye_or_occlusion_aware_gather",
        "render_pass_safe": True,
        "alpha_preserving": True,
    }


def flatten_depth_of_field_settings(value: Any) -> dict[str, Any]:
    settings = normalize_depth_of_field_settings(value)
    return {
        "depth_of_field_mode": settings["mode"],
        "depth_of_field_enabled": settings["enabled"],
        "depth_of_field_strength": settings["strength"],
        "dof_focus_depth": settings["focus_depth"],
        "dof_focus_range": settings["focus_range"],
        "dof_max_blur_px": settings["max_blur_px"],
        "dof_near_blur": settings["near_blur"],
        "dof_far_blur": settings["far_blur"],
        "dof_bokeh_shape": settings["bokeh_shape"],
    }


def _smoothstep(edge0: Any, edge1: Any, value: Any):
    import numpy as np

    denom = np.maximum(float(edge1) - float(edge0), 1.0e-6)
    x = np.clip((value - float(edge0)) / denom, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def apply_depth_of_field_to_overlay(
    overlay: Any,
    depth_map: Any,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    """Apply a deterministic depth-banded blur to an RGBA overlay image."""
    cfg = normalize_depth_of_field_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "max_circle_of_confusion_px": 0.0,
        "layer_count": 0,
    }
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0 or float(cfg["max_blur_px"]) <= 0.0:
        return overlay, diagnostics

    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception as exc:
        diagnostics["warnings"] = [f"depth of field skipped: {type(exc).__name__}: {exc}"]
        return overlay, diagnostics

    try:
        image = overlay.convert("RGBA") if hasattr(overlay, "convert") else Image.fromarray(overlay, "RGBA")
        depth = np.asarray(depth_map, dtype=np.float32)
        if depth.ndim != 2 or depth.size <= 0:
            raise ValueError("depth_map must be a 2D array")
        width, height = image.size
        if depth.shape != (height, width):
            depth_img = Image.fromarray(np.clip(depth * 255.0, 0, 255).astype(np.uint8), "L")
            depth_img = depth_img.resize((width, height), Image.Resampling.BILINEAR)
            depth = np.asarray(depth_img, dtype=np.float32) / 255.0
        arr = np.asarray(image, dtype=np.float32) / 255.0
        alpha = np.clip(arr[:, :, 3], 0.0, 1.0)
        active = alpha > 0.001
        if not bool(active.any()):
            return overlay, diagnostics

        depth = np.nan_to_num(depth, nan=float(cfg["focus_depth"]), posinf=1.0, neginf=0.0)
        depth = np.clip(depth, 0.0, 1.0)
        focus = float(cfg["focus_depth"])
        focus_range = float(cfg["focus_range"])
        near_delta = np.maximum((focus - depth) - focus_range, 0.0)
        far_delta = np.maximum((depth - focus) - focus_range, 0.0)
        near_span = max(focus - focus_range, 1.0e-4)
        far_span = max(1.0 - focus - focus_range, 1.0e-4)
        coc = (
            near_delta / near_span * float(cfg["near_blur"])
            + far_delta / far_span * float(cfg["far_blur"])
        ) * float(cfg["max_blur_px"]) * float(cfg["strength"])
        coc = np.where(active, np.clip(coc, 0.0, float(cfg["max_blur_px"])), 0.0)
        max_coc = float(np.max(coc)) if coc.size else 0.0
        diagnostics["max_circle_of_confusion_px"] = max_coc
        if max_coc < 0.25:
            return overlay, diagnostics

        premul = arr.copy()
        premul[:, :, :3] *= alpha[:, :, None]
        current = premul
        layers = [
            max(0.35, max_coc * 0.36),
            max(0.70, max_coc * 0.68),
            max(1.00, max_coc),
        ]
        layer_count = 0
        for idx, radius in enumerate(layers):
            if radius <= 0.2:
                continue
            blurred = Image.fromarray(np.clip(current * 255.0, 0, 255).astype(np.uint8), "RGBA")
            blurred = blurred.filter(ImageFilter.GaussianBlur(radius=float(radius)))
            blurred_arr = np.asarray(blurred, dtype=np.float32) / 255.0
            lower = 0.20 if idx == 0 else layers[idx - 1] * 0.72
            mask = _smoothstep(lower, radius, coc)[:, :, None]
            current = current * (1.0 - mask) + blurred_arr * mask
            layer_count += 1

        out_alpha = np.clip(current[:, :, 3], 0.0, 1.0)
        out_rgb = np.where(
            out_alpha[:, :, None] > 1.0e-5,
            current[:, :, :3] / np.maximum(out_alpha[:, :, None], 1.0e-5),
            0.0,
        )
        out = np.dstack((np.clip(out_rgb, 0.0, 1.0), out_alpha))
        diagnostics["applied"] = True
        diagnostics["pixels"] = int(((coc > 0.25) & active).sum())
        diagnostics["layer_count"] = int(layer_count)
        return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), "RGBA"), diagnostics
    except Exception as exc:
        diagnostics["warnings"] = [f"depth of field skipped: {type(exc).__name__}: {exc}"]
        return overlay, diagnostics
