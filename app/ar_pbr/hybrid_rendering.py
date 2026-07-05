"""Hybrid accumulation, GI, and denoise controls for AR/PBR rendering."""
from __future__ import annotations

import math
from typing import Any, Mapping


DEFAULT_HYBRID_RENDER_MODE = "off"
DEFAULT_HYBRID_SAMPLE_COUNT = 1
DEFAULT_DIFFUSE_GI_STRENGTH = 0.0
DEFAULT_SPECULAR_GI_STRENGTH = 0.0
DEFAULT_DENOISE_STRENGTH = 0.0
DEFAULT_DENOISE_RADIUS = 1


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "hybrid", "path_traced", "path-traced"}:
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


def _nested_value(data: Mapping[str, Any], key: str) -> Any:
    nested = data.get("hybrid_rendering")
    if isinstance(nested, Mapping) and key in nested:
        return nested.get(key)
    nested = data.get("hybrid_accumulation")
    if isinstance(nested, Mapping) and key in nested:
        return nested.get(key)
    return data.get(key)


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def normalize_hybrid_render_settings(value: Any) -> dict[str, Any]:
    """Normalize optional Marmoset-style hybrid rendering controls.

    The current implementation is a deterministic approximation, not a full
    offline path tracer.  It lets preview/export paths agree on sample count,
    secondary diffuse/specular energy, and a lightweight denoise pass.
    """
    data = _as_mapping(value)
    nested = data.get("hybrid_rendering")
    hybrid_nested = nested if isinstance(nested, Mapping) else {}
    accumulation_raw = data.get("hybrid_accumulation")
    accumulation_map = accumulation_raw if isinstance(accumulation_raw, Mapping) else {}

    raw_mode = _first_value(
        hybrid_nested.get("mode")
        , accumulation_map.get("mode")
        , data.get("mode")
        , data.get("hybrid_render_mode")
        , data.get("render_quality")
        , data.get("quality")
        , DEFAULT_HYBRID_RENDER_MODE
    )
    mode = str(raw_mode or DEFAULT_HYBRID_RENDER_MODE).strip().casefold().replace("-", "_")
    if mode in {"pathtraced", "path_trace", "path_traced_preview", "pt"}:
        mode = "path_traced"
    if mode not in {"off", "realtime", "hybrid", "path_traced"}:
        mode = DEFAULT_HYBRID_RENDER_MODE

    enabled_raw = (
        hybrid_nested.get("enabled")
        if "enabled" in hybrid_nested
        else accumulation_map.get("enabled")
        if "enabled" in accumulation_map
        else accumulation_raw
        if isinstance(accumulation_raw, bool)
        else data.get("enabled")
        if "enabled" in data
        else data.get("hybrid_accumulation_enabled")
    )
    enabled = _bool_value(enabled_raw, mode in {"hybrid", "path_traced"})
    samples = _int_value(_first_value(
        _nested_value(data, "sample_count")
        , _nested_value(data, "samples")
        , data.get("sample_count")
        , data.get("hybrid_accumulation_samples")
        , data.get("accumulation_samples")
        , data.get("render_samples")),
        16 if enabled else DEFAULT_HYBRID_SAMPLE_COUNT,
        1,
        64,
    )
    if samples > 1 and mode == "off":
        mode = "hybrid"
    enabled = bool(enabled or samples > 1 or mode in {"hybrid", "path_traced"})

    default_diffuse = 0.22 if enabled else DEFAULT_DIFFUSE_GI_STRENGTH
    default_specular = 0.10 if enabled else DEFAULT_SPECULAR_GI_STRENGTH
    default_denoise = 0.35 if enabled and samples > 1 else DEFAULT_DENOISE_STRENGTH
    diffuse = _float_value(_first_value(
        _nested_value(data, "diffuse_gi_strength")
        , data.get("diffuse_gi_strength")
        , data.get("gi_diffuse_strength")
        , data.get("indirect_diffuse_strength")),
        default_diffuse,
        0.0,
        2.0,
    )
    specular = _float_value(_first_value(
        _nested_value(data, "specular_gi_strength")
        , data.get("specular_gi_strength")
        , data.get("gi_specular_strength")
        , data.get("indirect_specular_strength")),
        default_specular,
        0.0,
        2.0,
    )
    denoise = _float_value(_first_value(
        _nested_value(data, "denoise_strength")
        , data.get("denoise_strength")
        , data.get("spatial_denoise_strength")),
        default_denoise,
        0.0,
        1.0,
    )
    radius = _int_value(_first_value(
        _nested_value(data, "denoise_radius")
        , data.get("denoise_radius")
        , data.get("spatial_denoise_radius")),
        DEFAULT_DENOISE_RADIUS,
        1,
        3,
    )
    seed = _int_value(_first_value(
        _nested_value(data, "sample_seed")
        , data.get("sample_seed")
        , data.get("hybrid_sample_seed")
        , data.get("path_trace_seed")),
        0,
        0,
        2_147_483_647,
    )
    sample_gain = 1.0 - math.exp(-float(samples) / 8.0)
    if not enabled:
        mode = "off"
        samples = 1
        diffuse = 0.0
        specular = 0.0
        denoise = 0.0
        sample_gain = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.hybrid_rendering.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "sample_count": int(samples),
        "sample_seed": int(seed),
        "sample_gain": float(sample_gain),
        "diffuse_gi_strength": float(diffuse),
        "specular_gi_strength": float(specular),
        "denoise_strength": float(denoise),
        "denoise_radius": int(radius),
        "accumulation_model": "deterministic_multi_sample_gi_approximation",
        "denoise_model": "alpha_weighted_spatial_blend",
        "render_pass_safe": True,
    }


def flatten_hybrid_render_settings(value: Any) -> dict[str, Any]:
    settings = normalize_hybrid_render_settings(value)
    return {
        "hybrid_render_mode": settings["mode"],
        "hybrid_accumulation_enabled": settings["enabled"],
        "hybrid_accumulation_samples": settings["sample_count"],
        "hybrid_sample_seed": settings["sample_seed"],
        "diffuse_gi_strength": settings["diffuse_gi_strength"],
        "specular_gi_strength": settings["specular_gi_strength"],
        "denoise_strength": settings["denoise_strength"],
        "denoise_radius": settings["denoise_radius"],
    }


def apply_hybrid_gi(
    rgb: Any,
    *,
    albedo: Any,
    diffuse_env: Any,
    spec_env: Any,
    diffuse_weight: Any,
    fresnel: Any,
    roughness: Any,
    metallic: Any,
    ao: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_hybrid_render_settings(settings or {})
    if not bool(cfg["enabled"]):
        return rgb
    import numpy as np

    sample_gain = float(cfg["sample_gain"])
    diffuse_strength = float(cfg["diffuse_gi_strength"]) * sample_gain
    specular_strength = float(cfg["specular_gi_strength"]) * sample_gain
    rough = np.asarray(roughness, dtype=np.float32)
    metal = np.asarray(metallic, dtype=np.float32)
    ao_arr = np.asarray(ao, dtype=np.float32)
    diffuse_bounce = (
        np.asarray(albedo, dtype=np.float32)
        * np.asarray(diffuse_env, dtype=np.float32)
        * np.asarray(diffuse_weight, dtype=np.float32)
        * ao_arr[:, :, None]
        * diffuse_strength
        * (1.0 - metal[:, :, None])
        * (0.55 + 0.45 * rough[:, :, None])
    )
    specular_bounce = (
        np.asarray(spec_env, dtype=np.float32)
        * np.asarray(fresnel, dtype=np.float32)
        * specular_strength
        * (1.0 - rough[:, :, None] * 0.40)
        * (0.50 + 0.50 * ao_arr[:, :, None])
    )
    return np.asarray(rgb, dtype=np.float32) + diffuse_bounce + specular_bounce


def denoise_float_rgb(rgb: Any, alpha: Any, settings: Mapping[str, Any] | None) -> Any:
    cfg = normalize_hybrid_render_settings(settings or {})
    strength = float(cfg["denoise_strength"])
    if not bool(cfg["enabled"]) or strength <= 0.0:
        return rgb
    source = _as_mapping(settings)
    if "denoise_beauty" in source and not _bool_value(source.get("denoise_beauty"), True):
        return rgb
    raw_channels = source.get("denoise_channels")
    if isinstance(raw_channels, str):
        channels = {part.strip().casefold().replace("-", "_") for part in raw_channels.replace(";", ",").split(",")}
    elif isinstance(raw_channels, (list, tuple, set)):
        channels = {str(part).strip().casefold().replace("-", "_") for part in raw_channels}
    else:
        channels = set()
    if channels and channels.isdisjoint({"beauty", "color", "final"}):
        return rgb
    import numpy as np

    arr = np.asarray(rgb, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] < 3:
        return rgb
    mask = (np.asarray(alpha, dtype=np.float32) > 0.001).astype(np.float32)
    if not bool(mask.any()):
        return arr
    out = arr.copy()
    radius = int(cfg["denoise_radius"])
    for _ in range(max(1, radius)):
        padded = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        blurred = (
            padded[0:-2, 0:-2] + padded[0:-2, 1:-1] * 2.0 + padded[0:-2, 2:]
            + padded[1:-1, 0:-2] * 2.0 + padded[1:-1, 1:-1] * 4.0 + padded[1:-1, 2:] * 2.0
            + padded[2:, 0:-2] + padded[2:, 1:-1] * 2.0 + padded[2:, 2:]
        ) / 16.0
        local_luma = (
            out[:, :, 0] * 0.2126
            + out[:, :, 1] * 0.7152
            + out[:, :, 2] * 0.0722
        )
        blur_luma = (
            blurred[:, :, 0] * 0.2126
            + blurred[:, :, 1] * 0.7152
            + blurred[:, :, 2] * 0.0722
        )
        edge = np.clip(np.abs(local_luma - blur_luma), 0.0, 1.0)
        blend = strength * (1.0 - edge) * mask
        out = out * (1.0 - blend[:, :, None]) + blurred * blend[:, :, None]
    return out
