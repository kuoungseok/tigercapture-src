"""Pixel contracts for Painter's editable Quick Mask mode."""
from __future__ import annotations

from PIL import Image, ImageChops, ImageOps
from PySide6.QtGui import QColor, QImage, qGray

from app.painter_selection_mask import (
    PAINTER_SELECTION_MASK_FULL_VALUE,
    selection_mask_alpha8,
)


QUICK_MASK_BOUNDARY_SELECTED_VALUE = (
    PAINTER_SELECTION_MASK_FULL_VALUE + 1
) // 2
QUICK_MASK_OVERLAY_MAX_ALPHA = QUICK_MASK_BOUNDARY_SELECTED_VALUE


def _alpha8_to_pil(mask: QImage) -> Image.Image:
    converted = mask.convertToFormat(QImage.Format.Format_Alpha8)
    return Image.frombuffer(
        "L",
        (converted.width(), converted.height()),
        bytes(converted.constBits()),
        "raw",
        "L",
        converted.bytesPerLine(),
        1,
    ).copy()


def _pil_to_alpha8(mask: Image.Image) -> QImage:
    prepared = mask.convert("L")
    return QImage(
        prepared.tobytes(),
        prepared.width,
        prepared.height,
        prepared.width,
        QImage.Format.Format_Alpha8,
    ).copy()


def quick_mask_entry_selection(
    selection: QImage | None,
    width: int,
    height: int,
) -> QImage:
    if width <= 0 or height <= 0:
        raise ValueError("Quick Mask dimensions must be positive")
    if isinstance(selection, QImage) and not selection.isNull():
        return selection_mask_alpha8(selection, width, height)
    result = QImage(width, height, QImage.Format.Format_Alpha8)
    result.fill(0)
    return result


def quick_mask_grayscale_value(color: QColor) -> int:
    if not isinstance(color, QColor) or not color.isValid():
        raise ValueError("Quick Mask paint color must be valid")
    return qGray(color.rgb())


def apply_quick_mask_coverage(
    selection: QImage,
    coverage: QImage,
    selected_value: int,
) -> QImage:
    if not isinstance(selected_value, int) or isinstance(selected_value, bool):
        raise TypeError("Quick Mask selected value must be an integer")
    if not 0 <= selected_value <= PAINTER_SELECTION_MASK_FULL_VALUE:
        raise ValueError("Quick Mask selected value is outside the 8-bit domain")
    current = selection_mask_alpha8(selection)
    brush = selection_mask_alpha8(coverage, current.width(), current.height())
    current_pil = _alpha8_to_pil(current)
    target = Image.new("L", current_pil.size, selected_value)
    return _pil_to_alpha8(Image.composite(target, current_pil, _alpha8_to_pil(brush)))


def quick_mask_boundary_mask(selection: QImage) -> QImage:
    source = _alpha8_to_pil(selection_mask_alpha8(selection))
    return _pil_to_alpha8(
        source.point(
            lambda value: (
                PAINTER_SELECTION_MASK_FULL_VALUE
                if value >= QUICK_MASK_BOUNDARY_SELECTED_VALUE
                else 0
            )
        )
    )


def quick_mask_overlay_image(
    selection: QImage,
    width: int,
    height: int,
) -> QImage:
    selected = _alpha8_to_pil(selection_mask_alpha8(selection, width, height))
    protected = ImageOps.invert(selected)
    overlay_alpha = ImageChops.multiply(
        protected,
        Image.new("L", protected.size, QUICK_MASK_OVERLAY_MAX_ALPHA),
    )
    overlay = Image.new(
        "RGBA",
        protected.size,
        (PAINTER_SELECTION_MASK_FULL_VALUE, 0, 0, 0),
    )
    overlay.putalpha(overlay_alpha)
    raw = overlay.tobytes()
    return QImage(
        raw,
        overlay.width,
        overlay.height,
        overlay.width * len(overlay.getbands()),
        QImage.Format.Format_RGBA8888,
    ).copy()


__all__ = [
    "QUICK_MASK_BOUNDARY_SELECTED_VALUE",
    "QUICK_MASK_OVERLAY_MAX_ALPHA",
    "apply_quick_mask_coverage",
    "quick_mask_boundary_mask",
    "quick_mask_entry_selection",
    "quick_mask_grayscale_value",
    "quick_mask_overlay_image",
]
