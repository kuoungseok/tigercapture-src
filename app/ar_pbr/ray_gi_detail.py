"""Advanced ray/hybrid GI detail controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_RAY_GI_DETAIL_MODE = "off"
DEFAULT_RAY_GI_MAX_BOUNCES = 1
DEFAULT_RAY_GI_DIFFUSE_BOUNCES = 1
DEFAULT_RAY_GI_SPECULAR_BOUNCES = 1
DEFAULT_RAY_GI_REFRACTION_BOUNCES = 1
DEFAULT_DIRECT_RADIANCE_CLAMP = 0.0
DEFAULT_INDIRECT_RADIANCE_CLAMP = 0.0
DEFAULT_LIGHT_SAMPLING_MODE = "standard"
DEFAULT_LIGHT_SAMPLE_COUNT = 1
DEFAULT_ENVIRONMENT_SAMPLE_COUNT = 1
DEFAULT_DENOISE_CHANNELS = ["beauty"]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "advanced", "ray", "path_traced"}:
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


def _nested(data: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("ray_gi_detail", "ray_gi", "gi_detail", "path_tracing_detail"):
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    hybrid = data.get("hybrid_rendering")
    if isinstance(hybrid, Mapping):
        nested = hybrid.get("ray_gi_detail")
        if isinstance(nested, Mapping):
            return nested
    return {}


def _value(data: Mapping[str, Any], nested: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in nested:
            return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _explicit(data: Mapping[str, Any], nested: Mapping[str, Any], *keys: str) -> bool:
    return any(key in nested or key in data for key in keys)


def _mode(value: Any) -> str:
    text = str(value or DEFAULT_RAY_GI_DETAIL_MODE).strip().casefold().replace("-", "_")
    if text in {"pathtraced", "path_trace", "pt"}:
        return "path_traced"
    if text in {"raytraced", "ray_trace", "rt"}:
        return "ray_traced"
    if text in {"advanced", "detail", "hybrid_detail"}:
        return "hybrid"
    if text not in {"off", "hybrid", "ray_traced", "path_traced"}:
        return DEFAULT_RAY_GI_DETAIL_MODE
    return text


def _sampling_mode(value: Any, *, advanced: bool = False) -> str:
    text = str(value or ("mis" if advanced else DEFAULT_LIGHT_SAMPLING_MODE)).strip().casefold().replace("-", "_")
    if text in {"importance", "importance_sampling", "weighted"}:
        return "importance"
    if text in {"multiple_importance", "multiple_importance_sampling"}:
        return "mis"
    if text in {"reservoir", "ris", "restir"}:
        return "reservoir"
    if text not in {"standard", "importance", "mis", "reservoir"}:
        return DEFAULT_LIGHT_SAMPLING_MODE
    return text


def _denoise_channels(data: Mapping[str, Any], nested: Mapping[str, Any]) -> tuple[list[str], bool, bool, bool, bool, bool, bool]:
    aliases = {
        "beauty": "beauty",
        "color": "beauty",
        "final": "beauty",
        "diffuse": "diffuse",
        "diffuse_indirect": "diffuse",
        "specular": "specular",
        "specular_indirect": "specular",
        "transmission": "transmission",
        "refraction": "transmission",
    }
    raw = _value(data, nested, "denoise_channels", "ray_gi_denoise_channels")
    channels: list[str] = []
    if isinstance(raw, str):
        source = [part.strip() for part in raw.replace(";", ",").split(",")]
    elif isinstance(raw, (list, tuple, set)):
        source = list(raw)
    else:
        source = []
    for item in source:
        key = aliases.get(str(item).strip().casefold().replace("-", "_"))
        if key and key not in channels:
            channels.append(key)

    beauty = _bool_value(
        _value(data, nested, "denoise_beauty", "ray_gi_denoise_beauty"),
        "beauty" in channels if channels else True,
    )
    diffuse = _bool_value(
        _value(data, nested, "denoise_diffuse", "ray_gi_denoise_diffuse"),
        "diffuse" in channels,
    )
    specular = _bool_value(
        _value(data, nested, "denoise_specular", "ray_gi_denoise_specular"),
        "specular" in channels,
    )
    transmission = _bool_value(
        _value(data, nested, "denoise_transmission", "ray_gi_denoise_transmission"),
        "transmission" in channels,
    )
    if beauty and "beauty" not in channels:
        channels.append("beauty")
    if diffuse and "diffuse" not in channels:
        channels.append("diffuse")
    if specular and "specular" not in channels:
        channels.append("specular")
    if transmission and "transmission" not in channels:
        channels.append("transmission")
    if not channels:
        channels = list(DEFAULT_DENOISE_CHANNELS)
    albedo_guided = _bool_value(_value(data, nested, "denoise_albedo_guided", "ray_gi_denoise_albedo_guided"), False)
    normal_guided = _bool_value(_value(data, nested, "denoise_normal_guided", "ray_gi_denoise_normal_guided"), False)
    return channels, beauty, diffuse, specular, transmission, albedo_guided, normal_guided


def normalize_ray_gi_detail_settings(value: Any) -> dict[str, Any]:
    """Normalize advanced ray/path tracing controls without requiring a native tracer.

    Packet export applies the clamp and beauty-denoise-channel portions. Bounce
    counts and advanced sampling are diagnostic contracts until a native ray or
    hybrid GI integrator is available.
    """
    data = _as_mapping(value)
    nested = _nested(data)

    mode = _mode(_first_value(
        _value(data, nested, "mode", "ray_gi_detail_mode", "ray_gi_mode"),
        DEFAULT_RAY_GI_DETAIL_MODE,
    ))
    enabled_seed = _bool_value(
        _value(data, nested, "enabled", "ray_gi_detail_enabled", "advanced_gi_enabled"),
        mode != "off",
    )
    diffuse_default = 2 if enabled_seed else DEFAULT_RAY_GI_DIFFUSE_BOUNCES
    specular_default = 2 if enabled_seed else DEFAULT_RAY_GI_SPECULAR_BOUNCES
    refraction_default = 2 if enabled_seed else DEFAULT_RAY_GI_REFRACTION_BOUNCES
    diffuse_bounces = _int_value(
        _value(data, nested, "diffuse_bounces", "ray_gi_diffuse_bounces", "gi_bounces", "bounce_count"),
        diffuse_default,
        0,
        16,
    )
    specular_bounces = _int_value(
        _value(data, nested, "specular_bounces", "ray_gi_specular_bounces", "specular_bounce_count"),
        specular_default,
        0,
        16,
    )
    refraction_bounces = _int_value(
        _value(data, nested, "refraction_bounces", "ray_gi_refraction_bounces", "transmission_bounces"),
        refraction_default,
        0,
        16,
    )
    max_bounces = _int_value(
        _value(data, nested, "max_bounces", "ray_gi_max_bounces"),
        max(DEFAULT_RAY_GI_MAX_BOUNCES, diffuse_bounces, specular_bounces, refraction_bounces),
        0,
        32,
    )
    max_bounces = max(max_bounces, diffuse_bounces, specular_bounces, refraction_bounces)
    direct_clamp = _float_value(
        _value(data, nested, "direct_radiance_clamp", "ray_gi_direct_radiance_clamp"),
        DEFAULT_DIRECT_RADIANCE_CLAMP,
        0.0,
        64.0,
    )
    indirect_clamp = _float_value(
        _value(data, nested, "indirect_radiance_clamp", "ray_gi_indirect_radiance_clamp"),
        DEFAULT_INDIRECT_RADIANCE_CLAMP,
        0.0,
        64.0,
    )
    advanced_sampling = _bool_value(
        _value(data, nested, "advanced_light_sampling", "ray_gi_advanced_light_sampling"),
        False,
    )
    sampling_mode = _sampling_mode(
        _value(data, nested, "light_sampling_mode", "ray_gi_light_sampling_mode"),
        advanced=advanced_sampling,
    )
    light_samples = _int_value(
        _value(data, nested, "light_sample_count", "ray_gi_light_sample_count", "light_samples"),
        8 if advanced_sampling else DEFAULT_LIGHT_SAMPLE_COUNT,
        1,
        256,
    )
    env_samples = _int_value(
        _value(data, nested, "environment_sample_count", "ray_gi_environment_sample_count", "environment_samples"),
        16 if advanced_sampling else DEFAULT_ENVIRONMENT_SAMPLE_COUNT,
        1,
        512,
    )
    mis_enabled = _bool_value(
        _value(data, nested, "mis_enabled", "multiple_importance_sampling", "ray_gi_mis_enabled"),
        sampling_mode in {"mis", "reservoir"},
    )
    importance_sampling = _bool_value(
        _value(data, nested, "importance_sampling", "ray_gi_importance_sampling"),
        sampling_mode in {"importance", "mis", "reservoir"},
    )
    (
        denoise_channels,
        denoise_beauty,
        denoise_diffuse,
        denoise_specular,
        denoise_transmission,
        denoise_albedo_guided,
        denoise_normal_guided,
    ) = _denoise_channels(data, nested)

    denoise_explicit = _explicit(
        data,
        nested,
        "denoise_channels",
        "ray_gi_denoise_channels",
        "denoise_beauty",
        "ray_gi_denoise_beauty",
        "denoise_diffuse",
        "denoise_specular",
        "denoise_transmission",
        "denoise_albedo_guided",
        "denoise_normal_guided",
    )
    enabled = bool(
        enabled_seed
        or mode != "off"
        or diffuse_bounces > DEFAULT_RAY_GI_DIFFUSE_BOUNCES
        or specular_bounces > DEFAULT_RAY_GI_SPECULAR_BOUNCES
        or refraction_bounces > DEFAULT_RAY_GI_REFRACTION_BOUNCES
        or max_bounces > DEFAULT_RAY_GI_MAX_BOUNCES
        or direct_clamp > 0.0
        or indirect_clamp > 0.0
        or advanced_sampling
        or sampling_mode != DEFAULT_LIGHT_SAMPLING_MODE
        or light_samples > DEFAULT_LIGHT_SAMPLE_COUNT
        or env_samples > DEFAULT_ENVIRONMENT_SAMPLE_COUNT
        or mis_enabled
        or importance_sampling
        or denoise_explicit
    )
    if enabled and mode == "off":
        mode = "hybrid"
    if not enabled:
        mode = "off"
        diffuse_bounces = DEFAULT_RAY_GI_DIFFUSE_BOUNCES
        specular_bounces = DEFAULT_RAY_GI_SPECULAR_BOUNCES
        refraction_bounces = DEFAULT_RAY_GI_REFRACTION_BOUNCES
        max_bounces = DEFAULT_RAY_GI_MAX_BOUNCES
        direct_clamp = DEFAULT_DIRECT_RADIANCE_CLAMP
        indirect_clamp = DEFAULT_INDIRECT_RADIANCE_CLAMP
        advanced_sampling = False
        sampling_mode = DEFAULT_LIGHT_SAMPLING_MODE
        light_samples = DEFAULT_LIGHT_SAMPLE_COUNT
        env_samples = DEFAULT_ENVIRONMENT_SAMPLE_COUNT
        mis_enabled = False
        importance_sampling = False
        denoise_channels = list(DEFAULT_DENOISE_CHANNELS)
        denoise_beauty = True
        denoise_diffuse = False
        denoise_specular = False
        denoise_transmission = False
        denoise_albedo_guided = False
        denoise_normal_guided = False

    return {
        "schema": "tigerstudio.ar_pbr.ray_gi_detail.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "max_bounces": int(max_bounces),
        "diffuse_bounces": int(diffuse_bounces),
        "specular_bounces": int(specular_bounces),
        "refraction_bounces": int(refraction_bounces),
        "direct_radiance_clamp": float(direct_clamp),
        "indirect_radiance_clamp": float(indirect_clamp),
        "advanced_light_sampling": bool(advanced_sampling or sampling_mode != DEFAULT_LIGHT_SAMPLING_MODE),
        "light_sampling_mode": sampling_mode,
        "light_sample_count": int(light_samples),
        "environment_sample_count": int(env_samples),
        "mis_enabled": bool(mis_enabled),
        "importance_sampling": bool(importance_sampling),
        "denoise_channels": list(denoise_channels),
        "denoise_beauty": bool(denoise_beauty),
        "denoise_diffuse": bool(denoise_diffuse),
        "denoise_specular": bool(denoise_specular),
        "denoise_transmission": bool(denoise_transmission),
        "denoise_albedo_guided": bool(denoise_albedo_guided),
        "denoise_normal_guided": bool(denoise_normal_guided),
        "packet_policy": "direct_indirect_radiance_clamp_and_beauty_denoise_channel_gate",
        "full_gpu_policy": "contract_only_until_native_ray_or_hybrid_detail_path",
        "render_pass_safe": True,
    }


def flatten_ray_gi_detail_settings(value: Any) -> dict[str, Any]:
    settings = normalize_ray_gi_detail_settings(value)
    return {
        "ray_gi_detail_mode": settings["mode"],
        "ray_gi_detail_enabled": settings["enabled"],
        "ray_gi_max_bounces": settings["max_bounces"],
        "ray_gi_diffuse_bounces": settings["diffuse_bounces"],
        "ray_gi_specular_bounces": settings["specular_bounces"],
        "ray_gi_refraction_bounces": settings["refraction_bounces"],
        "ray_gi_direct_radiance_clamp": settings["direct_radiance_clamp"],
        "ray_gi_indirect_radiance_clamp": settings["indirect_radiance_clamp"],
        "ray_gi_advanced_light_sampling": settings["advanced_light_sampling"],
        "ray_gi_light_sampling_mode": settings["light_sampling_mode"],
        "ray_gi_light_sample_count": settings["light_sample_count"],
        "ray_gi_environment_sample_count": settings["environment_sample_count"],
        "ray_gi_mis_enabled": settings["mis_enabled"],
        "ray_gi_importance_sampling": settings["importance_sampling"],
        "ray_gi_denoise_channels": list(settings["denoise_channels"]),
        "ray_gi_denoise_beauty": settings["denoise_beauty"],
        "ray_gi_denoise_diffuse": settings["denoise_diffuse"],
        "ray_gi_denoise_specular": settings["denoise_specular"],
        "ray_gi_denoise_transmission": settings["denoise_transmission"],
        "ray_gi_denoise_albedo_guided": settings["denoise_albedo_guided"],
        "ray_gi_denoise_normal_guided": settings["denoise_normal_guided"],
    }
