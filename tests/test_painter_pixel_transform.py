from __future__ import annotations

from PySide6.QtGui import QColor, QImage


def _image() -> tuple[QImage, QImage]:
    image = QImage(12, 10, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    mask = QImage(12, 10, QImage.Format.Format_Alpha8)
    mask.fill(0)
    for y in range(2, 5):
        for x in range(2, 5):
            image.setPixelColor(x, y, QColor(220, 30, 20, 255))
            mask.setPixelColor(x, y, QColor(255, 255, 255, 255))
    return image, mask


def test_transform_selected_raster_moves_pixels_and_mask() -> None:
    from app.painter_pixel_transform import PixelTransform, transform_selected_raster

    image, mask = _image()
    output, moved_mask = transform_selected_raster(
        image, mask, PixelTransform(translate_x=4, translate_y=2), smooth=False
    )
    assert output.pixelColor(2, 2).alpha() == 0
    assert output.pixelColor(6, 4).red() == 220
    assert moved_mask.pixelColor(2, 2).alpha() == 0
    assert moved_mask.pixelColor(6, 4).alpha() == 255


def test_transform_preview_math_is_deterministic_and_supports_flip() -> None:
    from app.painter_pixel_transform import PixelTransform, transform_selected_raster

    image, mask = _image()
    settings = PixelTransform(
        scale_x=1.25, scale_y=0.75, rotation_degrees=18,
        skew_x_degrees=7, pivot_x=0.3, pivot_y=0.4, flip_x=True,
    )
    first, first_mask = transform_selected_raster(image, mask, settings)
    second, second_mask = transform_selected_raster(image, mask, settings)
    assert bytes(first.constBits()) == bytes(second.constBits())
    assert bytes(first_mask.constBits()) == bytes(second_mask.constBits())
