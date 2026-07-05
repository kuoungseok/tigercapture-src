"""Virtual light rigs for the Toon-only MMD renderer."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


MMD_LIGHTING_PRESETS: dict[str, dict[str, Any]] = {
    "studio_soft": {
        "label": "Studio Soft",
        "key_dir": (0.42, -0.76, -0.48),
        "key_color": (1.0, 0.96, 0.90),
        "key_intensity": 1.00,
        "fill_dir": (-0.58, -0.26, 0.42),
        "fill_color": (0.58, 0.70, 1.0),
        "fill_intensity": 0.32,
        "rim_color": (0.70, 0.88, 1.0),
        "rim_intensity": 0.12,
        "sky_color": (0.30, 0.34, 0.42),
        "ground_color": (0.18, 0.16, 0.14),
        "ambient_intensity": 0.40,
        "shadow_strength": 0.64,
        "soft_shadow_strength": 0.48,
        "shadow_softness": 1.20,
        "shadow_bias": 0.0040,
        "shadow_map_size": 1024,
        "contact_shadow_strength": 0.22,
        "ground_shadow_strength": 0.36,
        "bloom_enabled": True,
        "bloom_strength": 0.30,
        "bloom_radius": 2.0,
        "bloom_threshold": 0.08,
    },
    "golden_hour": {
        "label": "Golden Hour",
        "key_dir": (0.58, -0.58, -0.36),
        "key_color": (1.0, 0.82, 0.62),
        "key_intensity": 0.94,
        "fill_dir": (-0.50, -0.22, 0.50),
        "fill_color": (0.48, 0.62, 1.0),
        "fill_intensity": 0.26,
        "rim_color": (1.0, 0.62, 0.35),
        "rim_intensity": 0.18,
        "sky_color": (0.34, 0.30, 0.42),
        "ground_color": (0.28, 0.19, 0.12),
        "ambient_intensity": 0.34,
        "shadow_strength": 0.72,
        "soft_shadow_strength": 0.52,
        "shadow_softness": 1.35,
        "shadow_bias": 0.0042,
        "shadow_map_size": 1024,
        "contact_shadow_strength": 0.26,
        "ground_shadow_strength": 0.42,
        "bloom_enabled": True,
        "bloom_strength": 0.34,
        "bloom_radius": 2.15,
        "bloom_threshold": 0.08,
    },
    "night_stage": {
        "label": "Night Stage",
        "key_dir": (0.32, -0.76, -0.52),
        "key_color": (0.70, 0.82, 1.0),
        "key_intensity": 0.72,
        "fill_dir": (-0.62, -0.24, 0.42),
        "fill_color": (0.42, 0.34, 0.86),
        "fill_intensity": 0.28,
        "rim_color": (0.82, 0.66, 1.0),
        "rim_intensity": 0.30,
        "sky_color": (0.14, 0.17, 0.30),
        "ground_color": (0.06, 0.06, 0.10),
        "ambient_intensity": 0.28,
        "shadow_strength": 0.86,
        "soft_shadow_strength": 0.56,
        "shadow_softness": 1.55,
        "shadow_bias": 0.0045,
        "shadow_map_size": 1024,
        "contact_shadow_strength": 0.34,
        "ground_shadow_strength": 0.34,
        "bloom_enabled": True,
        "bloom_strength": 0.52,
        "bloom_radius": 2.45,
        "bloom_threshold": 0.06,
    },
}


def resolve_mmd_lighting(
    preset: str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    key = str(preset or "studio_soft").strip().casefold()
    if key not in MMD_LIGHTING_PRESETS:
        key = "studio_soft"
    out = deepcopy(MMD_LIGHTING_PRESETS[key])
    out["preset"] = key
    if overrides:
        for name, value in overrides.items():
            if name in out:
                out[name] = value
    return out
