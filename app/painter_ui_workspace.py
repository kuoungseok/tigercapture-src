"""Interactive canvas overlay for Painter's UI Design workspace."""
from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QTransform
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
    object_selection_requested = Signal(str, str)
    object_geometry_requested = Signal(str, float, float, float, float)
    object_changes_requested = Signal(str, object)
    objects_changes_requested = Signal(object)
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
        self._move_original_positions: dict[str, tuple[float, float]] = {}
        self._original_rotation = 0.0
        self._rotation_start_angle = 0.0
        self._snap_enabled = False
        self._snap_size = 8.0
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

    def set_snap(self, enabled: bool, size: float = 8.0) -> None:
        self._snap_enabled = bool(enabled)
        self._snap_size = max(1.0, float(size))

    def snap_enabled(self) -> bool:
        return self._snap_enabled

    def _active_artboard(self) -> dict[str, Any]:
        active = self._document["active_artboard_id"]
        return next(
            row for row in self._document["artboards"] if row["id"] == active
        )

    def _artboard_viewport(self) -> tuple[QRectF, float]:
        artboard = self._active_artboard()
        available_width = max(1.0, float(self.width()) - 24.0)
        available_height = max(1.0, float(self.height()) - 24.0)
        scale = min(
            available_width / max(1.0, float(artboard["width"])),
            available_height / max(1.0, float(artboard["height"])),
        )
        width = float(artboard["width"]) * scale
        height = float(artboard["height"]) * scale
        return (
            QRectF(
                (float(self.width()) - width) * 0.5,
                (float(self.height()) - height) * 0.5,
                width,
                height,
            ),
            scale,
        )

    def _scale(self) -> tuple[float, float]:
        _viewport, scale = self._artboard_viewport()
        return scale, scale

    def _document_point(self, point: QPointF) -> QPointF:
        viewport, scale = self._artboard_viewport()
        return QPointF(
            (point.x() - viewport.x()) / max(0.0001, scale),
            (point.y() - viewport.y()) / max(0.0001, scale),
        )

    def _object_rect(self, row: Mapping[str, Any]) -> QRectF:
        viewport, scale = self._artboard_viewport()
        return QRectF(
            viewport.x() + float(row["x"]) * scale,
            viewport.y() + float(row["y"]) * scale,
            float(row["width"]) * scale,
            float(row["height"]) * scale,
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

    @staticmethod
    def _rotation_handle_rect(rect: QRectF) -> QRectF:
        center_x = rect.center().x()
        return QRectF(center_x - 5.0, rect.top() - 25.0, 10.0, 10.0)

    @staticmethod
    def _unrotated_point(point: QPointF, rect: QRectF, angle: float) -> QPointF:
        if abs(float(angle)) < 0.001:
            return QPointF(point)
        transform = QTransform()
        transform.translate(rect.center().x(), rect.center().y())
        transform.rotate(-float(angle))
        transform.translate(-rect.center().x(), -rect.center().y())
        return transform.map(point)

    def _snap(self, value: float) -> float:
        if not self._snap_enabled:
            return float(value)
        return round(float(value) / self._snap_size) * self._snap_size

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
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
        if kind == "group":
            return
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
        artboard = self._active_artboard()
        viewport, _scale = self._artboard_viewport()
        painter.fillRect(self.rect(), QColor(18, 21, 27, 86))
        painter.fillRect(viewport, QColor(str(artboard.get("background") or "#FFFFFF")))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#718096"), 1.0))
        painter.drawRect(viewport)
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
        for row in self._visible_objects():
            painter.save()
            rect = self._object_rect(row)
            rotation = float(row.get("rotation", 0.0))
            if abs(rotation) >= 0.001:
                painter.translate(rect.center())
                painter.rotate(rotation)
                painter.translate(-rect.center())
            self._paint_object(painter, row)
            is_selected = row["id"] in selected_ids
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    QColor("#72A7FF") if is_selected else QColor("#9AA9BC"),
                    2.0 if is_selected else 1.0,
                )
            )
            painter.drawRect(rect)
            if row["id"] == selected and not row["locked"]:
                painter.setBrush(QColor("#F4F7FC"))
                painter.setPen(QPen(QColor("#356FC7"), 1.0))
                for handle in self._handle_rects(rect).values():
                    painter.drawRect(handle)
                rotate_handle = self._rotation_handle_rect(rect)
                painter.drawLine(
                    QPointF(rect.center().x(), rect.top()),
                    QPointF(rect.center().x(), rotate_handle.bottom()),
                )
                painter.setBrush(QColor("#F4F7FC"))
                painter.drawEllipse(rotate_handle)
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
        viewport, _scale = self._artboard_viewport()

        if self._tool in _CREATE_TOOLS:
            if not viewport.contains(self._press_position):
                event.ignore()
                return
            self._interaction = "create"
            self._preview_rect = QRectF(self._press_position, self._press_position)
            event.accept()
            return

        selected_row = self._selected_row()
        if selected_row is not None and not selected_row["locked"]:
            selected_rect = self._object_rect(selected_row)
            local_position = self._unrotated_point(
                event.position(),
                selected_rect,
                float(selected_row.get("rotation", 0.0)),
            )
            if self._rotation_handle_rect(selected_rect).contains(local_position):
                self._interaction = "rotate"
                self._active_object_id = selected_row["id"]
                self._original_rect = QRectF(selected_rect)
                self._original_rotation = float(selected_row.get("rotation", 0.0))
                delta = event.position() - selected_rect.center()
                self._rotation_start_angle = math.degrees(
                    math.atan2(delta.y(), delta.x())
                )
                event.accept()
                return
            for name in _HANDLE_NAMES:
                if self._handle_rects(selected_rect)[name].contains(local_position):
                    self._interaction = "resize"
                    self._active_object_id = selected_row["id"]
                    self._active_handle = name
                    self._original_rect = QRectF(selected_rect)
                    event.accept()
                    return

        selected = ""
        selected_row = None
        for row in self._visible_objects(reverse=True):
            rect = self._object_rect(row)
            local_position = self._unrotated_point(
                event.position(),
                rect,
                float(row.get("rotation", 0.0)),
            )
            if rect.contains(local_position):
                selected = row["id"]
                selected_row = row
                break
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.object_selection_requested.emit(selected, "toggle")
            self._cancel_interaction()
            event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.object_selection_requested.emit(selected, "add")
            self._cancel_interaction()
            event.accept()
            return
        if not selected:
            self._cancel_interaction()
            self.object_selection_requested.emit("", "replace")
        else:
            if selected not in self._document["selection"]["object_ids"]:
                self.object_selection_requested.emit(selected, "replace")
            if selected_row is not None and not selected_row["locked"]:
                self._interaction = "move"
                self._active_object_id = selected
                self._original_rect = QRectF(self._object_rect(selected_row))
                self._drag_offset = event.position() - self._original_rect.topLeft()
                selected_ids = list(self._document["selection"]["object_ids"])
                if selected not in selected_ids:
                    selected_ids = [selected]
                descendants = set(selected_ids)
                changed = True
                while changed:
                    before = len(descendants)
                    descendants.update(
                        row["id"]
                        for row in self._document["objects"]
                        if row["parent_id"] in descendants
                    )
                    changed = len(descendants) != before
                self._move_original_positions = {
                    row["id"]: (float(row["x"]), float(row["y"]))
                    for row in self._document["objects"]
                    if row["id"] in descendants and not row["locked"]
                }
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._interaction == "create":
            viewport, _scale = self._artboard_viewport()
            position = QPointF(
                max(viewport.left(), min(viewport.right(), event.position().x())),
                max(viewport.top(), min(viewport.bottom(), event.position().y())),
            )
            self._preview_rect = QRectF(
                self._press_position,
                position,
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
            next_x = max(
                0.0,
                min(
                    float(artboard["width"]) - float(row["width"]),
                    self._snap(doc.x()),
                ),
            )
            next_y = max(
                0.0,
                min(
                    float(artboard["height"]) - float(row["height"]),
                    self._snap(doc.y()),
                ),
            )
            original_primary = self._move_original_positions.get(
                row["id"],
                (float(row["x"]), float(row["y"])),
            )
            delta_x = next_x - original_primary[0]
            delta_y = next_y - original_primary[1]
            for moving_row in self._document["objects"]:
                original = self._move_original_positions.get(moving_row["id"])
                if original is None:
                    continue
                moving_row["x"] = max(
                    0.0,
                    min(
                        float(artboard["width"]) - float(moving_row["width"]),
                        original[0] + delta_x,
                    ),
                )
                moving_row["y"] = max(
                    0.0,
                    min(
                        float(artboard["height"]) - float(moving_row["height"]),
                        original[1] + delta_y,
                    ),
                )
            self.update()
            event.accept()
            return
        if self._interaction == "resize":
            rect = QRectF(self._original_rect)
            row = next(
                row
                for row in self._document["objects"]
                if row["id"] == self._active_object_id
            )
            point = self._unrotated_point(
                event.position(),
                self._original_rect,
                float(row.get("rotation", 0.0)),
            )
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
                viewport, scale = self._artboard_viewport()
                row["x"] = self._snap(
                    (rect.x() - viewport.x()) / max(0.0001, scale)
                )
                row["y"] = self._snap(
                    (rect.y() - viewport.y()) / max(0.0001, scale)
                )
                row["width"] = max(
                    1.0,
                    self._snap(rect.width() / max(0.0001, scale)),
                )
                row["height"] = max(
                    1.0,
                    self._snap(rect.height() / max(0.0001, scale)),
                )
                self.update()
            event.accept()
            return
        if self._interaction == "rotate":
            row = next(
                row
                for row in self._document["objects"]
                if row["id"] == self._active_object_id
            )
            delta = event.position() - self._original_rect.center()
            angle = math.degrees(math.atan2(delta.y(), delta.x()))
            rotation = self._original_rotation + angle - self._rotation_start_angle
            if self._snap_enabled:
                rotation = round(rotation / 15.0) * 15.0
            row["rotation"] = ((rotation + 180.0) % 360.0) - 180.0
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
                viewport, scale = self._artboard_viewport()
                self.object_create_requested.emit(
                    self._tool,
                    self._snap(
                        (rect.x() - viewport.x()) / max(0.0001, scale)
                    ),
                    self._snap(
                        (rect.y() - viewport.y()) / max(0.0001, scale)
                    ),
                    max(1.0, self._snap(rect.width() / max(0.0001, scale))),
                    max(1.0, self._snap(rect.height() / max(0.0001, scale))),
                )
        elif interaction in {"move", "resize", "rotate"} and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                if interaction == "move" and len(self._move_original_positions) > 1:
                    self.objects_changes_requested.emit(
                        {
                            selected_id: {
                                "x": float(selected_row["x"]),
                                "y": float(selected_row["y"]),
                            }
                            for selected_id in self._move_original_positions
                            for selected_row in self._document["objects"]
                            if selected_row["id"] == selected_id
                        }
                    )
                elif interaction == "rotate":
                    self.object_changes_requested.emit(
                        object_id,
                        {"rotation": float(row["rotation"])},
                    )
                else:
                    self.object_geometry_requested.emit(
                        object_id,
                        float(row["x"]),
                        float(row["y"]),
                        float(row["width"]),
                        float(row["height"]),
                    )
        self._cancel_interaction()
        self._move_original_positions = {}
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
