"""Realtime cloth/sheen controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_CLOTH_SHEEN_MODE = "off"
DEFAULT_CLOTH_SHEEN_STRENGTH = 0.0
DEFAULT_CLOTH_SHEEN_COLOR = [0.92, 0.96, 1.0]
DEFAULT_CLOTH_SHEEN_ROUGHNESS = 0.58
DEFAULT_CLOTH_SHEEN_EDGE_TINT = [0.72, 0.82, 1.0]
DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH = 0.24
DEFAULT_CLOTH_SHEEN_WRAP = 0.34
DEFAULT_CLOTH_SHEEN_RETROREFLECTION = 0.28


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "cloth", "sheen", "fabric", "velvet", "fuzz"}:
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
        "cloth_sheen_rendering",
        "cloth_rendering",
        "sheen_rendering",
        "fabric_rendering",
        "cloth_sheen",
        "cloth",
        "sheen",
        "fabric",
        "velvet",
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


def normalize_cloth_sheen_settings(value: Any) -> dict[str, Any]:
    """Normalize optional realtime cloth/fabric sheen controls.

    This approximates fabric with a broad Charlie-style sheen term, grazing
    fuzz, and retroreflection. It does not create weave geometry, simulate
    cloth, displace thread fibers, or render deep fiber shadows.
    """
    data = _as_mapping(value)
    cloth_raw = data.get("cloth_sheen", data.get("cloth", data.get("sheen")))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("cloth_sheen_mode"),
        data.get("cloth_mode"),
        data.get("sheen_mode"),
        DEFAULT_CLOTH_SHEEN_MODE,
    )
    mode = str(raw_mode or DEFAULT_CLOTH_SHEEN_MODE).strip().casefold().replace("-", "_")
    if mode in {"cloth", "fabric", "velvet", "fuzz", "soft_sheen", "charlie", "charlie_sheen"}:
        mode = "sheen"
    if mode not in {"off", "sheen"}:
        mode = DEFAULT_CLOTH_SHEEN_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("cloth_sheen_enabled"),
        data.get("cloth_enabled"),
        data.get("sheen_enabled"),
        cloth_raw if isinstance(cloth_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "sheen")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "sheen", "cloth"),
            data.get("cloth_sheen_strength"),
            data.get("cloth_strength"),
            data.get("sheen_strength"),
            cloth_raw if not isinstance(cloth_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_CLOTH_SHEEN_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "sheen"

    color = _vec3_value(
        _first_value(
            _nested(data, "color", "tint", "sheen_color", "cloth_sheen_color"),
            data.get("cloth_sheen_color"),
            data.get("sheen_color"),
            data.get("cloth_tint"),
        ),
        DEFAULT_CLOTH_SHEEN_COLOR,
    )
    roughness = _float_value(
        _first_value(
            _nested(data, "roughness", "width", "sheen_roughness", "cloth_sheen_roughness"),
            data.get("cloth_sheen_roughness"),
            data.get("sheen_roughness"),
        ),
        DEFAULT_CLOTH_SHEEN_ROUGHNESS,
        0.03,
        1.0,
    )
    edge_tint = _vec3_value(
        _first_value(
            _nested(data, "edge_tint", "edge_color", "fuzz_color", "cloth_sheen_edge_tint"),
            data.get("cloth_sheen_edge_tint"),
            data.get("sheen_edge_tint"),
            data.get("fuzz_tint"),
        ),
        DEFAULT_CLOTH_SHEEN_EDGE_TINT,
    )
    fiber_strength = _float_value(
        _first_value(
            _nested(data, "fiber_strength", "fuzz_strength", "fiber", "cloth_sheen_fiber_strength"),
            data.get("cloth_sheen_fiber_strength"),
            data.get("fuzz_strength"),
        ),
        DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH,
        0.0,
        1.0,
    )
    wrap = _float_value(
        _first_value(
            _nested(data, "wrap", "wrap_lighting", "cloth_sheen_wrap"),
            data.get("cloth_sheen_wrap"),
            data.get("sheen_wrap"),
        ),
        DEFAULT_CLOTH_SHEEN_WRAP,
        0.0,
        1.0,
    )
    retroreflection = _float_value(
        _first_value(
            _nested(data, "retroreflection", "retro", "backscatter", "cloth_sheen_retroreflection"),
            data.get("cloth_sheen_retroreflection"),
            data.get("sheen_retroreflection"),
        ),
        DEFAULT_CLOTH_SHEEN_RETROREFLECTION,
        0.0,
        1.0,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        fiber_strength = 0.0
        retroreflection = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.cloth_sheen.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "color": [float(v) for v in color],
        "roughness": float(roughness),
        "edge_tint": [float(v) for v in edge_tint],
        "fiber_strength": float(fiber_strength),
        "wrap": float(wrap),
        "retroreflection": float(retroreflection),
        "shading_model": "charlie_sheen_retroreflection_fabric_fuzz",
        "geometry_policy": "no_thread_geometry_or_weave_displacement",
        "simulation_policy": "no_cloth_simulation_or_groomed_fibers",
        "shadow_policy": "shading_only_no_deep_fiber_shadow_maps",
        "render_pass_safe": True,
    }


def flatten_cloth_sheen_settings(value: Any) -> dict[str, Any]:
    settings = normalize_cloth_sheen_settings(value)
    return {
        "cloth_sheen_mode": settings["mode"],
        "cloth_sheen_enabled": settings["enabled"],
        "cloth_sheen_strength": settings["strength"],
        "cloth_sheen_color": list(settings["color"]),
        "cloth_sheen_roughness": settings["roughness"],
        "cloth_sheen_edge_tint": list(settings["edge_tint"]),
        "cloth_sheen_fiber_strength": settings["fiber_strength"],
        "cloth_sheen_wrap": settings["wrap"],
        "cloth_sheen_retroreflection": settings["retroreflection"],
    }


def apply_cloth_sheen_shading(
    rgb: Any,
    albedo: Any,
    *,
    normal: tuple[Any, Any, Any],
    light_dir: tuple[float, float, float],
    view_dir: tuple[float, float, float],
    ndotl: Any,
    ndotv: Any,
    ndoth: Any,
    roughness: Any,
    ao: Any,
    direct_strength: float,
    env_rgb: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_cloth_sheen_settings(settings or {})
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
    n_len = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1.0e-6)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len
    lx, ly, lz = (float(light_dir[0]), float(light_dir[1]), float(light_dir[2]))
    vx, vy, vz = (float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
    lv = np.clip(lx * vx + ly * vy + lz * vz, -1.0, 1.0)

    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nv = np.clip(_arr(ndotv, 0.0), 0.0, 1.0)
    nh = np.clip(_arr(ndoth, 0.0), 0.0, 1.0)
    rough = np.clip(_arr(roughness, 0.55), 0.03, 1.0)
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)

    sheen_roughness = np.clip(float(cfg["roughness"]) * 0.72 + rough * 0.28, 0.03, 1.0)
    sin_h = np.sqrt(np.maximum(1.0 - nh * nh, 0.0))
    exponent = 1.0 + sheen_roughness * 9.0
    charlie = np.power(sin_h, exponent) * (0.45 + sheen_roughness * 0.75)
    wrap = max(0.0, min(1.0, float(cfg["wrap"])))
    n_dot_l = nx * lx + ny * ly + nz * lz
    wrap_light = np.clip((n_dot_l + wrap) / max(1.0 + wrap, 1.0e-6), 0.0, 1.0)
    edge = np.power(np.clip(1.0 - nv, 0.0, 1.0), 2.0)
    retro = np.power(np.clip(lv * 0.5 + 0.5, 0.0, 1.0), 3.0) * float(cfg["retroreflection"])
    fuzz = edge * wrap_light * float(cfg["fiber_strength"])

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
    edge_tint = np.asarray(cfg["edge_tint"], dtype=np.float32)
    cloth_tint = base[:, :, :3] * 0.38 + color[None, None, :] * 0.62
    sheen = (
        (charlie * (0.35 + nl * 0.65) + retro * wrap_light)[:, :, None]
        * cloth_tint
        * max(0.0, float(direct_strength))
        * float(cfg["strength"])
        * (0.30 + ao_arr[:, :, None] * 0.70)
    )
    fiber = (
        (fuzz[:, :, None] * edge_tint[None, None, :] + edge[:, :, None] * env * 0.18)
        * float(cfg["strength"])
        * (0.35 + ao_arr[:, :, None] * 0.65)
    )
    return np.clip(out + sheen + fiber, 0.0, 32.0)
