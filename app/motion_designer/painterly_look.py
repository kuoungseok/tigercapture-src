"""Provider-neutral painterly/toon/ink look contract for Motion layers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import AnimatedProperty, MotionEffectRef


PAINTERLY_LOOK_CONTRACT = "tigerstudio.motion.painterly_look.v1"
PAINTERLY_LOOK_KIND = "painterly_look"

_BASE = {
    "amount": 1.0,
    "color_levels": 8.0,
    "toon_amount": 0.0,
    "smoothing": 0.15,
    "edge_strength": 0.0,
    "edge_threshold": 0.18,
    "edge_softness": 0.08,
    "brush_amount": 0.0,
    "brush_scale": 18.0,
    "granulation": 0.0,
    "paper_amount": 0.0,
    "hatch_amount": 0.0,
    "hatch_spacing": 9.0,
    "working_limit": 480.0,
}


def _preset(**overrides: float) -> dict[str, float]:
    return {**_BASE, **overrides}


PAINTERLY_LOOK_PRESETS: dict[str, dict[str, float]] = {
    "realistic": _preset(smoothing=0.08),
    "toon": _preset(
        color_levels=5.0, toon_amount=0.82, smoothing=0.46,
        edge_strength=0.35, edge_threshold=0.16, edge_softness=0.06,
    ),
    "painted": _preset(
        color_levels=7.0, toon_amount=0.32, smoothing=0.62,
        edge_strength=0.16, brush_amount=0.42, brush_scale=24.0,
        granulation=0.18, paper_amount=0.13,
    ),
    "ink": _preset(
        color_levels=4.0, toon_amount=0.72, smoothing=0.28,
        edge_strength=0.92, edge_threshold=0.12, edge_softness=0.035,
        granulation=0.10, paper_amount=0.16, hatch_amount=0.34,
        hatch_spacing=8.0,
    ),
    "paper": _preset(
        color_levels=7.0, toon_amount=0.22, smoothing=0.24,
        edge_strength=0.18, brush_amount=0.18, brush_scale=32.0,
        granulation=0.30, paper_amount=0.48,
    ),
}

_LIMITS = {
    "amount": (0.0, 1.0),
    "color_levels": (2.0, 32.0),
    "toon_amount": (0.0, 1.0),
    "smoothing": (0.0, 1.0),
    "edge_strength": (0.0, 2.0),
    "edge_threshold": (0.0, 1.0),
    "edge_softness": (0.001, 1.0),
    "brush_amount": (0.0, 1.0),
    "brush_scale": (2.0, 256.0),
    "granulation": (0.0, 1.0),
    "paper_amount": (0.0, 1.0),
    "hatch_amount": (0.0, 1.0),
    "hatch_spacing": (2.0, 128.0),
    "working_limit": (320.0, 4096.0),
}


def painterly_look_presets() -> list[dict[str, Any]]:
    return [
        {"id": preset_id, "params": dict(params)}
        for preset_id, params in PAINTERLY_LOOK_PRESETS.items()
    ]


def normalize_painterly_look(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "realistic",
) -> dict[str, Any]:
    preset_id = str(preset or "realistic").strip().lower()
    defaults = PAINTERLY_LOOK_PRESETS.get(
        preset_id,
        PAINTERLY_LOOK_PRESETS["realistic"],
    )
    source = dict(values or {})
    normalized: dict[str, Any] = {}
    for key, (minimum, maximum) in _LIMITS.items():
        value = float(source.get(key, defaults[key]))
        normalized[key] = max(minimum, min(maximum, value))
    normalized["seed"] = max(
        0,
        min(2_147_483_647, int(source.get("seed", 20260729))),
    )
    normalized["line_color"] = str(source.get("line_color") or "#17202a")
    normalized["paper_color"] = str(source.get("paper_color") or "#f1ead9")
    normalized["preset"] = (
        preset_id if preset_id in PAINTERLY_LOOK_PRESETS else "custom"
    )
    return normalized


def make_painterly_look_effect(
    values: Mapping[str, Any] | None = None,
    *,
    preset: str = "realistic",
) -> MotionEffectRef:
    settings = normalize_painterly_look(values, preset=preset)
    metadata = {
        "contract": PAINTERLY_LOOK_CONTRACT,
        "preset": settings.pop("preset"),
        "line_color": settings.pop("line_color"),
        "paper_color": settings.pop("paper_color"),
        "temporal_lock": True,
        "material_overrides": {},
    }
    return MotionEffectRef(
        kind=PAINTERLY_LOOK_KIND,
        params={
            key: AnimatedProperty(default=value)
            for key, value in settings.items()
        },
        metadata=metadata,
    )


def is_painterly_look_effect(effect: MotionEffectRef) -> bool:
    return effect.kind.strip().lower() == PAINTERLY_LOOK_KIND


__all__ = [
    "PAINTERLY_LOOK_CONTRACT",
    "PAINTERLY_LOOK_KIND",
    "PAINTERLY_LOOK_PRESETS",
    "is_painterly_look_effect",
    "make_painterly_look_effect",
    "normalize_painterly_look",
    "painterly_look_presets",
]
