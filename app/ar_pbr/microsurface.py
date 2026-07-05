"""Detail-normal and microsurface controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_MICROSURFACE_MODE = "off"
DEFAULT_DETAIL_NORMAL_STRENGTH = 0.0
DEFAULT_DETAIL_NORMAL_SCALE = 32.0
DEFAULT_DETAIL_NORMAL_BLEND = "reoriented"
DEFAULT_DETAIL_NORMAL_SEED = 0
DEFAULT_MICRO_ROUGHNESS_STRENGTH = 0.0
DEFAULT_MICRO_ROUGHNESS_SCALE = 48.0
DEFAULT_MICRO_ROUGHNESS_CONTRAST = 0.35
DEFAULT_GLOSS_VARIATION_STRENGTH = 0.0
DEFAULT_GLOSS_BIAS = 0.0
DEFAULT_SPECULAR_MICRO_OCCLUSION = 0.0


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
        "detail",
        "detail_normal",
        "detail_normals",
        "microsurface",
        "micro_surface",
        "micro_roughness",
        "gloss",
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
    for container_key in (
        "microsurface_rendering",
        "advanced_microsurface",
        "micro_surface",
        "microsurface",
        "detail_normal",
        "detail_normals",
        "micro_roughness",
        "gloss_variation",
        "gloss",
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


def normalize_microsurface_settings(value: Any) -> dict[str, Any]:
    """Normalize detail normal and micro roughness/gloss controls."""
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("microsurface_mode"),
        data.get("micro_surface_mode"),
        data.get("detail_normal_mode"),
        data.get("micro_roughness_mode"),
        DEFAULT_MICROSURFACE_MODE,
    )
    mode = str(raw_mode or DEFAULT_MICROSURFACE_MODE).strip().casefold().replace("-", "_")
    if mode in {
        "detail",
        "detail_normal",
        "detail_normals",
        "micro",
        "micro_surface",
        "micro_roughness",
        "gloss",
        "advanced",
        "advanced_microsurface",
    }:
        mode = "microsurface"
    if mode not in {"off", "microsurface"}:
        mode = DEFAULT_MICROSURFACE_MODE

    raw_detail = data.get("detail_normal", data.get("detail_normals"))
    detail_strength = _float_value(
        _first_value(
            _nested(data, "detail_normal_strength", "normal_strength", "detail_strength", "strength"),
            data.get("detail_normal_strength"),
            data.get("detail_normals_strength"),
            raw_detail if not isinstance(raw_detail, Mapping) else None,
        ),
        DEFAULT_DETAIL_NORMAL_STRENGTH,
        0.0,
        2.0,
    )
    detail_enabled = _bool_value(
        _first_value(
            _nested(data, "detail_normal_enabled", "normal_enabled", "enabled"),
            data.get("detail_normal_enabled"),
            data.get("detail_normals_enabled"),
            raw_detail if isinstance(raw_detail, bool) else None,
        ),
        detail_strength > 0.0 or mode == "microsurface",
    )
    detail_scale = _float_value(
        _first_value(
            _nested(data, "detail_normal_scale", "normal_scale", "detail_scale", "scale"),
            data.get("detail_normal_scale"),
            data.get("detail_normals_scale"),
        ),
        DEFAULT_DETAIL_NORMAL_SCALE,
        0.25,
        1024.0,
    )
    detail_blend = str(_first_value(
        _nested(data, "detail_normal_blend", "normal_blend", "blend"),
        data.get("detail_normal_blend"),
        DEFAULT_DETAIL_NORMAL_BLEND,
    ) or DEFAULT_DETAIL_NORMAL_BLEND).strip().casefold().replace("-", "_")
    if detail_blend not in {"reoriented", "additive", "overlay"}:
        detail_blend = DEFAULT_DETAIL_NORMAL_BLEND
    detail_seed = _int_value(
        _first_value(_nested(data, "detail_normal_seed", "normal_seed", "seed"), data.get("detail_normal_seed")),
        DEFAULT_DETAIL_NORMAL_SEED,
        0,
        2_147_483_647,
    )

    raw_micro = data.get("micro_roughness")
    micro_strength = _float_value(
        _first_value(
            _nested(data, "micro_roughness_strength", "roughness_strength", "micro_strength"),
            data.get("micro_roughness_strength"),
            raw_micro if not isinstance(raw_micro, Mapping) else None,
        ),
        DEFAULT_MICRO_ROUGHNESS_STRENGTH,
        0.0,
        1.0,
    )
    micro_enabled = _bool_value(
        _first_value(
            _nested(data, "micro_roughness_enabled", "roughness_enabled"),
            data.get("micro_roughness_enabled"),
            raw_micro if isinstance(raw_micro, bool) else None,
        ),
        micro_strength > 0.0 or mode == "microsurface",
    )
    micro_scale = _float_value(
        _first_value(
            _nested(data, "micro_roughness_scale", "roughness_scale"),
            data.get("micro_roughness_scale"),
        ),
        DEFAULT_MICRO_ROUGHNESS_SCALE,
        0.25,
        1024.0,
    )
    micro_contrast = _float_value(
        _first_value(
            _nested(data, "micro_roughness_contrast", "roughness_contrast", "contrast"),
            data.get("micro_roughness_contrast"),
        ),
        DEFAULT_MICRO_ROUGHNESS_CONTRAST,
        0.0,
        1.0,
    )
    gloss_variation_strength = _float_value(
        _first_value(
            _nested(data, "gloss_variation_strength", "gloss_strength"),
            data.get("gloss_variation_strength"),
        ),
        DEFAULT_GLOSS_VARIATION_STRENGTH,
        0.0,
        1.0,
    )
    gloss_bias = _float_value(
        _first_value(_nested(data, "gloss_bias", "gloss_offset"), data.get("gloss_bias")),
        DEFAULT_GLOSS_BIAS,
        -1.0,
        1.0,
    )
    specular_micro_occlusion = _float_value(
        _first_value(
            _nested(data, "specular_micro_occlusion", "micro_occlusion", "specular_occlusion"),
            data.get("specular_micro_occlusion"),
        ),
        DEFAULT_SPECULAR_MICRO_OCCLUSION,
        0.0,
        1.0,
    )
    if detail_strength > 0.0:
        detail_enabled = True
    if micro_strength > 0.0 or gloss_variation_strength > 0.0 or abs(gloss_bias) > 0.0 or specular_micro_occlusion > 0.0:
        micro_enabled = True
    enabled = bool(detail_enabled or micro_enabled)
    if enabled:
        mode = "microsurface"
    else:
        mode = "off"
        detail_strength = 0.0
        micro_strength = 0.0
        gloss_variation_strength = 0.0
        gloss_bias = 0.0
        specular_micro_occlusion = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.microsurface.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "detail_normal_enabled": bool(detail_enabled and detail_strength > 0.0),
        "detail_normal_strength": float(detail_strength),
        "detail_normal_scale": float(detail_scale),
        "detail_normal_blend": detail_blend,
        "detail_normal_seed": int(detail_seed),
        "micro_roughness_enabled": bool(micro_enabled and (micro_strength > 0.0 or gloss_variation_strength > 0.0)),
        "micro_roughness_strength": float(micro_strength),
        "micro_roughness_scale": float(micro_scale),
        "micro_roughness_contrast": float(micro_contrast),
        "gloss_variation_strength": float(gloss_variation_strength),
        "gloss_bias": float(gloss_bias),
        "specular_micro_occlusion": float(specular_micro_occlusion),
        "normal_model": "deterministic_uv_world_detail_normal_layer",
        "roughness_model": "deterministic_micro_roughness_gloss_variation",
        "texture_policy": "procedural_detail_until_secondary_normal_map_slots_land",
        "render_pass_safe": True,
    }


def flatten_microsurface_settings(value: Any) -> dict[str, Any]:
    settings = normalize_microsurface_settings(value)
    return {
        "microsurface_mode": settings["mode"],
        "microsurface_enabled": settings["enabled"],
        "detail_normal_enabled": settings["detail_normal_enabled"],
        "detail_normal_strength": settings["detail_normal_strength"],
        "detail_normal_scale": settings["detail_normal_scale"],
        "detail_normal_blend": settings["detail_normal_blend"],
        "detail_normal_seed": settings["detail_normal_seed"],
        "micro_roughness_enabled": settings["micro_roughness_enabled"],
        "micro_roughness_strength": settings["micro_roughness_strength"],
        "micro_roughness_scale": settings["micro_roughness_scale"],
        "micro_roughness_contrast": settings["micro_roughness_contrast"],
        "gloss_variation_strength": settings["gloss_variation_strength"],
        "gloss_bias": settings["gloss_bias"],
        "specular_micro_occlusion": settings["specular_micro_occlusion"],
    }


def apply_detail_normal_layer(
    *,
    normal: tuple[Any, Any, Any],
    tangent: tuple[Any, Any, Any],
    bitangent: tuple[Any, Any, Any],
    uv: tuple[Any, Any],
    world_pos: tuple[Any, Any, Any],
    alpha: Any,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, Any, Any, dict[str, Any]]:
    cfg = normalize_microsurface_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "max_delta": 0.0,
        "mean_delta": 0.0,
    }
    if not bool(cfg["detail_normal_enabled"]) or float(cfg["detail_normal_strength"]) <= 0.0:
        return normal[0], normal[1], normal[2], diagnostics
    import numpy as np

    nx = np.asarray(normal[0], dtype=np.float32)
    ny = np.asarray(normal[1], dtype=np.float32)
    nz = np.asarray(normal[2], dtype=np.float32)
    shape = nx.shape
    if ny.shape != shape or nz.shape != shape:
        return normal[0], normal[1], normal[2], diagnostics

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        try:
            return np.broadcast_to(raw, shape).astype(np.float32, copy=False)
        except Exception:
            return np.full(shape, float(default), dtype=np.float32)

    tx = _arr(tangent[0], 1.0)
    ty = _arr(tangent[1], 0.0)
    tz = _arr(tangent[2], 0.0)
    bx = _arr(bitangent[0], 0.0)
    by = _arr(bitangent[1], 1.0)
    bz = _arr(bitangent[2], 0.0)
    u = _arr(uv[0], 0.0)
    v = _arr(uv[1], 0.0)
    wx = _arr(world_pos[0], 0.0)
    wy = _arr(world_pos[1], 0.0)
    wz = _arr(world_pos[2], 0.0)
    active = _arr(alpha, 0.0) > 0.001
    if not bool(active.any()):
        return normal[0], normal[1], normal[2], diagnostics

    strength = float(cfg["detail_normal_strength"])
    scale = float(cfg["detail_normal_scale"])
    seed = float(int(cfg["detail_normal_seed"]) % 100_000) * 0.013
    px = (u * 1.13 + wx * 0.19 + wz * 0.07 + seed) * scale
    py = (v * 1.07 + wy * 0.17 - wz * 0.05 - seed * 0.41) * scale
    bump_x = np.sin(px + np.cos(py * 0.70 + seed)) * np.cos(py * 0.37)
    bump_y = np.cos(py + np.sin(px * 0.63 - seed)) * np.sin(px * 0.41)
    if str(cfg["detail_normal_blend"]) == "overlay":
        bump_x *= 0.72 + 0.28 * np.sin((px + py) * 0.23)
        bump_y *= 0.72 + 0.28 * np.cos((px - py) * 0.19)
    elif str(cfg["detail_normal_blend"]) == "additive":
        bump_x *= 1.18
        bump_y *= 1.18

    tn_x = bump_x * strength
    tn_y = bump_y * strength
    tn_z = np.ones(shape, dtype=np.float32)
    tn_len = np.maximum(np.sqrt(tn_x * tn_x + tn_y * tn_y + tn_z * tn_z), 1.0e-6)
    tn_x, tn_y, tn_z = tn_x / tn_len, tn_y / tn_len, tn_z / tn_len
    out_x = tx * tn_x + bx * tn_y + nx * tn_z
    out_y = ty * tn_x + by * tn_y + ny * tn_z
    out_z = tz * tn_x + bz * tn_y + nz * tn_z
    out_len = np.maximum(np.sqrt(out_x * out_x + out_y * out_y + out_z * out_z), 1.0e-6)
    out_x, out_y, out_z = out_x / out_len, out_y / out_len, out_z / out_len
    out_x = np.where(active, out_x, nx)
    out_y = np.where(active, out_y, ny)
    out_z = np.where(active, out_z, nz)
    delta = np.sqrt((out_x - nx) ** 2 + (out_y - ny) ** 2 + (out_z - nz) ** 2)
    changed = active & (delta > 1.0e-5)
    if bool(changed.any()):
        diagnostics.update({
            "applied": True,
            "pixels": int(active.sum()),
            "changed_pixels": int(changed.sum()),
            "max_delta": float(np.max(delta[changed])),
            "mean_delta": float(np.mean(delta[changed])),
        })
    return out_x, out_y, out_z, diagnostics


def apply_microsurface_roughness(
    roughness: Any,
    *,
    uv: tuple[Any, Any],
    world_pos: tuple[Any, Any, Any],
    alpha: Any,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    cfg = normalize_microsurface_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "min_roughness": 0.0,
        "max_roughness": 0.0,
        "mean_roughness": 0.0,
        "max_delta": 0.0,
    }
    if (
        not bool(cfg["micro_roughness_enabled"])
        or (
            float(cfg["micro_roughness_strength"]) <= 0.0
            and float(cfg["gloss_variation_strength"]) <= 0.0
        )
    ):
        return roughness, diagnostics
    import numpy as np

    rough = np.asarray(roughness, dtype=np.float32)
    shape = rough.shape

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        try:
            return np.broadcast_to(raw, shape).astype(np.float32, copy=False)
        except Exception:
            return np.full(shape, float(default), dtype=np.float32)

    u = _arr(uv[0], 0.0)
    v = _arr(uv[1], 0.0)
    wx = _arr(world_pos[0], 0.0)
    wy = _arr(world_pos[1], 0.0)
    wz = _arr(world_pos[2], 0.0)
    active = _arr(alpha, 0.0) > 0.001
    if not bool(active.any()):
        return roughness, diagnostics

    seed = float(int(cfg["detail_normal_seed"]) % 100_000) * 0.017
    scale = float(cfg["micro_roughness_scale"])
    px = (u * 1.41 + wx * 0.23 + wz * 0.11 + seed) * scale
    py = (v * 1.37 + wy * 0.19 - wz * 0.09 - seed) * scale
    grain_a = np.sin(px + np.cos(py * 0.43))
    grain_b = np.cos(py * 0.83 + np.sin(px * 0.31))
    grain_c = np.sin((px - py) * 0.27 + seed)
    grain = 0.5 + 0.5 * (grain_a * 0.50 + grain_b * 0.34 + grain_c * 0.16)
    centered = (np.clip(grain, 0.0, 1.0) - 0.5) * 2.0
    strength = float(cfg["micro_roughness_strength"])
    contrast = float(cfg["micro_roughness_contrast"])
    gloss_strength = float(cfg["gloss_variation_strength"])
    gloss_bias = float(cfg["gloss_bias"])
    delta = centered * contrast * strength
    gloss_variation = (0.5 - grain) * gloss_strength * 0.22 - gloss_bias * gloss_strength * 0.18
    specular_micro_occlusion = float(cfg["specular_micro_occlusion"])
    occlusion_lift = specular_micro_occlusion * np.maximum(0.0, 1.0 - grain) * 0.06
    out = np.clip(rough + delta + gloss_variation + occlusion_lift, 0.025, 1.0)
    out = np.where(active, out, rough)
    changed = active & (np.abs(out - rough) > 1.0e-5)
    if bool(changed.any()):
        diagnostics.update({
            "applied": True,
            "pixels": int(active.sum()),
            "changed_pixels": int(changed.sum()),
            "min_roughness": float(np.min(out[active])),
            "max_roughness": float(np.max(out[active])),
            "mean_roughness": float(np.mean(out[active])),
            "max_delta": float(np.max(np.abs(out[changed] - rough[changed]))),
        })
    return out, diagnostics
