"""Canvas overlay for the first Painter UI Design workspace milestone."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.painter_ui_document import normalize_ui_document


class PainterUIDesignOverlay(QWidget):
    object_selected = Signal(str)
    object_move_requested = Signal(str, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._drag_object_id = ""
        self._drag_offset = (0.0, 0.0)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        self.update()

    def _active_artboard(self) -> dict[str, Any]:
        active = self._document["active_artboard_id"]
        return next(
            row for row in self._document["artboards"] if row["id"] == active
        )

    def _object_rect(self, row: Mapping[str, Any]) -> QRectF:
        artboard = self._active_artboard()
        sx = self.width() / max(1.0, float(artboard["width"]))
        sy = self.height() / max(1.0, float(artboard["height"]))
        return QRectF(
            float(row["x"]) * sx,
            float(row["y"]) * sy,
            float(row["width"]) * sx,
            float(row["height"]) * sy,
        )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        selected = self._document["selection"]["object_id"]
        active = self._document["active_artboard_id"]
        objects = sorted(
            (
                row
                for row in self._document["objects"]
                if row["artboard_id"] == active and row["visible"]
            ),
            key=lambda row: row["z_index"],
        )
        for row in objects:
            rect = self._object_rect(row)
            style = row["style"]
            fill = QColor(str(style.get("fill") or "#506884"))
            fill.setAlphaF(max(0.08, min(0.72, float(row["opacity"]) * 0.42)))
            painter.fillRect(rect, fill)
            is_selected = row["id"] == selected
            painter.setPen(
                QPen(
                    QColor("#72A7FF") if is_selected else QColor("#B8C4D6"),
                    2.0 if is_selected else 1.0,
                )
            )
            painter.drawRect(rect)
            painter.setPen(QColor("#F2F5F9"))
            font = QFont(self.font())
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(rect.adjusted(5, 3, -4, -3), row["name"])
            if is_selected:
                painter.setBrush(QColor("#F4F7FC"))
                for point in (
                    rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()
                ):
                    painter.drawRect(QRectF(point.x() - 3, point.y() - 3, 6, 6))

    def mousePressEvent(self, event) -> None:
        active = self._document["active_artboard_id"]
        candidates = sorted(
            (
                row
                for row in self._document["objects"]
                if row["artboard_id"] == active and row["visible"]
            ),
            key=lambda row: row["z_index"],
            reverse=True,
        )
        selected = ""
        for row in candidates:
            rect = self._object_rect(row)
            if rect.contains(event.position()):
                selected = row["id"]
                self._drag_object_id = selected
                self._drag_offset = (
                    event.position().x() - rect.x(),
                    event.position().y() - rect.y(),
                )
                break
        if not selected:
            self._drag_object_id = ""
        self.object_selected.emit(selected)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self._drag_object_id:
            return
        artboard = self._active_artboard()
        sx = self.width() / max(1.0, float(artboard["width"]))
        sy = self.height() / max(1.0, float(artboard["height"]))
        for row in self._document["objects"]:
            if row["id"] != self._drag_object_id:
                continue
            row["x"] = max(
                0.0,
                min(
                    float(artboard["width"]) - float(row["width"]),
                    (event.position().x() - self._drag_offset[0]) / max(0.0001, sx),
                ),
            )
            row["y"] = max(
                0.0,
                min(
                    float(artboard["height"]) - float(row["height"]),
                    (event.position().y() - self._drag_offset[1]) / max(0.0001, sy),
                ),
            )
            self.update()
            break
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        object_id = self._drag_object_id
        self._drag_object_id = ""
        if object_id:
            row = next(
                (item for item in self._document["objects"] if item["id"] == object_id),
                None,
            )
            if row is not None:
                self.object_move_requested.emit(
                    object_id,
                    float(row["x"]),
                    float(row["y"]),
                )
        event.accept()


__all__ = ["PainterUIDesignOverlay"]
