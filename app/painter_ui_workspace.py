"""Interactive canvas overlay for Painter's UI Design workspace."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.painter_ui_document import normalize_ui_document


_CREATE_TOOLS = {
    "frame",
    "rectangle",
    "ellipse",
    "line",
    "text",
    "image",
    "button",
    "progress",
}
_HANDLE_NAMES = ("nw", "ne", "sw", "se")


class PainterUIDesignOverlay(QWidget):
    object_selected = Signal(str)
    object_geometry_requested = Signal(str, float, float, float, float)
    object_create_requested = Signal(str, float, float, float, float)
    key_command = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._tool = "select"
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._press_position = QPointF()
        self._original_rect = QRectF()
        self._preview_rect = QRectF()
        self._drag_offset = QPointF()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        self.update()

    def set_tool(self, tool: str) -> str:
        requested = str(tool or "select").strip().casefold()
        self._tool = requested if requested in _CREATE_TOOLS else "select"
        self._cancel_interaction()
        self.setCursor(
            Qt.CursorShape.CrossCursor
            if self._tool in _CREATE_TOOLS
            else Qt.CursorShape.ArrowCursor
        )
        return self._tool

    def tool(self) -> str:
        return self._tool

    def _active_artboard(self) -> dict[str, Any]:
        active = self._document["active_artboard_id"]
        return next(
            row for row in self._document["artboards"] if row["id"] == active
        )

    def _scale(self) -> tuple[float, float]:
        artboard = self._active_artboard()
        return (
            self.width() / max(1.0, float(artboard["width"])),
            self.height() / max(1.0, float(artboard["height"])),
        )

    def _document_point(self, point: QPointF) -> QPointF:
        sx, sy = self._scale()
        return QPointF(
            point.x() / max(0.0001, sx),
            point.y() / max(0.0001, sy),
        )

    def _object_rect(self, row: Mapping[str, Any]) -> QRectF:
        sx, sy = self._scale()
        return QRectF(
            float(row["x"]) * sx,
            float(row["y"]) * sy,
            float(row["width"]) * sx,
            float(row["height"]) * sy,
        )

    @staticmethod
    def _handle_rects(rect: QRectF) -> dict[str, QRectF]:
        return {
            name: QRectF(point.x() - 5.0, point.y() - 5.0, 10.0, 10.0)
            for name, point in (
                ("nw", rect.topLeft()),
                ("ne", rect.topRight()),
                ("sw", rect.bottomLeft()),
                ("se", rect.bottomRight()),
            )
        }

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self._document["selection"]["object_id"]
        return next(
            (row for row in self._document["objects"] if row["id"] == selected),
            None,
        )

    def _visible_objects(self, *, reverse: bool = False) -> list[dict[str, Any]]:
        active = self._document["active_artboard_id"]
        return sorted(
            (
                row
                for row in self._document["objects"]
                if row["artboard_id"] == active and row["visible"]
            ),
            key=lambda row: row["z_index"],
            reverse=reverse,
        )

    def _paint_object(self, painter: QPainter, row: Mapping[str, Any]) -> None:
        rect = self._object_rect(row)
        style = row["style"]
        kind = str(row["kind"])
        fill = QColor(str(style.get("fill") or "#506884"))
        fill.setAlphaF(max(0.06, min(1.0, float(row["opacity"]))))
        stroke = QColor(str(style.get("stroke") or "#93A3B8"))
        painter.setPen(QPen(stroke, max(1.0, float(style.get("stroke_width") or 1.0))))
        painter.setBrush(fill)

        if kind == "ellipse":
            painter.drawEllipse(rect)
        elif kind == "line":
            painter.setPen(QPen(fill, max(1.5, float(style.get("stroke_width") or 2.0))))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        elif kind == "progress":
            painter.drawRoundedRect(rect, 3.0, 3.0)
            amount = max(0.0, min(1.0, float(row["content"].get("value", 0.64))))
            progress = QRectF(rect)
            progress.setWidth(rect.width() * amount)
            painter.fillRect(progress, QColor(str(style.get("accent") or "#6FA0F5")))
        elif kind == "text":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(str(style.get("text_color") or "#F2F5F9")))
        else:
            radius = max(0.0, float(style.get("radius") or 0.0))
            painter.drawRoundedRect(rect, radius, radius)
            if kind == "image":
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.topRight(), rect.bottomLeft())

        label = str(row["content"].get("text") or "")
        if kind in {"text", "button"} and not label:
            label = str(row["name"])
        if label and kind not in {"line", "image"}:
            painter.setPen(QColor(str(style.get("text_color") or "#F2F5F9")))
            font = QFont(self.font())
            font.setPointSize(max(7, int(style.get("font_size") or 9)))
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(6, 3, -5, -3),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        selected = self._document["selection"]["object_id"]
        for row in self._visible_objects():
            painter.save()
            self._paint_object(painter, row)
            rect = self._object_rect(row)
            is_selected = row["id"] == selected
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    QColor("#72A7FF") if is_selected else QColor("#9AA9BC"),
                    2.0 if is_selected else 1.0,
                )
            )
            painter.drawRect(rect)
            if is_selected and not row["locked"]:
                painter.setBrush(QColor("#F4F7FC"))
                painter.setPen(QPen(QColor("#356FC7"), 1.0))
                for handle in self._handle_rects(rect).values():
                    painter.drawRect(handle)
            painter.restore()

        if self._interaction == "create" and not self._preview_rect.isNull():
            painter.setBrush(QColor(80, 130, 210, 48))
            painter.setPen(QPen(QColor("#79AFFF"), 1.5, Qt.PenStyle.DashLine))
            painter.drawRect(self._preview_rect.normalized())

    def _cancel_interaction(self) -> None:
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._preview_rect = QRectF()
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._press_position = QPointF(event.position())

        if self._tool in _CREATE_TOOLS:
            self._interaction = "create"
            self._preview_rect = QRectF(self._press_position, self._press_position)
            event.accept()
            return

        selected_row = self._selected_row()
        if selected_row is not None and not selected_row["locked"]:
            selected_rect = self._object_rect(selected_row)
            for name in _HANDLE_NAMES:
                if self._handle_rects(selected_rect)[name].contains(event.position()):
                    self._interaction = "resize"
                    self._active_object_id = selected_row["id"]
                    self._active_handle = name
                    self._original_rect = QRectF(selected_rect)
                    event.accept()
                    return

        selected = ""
        for row in self._visible_objects(reverse=True):
            rect = self._object_rect(row)
            if rect.contains(event.position()):
                selected = row["id"]
                if not row["locked"]:
                    self._interaction = "move"
                    self._active_object_id = selected
                    self._original_rect = QRectF(rect)
                    self._drag_offset = event.position() - rect.topLeft()
                break
        if not selected:
            self._cancel_interaction()
        self.object_selected.emit(selected)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._interaction == "create":
            self._preview_rect = QRectF(
                self._press_position,
                event.position(),
            ).normalized()
            self.update()
            event.accept()
            return
        if self._interaction == "move":
            artboard = self._active_artboard()
            doc = self._document_point(event.position() - self._drag_offset)
            row = next(
                row
                for row in self._document["objects"]
                if row["id"] == self._active_object_id
            )
            row["x"] = max(
                0.0,
                min(float(artboard["width"]) - float(row["width"]), doc.x()),
            )
            row["y"] = max(
                0.0,
                min(float(artboard["height"]) - float(row["height"]), doc.y()),
            )
            self.update()
            event.accept()
            return
        if self._interaction == "resize":
            rect = QRectF(self._original_rect)
            point = event.position()
            if "n" in self._active_handle:
                rect.setTop(point.y())
            if "s" in self._active_handle:
                rect.setBottom(point.y())
            if "w" in self._active_handle:
                rect.setLeft(point.x())
            if "e" in self._active_handle:
                rect.setRight(point.x())
            rect = rect.normalized()
            if rect.width() >= 8.0 and rect.height() >= 8.0:
                row = next(
                    row
                    for row in self._document["objects"]
                    if row["id"] == self._active_object_id
                )
                sx, sy = self._scale()
                row["x"] = rect.x() / max(0.0001, sx)
                row["y"] = rect.y() / max(0.0001, sy)
                row["width"] = rect.width() / max(0.0001, sx)
                row["height"] = rect.height() / max(0.0001, sy)
                self.update()
            event.accept()
            return
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        interaction = self._interaction
        object_id = self._active_object_id
        if interaction == "create":
            rect = self._preview_rect.normalized()
            if rect.width() >= 6.0 and rect.height() >= 6.0:
                sx, sy = self._scale()
                self.object_create_requested.emit(
                    self._tool,
                    rect.x() / max(0.0001, sx),
                    rect.y() / max(0.0001, sy),
                    rect.width() / max(0.0001, sx),
                    rect.height() / max(0.0001, sy),
                )
        elif interaction in {"move", "resize"} and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                self.object_geometry_requested.emit(
                    object_id,
                    float(row["x"]),
                    float(row["y"]),
                    float(row["width"]),
                    float(row["height"]),
                )
        self._cancel_interaction()
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Delete:
            self.key_command.emit("delete", False)
            event.accept()
            return
        if (
            key == Qt.Key.Key_D
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.key_command.emit("duplicate", False)
            event.accept()
            return
        directions = {
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
        }
        if key in directions:
            self.key_command.emit(
                directions[key],
                bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
            )
            event.accept()
            return
        super().keyPressEvent(event)


__all__ = ["PainterUIDesignOverlay"]
