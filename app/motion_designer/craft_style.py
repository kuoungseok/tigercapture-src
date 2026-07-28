"""Craft/imperfection style contract for Motion Designer layers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import AnimatedProperty, MotionEffectRef


CRAFT_STYLE_CONTRACT = "tigerstudio.motion.craft_style.v1"
CRAFT_STYLE_KIND = "craft_style"

_SUBTLE_FILM = {
    "amount": 1.0,
    "grain_amount": 0.10,
    "grain_size": 1.4,
    "grain_cadence": 12.0,
    "grain_chroma": 0.0,
    "grain_shadow_response": 0.45,
    "grain_midtone_response": 1.0,
    "grain_highlight_response": 0.4,
    "weave_x": 0.8,
    "weave_y": 0.55,
    "weave_rotation": 0.05,
    "weave_frequency": 0.8,
    "flicker_amount": 0.018,
    "flicker_frequency": 7.0,
    "flicker_warmth": 0.08,
    "dust_amount": 0.015,
    "dust_lifetime": 0.35,
    "scratch_amount": 0.008,
    "scratch_direction": 0.0,
    "misregistration": 0.25,
    "halation_amount": 0.05,
    "halation_radius": 5.0,
    "warmth": 0.06,
    "vhs_amount": 0.0,
    "edge_roughness": 0.0,
    "edge_fiber_amount": 0.0,
    "edge_fiber_length": 8.0,
    "loop_period": 4.0,
}


def _preset(**overrides: float) -> dict[str, float]:
    return {**_SUBTLE_FILM, **overrides}


CRAFT_STYLE_PRESETS: dict[str, dict[str, float]] = {
    "subtle_film": dict(_SUBTLE_FILM),
    "handmade": _preset(
        grain_amount=0.18, grain_size=2.1, grain_cadence=8.0,
        weave_x=1.8, weave_y=1.2, weave_rotation=0.12, weave_frequency=1.2,
        flicker_amount=0.035, flicker_frequency=5.0, flicker_warmth=0.14,
        dust_amount=0.035, scratch_amount=0.018, misregistration=0.55,
        halation_amount=0.08, halation_radius=7.0, warmth=0.11,
        vhs_amount=0.015, edge_roughness=0.025,
    ),
    "archive_print": _preset(
        grain_amount=0.28, grain_size=2.8, grain_cadence=6.0,
        weave_x=3.0, weave_y=1.8, weave_rotation=0.2, weave_frequency=0.65,
        flicker_amount=0.055, flicker_frequency=3.5, flicker_warmth=0.22,
        dust_amount=0.075, scratch_amount=0.04, misregistration=1.2,
        halation_amount=0.13, halation_radius=9.0, warmth=0.18,
        vhs_amount=0.04, edge_roughness=0.06,
    ),
    "luxury_paper": _preset(
        grain_amount=0.07, grain_size=3.2, grain_cadence=2.0,
        weave_x=0.15, weave_y=0.1, weave_rotation=0.01,
        flicker_amount=0.004, dust_amount=0.004, scratch_amount=0.0,
        misregistration=0.12, halation_amount=0.025, warmth=0.13,
        edge_roughness=0.018,
    ),
    "documentary_handheld": _preset(
        grain_amount=0.2, grain_size=1.8, grain_cadence=18.0,
        weave_x=3.8, weave_y=2.7, weave_rotation=0.3, weave_frequency=1.7,
        flicker_amount=0.025, flicker_frequency=8.0, dust_amount=0.012,
        scratch_amount=0.004, misregistration=0.2, halation_amount=0.07,
        warmth=0.035,
    ),
    "vhs_tape": _preset(
        grain_amount=0.22, grain_size=2.4, grain_cadence=15.0,
        weave_x=1.4, weave_y=0.5, weave_frequency=2.1,
        flicker_amount=0.04, flicker_frequency=12.0, dust_amount=0.025,
        scratch_amount=0.01, misregistration=2.4, halation_amount=0.04,
        warmth=-0.03, vhs_amount=0.32,
    ),
    "printed_poster": _preset(
        grain_amount=0.12, grain_size=3.5, grain_cadence=1.0,
        weave_x=0.0, weave_y=0.0, weave_rotation=0.0,
        flicker_amount=0.0, dust_amount=0.025, scratch_amount=0.0,
        misregistration=3.2, halation_amount=0.0, warmth=0.08,
        edge_roughness=0.12,
    ),
    "warm_film": _preset(
        grain_amount=0.13, grain_size=1.55, grain_cadence=12.0,
        weave_x=0.65, weave_y=0.45, flicker_amount=0.014,
        dust_amount=0.01, scratch_amount=0.003, misregistration=0.18,
        halation_amount=0.16, halation_radius=11.0, warmth=0.28,
    ),
    "rough_cut": _preset(
        grain_amount=0.24, grain_size=2.6, grain_cadence=8.0,
        weave_x=2.2, weave_y=1.5, weave_rotation=0.16,
        flicker_amount=0.03, dust_amount=0.055, scratch_amount=0.028,
        misregistration=1.4, halation_amount=0.07, warmth=0.1,
        edge_roughness=0.22,
    ),
}

_LIMITS = {
    "amount": (0.0, 1.0),
    "grain_amount": (0.0, 1.0),
    "grain_size": (1.0, 12.0),
    "grain_cadence": (0.1, 120.0),
    "grain_chroma": (0.0, 1.0),
    "grain_shadow_response": (0.0, 2.0),
    "grain_midtone_response": (0.0, 2.0),
    "grain_highlight_response": (0.0, 2.0),
    "weave_x": (0.0, 100.0),
    "weave_y": (0.0, 100.0),
    "weave_rotation": (0.0, 10.0),
    "weave_frequency": (0.0, 30.0),
    "flicker_amount": (0.0, 1.0),
    "flicker_frequency": (0.0, 60.0),
    "flicker_warmth": (-1.0, 1.0),
    "dust_amount": (0.0, 1.0),
    "dust_lifetime": (0.04, 10.0),
    "scratch_amount": (0.0, 1.0),
    "scratch_direction": (-180.0, 180.0),
    "misregistration": (0.0, 20.0),
    "halation_amount": (0.0, 1.0),
    "halation_radius": (0.1, 100.0),
    "warmth": (-1.0, 1.0),
    "vhs_amount": (0.0, 1.0),
    "edge_roughness": (0.0, 1.0),
    "edge_fiber_amount": (0.0, 1.0),
    "edge_fiber_length": (1.0, 64.0),
    "loop_period": (0.1, 3600.0),
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
