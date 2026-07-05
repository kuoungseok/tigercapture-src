"""Height/vector displacement contract for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_DISPLACEMENT_MODE = "off"
DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH = 0.0
DEFAULT_DISPLACEMENT_HEIGHT_SCALE = 0.05
DEFAULT_DISPLACEMENT_HEIGHT_CENTER = 0.5
DEFAULT_VECTOR_DISPLACEMENT_STRENGTH = 0.0
DEFAULT_VECTOR_DISPLACEMENT_SPACE = "tangent"
DEFAULT_DISPLACEMENT_SUBDIVISION_MODE = "contract"
DEFAULT_DISPLACEMENT_MAX_OFFSET = 0.12
DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK = True


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
        "height",
        "vector",
        "displacement",
        "geometry",
        "tessellation",
    }:
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
        "displacement_rendering",
        "geometry_displacement",
        "height_displacement",
        "vector_displacement",
        "displacement",
        "height",
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


def normalize_displacement_settings(value: Any) -> dict[str, Any]:
    """Normalize height/vector geometry displacement controls.

    The current realtime path keeps parallax mapping as the visible fallback.
    Packet export applies a conservative world-position offset proxy for
    shading/procedural effects, without changing topology, silhouette, depth, or
    shadow-caster geometry.
    """
    data = _as_mapping(value)
    raw_displacement = data.get("geometry_displacement", data.get("displacement"))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("displacement_mode"),
        data.get("geometry_displacement_mode"),
        data.get("height_displacement_mode"),
        data.get("vector_displacement_mode"),
        DEFAULT_DISPLACEMENT_MODE,
    )
    requested_mode = str(raw_mode or DEFAULT_DISPLACEMENT_MODE).strip().casefold().replace("-", "_")
    if requested_mode in {
        "height",
        "height_map",
        "height_displacement",
        "vector",
        "vector_map",
        "vector_displacement",
        "geometry",
        "geometry_displacement",
        "tessellation",
        "adaptive_tessellation",
    }:
        requested_mode = "displacement"
    if requested_mode not in {"off", "displacement"}:
        requested_mode = DEFAULT_DISPLACEMENT_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("displacement_enabled"),
        data.get("geometry_displacement_enabled"),
        data.get("height_displacement_enabled"),
        data.get("vector_displacement_enabled"),
        raw_displacement if isinstance(raw_displacement, bool) else None,
    )
    enabled = _bool_value(enabled_raw, requested_mode == "displacement")
    height_strength = _float_value(
        _first_value(
            _nested(data, "height_strength", "height_displacement_strength", "strength", "amount"),
            data.get("height_displacement_strength"),
            data.get("displacement_height_strength"),
            data.get("displacement_strength"),
            raw_displacement if not isinstance(raw_displacement, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH,
        0.0,
        2.0,
    )
    height_scale = _float_value(
        _first_value(
            _nested(data, "height_scale", "scale", "depth", "displacement_depth"),
            data.get("displacement_height_scale"),
            data.get("height_scale"),
            data.get("displacement_depth"),
        ),
        DEFAULT_DISPLACEMENT_HEIGHT_SCALE,
        0.0,
        0.5,
    )
    height_center = _float_value(
        _first_value(
            _nested(data, "height_center", "center"),
            data.get("displacement_height_center"),
            data.get("height_center"),
        ),
        DEFAULT_DISPLACEMENT_HEIGHT_CENTER,
        0.0,
        1.0,
    )
    vector_strength = _float_value(
        _first_value(
            _nested(data, "vector_strength", "vector_displacement_strength"),
            data.get("vector_displacement_strength"),
            data.get("displacement_vector_strength"),
        ),
        DEFAULT_VECTOR_DISPLACEMENT_STRENGTH,
        0.0,
        2.0,
    )
    vector_space = str(_first_value(
        _nested(data, "vector_space", "vector_displacement_space", "space"),
        data.get("vector_displacement_space"),
        data.get("displacement_vector_space"),
        DEFAULT_VECTOR_DISPLACEMENT_SPACE,
    ) or DEFAULT_VECTOR_DISPLACEMENT_SPACE).strip().casefold().replace("-", "_")
    if vector_space not in {"tangent", "object", "world"}:
        vector_space = DEFAULT_VECTOR_DISPLACEMENT_SPACE
    subdivision_mode = str(_first_value(
        _nested(data, "subdivision_mode", "subdivision", "tessellation"),
        data.get("displacement_subdivision_mode"),
        data.get("displacement_subdivision"),
        DEFAULT_DISPLACEMENT_SUBDIVISION_MODE,
    ) or DEFAULT_DISPLACEMENT_SUBDIVISION_MODE).strip().casefold().replace("-", "_")
    if subdivision_mode not in {"contract", "none", "uniform", "adaptive", "tessellation"}:
        subdivision_mode = DEFAULT_DISPLACEMENT_SUBDIVISION_MODE
    max_offset = _float_value(
        _first_value(
            _nested(data, "max_offset", "offset_limit"),
            data.get("displacement_max_offset"),
        ),
        DEFAULT_DISPLACEMENT_MAX_OFFSET,
        0.0,
        1.0,
    )
    parallax_fallback = _bool_value(
        _first_value(
            _nested(data, "parallax_fallback", "realtime_fallback"),
            data.get("displacement_parallax_fallback"),
        ),
        DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK,
    )

    if height_strength > 0.0 or vector_strength > 0.0:
        enabled = True
    if enabled:
        mode = "displacement"
    else:
        mode = "off"
        height_strength = 0.0
        vector_strength = 0.0
        height_scale = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.displacement.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "height_strength": float(height_strength),
        "height_scale": float(height_scale),
        "height_center": float(height_center),
        "vector_strength": float(vector_strength),
        "vector_space": vector_space,
        "subdivision_mode": subdivision_mode,
        "max_offset": float(max_offset),
        "parallax_fallback": bool(parallax_fallback),
        "geometry_model": "height_or_vector_geometry_displacement_contract",
        "packet_model": "normal_space_position_offset_for_lighting_and_render_passes",
        "realtime_fallback": "parallax_mapping",
        "silhouette_policy": "no_packet_silhouette_or_tessellation_change",
        "shadow_policy": "no_displaced_shadow_caster_until_native_tessellation",
        "render_pass_safe": True,
    }


def flatten_displacement_settings(value: Any) -> dict[str, Any]:
    settings = normalize_displacement_settings(value)
    return {
        "displacement_mode": settings["mode"],
        "displacement_enabled": settings["enabled"],
        "displacement_height_strength": settings["height_strength"],
        "displacement_height_scale": settings["height_scale"],
        "displacement_height_center": settings["height_center"],
        "vector_displacement_strength": settings["vector_strength"],
        "vector_displacement_space": settings["vector_space"],
        "displacement_subdivision_mode": settings["subdivision_mode"],
        "displacement_max_offset": settings["max_offset"],
        "displacement_parallax_fallback": settings["parallax_fallback"],
    }


def apply_displacement_proxy(
    *,
    world_pos: tuple[Any, Any, Any],
    normal: tuple[Any, Any, Any],
    tangent: tuple[Any, Any, Any],
    bitangent: tuple[Any, Any, Any],
    height: Any = None,
    vector_sample: Any = None,
    alpha: Any,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, Any, Any, dict[str, Any]]:
    cfg = normalize_displacement_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "height_pixels": 0,
        "vector_pixels": 0,
        "max_offset": 0.0,
        "mean_offset": 0.0,
    }
    if not bool(cfg["enabled"]):
        return world_pos[0], world_pos[1], world_pos[2], diagnostics

    import numpy as np

    wx = np.asarray(world_pos[0], dtype=np.float32)
    wy = np.asarray(world_pos[1], dtype=np.float32)
    wz = np.asarray(world_pos[2], dtype=np.float32)
    shape = wx.shape
    if wy.shape != shape or wz.shape != shape:
        return world_pos[0], world_pos[1], world_pos[2], diagnostics

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        try:
            return np.broadcast_to(raw, shape).astype(np.float32, copy=False)
        except Exception:
            return np.full(shape, float(default), dtype=np.float32)

    nx = _arr(normal[0], 0.0)
    ny = _arr(normal[1], 0.0)
    nz = _arr(normal[2], 1.0)
    tx = _arr(tangent[0], 1.0)
    ty = _arr(tangent[1], 0.0)
    tz = _arr(tangent[2], 0.0)
    bx = _arr(bitangent[0], 0.0)
    by = _arr(bitangent[1], 1.0)
    bz = _arr(bitangent[2], 0.0)
    active = _arr(alpha, 0.0) > 0.001
    if not bool(active.any()):
        return world_pos[0], world_pos[1], world_pos[2], diagnostics

    dx = np.zeros(shape, dtype=np.float32)
    dy = np.zeros(shape, dtype=np.float32)
    dz = np.zeros(shape, dtype=np.float32)
    height_pixels = 0
    vector_pixels = 0
    scale = float(cfg["height_scale"])
    height_strength = float(cfg["height_strength"])
    if height is not None and height_strength > 0.0 and scale > 0.0:
        h = np.clip(_arr(height, float(cfg["height_center"])), 0.0, 1.0)
        offset = (h - float(cfg["height_center"])) * scale * height_strength
        dx += nx * offset
        dy += ny * offset
        dz += nz * offset
        height_pixels = int((active & (np.abs(offset) > 1.0e-7)).sum())

    vector_strength = float(cfg["vector_strength"])
    if vector_sample is not None and vector_strength > 0.0 and scale > 0.0:
        sample = np.asarray(vector_sample, dtype=np.float32)
        if sample.ndim >= 3 and sample.shape[-1] >= 3:
            vx = _arr(sample[:, :, 0] * 2.0 - 1.0, 0.0)
            vy = _arr(sample[:, :, 1] * 2.0 - 1.0, 0.0)
            vz = _arr(sample[:, :, 2] * 2.0 - 1.0, 0.0)
            amount = scale * vector_strength
            if str(cfg["vector_space"]) == "tangent":
                vdx = (tx * vx + bx * vy + nx * vz) * amount
                vdy = (ty * vx + by * vy + ny * vz) * amount
                vdz = (tz * vx + bz * vy + nz * vz) * amount
            else:
                vdx = vx * amount
                vdy = vy * amount
                vdz = vz * amount
            dx += vdx
            dy += vdy
            dz += vdz
            vmag = np.sqrt(vdx * vdx + vdy * vdy + vdz * vdz)
            vector_pixels = int((active & (vmag > 1.0e-7)).sum())

    mag = np.sqrt(dx * dx + dy * dy + dz * dz)
    max_offset = float(cfg["max_offset"])
    if max_offset > 0.0:
        clamp = np.where(mag > max_offset, max_offset / np.maximum(mag, 1.0e-8), 1.0)
        dx *= clamp
        dy *= clamp
        dz *= clamp
        mag = np.minimum(mag, max_offset)
    changed = active & (mag > 1.0e-7)
    if not bool(changed.any()):
        return world_pos[0], world_pos[1], world_pos[2], diagnostics

    out_x = np.where(active, wx + dx, wx)
    out_y = np.where(active, wy + dy, wy)
    out_z = np.where(active, wz + dz, wz)
    diagnostics.update({
        "applied": True,
        "pixels": int(active.sum()),
        "changed_pixels": int(changed.sum()),
        "height_pixels": int(height_pixels),
        "vector_pixels": int(vector_pixels),
        "max_offset": float(np.max(mag[changed])),
        "mean_offset": float(np.mean(mag[changed])),
    })
    return out_x, out_y, out_z, diagnostics
