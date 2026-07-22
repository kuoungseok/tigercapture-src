"""Deterministic CPU effects shared by Motion Designer preview and export."""
from __future__ import annotations

from typing import Any

from PySide6.QtGui import QImage

from .keyframes import evaluate_property
from .schema import MotionEffectRef


def _value(effect: MotionEffectRef, key: str, time_ms: float, default: Any) -> Any:
    prop = effect.params.get(key)
    return evaluate_property(prop, time_ms) if prop is not None else default


def _rgba_array(image: QImage):
    import numpy as np

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    return array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def _qimage(array) -> QImage:
    import numpy as np

    rgba = np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))
    height, width = rgba.shape[:2]
    straight = QImage(rgba.data, width, height, rgba.strides[0], QImage.Format_RGBA8888).copy()
    return straight.convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def apply_effects(image: QImage, effects: list[MotionEffectRef], time_ms: float) -> QImage:
    if not effects:
        return image
    import cv2
    import numpy as np

    rgba = _rgba_array(image).astype(np.float32)
    for effect in effects:
        if not effect.enabled:
            continue
        kind = effect.kind.lower().strip()
        rgb = rgba[..., :3]
        if kind == "brightness_contrast":
            brightness = float(_value(effect, "brightness", time_ms, 0.0))
            contrast = max(0.0, float(_value(effect, "contrast", time_ms, 1.0)))
            rgba[..., :3] = (rgb - 127.5) * contrast + 127.5 + brightness * 255.0
        elif kind == "saturation":
            amount = max(0.0, float(_value(effect, "amount", time_ms, 1.0)))
            luminance = rgb[..., 0:1] * .2126 + rgb[..., 1:2] * .7152 + rgb[..., 2:3] * .0722
            rgba[..., :3] = luminance + (rgb - luminance) * amount
        elif kind in {"blur", "gaussian_blur"}:
            radius = max(0.0, float(_value(effect, "radius", time_ms, 4.0)))
            if radius > 0.01:
                rgba = cv2.GaussianBlur(rgba, (0, 0), sigmaX=radius, sigmaY=radius)
        elif kind == "unsharp_mask":
            radius = max(.01, float(_value(effect, "radius", time_ms, 2.0)))
            amount = max(0.0, float(_value(effect, "amount", time_ms, .75)))
            blurred = cv2.GaussianBlur(rgb, (0, 0), sigmaX=radius, sigmaY=radius)
            rgba[..., :3] = rgb + (rgb - blurred) * amount
        elif kind == "glow":
            threshold = max(0.0, min(1.0, float(_value(effect, "threshold", time_ms, .7)))) * 255.0
            radius = max(.01, float(_value(effect, "radius", time_ms, 8.0)))
            intensity = max(0.0, float(_value(effect, "intensity", time_ms, .7)))
            source_alpha = rgba[..., 3] / 255.0
            selected = (np.max(rgb, axis=2) >= threshold).astype(np.float32) * source_alpha
            bright = rgb * selected[..., None]
            halo_rgb = cv2.GaussianBlur(bright, (0, 0), sigmaX=radius, sigmaY=radius) * intensity
            halo_alpha = cv2.GaussianBlur(selected, (0, 0), sigmaX=radius, sigmaY=radius) * min(1.0, intensity)
            output_alpha = np.clip(source_alpha + halo_alpha * (1.0 - source_alpha), 0.0, 1.0)
            premultiplied = rgb * source_alpha[..., None] + halo_rgb * (1.0 - source_alpha[..., None])
            rgba[..., :3] = np.divide(
                premultiplied, output_alpha[..., None],
                out=np.zeros_like(premultiplied), where=output_alpha[..., None] > 1e-6,
            )
            rgba[..., 3] = output_alpha * 255.0
        elif kind == "vignette":
            amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, .35))))
            softness = max(.05, float(_value(effect, "softness", time_ms, .65)))
            height, width = rgba.shape[:2]
            yy, xx = np.ogrid[-1:1:complex(height), -1:1:complex(width)]
            radius = np.sqrt(xx * xx + yy * yy)
            shade = 1.0 - amount * np.clip((radius - (1.0 - softness)) / softness, 0.0, 1.0)
            rgba[..., :3] = rgb * shade[..., None]
        rgba = np.clip(rgba, 0, 255)
    return _qimage(rgba)
