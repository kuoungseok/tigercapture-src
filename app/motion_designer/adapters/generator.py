"""Canonical procedural renderer for Motion Designer Generator layers."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen, QRadialGradient

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import transparent_image
from app.motion_designer.vector_shapes import evaluate_source_param


def _color(value, fallback: str) -> QColor:
    color = QColor(str(value or fallback))
    return color if color.isValid() else QColor(fallback)


def _evaluated(layer: MotionLayer, time_ms: float) -> dict:
    params = layer.source.params
    return {
        key: evaluate_source_param(params, key, time_ms, fallback)
        for key, fallback in (
            ("kind", "gradient"),
            ("width", 1920),
            ("height", 1080),
            ("color_a", "#24677f"),
            ("color_b", "#111820"),
            ("scale", 96.0),
            ("angle", 35.0),
            ("offset", [0.0, 0.0]),
            ("seed", 17),
            ("detail", 4),
            ("contrast", 1.0),
            ("softness", 0.0),
        )
    }


def _gradient(painter: QPainter, rect: QRectF, values: dict) -> None:
    angle = math.radians(float(values["angle"]))
    direction = QPointF(math.cos(angle), math.sin(angle))
    center = rect.center()
    radius = abs(rect.width() * direction.x()) + abs(rect.height() * direction.y())
    start = center - direction * (radius * 0.5)
    end = center + direction * (radius * 0.5)
    gradient = QLinearGradient(start, end)
    gradient.setColorAt(0.0, _color(values["color_a"], "#24677f"))
    gradient.setColorAt(1.0, _color(values["color_b"], "#111820"))
    painter.fillRect(rect, gradient)


def _checkerboard(painter: QPainter, rect: QRectF, values: dict) -> None:
    scale = max(2.0, float(values["scale"]))
    offset = list(values["offset"] or [0.0, 0.0])
    colors = (
        _color(values["color_a"], "#24677f"),
        _color(values["color_b"], "#111820"),
    )
    start_x = math.floor((-float(offset[0])) / scale) - 1
    start_y = math.floor((-float(offset[1])) / scale) - 1
    columns = int(math.ceil(rect.width() / scale)) + 3
    rows = int(math.ceil(rect.height() / scale)) + 3
    for row in range(start_y, start_y + rows):
        for column in range(start_x, start_x + columns):
            painter.fillRect(
                QRectF(
                    column * scale + float(offset[0]),
                    row * scale + float(offset[1]),
                    scale,
                    scale,
                ),
                colors[(row + column) & 1],
            )


def _grid(painter: QPainter, rect: QRectF, values: dict) -> None:
    painter.fillRect(rect, _color(values["color_b"], "#111820"))
    scale = max(2.0, float(values["scale"]))
    offset = list(values["offset"] or [0.0, 0.0])
    pen = QPen(_color(values["color_a"], "#24677f"))
    pen.setWidthF(max(1.0, scale * 0.025))
    painter.setPen(pen)
    x = float(offset[0]) % scale
    while x <= rect.width():
        painter.drawLine(QPointF(x, 0.0), QPointF(x, rect.height()))
        x += scale
    y = float(offset[1]) % scale
    while y <= rect.height():
        painter.drawLine(QPointF(0.0, y), QPointF(rect.width(), y))
        y += scale


def _noise(width: int, height: int, values: dict) -> QImage:
    import numpy as np

    rng = np.random.default_rng(int(values["seed"]))
    detail = max(1, min(8, int(values["detail"])))
    noise = np.zeros((height, width), dtype=np.float32)
    weight = 0.0
    for octave in range(detail):
        step = max(1, int(float(values["scale"]) / (2 ** octave)))
        grid_h = height // step + 2
        grid_w = width // step + 2
        coarse = rng.random((grid_h, grid_w), dtype=np.float32)
        expanded = np.repeat(np.repeat(coarse, step, axis=0), step, axis=1)[:height, :width]
        octave_weight = 0.5 ** octave
        noise += expanded * octave_weight
        weight += octave_weight
    noise /= max(weight, 1e-6)
    contrast = float(values["contrast"])
    noise = np.clip((noise - 0.5) * contrast + 0.5, 0.0, 1.0)
    first = _color(values["color_a"], "#24677f")
    second = _color(values["color_b"], "#111820")
    a = np.array([first.red(), first.green(), first.blue(), first.alpha()], dtype=np.float32)
    b = np.array([second.red(), second.green(), second.blue(), second.alpha()], dtype=np.float32)
    rgba = (b[None, None, :] + (a - b)[None, None, :] * noise[..., None]).astype(np.uint8)
    image = QImage(rgba.data, width, height, width * 4, QImage.Format_RGBA8888)
    return image.copy().convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def _rays(painter: QPainter, rect: QRectF, values: dict) -> None:
    center = rect.center()
    offset = list(values["offset"] or [0.0, 0.0])
    center += QPointF(float(offset[0]), float(offset[1]))
    painter.fillRect(rect, _color(values["color_b"], "#111820"))
    painter.setBrush(_color(values["color_a"], "#24677f"))
    painter.setPen(QColor(0, 0, 0, 0))
    count = max(4, min(128, int(float(values["scale"]) / 5.0)))
    radius = math.hypot(rect.width(), rect.height())
    phase = math.radians(float(values["angle"]))
    for index in range(0, count, 2):
        a0 = phase + index * math.tau / count
        a1 = phase + (index + 1) * math.tau / count
        polygon = [
            center,
            center + QPointF(math.cos(a0) * radius, math.sin(a0) * radius),
            center + QPointF(math.cos(a1) * radius, math.sin(a1) * radius),
        ]
        from PySide6.QtGui import QPolygonF

        painter.drawPolygon(QPolygonF(polygon))


def render_generator(layer: MotionLayer, time_ms: float = 0.0, **_kwargs) -> QImage:
    values = _evaluated(layer, time_ms)
    width = max(1, min(16384, int(values["width"])))
    height = max(1, min(16384, int(values["height"])))
    kind = str(values["kind"]).lower()
    if kind == "noise":
        return _noise(width, height, values)
    image = transparent_image(width, height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(0.0, 0.0, float(width), float(height))
    if kind == "solid":
        painter.fillRect(rect, _color(values["color_a"], "#24677f"))
    elif kind == "checkerboard":
        _checkerboard(painter, rect, values)
    elif kind == "grid":
        _grid(painter, rect, values)
    elif kind == "rays":
        _rays(painter, rect, values)
    else:
        _gradient(painter, rect, values)
    painter.end()
    return image


__all__ = ["render_generator"]
