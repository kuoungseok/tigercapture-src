from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPixmap


def draw_pixmap_cover(
    painter: QPainter,
    target: QRect,
    pixmap: QPixmap,
    radius: float = 4.0,
    opacity: float = 1.0,
    soften: float = 0.0,
) -> None:
    """Draw a pixmap like object-fit: cover without stretching the source."""
    if (
        target.width() <= 0
        or target.height() <= 0
        or pixmap is None
        or pixmap.isNull()
        or pixmap.width() <= 0
        or pixmap.height() <= 0
    ):
        return
    dst_ratio = target.width() / max(1, target.height())
    src_ratio = pixmap.width() / max(1, pixmap.height())
    if src_ratio > dst_ratio:
        crop_w = max(1, int(round(pixmap.height() * dst_ratio)))
        src = QRect(max(0, (pixmap.width() - crop_w) // 2), 0, crop_w, pixmap.height())
    else:
        crop_h = max(1, int(round(pixmap.width() / max(dst_ratio, 0.001))))
        src = QRect(0, max(0, (pixmap.height() - crop_h) // 2), pixmap.width(), crop_h)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.setOpacity(max(0.0, min(1.0, float(opacity))))
    path = QPainterPath()
    path.addRoundedRect(QRectF(target), radius, radius)
    painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
    softness = max(0.0, min(1.0, float(soften)))
    if softness > 0.0:
        scale_down = max(2, int(round(2 + softness * 4)))
        low_w = max(1, target.width() // scale_down)
        low_h = max(1, target.height() // scale_down)
        softened = QPixmap(low_w, low_h)
        softened.fill(Qt.GlobalColor.transparent)
        low_painter = QPainter(softened)
        low_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        low_painter.drawPixmap(QRect(0, 0, low_w, low_h), pixmap, src)
        low_painter.end()
        painter.drawPixmap(target, softened)
    else:
        painter.drawPixmap(target, pixmap, src)
    painter.restore()


__all__ = ["draw_pixmap_cover"]
