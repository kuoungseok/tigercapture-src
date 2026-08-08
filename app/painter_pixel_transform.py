"""Deterministic raster selection transforms for Painter Painting mode."""
from __future__ import annotations

from dataclasses import dataclass
from math import radians, tan

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from app.painter_dimensions import positive_integer


@dataclass(frozen=True)
class PixelTransform:
    translate_x: float = 0.0
    translate_y: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_degrees: float = 0.0
    skew_x_degrees: float = 0.0
    skew_y_degrees: float = 0.0
    pivot_x: float = 0.5
    pivot_y: float = 0.5
    flip_x: bool = False
    flip_y: bool = False


def selection_transform_matrix(
    width: int,
    height: int,
    settings: PixelTransform,
) -> QTransform:
    target_width = positive_integer(width, field="transform width")
    target_height = positive_integer(height, field="transform height")
    px = float(settings.pivot_x) * target_width
    py = float(settings.pivot_y) * target_height
    sx = float(settings.scale_x) * (-1.0 if settings.flip_x else 1.0)
    sy = float(settings.scale_y) * (-1.0 if settings.flip_y else 1.0)
    if sx == 0.0 or sy == 0.0:
        raise ValueError("Transform scale cannot be zero")
    transform = QTransform()
    transform.translate(float(settings.translate_x), float(settings.translate_y))
    transform.translate(px, py)
    transform.rotate(float(settings.rotation_degrees))
    transform.shear(
        tan(radians(float(settings.skew_x_degrees))),
        tan(radians(float(settings.skew_y_degrees))),
    )
    transform.scale(sx, sy)
    transform.translate(-px, -py)
    return transform


def _normalized_argb(image: QImage, width: int, height: int) -> QImage:
    result = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if result.width() != width or result.height() != height:
        result = result.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return result


def transform_selected_raster(
    image: QImage,
    mask: QImage,
    settings: PixelTransform,
    *,
    smooth: bool = True,
) -> tuple[QImage, QImage]:
    """Move selected pixels, clearing their source before compositing the result."""

    if image.isNull() or mask.isNull():
        raise ValueError("Raster transform requires an image and selection mask")
    width, height = image.width(), image.height()
    source = _normalized_argb(image, width, height)
    from app.painter_selection_mask import selection_mask_alpha8

    alpha_mask = selection_mask_alpha8(mask, width, height)

    selected = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    selected.fill(Qt.GlobalColor.transparent)
    selected_painter = QPainter(selected)
    selected_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    selected_painter.drawImage(0, 0, source)
    selected_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    selected_painter.drawImage(0, 0, alpha_mask)
    selected_painter.end()

    base = source.copy()
    clear = QPainter(base)
    clear.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    clear.drawImage(0, 0, alpha_mask)
    clear.end()

    matrix = selection_transform_matrix(width, height, settings)
    output = base.copy()
    painter = QPainter(output)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, bool(smooth))
    painter.setTransform(matrix)
    painter.drawImage(0, 0, selected)
    painter.end()

    transformed_mask = QImage(width, height, QImage.Format.Format_Alpha8)
    transformed_mask.fill(0)
    mask_painter = QPainter(transformed_mask)
    mask_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, bool(smooth))
    mask_painter.setTransform(matrix)
    mask_painter.drawImage(0, 0, alpha_mask)
    mask_painter.end()
    return output, transformed_mask


__all__ = ["PixelTransform", "selection_transform_matrix", "transform_selected_raster"]
