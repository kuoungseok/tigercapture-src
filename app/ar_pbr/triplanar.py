"""Triplanar texture-projection controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_TRIPLANAR_MODE = "off"
DEFAULT_TRIPLANAR_STRENGTH = 0.0
DEFAULT_TRIPLANAR_SCALE = 1.0
DEFAULT_TRIPLANAR_BLEND_SHARPNESS = 4.0
DEFAULT_TRIPLANAR_OFFSET = [0.0, 0.0, 0.0]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "triplanar", "tri_planar", "box", "box_projection"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "none", "uv"}:
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
        "triplanar_rendering",
        "triplanar_projection",
        "triplanar",
        "texture_projection",
        "box_projection",
        "projection",
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


def _vec3_value(value: Any, default: list[float], lo: float, hi: float) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        fallback = float(default[idx] if idx < len(default) else 0.0)
        raw = source[idx] if idx < len(source) else fallback
        out.append(_float_value(raw, fallback, lo, hi))
    return out


def normalize_triplanar_settings(value: Any) -> dict[str, Any]:
    """Normalize optional triplanar projection controls.

    This is a realtime box-projection approximation. It projects texture maps
    from object/world position along the three major axes and blends them by
    normal direction; it does not create per-face UV unwraps or texture baking.
    """
    data = _as_mapping(value)
    triplanar_raw = data.get("triplanar")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("triplanar_mode"),
        data.get("texture_projection_mode"),
        DEFAULT_TRIPLANAR_MODE,
    )
    mode = str(raw_mode or DEFAULT_TRIPLANAR_MODE).strip().casefold().replace("-", "_")
    if mode in {"tri_planar", "triplanar_projection", "box", "box_projection", "world", "object"}:
        mode = "triplanar"
    if mode not in {"off", "triplanar"}:
        mode = DEFAULT_TRIPLANAR_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("triplanar_enabled"),
        data.get("texture_projection_enabled"),
        triplanar_raw if isinstance(triplanar_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "triplanar")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "blend", "amount", "triplanar_strength"),
            data.get("triplanar_strength"),
            triplanar_raw if not isinstance(triplanar_raw, Mapping) else None,
        ),
        1.0 if enabled else DEFAULT_TRIPLANAR_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "triplanar"

    scale = _float_value(
        _first_value(
            _nested(data, "scale", "tiling", "tile_scale", "triplanar_scale"),
            data.get("triplanar_scale"),
            data.get("texture_projection_scale"),
        ),
        DEFAULT_TRIPLANAR_SCALE,
        0.01,
        64.0,
    )
    blend_sharpness = _float_value(
        _first_value(
            _nested(data, "blend_sharpness", "sharpness", "normal_blend", "triplanar_blend_sharpness"),
            data.get("triplanar_blend_sharpness"),
            data.get("triplanar_sharpness"),
        ),
        DEFAULT_TRIPLANAR_BLEND_SHARPNESS,
        1.0,
        16.0,
    )
    offset = _vec3_value(
        _first_value(
            _nested(data, "offset", "position_offset", "triplanar_offset"),
            data.get("triplanar_offset"),
            data.get("texture_projection_offset"),
        ),
        DEFAULT_TRIPLANAR_OFFSET,
        -64.0,
        64.0,
    )
    space = str(
        _first_value(
            _nested(data, "space", "projection_space"),
            data.get("triplanar_space"),
            data.get("texture_projection_space"),
            "object",
        )
    ).strip().casefold().replace("-", "_")
    if space not in {"object", "world"}:
        space = "object"

    if not enabled:
        mode = "off"
        strength = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.triplanar.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "scale": float(scale),
        "blend_sharpness": float(blend_sharpness),
        "offset": [float(v) for v in offset],
        "space": space,
        "projection_model": "normal_weighted_axis_box_projection",
        "map_policy": "all_material_maps_share_triplanar_projection",
        "normal_policy": "normal_maps_sampled_with_existing_tangent_space_interpretation",
        "uv_policy": "blends_authored_uv_sampling_to_triplanar_projection_by_strength",
        "bake_policy": "no_generated_uv_unwrap_or_texture_bake",
        "render_pass_safe": True,
    }


def flatten_triplanar_settings(value: Any) -> dict[str, Any]:
    settings = normalize_triplanar_settings(value)
    return {
        "triplanar_mode": settings["mode"],
        "triplanar_enabled": settings["enabled"],
        "triplanar_strength": settings["strength"],
        "triplanar_scale": settings["scale"],
        "triplanar_blend_sharpness": settings["blend_sharpness"],
        "triplanar_offset": list(settings["offset"]),
        "triplanar_space": settings["space"],
    }


def triplanar_weights(nx: Any, ny: Any, nz: Any, settings: Mapping[str, Any] | None) -> tuple[Any, Any, Any]:
    import numpy as np

    cfg = normalize_triplanar_settings(settings or {})
    sharpness = max(1.0, float(cfg["blend_sharpness"]))
    wx = np.power(np.abs(np.asarray(nx, dtype=np.float32)), sharpness)
    wy = np.power(np.abs(np.asarray(ny, dtype=np.float32)), sharpness)
    wz = np.power(np.abs(np.asarray(nz, dtype=np.float32)), sharpness)
    total = np.maximum(wx + wy + wz, 1.0e-6)
    return wx / total, wy / total, wz / total


def triplanar_uvs(x: Any, y: Any, z: Any, settings: Mapping[str, Any] | None) -> tuple[tuple[Any, Any], tuple[Any, Any], tuple[Any, Any]]:
    import numpy as np

    cfg = normalize_triplanar_settings(settings or {})
    scale = float(cfg["scale"])
    offset = list(cfg.get("offset") or DEFAULT_TRIPLANAR_OFFSET)
    px = np.asarray(x, dtype=np.float32) * scale + float(offset[0])
    py = np.asarray(y, dtype=np.float32) * scale + float(offset[1])
    pz = np.asarray(z, dtype=np.float32) * scale + float(offset[2])
    # X projection uses the YZ plane, Y projection uses XZ, Z projection uses XY.
    return (pz, py), (px, pz), (px, py)
