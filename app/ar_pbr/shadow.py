"""Shared AR/PBR shadow-map settings and diagnostics."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SHADOW_MAP_SIZE = 1024
DEFAULT_SHADOW_FILTER = "pcf"
DEFAULT_SHADOW_LIGHT_TYPE = "directional"
DEFAULT_SHADOW_STRENGTH = 0.78
DEFAULT_SHADOW_PCF_RADIUS = 1.35
DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS = 2.5
DEFAULT_SHADOW_BIAS = 0.002
DEFAULT_SHADOW_NORMAL_BIAS = 0.002
DEFAULT_SPOT_INNER_ANGLE = 28.0
DEFAULT_SPOT_OUTER_ANGLE = 45.0
SHADOW_PCF_KERNEL = "5x5"
SHADOW_PCSS_BLOCKER_KERNEL = "5x5"


def _clamp_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def normalize_shadow_filter(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"pcss", "percentage_closer_soft_shadows", "soft"}:
        return "pcss"
    return "pcf"


def normalize_shadow_light_type(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text in {"spot", "spotlight", "spot_light"}:
        return "spot"
    return "directional"


def normalize_shadow_settings(lighting: Mapping[str, Any] | None) -> dict[str, Any]:
    data = lighting if isinstance(lighting, Mapping) else {}
    light_type = normalize_shadow_light_type(data.get("shadow_light_type", data.get("light_type", DEFAULT_SHADOW_LIGHT_TYPE)))
    filter_name = normalize_shadow_filter(
        data.get("shadow_filter", data.get("shadow_filter_mode", data.get("shadow_soft_filter", DEFAULT_SHADOW_FILTER)))
    )
    spot_outer = _clamp_float(
        data.get("shadow_spot_outer_angle", data.get("spot_outer_angle")),
        DEFAULT_SPOT_OUTER_ANGLE,
        1.0,
        89.0,
    )
    spot_inner = _clamp_float(
        data.get("shadow_spot_inner_angle", data.get("spot_inner_angle")),
        min(DEFAULT_SPOT_INNER_ANGLE, spot_outer),
        0.0,
        spot_outer,
    )
    return {
        "schema": "tigerstudio.ar_pbr.shadow_map.v1",
        "enabled": True,
        "primary_shadow_model": "shadow_map",
        "contact_shadow_role": "helper_only",
        "light_type": light_type,
        "filter": filter_name,
        "map_size": int(_clamp_float(data.get("shadow_map_size"), DEFAULT_SHADOW_MAP_SIZE, 256.0, 4096.0)),
        "pcf_radius_texels": _clamp_float(
            data.get("shadow_pcf_radius", data.get("shadow_softness")),
            DEFAULT_SHADOW_PCF_RADIUS,
            0.0,
            12.0,
        ),
        "pcss_blocker_radius_texels": _clamp_float(
            data.get("shadow_pcss_blocker_radius", data.get("pcss_blocker_radius")),
            DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS,
            0.0,
            16.0,
        ),
        "bias": _clamp_float(data.get("shadow_bias"), DEFAULT_SHADOW_BIAS, 0.00005, 0.08),
        "normal_bias": _clamp_float(data.get("shadow_normal_bias"), DEFAULT_SHADOW_NORMAL_BIAS, 0.0, 0.08),
        "spot_inner_angle": spot_inner,
        "spot_outer_angle": spot_outer,
    }


def shadow_filter_diagnostics(
    *,
    settings: Mapping[str, Any],
    shadow_map_requested: bool,
    shadow_map_enabled: bool,
    backend: str = "",
    shadow_error: str = "",
) -> dict[str, Any]:
    shadow = normalize_shadow_settings(settings)
    return {
        "schema": "tigerstudio.ar_pbr.shadow_filter.v1",
        "shadow_map_requested": bool(shadow_map_requested),
        "shadow_map_enabled": bool(shadow_map_enabled),
        "shadow_map_size": int(shadow["map_size"]),
        "primary_shadow_model": "shadow_map" if shadow_map_enabled else "contact_shadow_fallback",
        "contact_shadow_role": "helper_only",
        "light_type": str(shadow["light_type"]),
        "filter": str(shadow["filter"]) if shadow_map_enabled else "contact_shadow_fallback",
        "backend": str(backend or ("shadow_map" if shadow_map_enabled else "fallback")),
        "pcf_kernel": SHADOW_PCF_KERNEL,
        "pcf_radius_texels": float(shadow["pcf_radius_texels"]),
        "pcss_blocker_kernel": SHADOW_PCSS_BLOCKER_KERNEL if shadow["filter"] == "pcss" else "",
        "pcss_blocker_radius_texels": float(shadow["pcss_blocker_radius_texels"]),
        "bias": float(shadow["bias"]),
        "normal_bias": float(shadow["normal_bias"]),
        "spot_inner_angle": float(shadow["spot_inner_angle"]),
        "spot_outer_angle": float(shadow["spot_outer_angle"]),
        "shadow_error": str(shadow_error or ""),
    }
