"""Interactive add/remove brush for decomposition masks."""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget


class MaskRefineCanvas(QWidget):
    mask_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionMaskRefineCanvas")
        self.setMinimumSize(320, 180)
        self.setMouseTracking(True)
        self._source = QImage()
        self._mask = QImage()
        self._brush_radius = 18
        self._mode = "add"
        self._show_mask = True
        self._last_point: QPoint | None = None

    def set_images(self, source: QImage, mask: QImage) -> None:
        self._source = source.convertToFormat(QImage.Format_RGBA8888)
        self._mask = mask.convertToFormat(QImage.Format_Grayscale8)
        if self._mask.size() != self._source.size():
            self._mask = self._mask.scaled(
                self._source.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
        self.update()

    def set_brush_radius(self, radius: int) -> None:
        self._brush_radius = max(1, min(256, int(radius)))

    def set_mode(self, mode: str) -> None:
        normalized = str(mode or "").strip().casefold()
        if normalized not in {"add", "remove"}:
            raise ValueError(f"unsupported mask brush mode: {mode}")
        self._mode = normalized

    def mask_image(self) -> QImage:
        return self._mask.copy()

    def set_mask_visible(self, visible: bool) -> None:
        self._show_mask = bool(visible)
        self.update()

    def _image_point(self, point: QPoint) -> QPoint | None:
        if self._source.isNull():
            return None
        fitted = self._fitted_rect()
        if not fitted.contains(point):
            return None
        x = round((point.x() - fitted.x()) * self._source.width() / max(1, fitted.width()))
        y = round((point.y() - fitted.y()) * self._source.height() / max(1, fitted.height()))
        return QPoint(
            max(0, min(self._source.width() - 1, x)),
            max(0, min(self._source.height() - 1, y)),
        )

    def _fitted_rect(self):
        from PySide6.QtCore import QRect

        size = self._source.size()
        size.scale(self.size(), Qt.KeepAspectRatio)
        return QRect(
            (self.width() - size.width()) // 2,
            (self.height() - size.height()) // 2,
            size.width(),
            size.height(),
        )

    def _paint_mask(self, start: QPoint, end: QPoint) -> None:
        if self._mask.isNull():
            return
        painter = QPainter(self._mask)
        color = QColor(255, 255, 255) if self._mode == "add" else QColor(0, 0, 0)
        pen = QPen(
            color,
            self._brush_radius * 2,
            Qt.SolidLine,
            Qt.RoundCap,
            Qt.RoundJoin,
        )
        painter.setPen(pen)
        painter.drawLine(start, end)
        painter.end()
        self.mask_changed.emit()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            point = self._image_point(event.position().toPoint())
            if point is not None:
                self._last_point = point
                self._paint_mask(point, point)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._last_point is not None and event.buttons() & Qt.LeftButton:
            point = self._image_point(event.position().toPoint())
            if point is not None:
                self._paint_mask(self._last_point, point)
                self._last_point = point
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._last_point = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101217"))
        if self._source.isNull():
            painter.end()
            return
        target = self._fitted_rect()
        painter.drawImage(target, self._source)
        if self._show_mask and not self._mask.isNull():
            overlay = QImage(self._mask.size(), QImage.Format_RGBA8888)
            overlay.fill(Qt.transparent)
            mask_painter = QPainter(overlay)
            mask_painter.fillRect(overlay.rect(), QColor(62, 188, 224, 112))
            mask_painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            mask_painter.drawImage(overlay.rect(), self._mask)
            mask_painter.end()
            painter.drawImage(target, overlay)
        painter.end()


__all__ = ["MaskRefineCanvas"]
