"""Motion source frame conversion helpers."""
from __future__ import annotations

from PySide6.QtGui import QImage


def premultiplied(image: QImage) -> QImage:
    if image.format() == QImage.Format_RGBA8888_Premultiplied:
        return image
    return image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def transparent_image(width: int, height: int) -> QImage:
    image = QImage(max(1, int(width)), max(1, int(height)), QImage.Format_RGBA8888_Premultiplied)
    image.fill(0)
    return image
