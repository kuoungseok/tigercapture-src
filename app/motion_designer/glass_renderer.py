"""Deterministic backdrop renderer for Tiger Glass layers."""
from __future__ import annotations

import math

from PySide6.QtGui import QImage

from .keyframes import evaluate_property
from .schema import MotionEffectRef


def _value(effect: MotionEffectRef, key: str, time_ms: float, default: float) -> float:
    prop = effect.params.get(key)
    return float(evaluate_property(prop, time_ms) if prop is not None else default)


def _rgba(image: QImage):
    import numpy as np

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(),
        straight.bytesPerLine(),
    )
    return rows[:, : straight.width() * 4].reshape(
        straight.height(),
        straight.width(),
        4,
    ).copy().astype(np.float32)


def _qimage(array) -> QImage:
    import numpy as np

    rgba = np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))
    height, width = rgba.shape[:2]
    return QImage(
        rgba.data,
        width,
        height,
        rgba.strides[0],
        QImage.Format_RGBA8888,
    ).copy().convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def _color(value: object):
    import numpy as np

    text = str(value or "#ffffff").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    try:
        rgb = [int(text[index:index + 2], 16) for index in (0, 2, 4)]
    except (TypeError, ValueError):
        rgb = [255, 255, 255]
    return np.asarray(rgb, dtype=np.float32)


def render_glass_surface(
    backdrop: QImage,
    mask_surface: QImage,
    effect: MotionEffectRef,
    time_ms: float,
) -> QImage:
    import cv2
    import numpy as np

    background = _rgba(backdrop)
    mask = _rgba(mask_surface)[..., 3] / 255.0
    full_height, full_width = mask.shape
    if mask.max(initial=0.0) <= 1e-6:
        return mask_surface

    blur_radius = max(0.0, _value(effect, "blur_radius", time_ms, 4.0))
    refraction = max(0.0, _value(effect, "refraction", time_ms, 3.0))
    dispersion = max(0.0, _value(effect, "dispersion", time_ms, 0.35))
    active_y, active_x = np.nonzero(mask > 1e-4)
    padding = int(math.ceil(blur_radius * 3.0 + refraction + dispersion + 4.0))
    left = max(0, int(active_x.min()) - padding)
    top = max(0, int(active_y.min()) - padding)
    right = min(full_width, int(active_x.max()) + padding + 1)
    bottom = min(full_height, int(active_y.max()) + padding + 1)
    background = background[top:bottom, left:right].copy()
    mask = mask[top:bottom, left:right].copy()
    height, width = mask.shape
    sampled = background.copy()
    if blur_radius > 0.01:
        quality = str(effect.metadata.get("quality") or "preview").lower()
        long_edge_budget = {
            "draft": 480.0,
            "preview": 960.0,
            "final": float(max(width, height)),
        }.get(quality, 960.0)
        pyramid_scale = min(
            1.0,
            long_edge_budget / max(1.0, float(max(width, height))),
        )
        if pyramid_scale < 0.999:
            small_width = max(2, int(round(width * pyramid_scale)))
            small_height = max(2, int(round(height * pyramid_scale)))
            small = cv2.resize(
                sampled,
                (small_width, small_height),
                interpolation=cv2.INTER_AREA,
            )
            small = cv2.GaussianBlur(
                small,
                (0, 0),
                sigmaX=max(0.01, blur_radius * pyramid_scale),
                sigmaY=max(0.01, blur_radius * pyramid_scale),
            )
            sampled = cv2.resize(
                small,
                (width, height),
                interpolation=cv2.INTER_LINEAR,
            )
        else:
            sampled = cv2.GaussianBlur(
                sampled,
                (0, 0),
                sigmaX=blur_radius,
                sigmaY=blur_radius,
            )

    normal_scale = max(0.1, _value(effect, "normal_scale", time_ms, 1.4))
    driver_x = _value(effect, "driver_x", time_ms, 0.0)
    driver_y = _value(effect, "driver_y", time_ms, 0.0)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    phase = float(time_ms) * 0.001
    wave_x = np.sin(
        yy / max(1.0, height) * math.tau * normal_scale + phase * 1.7
    )
    wave_y = np.cos(
        xx / max(1.0, width) * math.tau * normal_scale - phase * 1.3
    )
    map_x = xx + (wave_x + driver_x * 0.25) * refraction
    map_y = yy + (wave_y + driver_y * 0.25) * refraction
    sampled = cv2.remap(
        sampled,
        map_x,
        map_y,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    if dispersion > 1e-4:
        sampled[..., 0] = cv2.warpAffine(
            sampled[..., 0],
            np.asarray([[1.0, 0.0, dispersion], [0.0, 1.0, 0.0]], dtype=np.float32),
            (width, height),
            borderMode=cv2.BORDER_REFLECT_101,
        )
        sampled[..., 2] = cv2.warpAffine(
            sampled[..., 2],
            np.asarray([[1.0, 0.0, -dispersion], [0.0, 1.0, 0.0]], dtype=np.float32),
            (width, height),
            borderMode=cv2.BORDER_REFLECT_101,
        )

    tint = _color(effect.metadata.get("tint"))
    absorption = max(0.0, min(1.0, _value(effect, "absorption", time_ms, 0.08)))
    tint_strength = max(0.0, min(1.0, _value(effect, "tint_strength", time_ms, 0.05)))
    sampled[..., :3] *= 1.0 - absorption * 0.35
    sampled[..., :3] = (
        sampled[..., :3] * (1.0 - tint_strength)
        + tint * tint_strength
    )

    thickness = max(0.0, min(2.0, _value(effect, "thickness", time_ms, 0.45)))
    edge_strength = max(0.0, _value(effect, "edge_highlight", time_ms, 0.35))
    specular = max(0.0, _value(effect, "specular", time_ms, 0.4))
    edge = cv2.morphologyEx(mask, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    light = np.clip(
        0.5 + 0.5 * np.sin(
            xx / max(1.0, width) * math.pi + yy / max(1.0, height) * 0.7
            + phase * 1.2 + driver_x * 0.08 - driver_y * 0.06
        ),
        0.0,
        1.0,
    )
    highlight = edge * edge_strength * thickness + edge * light * specular
    bloom = max(0.0, _value(effect, "bloom", time_ms, 0.08))
    if bloom > 1e-6:
        highlight += cv2.GaussianBlur(
            highlight,
            (0, 0),
            sigmaX=max(1.0, 3.0 * bloom),
        ) * bloom
    sampled[..., :3] += highlight[..., None] * 255.0
    sampled[..., 3] = mask * 255.0
    output = np.zeros((full_height, full_width, 4), dtype=np.float32)
    output[top:bottom, left:right] = sampled
    return _qimage(output)


__all__ = ["render_glass_surface"]
