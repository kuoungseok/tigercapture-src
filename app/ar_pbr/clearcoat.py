"""Clearcoat layer controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_CLEARCOAT_MODE = "off"
DEFAULT_CLEARCOAT_STRENGTH = 0.0
DEFAULT_CLEARCOAT_ROUGHNESS = 0.12
DEFAULT_CLEARCOAT_IOR = 1.5
DEFAULT_CLEARCOAT_TINT = [1.0, 1.0, 1.0]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "clearcoat", "clear_coat", "coat"}:
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
    for container_key in ("clearcoat_rendering", "clearcoat", "clear_coat", "coat"):
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


def _f0_from_ior(ior: float) -> float:
    eta = max(1.0, float(ior))
    return ((eta - 1.0) / max(eta + 1.0, 1.0e-6)) ** 2


def normalize_clearcoat_settings(value: Any) -> dict[str, Any]:
    """Normalize optional top-coat specular layer controls."""
    data = _as_mapping(value)
    clearcoat_raw = data.get("clearcoat")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("clearcoat_mode"),
        data.get("clear_coat_mode"),
        DEFAULT_CLEARCOAT_MODE,
    )
    mode = str(raw_mode or DEFAULT_CLEARCOAT_MODE).strip().casefold().replace("-", "_")
    if mode in {"clear_coat", "coat", "topcoat", "top_coat"}:
        mode = "clearcoat"
    if mode not in {"off", "clearcoat"}:
        mode = DEFAULT_CLEARCOAT_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("clearcoat_enabled"),
        data.get("clear_coat_enabled"),
        clearcoat_raw if isinstance(clearcoat_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "clearcoat")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "factor", "clearcoat"),
            data.get("clearcoat_strength"),
            data.get("clearcoat_factor"),
            data.get("clear_coat_strength"),
            clearcoat_raw if not isinstance(clearcoat_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_CLEARCOAT_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "clearcoat"
    roughness = _float_value(
        _first_value(
            _nested(data, "clearcoat_roughness", "coat_roughness", "roughness"),
            data.get("clearcoat_roughness"),
            data.get("clear_coat_roughness"),
        ),
        DEFAULT_CLEARCOAT_ROUGHNESS,
        0.02,
        1.0,
    )
    ior = _float_value(
        _first_value(
            _nested(data, "clearcoat_ior", "coat_ior", "ior"),
            data.get("clearcoat_ior"),
            data.get("clear_coat_ior"),
        ),
        DEFAULT_CLEARCOAT_IOR,
        1.0,
        2.5,
    )
    tint = _vec3_value(
        _first_value(
            _nested(data, "tint", "color", "clearcoat_tint", "clearcoat_color"),
            data.get("clearcoat_tint"),
            data.get("clear_coat_tint"),
        ),
        DEFAULT_CLEARCOAT_TINT,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.clearcoat.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "roughness": float(roughness),
        "ior": float(ior),
        "f0": float(_f0_from_ior(ior)),
        "tint": [float(v) for v in tint],
        "layer_model": "secondary_ggx_top_specular_lobe",
        "energy_compensation": "attenuate_base_specular_slightly",
        "render_pass_safe": True,
    }


def flatten_clearcoat_settings(value: Any) -> dict[str, Any]:
    settings = normalize_clearcoat_settings(value)
    return {
        "clearcoat_mode": settings["mode"],
        "clearcoat_enabled": settings["enabled"],
        "clearcoat_strength": settings["strength"],
        "clearcoat_roughness": settings["roughness"],
        "clearcoat_ior": settings["ior"],
        "clearcoat_tint": list(settings["tint"]),
    }


def apply_clearcoat_layer(
    rgb: Any,
    *,
    spec_env: Any,
    ndotv: Any,
    ndotl: Any,
    ndoth: Any,
    vdoth: Any,
    roughness: Any,
    metallic: Any,
    ao: Any,
    direct_strength: float,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_clearcoat_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return rgb
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
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

    strength = float(cfg["strength"])
    coat_rough = float(cfg["roughness"])
    f0 = float(cfg["f0"])
    tint = np.asarray(cfg["tint"], dtype=np.float32)
    nv = np.clip(_arr(ndotv, 1.0), 0.0, 1.0)
    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nh = np.clip(_arr(ndoth, 0.0), 0.0, 1.0)
    vh = np.clip(_arr(vdoth, 1.0), 0.0, 1.0)
    metal = np.clip(_arr(metallic, 0.0), 0.0, 1.0)
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)
    coat_fresnel = f0 + (1.0 - f0) * np.power(1.0 - nv, 5.0)
    half_fresnel = f0 + (1.0 - f0) * np.power(1.0 - vh, 5.0)

    a = max(0.02, coat_rough) ** 2
    a2 = a * a
    denom = nh * nh * (a2 - 1.0) + 1.0
    distribution = a2 / np.maximum(np.pi * denom * denom, 1.0e-6)
    k = ((coat_rough + 1.0) ** 2) / 8.0
    g_v = nv / np.maximum(nv * (1.0 - k) + k, 1.0e-6)
    g_l = nl / np.maximum(nl * (1.0 - k) + k, 1.0e-6)
    direct = (
        distribution
        * g_v
        * g_l
        * half_fresnel
        / np.maximum(4.0 * nv * nl, 1.0e-5)
        * nl
        * max(0.0, float(direct_strength))
    )
    env = np.asarray(spec_env, dtype=np.float32)
    env_boost = 1.18 - coat_rough * 0.42
    coat = (
        (env * (coat_fresnel[:, :, None] * env_boost) + direct[:, :, None])
        * tint[None, None, :]
        * strength
        * (0.40 + 0.60 * ao_arr[:, :, None])
        * (1.0 - metal[:, :, None] * 0.18)
    )
    base_attenuation = 1.0 - strength * (0.025 + 0.025 * (1.0 - np.clip(rough, 0.0, 1.0)))[:, :, None]
    return out * base_attenuation + coat
