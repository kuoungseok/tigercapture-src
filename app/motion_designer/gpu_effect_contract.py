"""GPU eligibility and uniform mapping for common Motion effects."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor

from .keyframes import evaluate_property
from .schema import MotionEffectRef


@dataclass(frozen=True, slots=True)
class GpuEffectParameters:
    kind: str
    mode: int
    values: tuple[float, float, float, float, float, float]
    color: QColor


_EFFECT_MODES = {
    "brightness_contrast": 1,
    "saturation": 2,
    "blur": 3,
    "gaussian_blur": 3,
    "unsharp_mask": 4,
    "glow": 5,
    "vignette": 6,
    "drop_shadow": 7,
    "light_sweep": 8,
    "fractal_noise": 9,
    "posterize": 10,
    "directional_blur": 11,
    "displacement": 12,
}


def gpu_effect_kind(effect: MotionEffectRef) -> str:
    return effect.kind.strip().lower()


def is_common_gpu_effect(effect: MotionEffectRef) -> bool:
    return effect.enabled and gpu_effect_kind(effect) in _EFFECT_MODES


def unsupported_gpu_effect_reason(effect: MotionEffectRef) -> str:
    return f"effect_requires_raster:{gpu_effect_kind(effect) or 'unknown'}"


def _value(
    effect: MotionEffectRef,
    name: str,
    time_ms: float,
    default: float,
) -> float:
    prop = effect.params.get(name)
    if prop is None:
        return default
    try:
        return float(evaluate_property(prop, time_ms))
    except (TypeError, ValueError):
        return default


def _color(
    effect: MotionEffectRef,
    name: str,
    time_ms: float,
    default: str,
) -> QColor:
    prop = effect.params.get(name)
    raw = evaluate_property(prop, time_ms) if prop is not None else default
    color = QColor(str(raw or default))
    return color if color.isValid() else QColor(default)


def gpu_effect_parameters(
    effect: MotionEffectRef,
    time_ms: float,
    *,
    pixel_scale: float = 1.0,
) -> GpuEffectParameters:
    kind = gpu_effect_kind(effect)
    mode = _EFFECT_MODES[kind]
    scale = max(0.0001, float(pixel_scale))
    values = [0.0] * 6
    color = QColor("#ffffff")
    if kind == "brightness_contrast":
        values[:2] = [
            _value(effect, "brightness", time_ms, 0.0),
            max(0.0, _value(effect, "contrast", time_ms, 1.0)),
        ]
    elif kind == "saturation":
        values[0] = max(0.0, _value(effect, "amount", time_ms, 1.0))
    elif kind in {"blur", "gaussian_blur"}:
        values[0] = max(0.0, _value(effect, "radius", time_ms, 4.0)) * scale
    elif kind == "unsharp_mask":
        values[:2] = [
            max(0.01, _value(effect, "radius", time_ms, 2.0)) * scale,
            max(0.0, _value(effect, "amount", time_ms, 0.75)),
        ]
    elif kind == "glow":
        values[:3] = [
            min(1.0, max(0.0, _value(effect, "threshold", time_ms, 0.7))),
            max(0.01, _value(effect, "radius", time_ms, 8.0)) * scale,
            max(0.0, _value(effect, "intensity", time_ms, 0.7)),
        ]
    elif kind == "vignette":
        values[:2] = [
            min(1.0, max(0.0, _value(effect, "amount", time_ms, 0.35))),
            max(0.05, _value(effect, "softness", time_ms, 0.65)),
        ]
    elif kind == "drop_shadow":
        values[:4] = [
            _value(effect, "offset_x", time_ms, 12.0) * scale,
            _value(effect, "offset_y", time_ms, 12.0) * scale,
            min(100.0, max(0.0, _value(effect, "radius", time_ms, 10.0)))
            * scale,
            min(1.0, max(0.0, _value(effect, "opacity", time_ms, 0.65))),
        ]
        color = _color(effect, "color", time_ms, "#000000")
    elif kind == "light_sweep":
        values[:] = [
            _value(effect, "center_x", time_ms, 0.5),
            _value(effect, "center_y", time_ms, 0.5),
            _value(effect, "angle", time_ms, -24.0),
            min(1.0, max(0.005, _value(effect, "width", time_ms, 0.16))),
            min(1.0, max(0.01, _value(effect, "softness", time_ms, 0.45))),
            min(8.0, max(0.0, _value(effect, "intensity", time_ms, 1.2))),
        ]
        color = _color(effect, "color", time_ms, "#ffffff")
    elif kind == "fractal_noise":
        values[:] = [
            min(1.0, max(0.0, _value(effect, "amount", time_ms, 0.35))),
            min(1000.0, max(2.0, _value(effect, "scale", time_ms, 120.0)))
            * scale,
            min(8.0, max(1.0, _value(effect, "octaves", time_ms, 4.0))),
            min(8.0, max(0.0, _value(effect, "contrast", time_ms, 1.4))),
            _value(effect, "evolution", time_ms, 0.0),
            _value(effect, "speed", time_ms, 0.0),
        ]
        color = QColor.fromRgbF(
            (_value(effect, "seed", time_ms, 1.0) % 997.0) / 997.0,
            0.0,
            0.0,
        )
    elif kind == "posterize":
        values[:2] = [
            min(64.0, max(2.0, round(_value(effect, "levels", time_ms, 8.0)))),
            min(1.0, max(0.0, _value(effect, "amount", time_ms, 1.0))),
        ]
    elif kind == "directional_blur":
        values[:3] = [
            min(200.0, max(0.0, _value(effect, "length", time_ms, 12.0)))
            * scale,
            _value(effect, "angle", time_ms, 0.0),
            min(32.0, max(2.0, _value(effect, "samples", time_ms, 8.0))),
        ]
    elif kind == "displacement":
        values[:3] = [
            min(300.0, max(0.0, _value(effect, "strength", time_ms, 16.0)))
            * scale,
            min(1000.0, max(2.0, _value(effect, "scale", time_ms, 120.0)))
            * scale,
            _value(effect, "speed", time_ms, 0.0),
        ]
    return GpuEffectParameters(
        kind=kind,
        mode=mode,
        values=tuple(float(value) for value in values),
        color=color,
    )


__all__ = [
    "GpuEffectParameters",
    "gpu_effect_kind",
    "gpu_effect_parameters",
    "is_common_gpu_effect",
    "unsupported_gpu_effect_reason",
]
