"""Tiger Glass material contract for backdrop-aware Motion layers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import AnimatedProperty, MotionEffectRef


GLASS_CONTRACT = "tigerstudio.motion.glass.v1"
GLASS_EFFECT_KIND = "tiger_glass"

_CLEAR = {
    "blur_radius": 4.0,
    "refraction": 3.0,
    "normal_scale": 1.4,
    "thickness": 0.45,
    "absorption": 0.08,
    "edge_highlight": 0.35,
    "specular": 0.4,
    "dispersion": 0.35,
    "bloom": 0.08,
    "tint_strength": 0.05,
    "driver_x": 0.0,
    "driver_y": 0.0,
}


def _preset(**overrides: Any) -> dict[str, Any]:
    return {**_CLEAR, **overrides}


GLASS_PRESETS: dict[str, dict[str, Any]] = {
    "clear": _preset(tint="#dff7ff"),
    "frosted": _preset(
        blur_radius=18.0, refraction=1.5, normal_scale=2.2,
        absorption=0.18, tint="#e8f4f8", tint_strength=0.14,
        edge_highlight=0.22, dispersion=0.1,
    ),
    "tinted": _preset(
        blur_radius=9.0, refraction=4.0, absorption=0.3,
        tint="#57c8b5", tint_strength=0.38, edge_highlight=0.4,
    ),
    "glossy": _preset(
        blur_radius=6.0, refraction=5.5, normal_scale=1.8,
        thickness=0.7, edge_highlight=0.75, specular=0.9,
        dispersion=0.6, bloom=0.22, tint="#e7fbff",
    ),
    "liquid_cta": _preset(
        blur_radius=12.0, refraction=9.0, normal_scale=2.8,
        thickness=0.9, absorption=0.2, edge_highlight=0.95,
        specular=1.2, dispersion=1.1, bloom=0.3,
        tint="#a8e8ff", tint_strength=0.22,
    ),
}

_LIMITS = {
    "blur_radius": (0.0, 100.0),
    "refraction": (0.0, 64.0),
    "normal_scale": (0.1, 20.0),
    "thickness": (0.0, 2.0),
    "absorption": (0.0, 1.0),
    "edge_highlight": (0.0, 2.0),
    "specular": (0.0, 4.0),
    "dispersion": (0.0, 8.0),
    "bloom": (0.0, 2.0),
    "tint_strength": (0.0, 1.0),
    "driver_x": (-10.0, 10.0),
    "driver_y": (-10.0, 10.0),
}


def glass_presets() -> list[dict[str, Any]]:
    return [
        {"id": preset_id, "params": dict(params)}
        for preset_id, params in GLASS_PRESETS.items()
    ]


def normalize_glass(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "clear",
) -> dict[str, Any]:
    preset_id = str(preset or "clear")
    defaults = GLASS_PRESETS.get(preset_id, GLASS_PRESETS["clear"])
    source = dict(values or {})
    result: dict[str, Any] = {}
    for key, (minimum, maximum) in _LIMITS.items():
        result[key] = max(minimum, min(maximum, float(source.get(key, defaults[key]))))
    result["tint"] = str(source.get("tint") or defaults.get("tint") or "#ffffff")
    result["quality"] = str(source.get("quality") or "preview").lower()
    if result["quality"] not in {"draft", "preview", "final"}:
        result["quality"] = "preview"
    result["preset"] = preset_id if preset_id in GLASS_PRESETS else "custom"
    return result


def make_glass_effect(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "clear",
) -> MotionEffectRef:
    settings = normalize_glass(values, preset=preset)
    metadata = {
        "contract": GLASS_CONTRACT,
        "preset": settings.pop("preset"),
        "quality": settings.pop("quality"),
    }
    tint = settings.pop("tint")
    return MotionEffectRef(
        kind=GLASS_EFFECT_KIND,
        params={
            key: AnimatedProperty(default=value)
            for key, value in settings.items()
        },
        metadata={**metadata, "tint": tint},
    )


def glass_effect(effects: list[MotionEffectRef] | None) -> MotionEffectRef | None:
    return next(
        (
            effect for effect in effects or ()
            if effect.enabled and effect.kind.strip().lower() == GLASS_EFFECT_KIND
        ),
        None,
    )


__all__ = [
    "GLASS_CONTRACT",
    "GLASS_EFFECT_KIND",
    "GLASS_PRESETS",
    "glass_effect",
    "glass_presets",
    "make_glass_effect",
    "normalize_glass",
]
