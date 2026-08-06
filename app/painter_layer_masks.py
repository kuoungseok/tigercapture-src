"""Document-sized 8-bit raster masks for Painter layers."""
from __future__ import annotations

from typing import Iterable
import math
import numbers
import operator

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QTransform

from app.painter_dimensions import positive_integer


def _alpha8_value(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Painter {field} must be an integer, not bool")
    try:
        resolved = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter {field} must be an integer") from exc
    if not 0 <= resolved <= 255:
        raise ValueError(f"Painter {field} must be between 0 and 255")
    return resolved


def alpha8_mask(width: int, height: int, value: int = 255) -> QImage:
    image = QImage(
        positive_integer(width, field="mask width"),
        positive_integer(height, field="mask height"),
        QImage.Format.Format_Alpha8,
    )
    image.fill(_alpha8_value(value, field="mask value"))
    return image


def normalized_alpha8(mask: QImage, width: int, height: int) -> QImage:
    target_width = positive_integer(width, field="mask width")
    target_height = positive_integer(height, field="mask height")
    if not isinstance(mask, QImage) or mask.isNull():
        return alpha8_mask(target_width, target_height, 255)
    source = mask.convertToFormat(QImage.Format.Format_Alpha8)
    if source.size().width() != target_width or source.size().height() != target_height:
        source = source.scaled(target_width, target_height)
    return source


def polygon_alpha8_mask(
    width: int,
    height: int,
    points: Iterable[tuple[float, float]],
    *,
    inside: int = 255,
    outside: int = 0,
) -> QImage:
    image = alpha8_mask(width, height, outside)
    rows = [(float(x), float(y)) for x, y in points]
    if len(rows) < 3:
        return image
    path = QPainterPath()
    path.moveTo(rows[0][0] * image.width(), rows[0][1] * image.height())
    for x, y in rows[1:]:
        path.lineTo(x * image.width(), y * image.height())
    path.closeSubpath()
    painter = QPainter(image)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.fillPath(path, QColor(0, 0, 0, _alpha8_value(inside, field="inside value")))
    finally:
        painter.end()
    return image


def linear_gradient_alpha8_mask(
    width: int,
    height: int,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    start_value: int = 0,
    end_value: int = 255,
) -> QImage:
    image = alpha8_mask(width, height, 0)
    gradient = QLinearGradient(
        QPointF(float(start[0]) * image.width(), float(start[1]) * image.height()),
        QPointF(float(end[0]) * image.width(), float(end[1]) * image.height()),
    )
    gradient.setColorAt(0.0, QColor(0, 0, 0, _alpha8_value(start_value, field="gradient start value")))
    gradient.setColorAt(1.0, QColor(0, 0, 0, _alpha8_value(end_value, field="gradient end value")))
    painter = QPainter(image)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(QRect(0, 0, image.width(), image.height()), gradient)
    finally:
        painter.end()
    return image


def paint_mask_circle(
    mask: QImage,
    center: tuple[float, float],
    radius_px: float,
    value: int,
) -> QImage:
    output = mask.convertToFormat(QImage.Format.Format_Alpha8)
    painter = QPainter(output)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setPen(QColor(0, 0, 0, 0))
        if isinstance(radius_px, bool) or not isinstance(radius_px, numbers.Real):
            raise TypeError("Painter mask radius_px must be a real number, not bool")
        radius = float(radius_px)
        if not math.isfinite(radius):
            raise ValueError("Painter mask radius_px must be finite")
        if radius < 0.5:
            raise ValueError("Painter mask radius_px must be at least 0.5")
        painter.setBrush(QColor(0, 0, 0, _alpha8_value(value, field="mask value")))
        painter.drawEllipse(
            QPointF(float(center[0]), float(center[1])),
            radius,
            radius,
        )
    finally:
        painter.end()
    return output


def apply_alpha8_mask(image: QImage, mask: QImage) -> QImage:
    output = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    alpha = normalized_alpha8(mask, output.width(), output.height())
    painter = QPainter(output)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(0, 0, alpha)
    finally:
        painter.end()
    return output


def transform_alpha8_mask(
    mask: QImage,
    transform: QTransform,
    width: int,
    height: int,
    *,
    smooth: bool = True,
) -> QImage:
    source = normalized_alpha8(mask, width, height)
    output = alpha8_mask(width, height, 0)
    painter = QPainter(output)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, bool(smooth))
        painter.setTransform(transform)
        painter.drawImage(0, 0, source)
    finally:
        painter.end()
    return output


def resize_alpha8_mask(mask: QImage, width: int, height: int) -> QImage:
    return normalized_alpha8(mask, width, height)


def place_alpha8_mask(
    mask: QImage,
    width: int,
    height: int,
    offset_x: float,
    offset_y: float,
) -> QImage:
    output = alpha8_mask(width, height, 0)
    painter = QPainter(output)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(int(round(offset_x)), int(round(offset_y)), mask)
    finally:
        painter.end()
    return output


__all__ = [
    "alpha8_mask",
    "apply_alpha8_mask",
    "linear_gradient_alpha8_mask",
    "normalized_alpha8",
    "paint_mask_circle",
    "place_alpha8_mask",
    "polygon_alpha8_mask",
    "resize_alpha8_mask",
    "transform_alpha8_mask",
]
