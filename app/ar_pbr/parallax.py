"""Height-map parallax controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_PARALLAX_MODE = "off"
DEFAULT_PARALLAX_STRENGTH = 0.0
DEFAULT_PARALLAX_DEPTH = 0.035
DEFAULT_PARALLAX_CENTER = 0.5
DEFAULT_PARALLAX_STEPS = 1
MAX_PARALLAX_STEPS = 64


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "parallax", "height", "displacement"}:
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


def _int_value(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        out = int(round(float(value)))
    except Exception:
        out = int(default)
    return max(int(lo), min(int(hi), out))


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in ("parallax_rendering", "parallax", "displacement", "height"):
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def normalize_parallax_settings(value: Any) -> dict[str, Any]:
    """Normalize optional parallax/height-map controls.

    This is a realtime parallax-mapping approximation.  It offsets material UVs
    from a height texture; it does not alter mesh silhouettes or cast displaced
    geometry shadows.
    """
    data = _as_mapping(value)
    parallax_raw = data.get("parallax")
    displacement_raw = data.get("displacement")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("parallax_mode"),
        data.get("displacement_mode"),
        DEFAULT_PARALLAX_MODE,
    )
    mode = str(raw_mode or DEFAULT_PARALLAX_MODE).strip().casefold().replace("-", "_")
    if mode in {"height", "height_map", "displacement"}:
        mode = "parallax"
    if mode in {"parallax_occlusion", "parallax_occlusion_mapping"}:
        mode = "pom"
    if mode not in {"off", "parallax", "pom"}:
        mode = DEFAULT_PARALLAX_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("parallax_enabled"),
        data.get("displacement_enabled"),
        parallax_raw if isinstance(parallax_raw, bool) else None,
        displacement_raw if isinstance(displacement_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode in {"parallax", "pom"})
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "parallax_strength", "displacement_strength"),
            data.get("parallax_strength"),
            data.get("displacement_strength"),
            parallax_raw if not isinstance(parallax_raw, Mapping) else None,
            displacement_raw if not isinstance(displacement_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_PARALLAX_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        if mode == "off":
            mode = "pom" if _int_value(data.get("parallax_steps"), DEFAULT_PARALLAX_STEPS, 1, MAX_PARALLAX_STEPS) > 1 else "parallax"
    depth = _float_value(
        _first_value(
            _nested(data, "depth", "height_scale", "parallax_depth", "displacement_depth"),
            data.get("height_scale"),
            data.get("parallax_depth"),
            data.get("displacement_depth"),
        ),
        DEFAULT_PARALLAX_DEPTH,
        0.0,
        0.25,
    )
    center = _float_value(
        _first_value(
            _nested(data, "center", "height_center", "parallax_center"),
            data.get("height_center"),
            data.get("parallax_center"),
        ),
        DEFAULT_PARALLAX_CENTER,
        0.0,
        1.0,
    )
    steps = _int_value(
        _first_value(
            _nested(data, "steps", "sample_count", "parallax_steps"),
            data.get("parallax_steps"),
        ),
        24 if mode == "pom" else DEFAULT_PARALLAX_STEPS,
        1,
        MAX_PARALLAX_STEPS,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        depth = 0.0
        steps = 1
    return {
        "schema": "tigerstudio.ar_pbr.parallax.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "depth": float(depth),
        "center": float(center),
        "steps": int(steps),
        "mapping_model": (
            "height_map_parallax_occlusion_mapping"
            if mode == "pom"
            else "height_map_tangent_space_uv_offset"
        ),
        "silhouette_policy": "no_geometry_silhouette_displacement",
        "shadow_policy": "shading_only_no_displaced_shadow",
        "render_pass_safe": True,
    }


def flatten_parallax_settings(value: Any) -> dict[str, Any]:
    settings = normalize_parallax_settings(value)
    return {
        "parallax_mode": settings["mode"],
        "parallax_enabled": settings["enabled"],
        "parallax_strength": settings["strength"],
        "parallax_depth": settings["depth"],
        "parallax_center": settings["center"],
        "parallax_steps": settings["steps"],
    }


def apply_parallax_uv(
    u: Any,
    v: Any,
    *,
    height: Any,
    tangent_view_xy: tuple[Any, Any],
    settings: Mapping[str, Any] | None,
) -> tuple[Any, Any]:
    cfg = normalize_parallax_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return u, v
    import numpy as np

    height_arr = np.asarray(height, dtype=np.float32)
    vx = np.asarray(tangent_view_xy[0], dtype=np.float32)
    vy = np.asarray(tangent_view_xy[1], dtype=np.float32)
    if height_arr.shape != vx.shape or height_arr.shape != vy.shape:
        return u, v
    amount = (height_arr - float(cfg["center"])) * float(cfg["depth"]) * float(cfg["strength"])
    return np.asarray(u, dtype=np.float32) + vx * amount, np.asarray(v, dtype=np.float32) - vy * amount


def _sample_height_bilinear(
    height_texture: Any,
    u: Any,
    v: Any,
    *,
    channel: int = 0,
) -> Any:
    import numpy as np

    texture = np.asarray(height_texture, dtype=np.float32)
    if texture.ndim == 3:
        index = max(0, min(texture.shape[2] - 1, int(channel)))
        texture = texture[..., index]
    if texture.ndim != 2 or texture.size == 0:
        return np.zeros_like(np.asarray(u, dtype=np.float32))
    uu = np.clip(np.asarray(u, dtype=np.float32), 0.0, 1.0)
    vv = np.clip(np.asarray(v, dtype=np.float32), 0.0, 1.0)
    height, width = texture.shape
    x = uu * max(0, width - 1)
    y = (1.0 - vv) * max(0, height - 1)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    fx = x - x0
    fy = y - y0
    top = texture[y0, x0] * (1.0 - fx) + texture[y0, x1] * fx
    bottom = texture[y1, x0] * (1.0 - fx) + texture[y1, x1] * fx
    return np.asarray(top * (1.0 - fy) + bottom * fy, dtype=np.float32)


def apply_parallax_occlusion_uv(
    u: Any,
    v: Any,
    *,
    height_texture: Any,
    tangent_view: tuple[Any, Any, Any],
    settings: Mapping[str, Any] | None,
    channel: int = 0,
) -> tuple[Any, Any]:
    """Trace a tangent-space view ray through a height field.

    This mirrors the realtime POM shader for packet export. It changes texture
    lookup coordinates only; mesh silhouettes and displaced shadows remain
    outside this contract.
    """
    import numpy as np

    cfg = normalize_parallax_settings(settings or {})
    base_u = np.asarray(u, dtype=np.float32)
    base_v = np.asarray(v, dtype=np.float32)
    if not bool(cfg["enabled"]) or str(cfg["mode"]) != "pom":
        sampled = _sample_height_bilinear(height_texture, base_u, base_v, channel=channel)
        return apply_parallax_uv(
            base_u,
            base_v,
            height=sampled,
            tangent_view_xy=(tangent_view[0], tangent_view[1]),
            settings=cfg,
        )

    vx = np.asarray(tangent_view[0], dtype=np.float32)
    vy = np.asarray(tangent_view[1], dtype=np.float32)
    vz = np.maximum(np.abs(np.asarray(tangent_view[2], dtype=np.float32)), 0.08)
    if base_u.shape != vx.shape or base_u.shape != vy.shape or base_u.shape != vz.shape:
        return base_u, base_v

    steps = max(2, min(MAX_PARALLAX_STEPS, int(cfg["steps"])))
    ray_scale = float(cfg["depth"]) * float(cfg["strength"])
    ray_u = (vx / vz) * ray_scale
    ray_v = -(vy / vz) * ray_scale
    delta_u = ray_u / float(steps)
    delta_v = ray_v / float(steps)
    layer_step = 1.0 / float(steps)
    current_u = base_u.copy()
    current_v = base_v.copy()
    previous_u = current_u.copy()
    previous_v = current_v.copy()
    previous_layer = np.zeros_like(base_u)
    current_layer = np.zeros_like(base_u)
    active = np.ones_like(base_u, dtype=bool)
    center_bias = float(cfg["center"]) - 0.5

    for _ in range(steps):
        sampled_height = _sample_height_bilinear(
            height_texture,
            current_u,
            current_v,
            channel=channel,
        )
        surface_depth = np.clip(1.0 - sampled_height + center_bias, 0.0, 1.0)
        advance = active & (current_layer < surface_depth)
        if not bool(np.any(advance)):
            break
        previous_u = np.where(advance, current_u, previous_u)
        previous_v = np.where(advance, current_v, previous_v)
        previous_layer = np.where(advance, current_layer, previous_layer)
        current_u = np.where(advance, current_u - delta_u, current_u)
        current_v = np.where(advance, current_v - delta_v, current_v)
        current_layer = np.where(advance, current_layer + layer_step, current_layer)
        active = advance

    current_height = _sample_height_bilinear(
        height_texture,
        current_u,
        current_v,
        channel=channel,
    )
    previous_height = _sample_height_bilinear(
        height_texture,
        previous_u,
        previous_v,
        channel=channel,
    )
    current_error = current_layer - np.clip(1.0 - current_height + center_bias, 0.0, 1.0)
    previous_error = np.clip(1.0 - previous_height + center_bias, 0.0, 1.0) - previous_layer
    blend = np.clip(previous_error / np.maximum(previous_error + current_error, 1.0e-6), 0.0, 1.0)
    out_u = previous_u * (1.0 - blend) + current_u * blend
    out_v = previous_v * (1.0 - blend) + current_v * blend
    return np.clip(out_u, 0.0, 1.0), np.clip(out_v, 0.0, 1.0)
