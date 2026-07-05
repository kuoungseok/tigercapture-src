"""Height-map parallax controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_PARALLAX_MODE = "off"
DEFAULT_PARALLAX_STRENGTH = 0.0
DEFAULT_PARALLAX_DEPTH = 0.035
DEFAULT_PARALLAX_CENTER = 0.5
DEFAULT_PARALLAX_STEPS = 1


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
    if mode in {"height", "height_map", "displacement", "parallax_occlusion", "pom"}:
        mode = "parallax"
    if mode not in {"off", "parallax"}:
        mode = DEFAULT_PARALLAX_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("parallax_enabled"),
        data.get("displacement_enabled"),
        parallax_raw if isinstance(parallax_raw, bool) else None,
        displacement_raw if isinstance(displacement_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "parallax")
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
        mode = "parallax"
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
        DEFAULT_PARALLAX_STEPS,
        1,
        8,
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
        "mapping_model": "height_map_tangent_space_uv_offset",
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
