"""Craft/imperfection style contract for Motion Designer layers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import AnimatedProperty, MotionEffectRef


CRAFT_STYLE_CONTRACT = "tigerstudio.motion.craft_style.v1"
CRAFT_STYLE_KIND = "craft_style"

CRAFT_STYLE_PRESETS: dict[str, dict[str, float]] = {
    "subtle_film": {
        "amount": 1.0,
        "grain_amount": 0.10,
        "grain_size": 1.4,
        "grain_cadence": 12.0,
        "weave_x": 0.8,
        "weave_y": 0.55,
        "weave_rotation": 0.05,
        "weave_frequency": 0.8,
        "flicker_amount": 0.018,
        "flicker_frequency": 7.0,
        "flicker_warmth": 0.08,
    },
    "handmade": {
        "amount": 1.0,
        "grain_amount": 0.18,
        "grain_size": 2.1,
        "grain_cadence": 8.0,
        "weave_x": 1.8,
        "weave_y": 1.2,
        "weave_rotation": 0.12,
        "weave_frequency": 1.2,
        "flicker_amount": 0.035,
        "flicker_frequency": 5.0,
        "flicker_warmth": 0.14,
    },
    "archive_print": {
        "amount": 1.0,
        "grain_amount": 0.28,
        "grain_size": 2.8,
        "grain_cadence": 6.0,
        "weave_x": 3.0,
        "weave_y": 1.8,
        "weave_rotation": 0.2,
        "weave_frequency": 0.65,
        "flicker_amount": 0.055,
        "flicker_frequency": 3.5,
        "flicker_warmth": 0.22,
    },
}

_LIMITS = {
    "amount": (0.0, 1.0),
    "grain_amount": (0.0, 1.0),
    "grain_size": (1.0, 12.0),
    "grain_cadence": (0.1, 120.0),
    "weave_x": (0.0, 100.0),
    "weave_y": (0.0, 100.0),
    "weave_rotation": (0.0, 10.0),
    "weave_frequency": (0.0, 30.0),
    "flicker_amount": (0.0, 1.0),
    "flicker_frequency": (0.0, 60.0),
    "flicker_warmth": (-1.0, 1.0),
}


def craft_style_presets() -> list[dict[str, Any]]:
    return [
        {"id": preset_id, "params": dict(params)}
        for preset_id, params in CRAFT_STYLE_PRESETS.items()
    ]


def normalize_craft_style(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "subtle_film",
) -> dict[str, Any]:
    preset_id = str(preset or "subtle_film")
    defaults = CRAFT_STYLE_PRESETS.get(preset_id, CRAFT_STYLE_PRESETS["subtle_film"])
    source = dict(values or {})
    normalized: dict[str, Any] = {}
    for key, (minimum, maximum) in _LIMITS.items():
        value = float(source.get(key, defaults[key]))
        normalized[key] = max(minimum, min(maximum, value))
    normalized["seed"] = max(0, min(2_147_483_647, int(source.get("seed", 1))))
    normalized["seed_locked"] = bool(source.get("seed_locked", True))
    normalized["preset"] = preset_id if preset_id in CRAFT_STYLE_PRESETS else "custom"
    return normalized


def make_craft_style_effect(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "subtle_film",
) -> MotionEffectRef:
    settings = normalize_craft_style(values, preset=preset)
    metadata = {
        "contract": CRAFT_STYLE_CONTRACT,
        "preset": settings.pop("preset"),
        "seed_locked": settings.pop("seed_locked"),
    }
    return MotionEffectRef(
        kind=CRAFT_STYLE_KIND,
        params={
            key: AnimatedProperty(default=value)
            for key, value in settings.items()
        },
        metadata=metadata,
    )


def is_craft_style_effect(effect: MotionEffectRef) -> bool:
    return effect.kind.strip().lower() == CRAFT_STYLE_KIND


__all__ = [
    "CRAFT_STYLE_CONTRACT",
    "CRAFT_STYLE_KIND",
    "CRAFT_STYLE_PRESETS",
    "craft_style_presets",
    "is_craft_style_effect",
    "make_craft_style_effect",
    "normalize_craft_style",
]
