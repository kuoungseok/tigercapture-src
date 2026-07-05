"""Shared shadow/reflection catcher settings for AR/PBR compositing."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SHADOW_CATCHER_OPACITY = 0.86
DEFAULT_SHADOW_CATCHER_SOFTNESS = 0.55
DEFAULT_SHADOW_CATCHER_MATTE_ALPHA = 0.0
DEFAULT_REFLECTION_CATCHER_OPACITY = 0.20
DEFAULT_REFLECTION_CATCHER_ROUGHNESS = 0.62
DEFAULT_REFLECTION_CATCHER_SOFTNESS = 0.45
DEFAULT_CONTACT_REFLECTION_STRENGTH = 0.18
DEFAULT_CONTACT_REFLECTION_FALLOFF = 0.58


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _first(data: Mapping[str, Any], keys: tuple[str, ...], default: float) -> float:
    for key in keys:
        if key in data:
            return _float(data.get(key), default)
    return float(default)


def normalize_catcher_settings(value: Any) -> dict[str, Any]:
    """Normalize matte/catcher controls shared by preview and export paths."""
    data = _as_mapping(value)
    shadow_opacity = _clamp(
        _first(
            data,
            ("shadow_catcher_opacity", "shadow_opacity", "contact_shadow_opacity"),
            DEFAULT_SHADOW_CATCHER_OPACITY,
        ),
        0.0,
        1.0,
    )
    shadow_softness = _clamp(
        _first(
            data,
            ("shadow_catcher_softness", "contact_shadow_softness", "catcher_shadow_softness"),
            DEFAULT_SHADOW_CATCHER_SOFTNESS,
        ),
        0.0,
        1.0,
    )
    shadow_matte_alpha = _clamp(
        _first(
            data,
            ("shadow_catcher_matte_alpha", "shadow_matte_alpha", "catcher_matte_alpha"),
            DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
        ),
        0.0,
        1.0,
    )
    reflection_opacity = _clamp(
        _first(
            data,
            ("reflection_catcher_opacity", "reflection_opacity", "ground_reflection_opacity"),
            DEFAULT_REFLECTION_CATCHER_OPACITY,
        ),
        0.0,
        1.0,
    )
    reflection_roughness = _clamp(
        _first(
            data,
            ("reflection_catcher_roughness", "reflection_roughness", "ground_reflection_roughness"),
            DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
        ),
        0.02,
        1.0,
    )
    reflection_softness = _clamp(
        _first(
            data,
            ("reflection_catcher_softness", "reflection_softness", "reflection_blur"),
            DEFAULT_REFLECTION_CATCHER_SOFTNESS,
        ),
        0.0,
        1.0,
    )
    contact_reflection_strength = _clamp(
        _first(
            data,
            ("contact_reflection_strength", "contact_reflection", "contact_reflection_opacity"),
            DEFAULT_CONTACT_REFLECTION_STRENGTH,
        ),
        0.0,
        1.0,
    )
    contact_reflection_falloff = _clamp(
        _first(
            data,
            ("contact_reflection_falloff", "reflection_contact_falloff"),
            DEFAULT_CONTACT_REFLECTION_FALLOFF,
        ),
        0.05,
        1.0,
    )
    return {
        "schema": "tigerstudio.ar_pbr.catcher.v1",
        "shadow_catcher": {
            "opacity": shadow_opacity,
            "softness": shadow_softness,
            "matte_alpha": shadow_matte_alpha,
            "mode": "matte_soft_contact_shadow",
        },
        "reflection_catcher": {
            "opacity": reflection_opacity,
            "roughness": reflection_roughness,
            "softness": reflection_softness,
            "matte_alpha": shadow_matte_alpha,
            "contact_reflection_strength": contact_reflection_strength,
            "contact_reflection_falloff": contact_reflection_falloff,
            "mode": "roughness_blur_contact_reflection",
        },
    }


def flatten_catcher_settings(value: Any) -> dict[str, float]:
    settings = normalize_catcher_settings(value)
    shadow = settings["shadow_catcher"]
    reflection = settings["reflection_catcher"]
    return {
        "shadow_catcher_opacity": float(shadow["opacity"]),
        "shadow_catcher_softness": float(shadow["softness"]),
        "shadow_catcher_matte_alpha": float(shadow["matte_alpha"]),
        "reflection_catcher_opacity": float(reflection["opacity"]),
        "reflection_catcher_roughness": float(reflection["roughness"]),
        "reflection_catcher_softness": float(reflection["softness"]),
        "contact_reflection_strength": float(reflection["contact_reflection_strength"]),
        "contact_reflection_falloff": float(reflection["contact_reflection_falloff"]),
    }
