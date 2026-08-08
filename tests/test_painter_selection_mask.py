from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_contiguous_color_selection_does_not_select_disconnected_match() -> None:
    _app()
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    from app.painter_selection_mask import color_selection_mask

    image = QImage(30, 12, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#202020"))
    painter = QPainter(image)
    try:
        painter.fillRect(QRect(1, 1, 8, 8), QColor("#E04040"))
        painter.fillRect(QRect(20, 1, 8, 8), QColor("#E04040"))
    finally:
        painter.end()
    contiguous = color_selection_mask(image, 3, 3, tolerance=0, contiguous=True)
    global_mask = color_selection_mask(image, 3, 3, tolerance=0, contiguous=False)
    assert contiguous.pixelColor(3, 3).alpha() == 255
    assert contiguous.pixelColor(23, 3).alpha() == 0
    assert global_mask.pixelColor(23, 3).alpha() == 255


def test_selection_combine_and_morphology_preserve_non_rectangular_shape() -> None:
    _app()
    from app.painter_selection_mask import (
        combine_selection_masks,
        modify_selection_mask,
        polygon_selection_mask,
        selection_mask_bounds,
    )

    triangle = polygon_selection_mask(
        40, 40, [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9)]
    )
    square = polygon_selection_mask(
        40, 40, [(0.5, 0.5), (0.9, 0.5), (0.9, 0.9), (0.5, 0.9)]
    )
    added = combine_selection_masks(triangle, square, "add")
    subtracted = combine_selection_masks(added, square, "subtract")
    assert added.pixelColor(34, 34).alpha() == 255
    assert subtracted.pixelColor(34, 34).alpha() == 0
    assert triangle.pixelColor(34, 34).alpha() == 0
    expanded = modify_selection_mask(triangle, "expand", 2)
    contracted = modify_selection_mask(triangle, "contract", 2)
    border = modify_selection_mask(triangle, "border", 2)
    feathered = modify_selection_mask(triangle, "feather", 2.5)
    assert selection_mask_bounds(expanded)[0] < selection_mask_bounds(triangle)[0]
    assert selection_mask_bounds(contracted)[0] > selection_mask_bounds(triangle)[0]
    assert 0 < feathered.pixelColor(3, 3).alpha() < 255
    assert border.pixelColor(4, 4).alpha() > 0


def test_selection_mask_dimensions_require_complete_positive_pairs() -> None:
    from PySide6.QtGui import QImage
    from app.painter_selection_mask import polygon_selection_mask, selection_mask_alpha8

    mask = QImage(8, 8, QImage.Format.Format_Alpha8)
    mask.fill(0)
    with pytest.raises(ValueError, match="selection width must be positive"):
        polygon_selection_mask(0, 8, [])
    with pytest.raises(ValueError, match="selection mask height must be positive"):
        selection_mask_alpha8(mask, 8, 0)


def test_selection_expand_honors_radius_above_pillow_single_filter_limit() -> None:
    from PIL import Image
    from PySide6.QtGui import QImage
    from app.painter_selection_mask import modify_selection_mask, selection_mask_bounds

    raw = Image.new("L", (320, 320), 0)
    raw.putpixel((160, 160), 255)
    payload = raw.tobytes()
    mask = QImage(payload, 320, 320, 320, QImage.Format.Format_Alpha8).copy()
    expanded = modify_selection_mask(mask, "expand", 120)
    assert selection_mask_bounds(expanded) == (40, 40, 281, 281)


def test_selection_mask_modify_rejects_invalid_inputs_before_pillow() -> None:
    from PySide6.QtGui import QImage
    from app.painter_output import PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
    from app.painter_selection_mask import modify_selection_mask

    mask = QImage(8, 8, QImage.Format.Format_Alpha8)
    mask.fill(0)
    invalid_calls = (
        ("grow", 1),
        ("feather", True),
        ("feather", float("nan")),
        ("feather", float("inf")),
        ("feather", 0.0),
        ("feather", -1.0),
        ("feather", PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1),
        ("expand", 1.5),
        ("contract", 0),
        ("border", PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT + 1),
    )
    for operation, radius in invalid_calls:
        with pytest.raises((TypeError, ValueError)):
            modify_selection_mask(mask, operation, radius)
