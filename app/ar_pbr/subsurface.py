"""Realtime subsurface-scattering controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SUBSURFACE_MODE = "off"
DEFAULT_SUBSURFACE_STRENGTH = 0.0
DEFAULT_SUBSURFACE_COLOR = [1.0, 0.62, 0.42]
DEFAULT_SUBSURFACE_RADIUS = 0.38
DEFAULT_SUBSURFACE_POWER = 2.0
DEFAULT_SUBSURFACE_WRAP = 0.45
DEFAULT_SUBSURFACE_THICKNESS = 0.12


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "sss", "subsurface", "skin", "wax"}:
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
        "subsurface_rendering",
        "subsurface_scattering",
        "subsurface",
        "sss",
        "skin",
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


def normalize_subsurface_settings(value: Any) -> dict[str, Any]:
    """Normalize optional realtime SSS controls.

    This is a single-scatter screen/render-pass-safe approximation: wrap
    diffuse plus view/light backscatter tinting. It does not perform path
    traced random-walk diffusion, multi-layer skin shading, or texture-space
    diffusion blurs.
    """
    data = _as_mapping(value)
    sss_raw = data.get("subsurface", data.get("sss"))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("subsurface_mode"),
        data.get("sss_mode"),
        DEFAULT_SUBSURFACE_MODE,
    )
    mode = str(raw_mode or DEFAULT_SUBSURFACE_MODE).strip().casefold().replace("-", "_")
    if mode in {"sss", "subsurface_scattering", "skin", "wax", "single_scatter"}:
        mode = "subsurface"
    if mode not in {"off", "subsurface"}:
        mode = DEFAULT_SUBSURFACE_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("subsurface_enabled"),
        data.get("sss_enabled"),
        sss_raw if isinstance(sss_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "subsurface")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "subsurface", "sss"),
            data.get("subsurface_strength"),
            data.get("sss_strength"),
            sss_raw if not isinstance(sss_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_SUBSURFACE_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "subsurface"

    color = _vec3_value(
        _first_value(
            _nested(data, "color", "tint", "subsurface_color", "sss_color"),
            data.get("subsurface_color"),
            data.get("sss_color"),
        ),
        DEFAULT_SUBSURFACE_COLOR,
    )
    radius = _float_value(
        _first_value(
            _nested(data, "radius", "scatter_radius", "subsurface_radius"),
            data.get("subsurface_radius"),
            data.get("sss_radius"),
        ),
        DEFAULT_SUBSURFACE_RADIUS,
        0.0,
        4.0,
    )
    power = _float_value(
        _first_value(
            _nested(data, "power", "falloff", "subsurface_power"),
            data.get("subsurface_power"),
            data.get("sss_power"),
        ),
        DEFAULT_SUBSURFACE_POWER,
        0.5,
        8.0,
    )
    wrap = _float_value(
        _first_value(
            _nested(data, "wrap", "wrap_lighting", "subsurface_wrap"),
            data.get("subsurface_wrap"),
            data.get("sss_wrap"),
        ),
        DEFAULT_SUBSURFACE_WRAP,
        0.0,
        1.0,
    )
    thickness = _float_value(
        _first_value(
            _nested(data, "thickness", "depth", "subsurface_thickness"),
            data.get("subsurface_thickness"),
            data.get("sss_thickness"),
        ),
        DEFAULT_SUBSURFACE_THICKNESS,
        0.0,
        2.0,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        radius = 0.0
        thickness = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.subsurface.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "color": [float(v) for v in color],
        "radius": float(radius),
        "power": float(power),
        "wrap": float(wrap),
        "thickness": float(thickness),
        "scattering_model": "single_scatter_wrap_diffuse_backscatter",
        "diffusion_policy": "no_random_walk_or_texture_space_diffusion",
        "shadow_policy": "shading_only_no_translucent_shadow_maps",
        "render_pass_safe": True,
    }


def flatten_subsurface_settings(value: Any) -> dict[str, Any]:
    settings = normalize_subsurface_settings(value)
    return {
        "subsurface_mode": settings["mode"],
        "subsurface_enabled": settings["enabled"],
        "subsurface_strength": settings["strength"],
        "subsurface_color": list(settings["color"]),
        "subsurface_radius": settings["radius"],
        "subsurface_power": settings["power"],
        "subsurface_wrap": settings["wrap"],
        "subsurface_thickness": settings["thickness"],
    }


def apply_subsurface_scattering(
    rgb: Any,
    albedo: Any,
    *,
    normal: tuple[Any, Any, Any],
    light_dir: tuple[float, float, float],
    view_dir: tuple[float, float, float],
    ndotl: Any,
    ao: Any,
    direct_strength: float,
    env_rgb: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_subsurface_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return rgb
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
    base = np.asarray(albedo, dtype=np.float32)
    if out.ndim != 3 or base.ndim != 3 or out.shape[:2] != base.shape[:2]:
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

    nx = _arr(normal[0], 0.0)
    ny = _arr(normal[1], 0.0)
    nz = _arr(normal[2], 1.0)
    length = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1.0e-6)
    nx, ny, nz = nx / length, ny / length, nz / length
    lx, ly, lz = (float(light_dir[0]), float(light_dir[1]), float(light_dir[2]))
    vx, vy, vz = (float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nv = np.clip(nx * vx + ny * vy + nz * vz, 0.0, 1.0)
    back = np.clip(-(nx * lx + ny * ly + nz * lz), 0.0, 1.0)
    wrap = max(0.0, min(1.0, float(cfg["wrap"])))
    wrap_light = np.clip((nx * lx + ny * ly + nz * lz + wrap) / max(1.0 + wrap, 1.0e-6), 0.0, 1.0)
    falloff = max(0.5, float(cfg["power"]))
    scatter_shape = np.power(wrap_light, 1.0 / falloff) * 0.58 + np.power(back, falloff) * 0.42
    thickness = float(cfg["thickness"])
    radius = float(cfg["radius"])
    strength = float(cfg["strength"])
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)
    env = np.asarray(env_rgb, dtype=np.float32)
    if env.ndim == 1 and env.shape[0] >= 3:
        env = env[None, None, :3]
    if env.ndim != 3 or env.shape[2] < 3:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.18
    tint = np.asarray(cfg["color"], dtype=np.float32)
    edge = np.power(np.clip(1.0 - nv, 0.0, 1.0), 1.5)
    scatter = (
        base[:, :, :3]
        * tint[None, None, :]
        * (scatter_shape[:, :, None] * (0.65 + radius * 0.35) + edge[:, :, None] * (0.20 + thickness * 0.15))
        * (0.35 + np.asarray(env[:, :, :3], dtype=np.float32) * 0.65)
        * max(0.0, float(direct_strength))
        * strength
        * (0.45 + thickness)
        * (0.35 + ao_arr[:, :, None] * 0.65)
    )
    # Keep forward-lit diffuse from being simply duplicated by the SSS lobe.
    scatter *= (1.0 - nl[:, :, None] * 0.22)
    return np.clip(out + scatter, 0.0, 32.0)
