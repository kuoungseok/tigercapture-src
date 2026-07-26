"""Interactive canvas overlay for Painter's UI Design workspace."""
from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import QWidget

from app.painter_ui_constraints import (
    constrain_ui_size,
    reanchor_resize_rect,
    resolve_ui_constraints,
    ui_pivot_point,
)
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_image_renderer import draw_ui_image
from app.painter_ui_style_renderer import (
    draw_ui_object_shadow,
    draw_ui_text_block,
    ui_color,
)


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
    artboard_activation_requested = Signal(str)
    artboard_geometry_requested = Signal(str, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._effective_document = self._document
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
        self._view_scale: float | None = None
        self._view_offset = QPointF()
        self._resolved_geometry: dict[str, dict[str, float]] = {}
        self._pan_start = QPointF()
        self._pan_origin = QPointF()
        self._marquee_mode = "replace"
        self._guide_x: float | None = None
        self._guide_y: float | None = None
        self._active_artboard_drag_id = ""
        self._artboard_drag_origin = QPointF()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        from app.painter_ui_responsive import resolve_ui_responsive_document

        self._effective_document = resolve_ui_responsive_document(self._document)
        self._resolved_geometry = resolve_ui_constraints(self._effective_document)
        self.update()

    @staticmethod
    def _paint_artboard_layout(
        painter: QPainter,
        artboard: Mapping[str, Any],
        viewport: QRectF,
        scale: float,
    ) -> None:
        from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

        layout = normalize_ui_artboard_layout(
            artboard,
            width=float(artboard["width"]),
            height=float(artboard["height"]),
        )
        grid = layout["layout_grid"]
        painter.save()
        painter.setClipRect(viewport)
        color = QColor(str(grid["color"]))
        line_color = QColor(color)
        line_color.setAlpha(max(48, line_color.alpha()))
        mode = grid["mode"] if grid["visible"] else "none"
        if mode == "grid":
            step = float(grid["size"]) * scale
            if step >= 3.0:
                painter.setPen(QPen(line_color, 1.0))
                x = viewport.left() + step
                while x < viewport.right() and x <= viewport.left() + step * 1024:
                    painter.drawLine(QPointF(x, viewport.top()), QPointF(x, viewport.bottom()))
                    x += step
                y = viewport.top() + step
                while y < viewport.bottom() and y <= viewport.top() + step * 1024:
                    painter.drawLine(QPointF(viewport.left(), y), QPointF(viewport.right(), y))
                    y += step
        elif mode == "columns":
            count = int(grid["count"])
            margin = float(grid["margin"]) * scale
            gutter = float(grid["gutter"]) * scale
            available = viewport.width() - margin * 2.0 - gutter * max(0, count - 1)
            column_width = available / count if count > 0 else 0.0
            if column_width > 0.0:
                fill = QColor(color)
                fill.setAlpha(max(18, min(72, fill.alpha())))
                painter.setPen(QPen(line_color, 1.0))
                painter.setBrush(fill)
                x = viewport.left() + margin
                for _index in range(count):
                    column = QRectF(x, viewport.top(), column_width, viewport.height())
                    painter.drawRect(column)
                    x += column_width + gutter
        guides = layout["guides"]
        if guides["visible"]:
            guide_pen = QPen(QColor("#35B9FFB8"), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for position in guides["vertical"]:
                x = viewport.left() + float(position) * scale
                painter.drawLine(QPointF(x, viewport.top()), QPointF(x, viewport.bottom()))
            for position in guides["horizontal"]:
                y = viewport.top() + float(position) * scale
                painter.drawLine(QPointF(viewport.left(), y), QPointF(viewport.right(), y))
        if layout["safe_area_visible"]:
            safe = layout["safe_area"]
            safe_rect = viewport.adjusted(
                float(safe["left"]) * scale,
                float(safe["top"]) * scale,
                -float(safe["right"]) * scale,
                -float(safe["bottom"]) * scale,
            )
            if safe_rect.width() > 0.0 and safe_rect.height() > 0.0:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(
                    QPen(QColor("#F4C96BB8"), 1.0, Qt.PenStyle.DashLine)
                )
                painter.drawRect(safe_rect)
        painter.restore()

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

    def _scene_bounds(self) -> QRectF:
        bounds = QRectF()
        for artboard in self._document["artboards"]:
            rect = QRectF(
                float(artboard["x"]),
                float(artboard["y"]),
                float(artboard["width"]),
                float(artboard["height"]),
            )
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    def _fit_transform(self, bounds: QRectF) -> tuple[float, QPointF]:
        available_width = max(1.0, float(self.width()) - 24.0)
        available_height = max(1.0, float(self.height()) - 24.0)
        scale = min(
            available_width / max(1.0, bounds.width()),
            available_height / max(1.0, bounds.height()),
        )
        offset = QPointF(
            float(self.width()) * 0.5 - bounds.center().x() * scale,
            float(self.height()) * 0.5 - bounds.center().y() * scale,
        )
        return scale, offset

    def _view_transform(self) -> tuple[float, QPointF]:
        if self._view_scale is None:
            return self._fit_transform(self._scene_bounds())
        return self._view_scale, QPointF(self._view_offset)

    def _artboard_viewport(
        self,
        artboard: Mapping[str, Any] | None = None,
    ) -> tuple[QRectF, float]:
        row = artboard or self._active_artboard()
        scale, offset = self._view_transform()
        return QRectF(
            offset.x() + float(row["x"]) * scale,
            offset.y() + float(row["y"]) * scale,
            float(row["width"]) * scale,
            float(row["height"]) * scale,
        ), scale

    def _artboard_title_rect(self, artboard: Mapping[str, Any]) -> QRectF:
        viewport, _scale = self._artboard_viewport(artboard)
        return QRectF(viewport.left(), viewport.top() - 22.0, viewport.width(), 22.0)

    def fit_all(self) -> None:
        self._view_scale, self._view_offset = self._fit_transform(
            self._scene_bounds()
        )
        self.update()

    def fit_artboard(self, artboard_id: str = "") -> None:
        target = str(artboard_id or self._document["active_artboard_id"])
        artboard = next(
            row for row in self._document["artboards"] if row["id"] == target
        )
        bounds = QRectF(
            float(artboard["x"]),
            float(artboard["y"]),
            float(artboard["width"]),
            float(artboard["height"]),
        )
        self._view_scale, self._view_offset = self._fit_transform(bounds)
        self.update()

    def fit_selection(self) -> bool:
        selected_ids = set(self._document["selection"]["object_ids"])
        rows = [
            row for row in self._document["objects"] if row["id"] in selected_ids
        ]
        if not rows:
            return False
        bounds = QRectF()
        artboards = {row["id"]: row for row in self._document["artboards"]}
        for row in rows:
            artboard = artboards[row["artboard_id"]]
            rect = QRectF(
                float(artboard["x"]) + float(row["x"]),
                float(artboard["y"]) + float(row["y"]),
                float(row["width"]),
                float(row["height"]),
            )
            bounds = rect if bounds.isNull() else bounds.united(rect)
        self._view_scale, self._view_offset = self._fit_transform(bounds)
        self.update()
        return True

    def view_state(self) -> dict[str, Any]:
        scale, offset = self._view_transform()
        return {
            "scale": scale,
            "zoom_percent": round(scale * 100.0, 2),
            "offset_x": offset.x(),
            "offset_y": offset.y(),
        }

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
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        viewport, scale = self._artboard_viewport(artboard)
        geometry = self._resolved_geometry.get(str(row["id"]), row)
        return QRectF(
            viewport.x() + float(geometry["x"]) * scale,
            viewport.y() + float(geometry["y"]) * scale,
            float(geometry["width"]) * scale,
            float(geometry["height"]) * scale,
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
    def _rotation_handle_rect(
        rect: QRectF,
        constraints: Mapping[str, Any] | None = None,
    ) -> QRectF:
        pivot = ui_pivot_point(rect, constraints)
        return QRectF(pivot.x() - 5.0, rect.top() - 25.0, 10.0, 10.0)

    @staticmethod
    def _unrotated_point(
        point: QPointF,
        rect: QRectF,
        angle: float,
        constraints: Mapping[str, Any] | None = None,
    ) -> QPointF:
        if abs(float(angle)) < 0.001:
            return QPointF(point)
        pivot = ui_pivot_point(rect, constraints)
        transform = QTransform()
        transform.translate(pivot.x(), pivot.y())
        transform.rotate(-float(angle))
        transform.translate(-pivot.x(), -pivot.y())
        return transform.map(point)

    def _snap(self, value: float) -> float:
        if not self._snap_enabled:
            return float(value)
        return round(float(value) / self._snap_size) * self._snap_size

    def _smart_snap_position(
        self,
        row: Mapping[str, Any],
        x: float,
        y: float,
    ) -> tuple[float, float]:
        self._guide_x = None
        self._guide_y = None
        if not self._snap_enabled:
            return x, y
        _viewport, scale = self._artboard_viewport()
        tolerance = 6.0 / max(0.0001, scale)
        width = float(row["width"])
        height = float(row["height"])
        moving_x = (x, x + width * 0.5, x + width)
        moving_y = (y, y + height * 0.5, y + height)
        excluded = set(self._move_original_positions)
        candidates_x: list[float] = []
        candidates_y: list[float] = []
        for other in self._document["objects"]:
            if (
                other["id"] in excluded
                or other["artboard_id"] != row["artboard_id"]
                or not other["visible"]
            ):
                continue
            ox = float(other["x"])
            oy = float(other["y"])
            ow = float(other["width"])
            oh = float(other["height"])
            candidates_x.extend((ox, ox + ow * 0.5, ox + ow))
            candidates_y.extend((oy, oy + oh * 0.5, oy + oh))
        best_x: tuple[float, float] | None = None
        best_y: tuple[float, float] | None = None
        for candidate in candidates_x:
            for anchor in moving_x:
                delta = candidate - anchor
                if abs(delta) <= tolerance and (
                    best_x is None or abs(delta) < abs(best_x[0])
                ):
                    best_x = (delta, candidate)
        for candidate in candidates_y:
            for anchor in moving_y:
                delta = candidate - anchor
                if abs(delta) <= tolerance and (
                    best_y is None or abs(delta) < abs(best_y[0])
                ):
                    best_y = (delta, candidate)
        viewport, scale = self._artboard_viewport()
        if best_x is not None:
            x += best_x[0]
            self._guide_x = viewport.left() + best_x[1] * scale
        if best_y is not None:
            y += best_y[0]
            self._guide_y = viewport.top() + best_y[1] * scale
        return x, y

    def _resize_rect(self, point: QPointF, modifiers) -> QRectF:
        original = QRectF(self._original_rect)
        center_based = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        force_ratio = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == self._active_object_id
            ),
            None,
        )
        constraints = row.get("constraints") if row is not None else None
        if center_based:
            center = original.center()
            half_width = abs(point.x() - center.x())
            half_height = abs(point.y() - center.y())
            raw = QRectF(
                center.x() - half_width,
                center.y() - half_height,
                half_width * 2.0,
                half_height * 2.0,
            )
        else:
            anchor = {
                "nw": original.bottomRight(),
                "ne": original.bottomLeft(),
                "sw": original.topRight(),
                "se": original.topLeft(),
            }[self._active_handle]
            raw = QRectF(anchor, point).normalized()
        _viewport, scale = self._artboard_viewport()
        width, height = constrain_ui_size(
            raw.width() / max(0.0001, scale),
            raw.height() / max(0.0001, scale),
            constraints,
            force_ratio=force_ratio,
            fallback_ratio=original.width() / max(0.0001, original.height()),
        )
        return reanchor_resize_rect(
            raw,
            original,
            self._active_handle,
            center_based=center_based,
            width=width * scale,
            height=height * scale,
        )

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
        return next(
            (row for row in self._document["objects"] if row["id"] == selected),
            None,
        )

    def _visible_objects(self, *, reverse: bool = False) -> list[dict[str, Any]]:
        return sorted(
            (
                row
                for row in self._effective_document["objects"]
                if row["visible"]
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
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, float(row["opacity"]))))
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        _viewport, scale = self._artboard_viewport(artboard)
        draw_ui_object_shadow(painter, rect, kind, style, scale=scale)
        fill = ui_color(style.get("fill"), "#506884")
        stroke = ui_color(style.get("stroke"), "#93A3B8")
        painter.setPen(
            QPen(
                stroke,
                max(1.0, float(style.get("stroke_width") or 1.0) * scale),
            )
        )
        painter.setBrush(fill)

        if kind == "ellipse":
            painter.drawEllipse(rect)
        elif kind == "line":
            painter.setPen(
                QPen(
                    fill,
                    max(1.5, float(style.get("stroke_width") or 2.0) * scale),
                )
            )
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        elif kind == "progress":
            painter.drawRoundedRect(rect, 3.0 * scale, 3.0 * scale)
            amount = max(0.0, min(1.0, float(row["content"].get("value", 0.64))))
            progress = QRectF(rect)
            progress.setWidth(rect.width() * amount)
            painter.fillRect(progress, ui_color(style.get("accent"), "#6FA0F5"))
        elif kind == "text":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(ui_color(style.get("text_color"), "#F2F5F9"))
        elif kind == "image":
            radius = max(0.0, float(style.get("radius") or 0.0) * scale)
            painter.drawRoundedRect(rect, radius, radius)
            if not draw_ui_image(painter, rect, row.get("content")):
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.topRight(), rect.bottomLeft())
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        else:
            radius = max(0.0, float(style.get("radius") or 0.0) * scale)
            painter.drawRoundedRect(rect, radius, radius)

        label = str(row["content"].get("text") or "")
        if kind in {"text", "button"} and not label:
            label = str(row["name"])
        if label and kind not in {"line", "image"}:
            text_style = style
            if kind == "text" and "shadow" in style and "text_shadow" not in style:
                text_style = {**style, "text_shadow": style["shadow"]}
            draw_ui_text_block(
                painter,
                rect,
                label,
                text_style,
                self.font(),
                scale=scale,
            )
        painter.restore()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(18, 21, 27, 86))
        active_id = self._document["active_artboard_id"]
        for artboard in self._document["artboards"]:
            viewport, scale = self._artboard_viewport(artboard)
            painter.fillRect(
                viewport,
                QColor(str(artboard.get("background") or "#FFFFFF")),
            )
            self._paint_artboard_layout(painter, artboard, viewport, scale)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    QColor("#72A7FF")
                    if artboard["id"] == active_id
                    else QColor("#657184"),
                    2.0 if artboard["id"] == active_id else 1.0,
                )
            )
            painter.drawRect(viewport)
            painter.setPen(QColor("#B7C0CD"))
            painter.drawText(
                QPointF(viewport.left(), viewport.top() - 7.0),
                str(artboard["name"]),
            )
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
        for row in self._visible_objects():
            painter.save()
            rect = self._object_rect(row)
            rotation = float(row.get("rotation", 0.0))
            pivot = ui_pivot_point(rect, row.get("constraints"))
            if abs(rotation) >= 0.001:
                painter.translate(pivot)
                painter.rotate(rotation)
                painter.translate(-pivot)
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
                rotate_handle = self._rotation_handle_rect(
                    rect,
                    row.get("constraints"),
                )
                painter.drawLine(
                    pivot,
                    QPointF(pivot.x(), rotate_handle.bottom()),
                )
                painter.setBrush(QColor("#F4F7FC"))
                painter.drawEllipse(rotate_handle)
                painter.setBrush(QColor("#72A7FF"))
                painter.drawEllipse(pivot, 3.0, 3.0)
            painter.restore()

        if self._interaction == "create" and not self._preview_rect.isNull():
            painter.setBrush(QColor(80, 130, 210, 48))
            painter.setPen(QPen(QColor("#79AFFF"), 1.5, Qt.PenStyle.DashLine))
            painter.drawRect(self._preview_rect.normalized())
        elif self._interaction == "marquee" and not self._preview_rect.isNull():
            painter.setBrush(QColor(71, 124, 210, 34))
            painter.setPen(QPen(QColor("#6FA0F5"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRect(self._preview_rect.normalized())
        if self._guide_x is not None or self._guide_y is not None:
            viewport, _scale = self._artboard_viewport()
            painter.setPen(QPen(QColor("#FF4FA3"), 1.0))
            if self._guide_x is not None:
                painter.drawLine(
                    QPointF(self._guide_x, viewport.top()),
                    QPointF(self._guide_x, viewport.bottom()),
                )
            if self._guide_y is not None:
                painter.drawLine(
                    QPointF(viewport.left(), self._guide_y),
                    QPointF(viewport.right(), self._guide_y),
                )

    def _cancel_interaction(self) -> None:
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._preview_rect = QRectF()
        self._guide_x = None
        self._guide_y = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._interaction = "pan"
            self._pan_start = QPointF(event.position())
            _scale, offset = self._view_transform()
            self._pan_origin = offset
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._press_position = QPointF(event.position())
        viewport, _scale = self._artboard_viewport()

        if self._tool == "select":
            for artboard in reversed(self._document["artboards"]):
                if self._artboard_title_rect(artboard).contains(event.position()):
                    if artboard["id"] != self._document["active_artboard_id"]:
                        self.artboard_activation_requested.emit(artboard["id"])
                    scale, offset = self._view_transform()
                    self._view_scale = scale
                    self._view_offset = offset
                    self._interaction = "artboard_move"
                    self._active_artboard_drag_id = str(artboard["id"])
                    self._artboard_drag_origin = QPointF(
                        float(artboard["x"]),
                        float(artboard["y"]),
                    )
                    self.setCursor(Qt.CursorShape.SizeAllCursor)
                    event.accept()
                    return

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
                selected_row.get("constraints"),
            )
            if self._rotation_handle_rect(
                selected_rect,
                selected_row.get("constraints"),
            ).contains(local_position):
                self._interaction = "rotate"
                self._active_object_id = selected_row["id"]
                self._original_rect = QRectF(selected_rect)
                self._original_rotation = float(selected_row.get("rotation", 0.0))
                delta = event.position() - ui_pivot_point(
                    selected_rect,
                    selected_row.get("constraints"),
                )
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
                row.get("constraints"),
            )
            if rect.contains(local_position):
                selected = row["id"]
                selected_row = row
                break
        if selected_row is None:
            for artboard in reversed(self._document["artboards"]):
                viewport, _scale = self._artboard_viewport(artboard)
                if viewport.contains(event.position()):
                    if artboard["id"] != self._document["active_artboard_id"]:
                        self.artboard_activation_requested.emit(artboard["id"])
                    break
        if selected_row is not None:
            target_artboard = str(selected_row["artboard_id"])
            if target_artboard != self._document["active_artboard_id"]:
                self.artboard_activation_requested.emit(target_artboard)
        modifiers = event.modifiers()
        if selected and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.object_selection_requested.emit(selected, "toggle")
            self._cancel_interaction()
            event.accept()
            return
        if selected and modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.object_selection_requested.emit(selected, "add")
            self._cancel_interaction()
            event.accept()
            return
        if not selected:
            self._interaction = "marquee"
            self._preview_rect = QRectF(
                self._press_position,
                self._press_position,
            )
            self._marquee_mode = (
                "toggle"
                if modifiers & Qt.KeyboardModifier.ControlModifier
                else "add"
                if modifiers & Qt.KeyboardModifier.ShiftModifier
                else "replace"
            )
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
        if self._interaction == "pan":
            self._view_scale, _offset = self._view_transform()
            self._view_offset = self._pan_origin + (
                event.position() - self._pan_start
            )
            self.update()
            event.accept()
            return
        if self._interaction == "marquee":
            self._preview_rect = QRectF(
                self._press_position,
                event.position(),
            ).normalized()
            self.update()
            event.accept()
            return
        if self._interaction == "artboard_move":
            artboard = next(
                row
                for row in self._document["artboards"]
                if row["id"] == self._active_artboard_drag_id
            )
            scale, _offset = self._view_transform()
            delta = event.position() - self._press_position
            artboard["x"] = self._snap(
                self._artboard_drag_origin.x()
                + delta.x() / max(0.0001, scale)
            )
            artboard["y"] = self._snap(
                self._artboard_drag_origin.y()
                + delta.y() / max(0.0001, scale)
            )
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
            next_x, next_y = self._smart_snap_position(
                row,
                next_x,
                next_y,
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
            row = next(
                row
                for row in self._document["objects"]
                if row["id"] == self._active_object_id
            )
            point = self._unrotated_point(
                event.position(),
                self._original_rect,
                float(row.get("rotation", 0.0)),
                row.get("constraints"),
            )
            rect = self._resize_rect(point, event.modifiers())
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
            delta = event.position() - ui_pivot_point(
                self._original_rect,
                row.get("constraints"),
            )
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
        elif interaction == "marquee":
            rect = self._preview_rect.normalized()
            active = self._document["active_artboard_id"]
            selected_ids = [
                row["id"]
                for row in self._visible_objects()
                if row["artboard_id"] == active
                and rect.intersects(self._object_rect(row))
            ] if rect.width() >= 3.0 and rect.height() >= 3.0 else []
            if self._marquee_mode == "replace":
                if selected_ids:
                    self.object_selection_requested.emit(selected_ids[0], "replace")
                    for selected_id in selected_ids[1:]:
                        self.object_selection_requested.emit(selected_id, "add")
                else:
                    self.object_selection_requested.emit("", "replace")
            else:
                for selected_id in selected_ids:
                    self.object_selection_requested.emit(
                        selected_id,
                        self._marquee_mode,
                    )
        elif interaction == "artboard_move" and self._active_artboard_drag_id:
            artboard = next(
                row
                for row in self._document["artboards"]
                if row["id"] == self._active_artboard_drag_id
            )
            self.artboard_geometry_requested.emit(
                self._active_artboard_drag_id,
                float(artboard["x"]),
                float(artboard["y"]),
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
        self._active_artboard_drag_id = ""
        if self._tool == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._move_original_positions = {}
        event.accept()

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if not delta:
            event.ignore()
            return
        old_scale, old_offset = self._view_transform()
        anchor = QPointF(event.position())
        world = QPointF(
            (anchor.x() - old_offset.x()) / max(0.0001, old_scale),
            (anchor.y() - old_offset.y()) / max(0.0001, old_scale),
        )
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self._view_scale = max(0.03, min(8.0, old_scale * factor))
        self._view_offset = QPointF(
            anchor.x() - world.x() * self._view_scale,
            anchor.y() - world.y() * self._view_scale,
        )
        self.update()
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
