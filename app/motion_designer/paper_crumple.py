"""Editable paper crumple effects and animation presets."""
from __future__ import annotations

from .schema import AnimatedProperty, Keyframe, MotionEffectRef


PAPER_CRUMPLE_DEFAULTS = {
    "amount": 0.0,
    "crease_density": 7.0,
    "sharpness": 10.0,
    "depth": 28.0,
    "residual_wrinkle": 0.0,
    "seed": 17.0,
}


def _animated(
    default: float,
    rows: list[tuple[int, float]],
) -> AnimatedProperty:
    return AnimatedProperty(
        default=float(default),
        keyframes=[
            Keyframe(
                time_ms=max(0, int(time_ms)),
                value=float(value),
                interpolation="bezier",
                out_tangent=(0.18, 0.0),
                in_tangent=(0.78, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def make_paper_crumple_effect(
    values: dict[str, float] | None = None,
) -> MotionEffectRef:
    settings = {**PAPER_CRUMPLE_DEFAULTS, **(values or {})}
    return MotionEffectRef(
        kind="paper_crumple",
        params={
            key: AnimatedProperty(default=float(value))
            for key, value in settings.items()
        },
        metadata={
            "paper_deformation": "gpu_2_5d",
            "deterministic_seed": True,
        },
    )


def make_crumple_unfold_effect(
    *,
    start_ms: int,
    crumple_duration_ms: int = 650,
    hold_duration_ms: int = 180,
    unfold_duration_ms: int = 900,
    seed: float = 17.0,
    residual_wrinkle: float = 0.12,
) -> MotionEffectRef:
    start = max(0, int(start_ms))
    peak = start + max(1, int(crumple_duration_ms))
    unfold = peak + max(0, int(hold_duration_ms))
    unfold_duration = max(1, int(unfold_duration_ms))
    end = unfold + unfold_duration
    settle = max(unfold, end - min(180, max(1, unfold_duration // 3)))
    rebound = max(settle, end - min(70, max(1, unfold_duration // 8)))
    effect = make_paper_crumple_effect({"seed": seed})
    effect.params["amount"] = _animated(
        0.0,
        [
            (start, 0.0),
            (peak, 1.0),
            (unfold, 1.0),
            (settle, 0.0),
            (rebound, 0.055),
            (end, 0.0),
        ],
    )
    effect.params["residual_wrinkle"] = _animated(
        0.0,
        [(start, 0.0), (unfold, 0.0), (end, residual_wrinkle)],
    )
    effect.metadata.update({
        "preset": "crumple_unfold",
        "animation_end_ms": end,
        "unfold_overshoot": 0.055,
    })
    return effect


__all__ = [
    "PAPER_CRUMPLE_DEFAULTS",
    "make_crumple_unfold_effect",
    "make_paper_crumple_effect",
]
