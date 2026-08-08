from __future__ import annotations

from app.motion_designer.gpu_effect_contract import (
    gpu_effect_parameters,
    is_common_gpu_effect,
    unsupported_gpu_effect_reason,
)
from app.motion_designer.schema import AnimatedProperty, MotionEffectRef


def test_common_gpu_effect_contract_maps_animated_values() -> None:
    effect = MotionEffectRef(
        kind="brightness_contrast",
        params={
            "brightness": AnimatedProperty(default=0.2),
            "contrast": AnimatedProperty(default=1.35),
        },
    )
    parameters = gpu_effect_parameters(effect, 500)
    assert is_common_gpu_effect(effect)
    assert parameters.mode == 1
    assert parameters.values[:2] == (0.2, 1.35)


def test_common_gpu_effect_contract_scales_pixel_parameters() -> None:
    effect = MotionEffectRef(
        kind="directional_blur",
        params={
            "length": AnimatedProperty(default=20.0),
            "angle": AnimatedProperty(default=35.0),
            "samples": AnimatedProperty(default=80),
        },
    )
    parameters = gpu_effect_parameters(effect, 0, pixel_scale=0.5)
    assert parameters.values[:3] == (10.0, 35.0, 32.0)


def test_unknown_effect_fails_closed_with_specific_reason() -> None:
    effect = MotionEffectRef(kind="mesh_warp")
    assert not is_common_gpu_effect(effect)
    assert unsupported_gpu_effect_reason(effect) == (
        "effect_requires_raster:mesh_warp"
    )


def test_paper_crumple_maps_to_gpu_with_deterministic_controls() -> None:
    effect = MotionEffectRef(
        kind="paper_crumple",
        params={
            "amount": AnimatedProperty(default=0.8),
            "crease_density": AnimatedProperty(default=9),
            "sharpness": AnimatedProperty(default=12.0),
            "depth": AnimatedProperty(default=30.0),
            "residual_wrinkle": AnimatedProperty(default=0.14),
            "seed": AnimatedProperty(default=73),
        },
    )
    parameters = gpu_effect_parameters(effect, 0, pixel_scale=0.5)
    assert is_common_gpu_effect(effect)
    assert parameters.mode == 13
    assert parameters.values == (0.8, 9.0, 12.0, 15.0, 0.14, 73.0)
