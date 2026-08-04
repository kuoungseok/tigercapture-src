"""Document-sized transparent raster surfaces for Painter paint layers."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QPainter


def transparent_raster(width: int, height: int) -> QImage:
    image = QImage(
        max(1, int(width)),
        max(1, int(height)),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(Qt.GlobalColor.transparent)
    return image


def normalized_raster(image: QImage | None, width: int, height: int) -> QImage:
    target = QSize(max(1, int(width)), max(1, int(height)))
    if image is None or image.isNull():
        return transparent_raster(target.width(), target.height())
    converted = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    if converted.size() == target:
        return converted.copy()
    out = transparent_raster(target.width(), target.height())
    painter = QPainter(out)
    try:
        painter.drawImage(out.rect(), converted)
    finally:
        painter.end()
    return out


def copy_raster_map(images: Mapping[str, QImage] | None) -> dict[str, QImage]:
    return {
        str(layer_id): image.copy()
        for layer_id, image in dict(images or {}).items()
        if isinstance(image, QImage) and not image.isNull()
    }


def raster_png_bytes(image: QImage | None) -> bytes | None:
    if image is None or image.isNull():
        return None
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    try:
        if not image.save(buffer, "PNG"):
            return None
    finally:
        buffer.close()
    return bytes(data)


def load_raster(path: str | Path, width: int, height: int) -> QImage:
    image = QImage(str(path or ""))
    return normalized_raster(image, width, height)


def raster_has_pixels(image: QImage | None) -> bool:
    if image is None or image.isNull():
        return False
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    raw = np.frombuffer(converted.constBits(), dtype=np.uint8, count=converted.sizeInBytes())
    rows = raw.reshape(converted.height(), converted.bytesPerLine())
    return bool(np.any(rows[:, 3 : converted.width() * 4 : 4]))


__all__ = [
    "copy_raster_map",
    "load_raster",
    "normalized_raster",
    "raster_has_pixels",
    "raster_png_bytes",
    "transparent_raster",
]
