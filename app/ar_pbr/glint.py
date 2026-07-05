"""Realtime glint/sparkle controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_GLINT_MODE = "off"
DEFAULT_GLINT_STRENGTH = 0.0
DEFAULT_GLINT_COLOR = [1.0, 0.96, 0.82]
DEFAULT_GLINT_DENSITY = 0.24
DEFAULT_GLINT_SCALE = 64.0
DEFAULT_GLINT_THRESHOLD = 0.62
DEFAULT_GLINT_SHARPNESS = 18.0
DEFAULT_GLINT_ROUGHNESS_JITTER = 0.55


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "glint", "sparkle", "flakes", "microflake"}:
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
        "glint_sparkle_rendering",
        "sparkle_rendering",
        "glint_rendering",
        "microflake_rendering",
        "flake_rendering",
        "glint_sparkle",
        "sparkle",
        "glint",
        "microflake",
        "flakes",
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


def _vec3_value(value: Any, default: list[float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        fallback = float(default[idx] if idx < len(default) else 1.0)
        raw = source[idx] if idx < len(source) else fallback
        out.append(_float_value(raw, fallback, 0.0, 1.0))
    return out


def normalize_glint_sparkle_settings(value: Any) -> dict[str, Any]:
    """Normalize optional realtime microflake glint/sparkle controls.

    This is a deterministic shader-only sparkle approximation for glossy
    flecks, glitter, and metallic paint. It does not create microflake
    geometry, spectral dispersion, particles, stochastic temporal shimmer, or
    caustic light paths.
    """
    data = _as_mapping(value)
    glint_raw = data.get("glint_sparkle", data.get("sparkle", data.get("glint")))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("glint_mode"),
        data.get("sparkle_mode"),
        data.get("microflake_mode"),
        DEFAULT_GLINT_MODE,
    )
    mode = str(raw_mode or DEFAULT_GLINT_MODE).strip().casefold().replace("-", "_")
    if mode in {"glitter", "sparkles", "flake", "flakes", "microflake", "microflakes", "metal_flake"}:
        mode = "sparkle"
    if mode not in {"off", "sparkle"}:
        mode = DEFAULT_GLINT_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("glint_enabled"),
        data.get("sparkle_enabled"),
        data.get("microflake_enabled"),
        glint_raw if isinstance(glint_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "sparkle")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "sparkle", "glint"),
            data.get("glint_strength"),
            data.get("sparkle_strength"),
            data.get("microflake_strength"),
            glint_raw if not isinstance(glint_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_GLINT_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "sparkle"

    color = _vec3_value(
        _first_value(
            _nested(data, "color", "tint", "sparkle_color", "glint_color"),
            data.get("glint_color"),
            data.get("sparkle_color"),
            data.get("microflake_color"),
        ),
        DEFAULT_GLINT_COLOR,
    )
    density = _float_value(
        _first_value(
            _nested(data, "density", "coverage", "flake_density"),
            data.get("glint_density"),
            data.get("sparkle_density"),
            data.get("microflake_density"),
        ),
        DEFAULT_GLINT_DENSITY,
        0.0,
        1.0,
    )
    scale = _float_value(
        _first_value(
            _nested(data, "scale", "size", "frequency", "flake_scale"),
            data.get("glint_scale"),
            data.get("sparkle_scale"),
            data.get("microflake_scale"),
        ),
        DEFAULT_GLINT_SCALE,
        1.0,
        512.0,
    )
    threshold = _float_value(
        _first_value(
            _nested(data, "threshold", "cutoff", "sparkle_threshold"),
            data.get("glint_threshold"),
            data.get("sparkle_threshold"),
        ),
        DEFAULT_GLINT_THRESHOLD,
        0.0,
        0.98,
    )
    sharpness = _float_value(
        _first_value(
            _nested(data, "sharpness", "focus", "sparkle_sharpness"),
            data.get("glint_sharpness"),
            data.get("sparkle_sharpness"),
        ),
        DEFAULT_GLINT_SHARPNESS,
        1.0,
        64.0,
    )
    roughness_jitter = _float_value(
        _first_value(
            _nested(data, "roughness_jitter", "roughness_variation", "flake_jitter"),
            data.get("glint_roughness_jitter"),
            data.get("sparkle_roughness_jitter"),
        ),
        DEFAULT_GLINT_ROUGHNESS_JITTER,
        0.0,
        1.0,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        density = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.glint_sparkle.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "color": [float(v) for v in color],
        "density": float(density),
        "scale": float(scale),
        "threshold": float(threshold),
        "sharpness": float(sharpness),
        "roughness_jitter": float(roughness_jitter),
        "shading_model": "deterministic_microflake_sparkle_specular",
        "sampling_policy": "uv_world_hash_no_stochastic_temporal_sampling",
        "geometry_policy": "no_microflake_geometry_or_particle_sprites",
        "spectrum_policy": "no_spectral_dispersion_or_prismatic_split",
        "shadow_policy": "shading_only_no_sparkle_shadow_or_caustic_paths",
        "render_pass_safe": True,
    }


def flatten_glint_sparkle_settings(value: Any) -> dict[str, Any]:
    settings = normalize_glint_sparkle_settings(value)
    return {
        "glint_mode": settings["mode"],
        "glint_enabled": settings["enabled"],
        "glint_strength": settings["strength"],
        "glint_color": list(settings["color"]),
        "glint_density": settings["density"],
        "glint_scale": settings["scale"],
        "glint_threshold": settings["threshold"],
        "glint_sharpness": settings["sharpness"],
        "glint_roughness_jitter": settings["roughness_jitter"],
    }


def apply_glint_sparkle_shading(
    rgb: Any,
    *,
    uv: tuple[Any, Any],
    world_pos: tuple[Any, Any, Any],
    ndotl: Any,
    ndotv: Any,
    ndoth: Any,
    roughness: Any,
    ao: Any,
    direct_strength: float,
    env_rgb: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_glint_sparkle_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return rgb
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
    if out.ndim != 3:
        return rgb
    shape = out.shape[:2]

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
    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nv = np.clip(_arr(ndotv, 0.0), 0.0, 1.0)
    nh = np.clip(_arr(ndoth, 0.0), 0.0, 1.0)
    rough = np.clip(_arr(roughness, 0.35), 0.015, 1.0)
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)

    scale = max(1.0, float(cfg["scale"]))
    density = max(0.0, min(1.0, float(cfg["density"])))
    threshold = max(0.0, min(0.98, float(cfg["threshold"])))
    cell_u = np.floor(u * scale + wx * 0.27)
    cell_v = np.floor(v * scale + wy * 0.27 + wz * 0.11)

    def _hash(x: Any, y: Any, salt: float = 0.0):
        raw = np.sin(x * 127.1 + y * 311.7 + float(salt)) * 43758.5453
        return raw - np.floor(raw)

    seed = _hash(cell_u, cell_v, 0.0)
    seed_b = _hash(cell_u + 19.19, cell_v - 7.31, 23.17)
    density_gate = np.clip((seed - (1.0 - density)) / max(density, 1.0e-5), 0.0, 1.0)
    sparkle_gate = np.clip((density_gate * seed_b - threshold) / max(1.0 - threshold, 1.0e-5), 0.0, 1.0)
    sparkle_gate = sparkle_gate * sparkle_gate * (3.0 - 2.0 * sparkle_gate)

    rough_jitter = max(0.0, min(1.0, float(cfg["roughness_jitter"])))
    micro_rough = np.clip(rough * (1.0 - rough_jitter * (0.35 + seed_b * 0.55)), 0.015, 1.0)
    sharpness = max(1.0, min(64.0, float(cfg["sharpness"])))
    exponent = (10.0 + sharpness * 3.2) * (1.0 - micro_rough * 0.58)
    needle = np.power(nh, np.maximum(exponent, 2.0))
    grazing = np.power(np.clip(1.0 - nv, 0.0, 1.0), 3.0)
    flake_floor = (1.0 - rough) * 0.035
    glitter = sparkle_gate * (needle * (0.55 + nl * 0.45) + grazing * 0.12 + flake_floor)

    env = np.asarray(env_rgb, dtype=np.float32)
    if env.ndim == 1 and env.shape[0] >= 3:
        env = env[None, None, :3]
    if env.ndim != 3 or env.shape[2] < 3:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.18
    try:
        env = np.broadcast_to(env[:, :, :3], (*shape, 3)).astype(np.float32, copy=False)
    except Exception:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.18

    color = np.asarray(cfg["color"], dtype=np.float32)
    strength = float(cfg["strength"])
    ao_weight = 0.35 + ao_arr[:, :, None] * 0.65
    direct = glitter[:, :, None] * color[None, None, :] * max(0.0, float(direct_strength)) * strength * ao_weight
    env_glint = (
        sparkle_gate[:, :, None]
        * env
        * color[None, None, :]
        * (0.08 + grazing[:, :, None] * 0.34)
        * (1.0 - rough[:, :, None] * 0.55)
        * strength
        * ao_weight
    )
    return np.clip(out + direct + env_glint, 0.0, 32.0)
