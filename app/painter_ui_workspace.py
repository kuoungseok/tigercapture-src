"""Interactive canvas overlay for Painter's UI Design workspace."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Signal, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import QWidget

from app.painter_ui_constraints import (
    constrain_ui_size,
    reanchor_resize_rect,
    resolve_ui_constraints,
    ui_pivot_point,
)
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_image_renderer import draw_ui_image
from app.painter_ui_motion_bridge import resolved_ui_geometry
from app.painter_ui_style_renderer import (
    draw_ui_object_inner_shadows,
    draw_ui_object_shadow,
    draw_ui_background_blur,
    draw_ui_text_block,
    draw_ui_vector_paths,
    blur_ui_image,
    has_ui_vector_geometry,
    ui_blur_radius,
    ui_color,
    ui_fill_brush,
)


_CREATE_TOOLS = {
    "frame",
    "rectangle",
    "ellipse",
    "line",
    "polygon",
    "star",
    "arc",
    "path",
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
    guide_create_requested = Signal(str, float)
    guide_update_requested = Signal(str, float, float)
    guide_remove_requested = Signal(str, float)
    ruler_origin_requested = Signal(float, float)
    ruler_origin_reset_requested = Signal()
    view_changed = Signal(object)
    edit_scope_enter_requested = Signal(str)
    edit_scope_exit_requested = Signal()
    text_change_requested = Signal(str, str)
    text_edit_started = Signal(str)
    text_edit_finished = Signal(str, bool)
    vector_edit_changed = Signal(object)

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
        self._resize_original_geometries: dict[
            str,
            tuple[float, float, float, float],
        ] = {}
        self._original_rotation = 0.0
        self._rotation_start_angle = 0.0
        self._snap_enabled = False
        self._snap_size = 8.0
        self._view_scale: float | None = None
        self._view_offset = QPointF()
        self._resolved_geometry: dict[str, dict[str, float]] = {}
        self._motion_preview: dict[str, dict[str, Any]] = {}
        self._motion_actor_compositions: dict[str, Any] = {}
        self._motion_actor_time_ms = 0
        self._motion_actor_renderer = None
        self._motion_actor_frame_cache: dict[tuple[Any, ...], Any] = {}
        self._pan_start = QPointF()
        self._pan_origin = QPointF()
        self._space_pan_active = False
        self._marquee_mode = "replace"
        self._guide_x: float | None = None
        self._guide_y: float | None = None
        self._active_artboard_drag_id = ""
        self._artboard_drag_origin = QPointF()
        self._rulers_visible = True
        self._ruler_size = 20.0
        self._ruler_guide_preview: tuple[str, float] | None = None
        self._ruler_origin_preview: QPointF | None = None
        self._active_guide_position = 0.0
        self._edit_scope_id = ""
        self._text_editor = None
        self._text_edit_object_id = ""
        self._auto_layout_active_target = ""
        self._auto_layout_drag_original: dict[str, Any] | None = None
        self._vector_edit_object_id = ""
        self._vector_active_node_id = ""
        self._vector_active_handle = ""
        self._vector_active_segment_id = ""
        self._vector_original_content: dict[str, Any] | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        from app.painter_ui_themes import resolve_ui_theme_document

        self._effective_document = resolve_ui_theme_document(self._document)
        self._resolved_geometry = resolve_ui_constraints(
            self._effective_document,
            resolved_ui_geometry(self._effective_document),
        )
        if self._edit_scope_id not in {
            row["id"] for row in self._document["objects"]
        }:
            self._edit_scope_id = ""
        vector_row = next(
            (
                row
                for row in self._document["objects"]
                if row["id"] == self._vector_edit_object_id
            ),
            None,
        )
        if (
            vector_row is None
            or vector_row["kind"] != "path"
            or self._document["selection"]["object_id"]
            != self._vector_edit_object_id
        ):
            self._vector_edit_object_id = ""
            self._vector_active_node_id = ""
            self._vector_active_handle = ""
            self._vector_active_segment_id = ""
        if self._text_edit_object_id and not any(
            row["id"] == self._text_edit_object_id
            and row["kind"] == "text"
            for row in self._document["objects"]
        ):
            self._finish_text_edit(commit=False)
        else:
            self._position_text_editor()
        self.update()

    def begin_text_edit(
        self,
        object_id: str,
        *,
        cursor_position: QPointF | None = None,
    ) -> bool:
        target = str(object_id or "")
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == target and item["kind"] == "text"
            ),
            None,
        )
        if row is None or bool(row.get("locked", False)):
            return False
        if self._text_edit_object_id and self._text_edit_object_id != target:
            self._finish_text_edit(commit=True)
        if self._text_editor is None:
            from app.painter_ui_inline_text_editor import (
                PainterUIInlineTextEditor,
            )

            editor = PainterUIInlineTextEditor(self)
            editor.commit_requested.connect(
                lambda text: self._finish_text_edit(
                    commit=True,
                    text=text,
                )
            )
            editor.cancel_requested.connect(
                lambda: self._finish_text_edit(commit=False)
            )
            self._text_editor = editor
        editor = self._text_editor
        self._text_edit_object_id = target
        editor.reset_finish_state()
        editor.setPlainText(str((row.get("content") or {}).get("text") or ""))
        font = QFont(self.font())
        _viewport, scale = self._artboard_viewport(
            next(
                artboard
                for artboard in self._document["artboards"]
                if artboard["id"] == row["artboard_id"]
            )
        )
        font.setPixelSize(
            max(
                9,
                min(
                    144,
                    round(float(row["style"].get("font_size") or 16.0) * scale),
                ),
            )
        )
        font.setWeight(
            QFont.Weight(
                max(
                    int(QFont.Weight.Thin),
                    min(
                        int(QFont.Weight.Black),
                        int(row["style"].get("font_weight") or 400),
                    ),
                )
            )
        )
        from app.painter_ui_typography import apply_ui_font_axes

        apply_ui_font_axes(font, row["style"].get("font_axes"))
        editor.setFont(font)
        color = ui_color(
            row["style"].get("text_color")
            or row["style"].get("fill"),
            "#F2F5F9",
        ).name()
        editor.setStyleSheet(
            "QPlainTextEdit#PainterUIInlineTextEditor {"
            " background: rgba(12, 17, 24, 205);"
            f" color: {color};"
            " border: 1px solid #6FA0F5;"
            " padding: 2px;"
            " selection-background-color: #376DB8;"
            "}"
        )
        self._position_text_editor()
        editor.show()
        editor.raise_()
        editor.setFocus(Qt.FocusReason.MouseFocusReason)
        if cursor_position is None:
            editor.selectAll()
        else:
            local = editor.mapFrom(
                self,
                cursor_position.toPoint(),
            )
            editor.setTextCursor(editor.cursorForPosition(local))
        self.text_edit_started.emit(target)
        self.update()
        return True

    def _position_text_editor(self) -> None:
        editor = self._text_editor
        target = self._text_edit_object_id
        if editor is None or not target:
            return
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == target
            ),
            None,
        )
        if row is None:
            return
        rect = self._object_rect(row).adjusted(-2.0, -2.0, 2.0, 2.0)
        rect.setWidth(max(80.0, rect.width()))
        rect.setHeight(max(32.0, rect.height()))
        editor.setGeometry(rect.toAlignedRect())

    def _finish_text_edit(
        self,
        *,
        commit: bool,
        text: str | None = None,
    ) -> None:
        editor = self._text_editor
        target = self._text_edit_object_id
        if editor is None or not target:
            return
        value = editor.toPlainText() if text is None else str(text)
        original = next(
            (
                str((row.get("content") or {}).get("text") or "")
                for row in self._document["objects"]
                if row["id"] == target
            ),
            "",
        )
        self._text_edit_object_id = ""
        editor.hide()
        editor.reset_finish_state()
        if commit and value != original:
            self.text_change_requested.emit(target, value)
        self.text_edit_finished.emit(target, bool(commit))
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.update()

    def is_text_editing(self) -> bool:
        return bool(self._text_edit_object_id)

    def set_edit_scope(self, object_id: str = "") -> str:
        target = str(object_id or "")
        if target:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == target
                ),
                None,
            )
            if row is None or row["kind"] not in {"frame", "group"}:
                target = ""
        self._edit_scope_id = target
        self.update()
        return target

    def edit_scope_id(self) -> str:
        return str(self._edit_scope_id)

    def _edit_scope_object_ids(self) -> set[str]:
        if not self._edit_scope_id:
            return set()
        result = {self._edit_scope_id}
        changed = True
        while changed:
            before = len(result)
            result.update(
                str(row["id"])
                for row in self._document["objects"]
                if str(row.get("parent_id") or "") in result
            )
            changed = len(result) != before
        return result

    def _row_in_edit_scope(self, row: Mapping[str, Any]) -> bool:
        if not self._edit_scope_id:
            return True
        return str(row["id"]) in self._edit_scope_object_ids()

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
        painter.save()
        painter.setClipRect(viewport)
        for grid in layout["layout_grids"]:
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
            elif mode in {"columns", "rows"}:
                count = int(grid["count"])
                margin = float(grid["margin"]) * scale
                gutter = float(grid["gutter"]) * scale
                extent = viewport.width() if mode == "columns" else viewport.height()
                if grid["alignment"] == "center":
                    cell_size = float(grid["size"]) * scale
                    band = cell_size * count + gutter * max(0, count - 1)
                    start = (extent - band) * 0.5
                else:
                    available = extent - margin * 2.0 - gutter * max(0, count - 1)
                    cell_size = available / count if count > 0 else 0.0
                    start = margin
                if cell_size > 0.0:
                    fill = QColor(color)
                    fill.setAlpha(max(18, min(72, fill.alpha())))
                    painter.setPen(QPen(line_color, 1.0))
                    painter.setBrush(fill)
                    position = start
                    for _index in range(count):
                        if mode == "columns":
                            rect = QRectF(
                                viewport.left() + position,
                                viewport.top(),
                                cell_size,
                                viewport.height(),
                            )
                        else:
                            rect = QRectF(
                                viewport.left(),
                                viewport.top() + position,
                                viewport.width(),
                                cell_size,
                            )
                        painter.drawRect(rect)
                        position += cell_size + gutter
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

    def set_motion_preview(
        self,
        states: Mapping[str, Mapping[str, Any]] | None,
    ) -> None:
        self._motion_preview = {
            str(object_id): dict(state)
            for object_id, state in (states or {}).items()
            if isinstance(state, Mapping)
        }
        self.update()

    def set_motion_actor_sources(
        self,
        compositions: Mapping[str, Any] | None,
    ) -> None:
        self._motion_actor_compositions = dict(compositions or {})
        self._motion_actor_frame_cache.clear()
        self.update()

    def set_motion_actor_time(self, time_ms: int) -> None:
        self._motion_actor_time_ms = max(0, int(time_ms))
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

    def set_rulers_visible(self, visible: bool) -> None:
        self._rulers_visible = bool(visible)
        self.update()

    def rulers_visible(self) -> bool:
        return self._rulers_visible

    @staticmethod
    def _ruler_step(scale: float) -> float:
        target_world = 72.0 / max(0.0001, float(scale))
        exponent = math.floor(math.log10(max(0.0001, target_world)))
        unit = 10.0 ** exponent
        for multiplier in (1.0, 2.0, 5.0, 10.0):
            step = multiplier * unit
            if step >= target_world:
                return step
        return 10.0 * unit

    def _paint_rulers(self, painter: QPainter) -> None:
        if not self._rulers_visible:
            return
        size = self._ruler_size
        viewport, scale = self._artboard_viewport()
        painter.save()
        painter.fillRect(QRectF(0.0, 0.0, self.width(), size), QColor("#20242A"))
        painter.fillRect(QRectF(0.0, 0.0, size, self.height()), QColor("#20242A"))
        painter.fillRect(QRectF(0.0, 0.0, size, size), QColor("#171B21"))
        painter.setPen(QPen(QColor("#3A424D"), 1.0))
        painter.drawLine(QPointF(size, 0.0), QPointF(size, self.height()))
        painter.drawLine(QPointF(0.0, size), QPointF(self.width(), size))

        step = self._ruler_step(scale)
        minor = step / 5.0
        from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

        artboard = self._active_artboard()
        origin = normalize_ui_artboard_layout(
            artboard,
            width=float(artboard["width"]),
            height=float(artboard["height"]),
        )["guides"]["origin"]
        left_world = (size - viewport.left()) / max(0.0001, scale)
        right_world = (self.width() - viewport.left()) / max(0.0001, scale)
        top_world = (size - viewport.top()) / max(0.0001, scale)
        bottom_world = (self.height() - viewport.top()) / max(0.0001, scale)
        painter.setFont(self.font())
        painter.setPen(QColor("#AEB8C5"))

        painter.save()
        painter.setClipRect(
            QRectF(size, 0.0, max(0.0, self.width() - size), size)
        )
        first_x = math.floor(left_world / minor) * minor
        x = first_x
        guard = 0
        while x <= right_world and guard < 2000:
            screen_x = viewport.left() + x * scale
            major = abs((x / step) - round(x / step)) < 0.001
            tick = 8.0 if major else 4.0
            painter.drawLine(
                QPointF(screen_x, size),
                QPointF(screen_x, size - tick),
            )
            if major and screen_x >= size + 18.0:
                painter.drawText(
                    QPointF(screen_x + 2.0, 10.0),
                    str(int(round(x - float(origin["x"])))),
                )
            x += minor
            guard += 1
        painter.restore()

        painter.save()
        painter.setClipRect(
            QRectF(0.0, size, size, max(0.0, self.height() - size))
        )
        first_y = math.floor(top_world / minor) * minor
        y = first_y
        guard = 0
        while y <= bottom_world and guard < 2000:
            screen_y = viewport.top() + y * scale
            major = abs((y / step) - round(y / step)) < 0.001
            tick = 8.0 if major else 4.0
            painter.drawLine(
                QPointF(size, screen_y),
                QPointF(size - tick, screen_y),
            )
            if major and screen_y >= size + 18.0:
                painter.save()
                painter.translate(9.0, screen_y - 2.0)
                painter.rotate(-90.0)
                painter.drawText(
                    QPointF(0.0, 0.0),
                    str(int(round(y - float(origin["y"])))),
                )
                painter.restore()
            y += minor
            guard += 1
        painter.restore()

    def _guide_at(self, position: QPointF) -> tuple[str, float] | None:
        from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

        artboard = self._active_artboard()
        layout = normalize_ui_artboard_layout(
            artboard,
            width=float(artboard["width"]),
            height=float(artboard["height"]),
        )
        guides = layout["guides"]
        if not guides["visible"] or guides["locked"]:
            return None
        viewport, scale = self._artboard_viewport(artboard)
        tolerance = 5.0
        candidates: list[tuple[float, str, float]] = []
        if viewport.top() <= position.y() <= viewport.bottom():
            for value in guides["vertical"]:
                distance = abs(
                    position.x() - (viewport.left() + float(value) * scale)
                )
                if distance <= tolerance:
                    candidates.append((distance, "vertical", float(value)))
        if viewport.left() <= position.x() <= viewport.right():
            for value in guides["horizontal"]:
                distance = abs(
                    position.y() - (viewport.top() + float(value) * scale)
                )
                if distance <= tolerance:
                    candidates.append((distance, "horizontal", float(value)))
        if not candidates:
            return None
        _distance, orientation, value = min(candidates, key=lambda item: item[0])
        return orientation, value

        if self._ruler_guide_preview is not None:
            orientation, position = self._ruler_guide_preview
            painter.setPen(QPen(QColor("#35B9FF"), 1.0))
            if orientation == "vertical":
                painter.drawLine(
                    QPointF(position, size),
                    QPointF(position, self.height()),
                )
            else:
                painter.drawLine(
                    QPointF(size, position),
                    QPointF(self.width(), position),
                )
        if self._ruler_origin_preview is not None:
            painter.setPen(QPen(QColor("#F1C66D"), 1.0))
            painter.drawLine(
                QPointF(self._ruler_origin_preview.x(), size),
                QPointF(self._ruler_origin_preview.x(), self.height()),
            )
            painter.drawLine(
                QPointF(size, self._ruler_origin_preview.y()),
                QPointF(self.width(), self._ruler_origin_preview.y()),
            )
        painter.restore()

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
        self._emit_view_changed()

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
        self._emit_view_changed()

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
        self._emit_view_changed()
        return True

    def fit_object(self, object_id: str) -> bool:
        target = str(object_id or "")
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == target
            ),
            None,
        )
        if row is None:
            return False
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        bounds = QRectF(
            float(artboard["x"]) + float(row["x"]),
            float(artboard["y"]) + float(row["y"]),
            float(row["width"]),
            float(row["height"]),
        )
        self._view_scale, self._view_offset = self._fit_transform(bounds)
        self.update()
        self._emit_view_changed()
        return True

    def fit_object(self, object_id: str) -> bool:
        target = str(object_id or "")
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == target
            ),
            None,
        )
        if row is None:
            return False
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        bounds = QRectF(
            float(artboard["x"]) + float(row["x"]),
            float(artboard["y"]) + float(row["y"]),
            float(row["width"]),
            float(row["height"]),
        )
        self._view_scale, self._view_offset = self._fit_transform(bounds)
        self.update()
        self._emit_view_changed()
        return True

    def set_zoom_percent(
        self,
        percent: float,
        *,
        anchor: QPointF | None = None,
    ) -> dict[str, Any]:
        old_scale, old_offset = self._view_transform()
        point = QPointF(anchor) if anchor is not None else QPointF(
            float(self.width()) * 0.5,
            float(self.height()) * 0.5,
        )
        world = QPointF(
            (point.x() - old_offset.x()) / max(0.0001, old_scale),
            (point.y() - old_offset.y()) / max(0.0001, old_scale),
        )
        self._view_scale = max(0.03, min(8.0, float(percent) / 100.0))
        self._view_offset = QPointF(
            point.x() - world.x() * self._view_scale,
            point.y() - world.y() * self._view_scale,
        )
        self.update()
        self._emit_view_changed()
        return self.view_state()

    def pan_view(
        self,
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        scale, offset = self._view_transform()
        self._view_scale = scale
        self._view_offset = QPointF(
            float(offset.x() + dx) if x is None else float(x),
            float(offset.y() + dy) if y is None else float(y),
        )
        self.update()
        self._emit_view_changed()
        return self.view_state()

    def _emit_view_changed(self) -> None:
        self._position_text_editor()
        self.view_changed.emit(self.view_state())

    def view_state(self) -> dict[str, Any]:
        scale, offset = self._view_transform()
        return {
            "scale": scale,
            "zoom_percent": round(scale * 100.0, 2),
            "offset_x": offset.x(),
            "offset_y": offset.y(),
        }

    def artboard_point_at(
        self,
        point: QPointF,
    ) -> tuple[str, QPointF] | None:
        """Map a viewport point to local coordinates on the top artboard."""
        candidates: list[tuple[dict[str, Any], QRectF, float]] = []
        for artboard in self._document["artboards"]:
            viewport, scale = self._artboard_viewport(artboard)
            if viewport.contains(point):
                candidates.append((artboard, viewport, scale))
        if not candidates:
            return None
        artboard, viewport, scale = candidates[-1]
        return (
            str(artboard["id"]),
            QPointF(
                (point.x() - viewport.x()) / max(0.0001, scale),
                (point.y() - viewport.y()) / max(0.0001, scale),
            ),
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
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        viewport, scale = self._artboard_viewport(artboard)
        geometry = self._resolved_geometry.get(str(row["id"]), row)
        x = float(geometry["x"])
        y = float(geometry["y"])
        width = float(geometry["width"])
        height = float(geometry["height"])
        preview = self._motion_preview.get(str(row["id"]))
        if preview is not None:
            preview_scale = list(preview.get("scale") or [1.0, 1.0])
            width *= float(preview_scale[0]) if preview_scale else 1.0
            height *= (
                float(preview_scale[1])
                if len(preview_scale) > 1
                else float(preview_scale[0]) if preview_scale else 1.0
            )
            position = list(
                preview.get("position")
                or [x + width * 0.5, y + height * 0.5]
            )
            center_x = float(position[0]) if position else x + width * 0.5
            center_y = (
                float(position[1])
                if len(position) > 1
                else y + height * 0.5
            )
            x = center_x - width * 0.5
            y = center_y - height * 0.5
        return QRectF(
            viewport.x() + x * scale,
            viewport.y() + y * scale,
            width * scale,
            height * scale,
        )

    def object_ids_at(self, x: float, y: float) -> list[str]:
        position = QPointF(float(x), float(y))
        hits: list[str] = []
        scope_ids = self._edit_scope_object_ids()
        for row in self._visible_objects(reverse=True):
            if scope_ids and str(row["id"]) not in scope_ids:
                continue
            if not self._point_visible_in_parent_clips(row, position):
                continue
            if not self._point_visible_in_object_mask(row, position):
                continue
            rect = self._object_rect(row)
            local_position = self._unrotated_point(
                position,
                rect,
                float(row.get("rotation", 0.0)),
                row.get("constraints"),
            )
            if rect.contains(local_position):
                hits.append(str(row["id"]))
        return hits

    def _display_rotation(self, row: Mapping[str, Any]) -> float:
        preview = self._motion_preview.get(str(row["id"]))
        if preview is not None:
            return float(preview.get("rotation", row.get("rotation", 0.0)))
        return float(row.get("rotation", 0.0))

    def _display_opacity(self, row: Mapping[str, Any]) -> float:
        preview = self._motion_preview.get(str(row["id"]))
        if preview is not None:
            return max(0.0, min(1.0, float(preview.get("opacity", 1.0))))
        return max(0.0, min(1.0, float(row.get("opacity", 1.0))))

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

    def _vector_control_positions(
        self,
        row: Mapping[str, Any],
    ) -> tuple[dict[str, QPointF], dict[tuple[str, str], QPointF]]:
        network = (row.get("content") or {}).get("vector_network")
        if not isinstance(network, Mapping):
            return {}, {}
        from app.painter_ui_vector_network import normalize_vector_network

        rect = self._object_rect(row)

        def screen_point(value: Mapping[str, Any]) -> QPointF:
            return QPointF(
                rect.left() + float(value.get("x") or 0.0) * rect.width(),
                rect.top() + float(value.get("y") or 0.0) * rect.height(),
            )

        normalized = normalize_vector_network(network)
        nodes = {
            str(node["id"]): screen_point(node)
            for node in normalized["nodes"]
        }
        handles: dict[tuple[str, str], QPointF] = {}
        for node in normalized["nodes"]:
            node_id = str(node["id"])
            for key in ("in_handle", "out_handle"):
                value = node.get(key)
                if isinstance(value, Mapping):
                    handles[(node_id, key)] = screen_point(value)
        return nodes, handles

    def _vector_control_at(
        self,
        row: Mapping[str, Any],
        position: QPointF,
    ) -> tuple[str, str]:
        nodes, handles = self._vector_control_positions(row)
        for (node_id, handle), point in handles.items():
            if math.hypot(position.x() - point.x(), position.y() - point.y()) <= 8.0:
                return node_id, handle
        for node_id, point in nodes.items():
            if math.hypot(position.x() - point.x(), position.y() - point.y()) <= 8.0:
                return node_id, "node"
        return "", ""

    def _vector_segment_at(
        self,
        row: Mapping[str, Any],
        position: QPointF,
    ) -> str:
        from app.painter_ui_vector_network import normalize_vector_network

        network = normalize_vector_network(
            (row.get("content") or {}).get("vector_network")
        )
        nodes, handles = self._vector_control_positions(row)

        def distance_to_line(point: QPointF, start: QPointF, end: QPointF) -> float:
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length_sq = dx * dx + dy * dy
            if length_sq <= 0.0001:
                return math.hypot(point.x() - start.x(), point.y() - start.y())
            amount = max(
                0.0,
                min(
                    1.0,
                    (
                        (point.x() - start.x()) * dx
                        + (point.y() - start.y()) * dy
                    )
                    / length_sq,
                ),
            )
            closest = QPointF(start.x() + dx * amount, start.y() + dy * amount)
            return math.hypot(point.x() - closest.x(), point.y() - closest.y())

        best: tuple[float, str] | None = None
        for segment in network["segments"]:
            start_id = segment["start_node_id"]
            end_id = segment["end_node_id"]
            start = nodes.get(start_id)
            end = nodes.get(end_id)
            if start is None or end is None:
                continue
            points = [start]
            if segment["kind"] == "cubic":
                control_a = handles.get((start_id, "out_handle"), start)
                control_b = handles.get((end_id, "in_handle"), end)
                for index in range(1, 25):
                    t = index / 24.0
                    inv = 1.0 - t
                    points.append(
                        QPointF(
                            inv**3 * start.x()
                            + 3 * inv * inv * t * control_a.x()
                            + 3 * inv * t * t * control_b.x()
                            + t**3 * end.x(),
                            inv**3 * start.y()
                            + 3 * inv * inv * t * control_a.y()
                            + 3 * inv * t * t * control_b.y()
                            + t**3 * end.y(),
                        )
                    )
            else:
                points.append(end)
            distance = min(
                distance_to_line(position, first, second)
                for first, second in zip(points, points[1:])
            )
            if distance <= 8.0 and (best is None or distance < best[0]):
                best = (distance, str(segment["id"]))
        return best[1] if best is not None else ""

    def _vector_normalized_point(
        self,
        row: Mapping[str, Any],
        position: QPointF,
    ) -> dict[str, float]:
        rect = self._object_rect(row)
        return {
            "x": (position.x() - rect.left()) / max(0.0001, rect.width()),
            "y": (position.y() - rect.top()) / max(0.0001, rect.height()),
        }

    def _paint_vector_controls(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        nodes, handles = self._vector_control_positions(row)
        if not nodes:
            return
        painter.save()
        if self._vector_active_segment_id:
            from app.painter_ui_vector_network import normalize_vector_network

            network = normalize_vector_network(
                (row.get("content") or {}).get("vector_network")
            )
            segment = next(
                (
                    item
                    for item in network["segments"]
                    if item["id"] == self._vector_active_segment_id
                ),
                None,
            )
            if segment is not None:
                start = nodes.get(segment["start_node_id"])
                end = nodes.get(segment["end_node_id"])
                if start is not None and end is not None:
                    highlight = QPainterPath(start)
                    if segment["kind"] == "cubic":
                        highlight.cubicTo(
                            handles.get(
                                (segment["start_node_id"], "out_handle"),
                                start,
                            ),
                            handles.get(
                                (segment["end_node_id"], "in_handle"),
                                end,
                            ),
                            end,
                        )
                    else:
                        highlight.lineTo(end)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#FFD166"), 2.2))
                    painter.drawPath(highlight)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#73A7F5"), 1.0))
        for (node_id, _handle), point in handles.items():
            origin = nodes.get(node_id)
            if origin is not None:
                painter.drawLine(origin, point)
        for (node_id, handle), point in handles.items():
            painter.setBrush(
                QColor("#FFD166")
                if node_id == self._vector_active_node_id
                and handle == self._vector_active_handle
                else QColor("#E9EEF7")
            )
            painter.setPen(QPen(QColor("#315F9F"), 1.0))
            painter.drawEllipse(point, 3.5, 3.5)
        for node_id, point in nodes.items():
            active = node_id == self._vector_active_node_id
            painter.setBrush(QColor("#FFD166") if active else QColor("#F5F8FD"))
            painter.setPen(QPen(QColor("#2B67BC"), 1.2))
            painter.drawRect(QRectF(point.x() - 4.5, point.y() - 4.5, 9.0, 9.0))
        painter.restore()

    def _vector_edit_state(
        self,
        row: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = row or next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == self._vector_edit_object_id
            ),
            None,
        )
        if target is None or target["kind"] != "path":
            return {}
        from app.painter_ui_vector_network import normalize_vector_network

        network = normalize_vector_network(
            (target.get("content") or {}).get("vector_network")
        )
        segment = next(
            (
                item
                for item in network["segments"]
                if item["id"] == self._vector_active_segment_id
            ),
            None,
        )
        if segment is None:
            segment = next(
                (
                    item
                    for item in network["segments"]
                    if item["start_node_id"] == self._vector_active_node_id
                    or item["end_node_id"] == self._vector_active_node_id
                ),
                None,
            )
        return {
            "object_id": str(target["id"]),
            "node_id": str(self._vector_active_node_id),
            "handle": str(self._vector_active_handle),
            "segment_id": str(segment["id"]) if segment is not None else "",
            "segment_kind": (
                str(segment["kind"]) if segment is not None else ""
            ),
            "node_count": len(network["nodes"]),
            "segment_count": len(network["segments"]),
            "closed": bool(network["closed"]),
            "stroke_width": float(
                (target.get("style") or {}).get("stroke_width") or 0.0
            ),
        }

    def exit_vector_edit(self) -> None:
        self._vector_edit_object_id = ""
        self._vector_active_node_id = ""
        self._vector_active_handle = ""
        self._vector_active_segment_id = ""
        self.vector_edit_changed.emit({})
        self.update()

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
        row = (
            None
            if self._interaction == "resize_multi"
            else next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == self._active_object_id
                ),
                None,
            )
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

    def _selected_rows(self) -> list[dict[str, Any]]:
        selected_ids = set(self._document["selection"]["object_ids"])
        return [
            row
            for row in self._document["objects"]
            if row["id"] in selected_ids and row["visible"]
        ]

    def _auto_layout_canvas_controls(self):
        if self._tool != "select":
            return None
        from app.painter_ui_auto_layout_overlay import (
            build_auto_layout_canvas_controls,
        )

        row = self._selected_row()
        if row is None or len(self._selected_rows()) != 1:
            return None
        _viewport, scale = self._artboard_viewport(
            next(
                artboard
                for artboard in self._document["artboards"]
                if artboard["id"] == row["artboard_id"]
            )
        )
        return build_auto_layout_canvas_controls(
            row,
            self._object_rect(row),
            self._document,
            QRectF(self.rect()),
            scale=scale,
        )

    def _preview_auto_layout(
        self,
        object_id: str,
        layout: Mapping[str, Any],
    ) -> None:
        from app.painter_ui_auto_layout import normalize_ui_auto_layout

        normalized = normalize_ui_auto_layout(layout)
        for document in (self._document, self._effective_document):
            row = next(
                (
                    item
                    for item in document["objects"]
                    if item["id"] == object_id
                ),
                None,
            )
            if row is not None:
                row["layout"] = copy.deepcopy(normalized)
        self._resolved_geometry = resolve_ui_constraints(
            self._effective_document,
            resolved_ui_geometry(self._effective_document),
        )
        self.update()

    def _multi_transform_rows(self) -> list[dict[str, Any]]:
        rows = self._selected_rows()
        if (
            len(rows) < 2
            or any(bool(row["locked"]) for row in rows)
            or len({str(row["artboard_id"]) for row in rows}) != 1
        ):
            return []
        return rows

    def _selection_bounds(
        self,
        rows: list[Mapping[str, Any]] | None = None,
    ) -> QRectF:
        targets = list(rows if rows is not None else self._selected_rows())
        bounds = QRectF()
        for row in targets:
            rect = self._object_rect(row)
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    def _visible_objects(self, *, reverse: bool = False) -> list[dict[str, Any]]:
        boolean_operands = self._boolean_operand_ids()
        return sorted(
            (
                row
                for row in self._effective_document["objects"]
                if row["visible"] and row["id"] not in boolean_operands
            ),
            key=lambda row: row["z_index"],
            reverse=reverse,
        )

    def _boolean_operand_ids(self) -> set[str]:
        result: set[str] = set()
        for row in self._effective_document["objects"]:
            boolean = (row.get("content") or {}).get("boolean")
            if not isinstance(boolean, Mapping) or not boolean.get("enabled"):
                continue
            result.update(str(item) for item in boolean.get("operand_ids", []))
        return result

    def _clipping_ancestors(
        self,
        row: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        objects = {
            item["id"]: item for item in self._effective_document["objects"]
        }
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        parent_id = str(row.get("parent_id") or "")
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            parent = objects.get(parent_id)
            if parent is None:
                break
            if parent["kind"] == "frame" and bool(
                parent.get("clip_content", False)
            ):
                result.append(parent)
            parent_id = str(parent.get("parent_id") or "")
        result.reverse()
        return result

    def _clip_path(self, row: Mapping[str, Any]) -> QPainterPath:
        rect = self._object_rect(row)
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        _viewport, scale = self._artboard_viewport(artboard)
        radius = max(
            0.0,
            float((row.get("style") or {}).get("radius") or 0.0) * scale,
        )
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        rotation = self._display_rotation(row)
        if abs(rotation) >= 0.001:
            pivot = ui_pivot_point(rect, row.get("constraints"))
            transform = QTransform()
            transform.translate(pivot.x(), pivot.y())
            transform.rotate(rotation)
            transform.translate(-pivot.x(), -pivot.y())
            path = transform.map(path)
        return path

    def _apply_parent_clips(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        for parent in self._clipping_ancestors(row):
            painter.setClipPath(
                self._clip_path(parent),
                Qt.ClipOperation.IntersectClip,
            )

    def _point_visible_in_parent_clips(
        self,
        row: Mapping[str, Any],
        point: QPointF,
    ) -> bool:
        return all(
            self._clip_path(parent).contains(point)
            for parent in self._clipping_ancestors(row)
        )

    def _paint_clip_indicator(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> None:
        if row["kind"] != "frame" or not bool(row.get("clip_content", False)):
            return
        size = max(8.0, min(16.0, min(rect.width(), rect.height()) * 0.08))
        corner = rect.topRight() + QPointF(-5.0, 5.0)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#F2B84B"), 2.0))
        painter.drawLine(
            QPointF(corner.x() - size, corner.y()),
            corner,
        )
        painter.drawLine(
            corner,
            QPointF(corner.x(), corner.y() + size),
        )
        painter.setPen(
            QPen(QColor("#F2B84B"), 1.0, Qt.PenStyle.DashLine)
        )
        painter.drawRoundedRect(
            rect.adjusted(3.0, 3.0, -3.0, -3.0),
            2.0,
            2.0,
        )
        painter.restore()

    def _object_shape_path(self, row: Mapping[str, Any]) -> QPainterPath:
        rect = self._object_rect(row)
        path = QPainterPath()
        if row["kind"] == "ellipse":
            path.addEllipse(rect)
            return path
        from app.painter_ui_parametric_shapes import (
            PARAMETRIC_SHAPE_KINDS,
            parametric_shape_path,
        )

        if row["kind"] in PARAMETRIC_SHAPE_KINDS:
            return parametric_shape_path(
                rect,
                str(row["kind"]),
                row.get("content"),
            )
        style = row.get("style") or {}
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        _viewport, scale = self._artboard_viewport(artboard)
        radii = style.get("corner_radii")
        radii = radii if isinstance(radii, Mapping) else {}
        fallback = max(0.0, float(style.get("radius") or 0.0))
        tl = max(0.0, float(radii.get("top_left", fallback) or 0.0) * scale)
        tr = max(0.0, float(radii.get("top_right", fallback) or 0.0) * scale)
        br = max(0.0, float(radii.get("bottom_right", fallback) or 0.0) * scale)
        bl = max(0.0, float(radii.get("bottom_left", fallback) or 0.0) * scale)
        maximum = min(rect.width(), rect.height()) * 0.5
        tl, tr, br, bl = (min(maximum, item) for item in (tl, tr, br, bl))
        path.moveTo(rect.left() + tl, rect.top())
        path.lineTo(rect.right() - tr, rect.top())
        path.quadTo(rect.topRight(), QPointF(rect.right(), rect.top() + tr))
        path.lineTo(rect.right(), rect.bottom() - br)
        path.quadTo(rect.bottomRight(), QPointF(rect.right() - br, rect.bottom()))
        path.lineTo(rect.left() + bl, rect.bottom())
        path.quadTo(rect.bottomLeft(), QPointF(rect.left(), rect.bottom() - bl))
        path.lineTo(rect.left(), rect.top() + tl)
        path.quadTo(rect.topLeft(), QPointF(rect.left() + tl, rect.top()))
        path.closeSubpath()
        return path

    def _mask_source_for_target(
        self,
        target_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for row in self._effective_document["objects"]:
            mask = row.get("mask")
            if (
                isinstance(mask, Mapping)
                and mask.get("enabled")
                and str(target_id) in {
                    str(item) for item in mask.get("target_ids", [])
                }
            ):
                return row, dict(mask)
        return None

    def _apply_object_mask(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        source = self._mask_source_for_target(str(row["id"]))
        if source is None:
            return
        mask_row, mask = source
        path = self._object_shape_path(mask_row)
        if mask.get("inverted"):
            artboard = next(
                item
                for item in self._document["artboards"]
                if item["id"] == row["artboard_id"]
            )
            viewport, _scale = self._artboard_viewport(artboard)
            outer = QPainterPath()
            outer.addRect(viewport)
            path = outer.subtracted(path)
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)

    def _point_visible_in_object_mask(
        self,
        row: Mapping[str, Any],
        point: QPointF,
    ) -> bool:
        source = self._mask_source_for_target(str(row["id"]))
        if source is None:
            return True
        mask_row, mask = source
        contains = self._object_shape_path(mask_row).contains(point)
        return not contains if mask.get("inverted") else contains

    def _paint_mask_indicator(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        mask = row.get("mask")
        if not isinstance(mask, Mapping) or not mask.get("enabled"):
            return
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#4ED6C3"), 2.0, Qt.PenStyle.DashLine))
        painter.drawPath(self._object_shape_path(row))
        painter.restore()

    def _boolean_path(self, row: Mapping[str, Any]) -> QPainterPath | None:
        boolean = (row.get("content") or {}).get("boolean")
        if not isinstance(boolean, Mapping) or not boolean.get("enabled"):
            return None
        by_id = {
            item["id"]: item for item in self._effective_document["objects"]
        }
        operands = [
            by_id[item]
            for item in boolean.get("operand_ids", [])
            if item in by_id
        ]
        if len(operands) < 2:
            return None
        result = self._object_shape_path(operands[0])
        operation = str(boolean.get("operation") or "union")
        for operand in operands[1:]:
            path = self._object_shape_path(operand)
            if operation == "subtract":
                result = result.subtracted(path)
            elif operation == "intersect":
                result = result.intersected(path)
            elif operation == "exclude":
                result = result.xored(path)
            else:
                result = result.united(path)
        return result

    @staticmethod
    def _composition_mode(blend_mode: object):
        return {
            "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
            "screen": QPainter.CompositionMode.CompositionMode_Screen,
            "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
            "darken": QPainter.CompositionMode.CompositionMode_Darken,
            "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
            "difference": QPainter.CompositionMode.CompositionMode_Difference,
            "exclusion": QPainter.CompositionMode.CompositionMode_Exclusion,
            "color_dodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
            "color_burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
            "hard_light": QPainter.CompositionMode.CompositionMode_HardLight,
            "soft_light": QPainter.CompositionMode.CompositionMode_SoftLight,
        }.get(
            str(blend_mode or "normal").casefold(),
            QPainter.CompositionMode.CompositionMode_SourceOver,
        )

    def _paint_object(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
        *,
        surface: QImage | None = None,
    ) -> None:
        rect = self._object_rect(row)
        style = row["style"]
        kind = str(row["kind"])
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        _viewport, scale = self._artboard_viewport(artboard)
        if surface is not None:
            draw_ui_background_blur(
                painter,
                surface,
                rect,
                kind,
                style,
                scale=scale,
            )
        radius = ui_blur_radius(style, "layer_blur", scale=scale)
        if radius <= 0.0 or kind == "group":
            self._paint_object_core(painter, row)
            return
        padding = max(2, int(math.ceil(radius * 3.0)))
        bounds = rect.adjusted(
            -padding,
            -padding,
            padding,
            padding,
        ).toAlignedRect()
        layer = QImage(
            max(1, bounds.width()),
            max(1, bounds.height()),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        layer.fill(Qt.GlobalColor.transparent)
        layer_painter = QPainter(layer)
        layer_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        layer_painter.translate(-bounds.left(), -bounds.top())
        self._paint_object_core(layer_painter, row)
        layer_painter.end()
        painter.drawImage(
            QPointF(float(bounds.left()), float(bounds.top())),
            blur_ui_image(layer, radius),
        )

    def _paint_object_core(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        rect = self._object_rect(row)
        style = row["style"]
        kind = str(row["kind"])
        if kind == "group":
            return
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, float(row["opacity"]))))
        painter.setCompositionMode(
            self._composition_mode(style.get("blend_mode"))
        )
        if kind == "motion_actor":
            image = self._motion_actor_frame(row, rect)
            if image is not None and not image.isNull():
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawImage(rect, image)
            else:
                painter.fillRect(rect, QColor("#151A22"))
                painter.setPen(QPen(QColor("#6FA0F5"), 1.0))
                painter.drawRect(rect)
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "Motion Actor",
                )
            painter.restore()
            return
        artboard = next(
            item
            for item in self._document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        _viewport, scale = self._artboard_viewport(artboard)
        content = row.get("content", {})
        if kind == "path" and not has_ui_vector_geometry(content):
            painter.restore()
            return
        draw_ui_object_shadow(painter, rect, kind, style, scale=scale)
        fill = ui_fill_brush(style, rect)
        stroke = ui_color(style.get("stroke"), "#93A3B8")
        painter.setPen(
            QPen(
                stroke,
                max(1.0, float(style.get("stroke_width") or 1.0) * scale),
            )
        )
        painter.setBrush(fill)

        boolean_path = self._boolean_path(row)
        if boolean_path is not None:
            painter.drawPath(boolean_path)
        elif kind == "ellipse":
            painter.drawEllipse(rect)
        elif kind == "line":
            painter.setPen(
                QPen(
                    fill,
                    max(1.5, float(style.get("stroke_width") or 2.0) * scale),
                )
            )
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        elif kind in {"polygon", "star", "arc"}:
            painter.drawPath(
                self._object_shape_path(row)
            )
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
                content = row.get("content", {})
                if isinstance(content, Mapping) and content.get("image_ref"):
                    painter.drawText(
                        rect.adjusted(6.0, 6.0, -6.0, -6.0),
                        Qt.AlignmentFlag.AlignCenter,
                        "Missing Figma image",
                    )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, radius, radius)
        elif kind == "path":
            draw_ui_vector_paths(painter, rect, content, style)
        else:
            radius = max(0.0, float(style.get("radius") or 0.0) * scale)
            painter.drawRoundedRect(rect, radius, radius)

        if kind != "image" and kind in {
            "button",
            "ellipse",
            "frame",
            "rectangle",
        } and str(content.get("source_path") or "").strip():
            painter.save()
            painter.setClipPath(self._object_shape_path(row))
            draw_ui_image(painter, rect, content)
            painter.restore()
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    stroke,
                    max(
                        1.0,
                        float(style.get("stroke_width") or 1.0) * scale,
                    ),
                )
            )
            painter.drawPath(self._object_shape_path(row))
            painter.restore()

        draw_ui_object_inner_shadows(
            painter,
            rect,
            kind,
            style,
            scale=scale,
        )
        label = str(row["content"].get("text") or "")
        if kind in {"text", "button"} and not label:
            label = str(row["name"])
        if (
            label
            and kind not in {"line", "image"}
            and str(row["id"]) != self._text_edit_object_id
        ):
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
                text_ranges=row["content"].get("text_ranges"),
            )
        painter.restore()

    def _motion_actor_frame(self, row: Mapping[str, Any], rect: QRectF):
        from app.motion_designer.schema import MotionComposition
        from app.painter_ui_motion_actor import motion_actor_composition_id

        composition_id = motion_actor_composition_id(row)
        value = self._motion_actor_compositions.get(composition_id)
        if isinstance(value, dict):
            value = MotionComposition.from_dict(value)
        if not isinstance(value, MotionComposition):
            return None
        content = row.get("content")
        content = content if isinstance(content, Mapping) else {}
        if bool(content.get("loop", True)):
            time_ms = self._motion_actor_time_ms % max(1, value.duration_ms)
        else:
            time_ms = min(self._motion_actor_time_ms, max(0, value.duration_ms - 1))
        frame_duration = 1000.0 / max(1.0, float(value.fps))
        frame_index = int(time_ms / frame_duration)
        width = max(32, min(960, int(round(rect.width()))))
        height = max(32, min(540, int(round(rect.height()))))
        key = (
            value.id,
            value.revision,
            frame_index,
            width,
            height,
        )
        cached = self._motion_actor_frame_cache.get(key)
        if cached is not None:
            return cached
        if self._motion_actor_renderer is None:
            from app.motion_designer.export_renderer import MotionExportRenderer

            self._motion_actor_renderer = MotionExportRenderer(cache_capacity=48)
        image = self._motion_actor_renderer.render_frame(
            value,
            frame_index * frame_duration,
            width=width,
            height=height,
        )
        self._motion_actor_frame_cache[key] = image
        if len(self._motion_actor_frame_cache) > 72:
            oldest = next(iter(self._motion_actor_frame_cache))
            self._motion_actor_frame_cache.pop(oldest, None)
        return image

    def paintEvent(self, _event) -> None:
        surface = QImage(
            max(1, self.width()),
            max(1, self.height()),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        surface.fill(QColor("#3F4145"))
        scene_painter = QPainter(surface)
        scene_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        scene_painter.fillRect(self.rect(), QColor("#3F4145"))
        active_id = self._document["active_artboard_id"]
        for artboard in self._document["artboards"]:
            viewport, scale = self._artboard_viewport(artboard)
            scene_painter.fillRect(
                viewport,
                QColor(str(artboard.get("background") or "#FFFFFF")),
            )
            self._paint_artboard_layout(
                scene_painter,
                artboard,
                viewport,
                scale,
            )
            scene_painter.setBrush(Qt.BrushStyle.NoBrush)
            scene_painter.setPen(
                QPen(
                    QColor("#72A7FF")
                    if artboard["id"] == active_id
                    else QColor("#657184"),
                    2.0 if artboard["id"] == active_id else 1.0,
                )
            )
            scene_painter.drawRect(viewport)
            scene_painter.setPen(QColor("#B7C0CD"))
            scene_painter.drawText(
                QPointF(viewport.left(), viewport.top() - 7.0),
                str(artboard["name"]),
            )
        scale, offset = self._view_transform()
        for section in self._document.get("sections", []):
            section_rect = QRectF(
                offset.x() + float(section["x"]) * scale,
                offset.y() + float(section["y"]) * scale,
                float(section["width"]) * scale,
                float(section["height"]) * scale,
            )
            scene_painter.setBrush(Qt.BrushStyle.NoBrush)
            scene_painter.setPen(
                QPen(QColor("#8B93A7"), 1.0, Qt.PenStyle.DashLine)
            )
            scene_painter.drawRoundedRect(section_rect, 6.0, 6.0)
            scene_painter.setPen(QColor("#C3CAD6"))
            scene_painter.drawText(
                section_rect.topLeft() + QPointF(4.0, -5.0),
                str(section["name"]),
            )
        for row in self._visible_objects():
            scene_painter.save()
            self._apply_parent_clips(scene_painter, row)
            self._apply_object_mask(scene_painter, row)
            rect = self._object_rect(row)
            rotation = self._display_rotation(row)
            pivot = ui_pivot_point(rect, row.get("constraints"))
            if abs(rotation) >= 0.001:
                scene_painter.translate(pivot)
                scene_painter.rotate(rotation)
                scene_painter.translate(-pivot)
            display_row = dict(row)
            display_row["opacity"] = self._display_opacity(row)
            if not self._row_in_edit_scope(row):
                display_row["opacity"] *= 0.2
            self._paint_object(
                scene_painter,
                display_row,
                surface=surface,
            )
            scene_painter.restore()
        scene_painter.end()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawImage(0, 0, surface)
        if self._edit_scope_id:
            scope_row = next(
                (
                    row
                    for row in self._document["objects"]
                    if row["id"] == self._edit_scope_id
                ),
                None,
            )
            if scope_row is not None:
                painter.save()
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(
                    QPen(
                        QColor("#63B3ED"),
                        1.5,
                        Qt.PenStyle.DashLine,
                    )
                )
                painter.drawRect(self._object_rect(scope_row))
                painter.restore()
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
        selected_rows = self._selected_rows()
        multi_rows = self._multi_transform_rows()
        multi_bounds = (
            self._selection_bounds(selected_rows)
            if len(selected_rows) > 1
            else QRectF()
        )
        for row in self._visible_objects():
            if not self._row_in_edit_scope(row):
                continue
            is_selected = row["id"] in selected_ids
            if not is_selected:
                continue
            painter.save()
            rect = self._object_rect(row)
            rotation = self._display_rotation(row)
            pivot = ui_pivot_point(rect, row.get("constraints"))
            if abs(rotation) >= 0.001:
                painter.translate(pivot)
                painter.rotate(rotation)
                painter.translate(-pivot)
            is_selected = row["id"] in selected_ids
            if is_selected:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#72A7FF"), 2.0))
                painter.drawRect(rect)
                self._paint_clip_indicator(painter, row, rect)
                self._paint_mask_indicator(painter, row)
            if (
                len(selected_ids) == 1
                and row["id"] == selected
                and not row["locked"]
            ):
                if (
                    row["kind"] == "path"
                    and row["id"] == self._vector_edit_object_id
                ):
                    self._paint_vector_controls(painter, row)
                else:
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
        from app.painter_ui_auto_layout_overlay import (
            paint_auto_layout_canvas_controls,
        )

        paint_auto_layout_canvas_controls(
            painter,
            self._auto_layout_canvas_controls(),
            active_target=self._auto_layout_active_target,
        )
        if not multi_bounds.isNull():
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#72A7FF"), 2.0))
            painter.drawRect(multi_bounds)
            if multi_rows:
                painter.setBrush(QColor("#F4F7FC"))
                painter.setPen(QPen(QColor("#356FC7"), 1.0))
                for handle in self._handle_rects(multi_bounds).values():
                    painter.drawRect(handle)
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
        self._paint_rulers(painter)

    def _cancel_interaction(self) -> None:
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._preview_rect = QRectF()
        self._guide_x = None
        self._guide_y = None
        self._ruler_guide_preview = None
        self._ruler_origin_preview = None
        self._active_guide_position = 0.0
        self._auto_layout_active_target = ""
        self._auto_layout_drag_original = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if (
            self._text_edit_object_id
            and self._text_editor is not None
            and not self._text_editor.geometry().contains(
                event.position().toPoint()
            )
        ):
            self._finish_text_edit(commit=True)
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and self._space_pan_active
        ):
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
        if self._rulers_visible:
            if (
                event.position().x() <= self._ruler_size
                and event.position().y() <= self._ruler_size
            ):
                self._interaction = "ruler_origin"
                self._ruler_origin_preview = QPointF(event.position())
                self.setCursor(Qt.CursorShape.CrossCursor)
                event.accept()
                return
            if (
                event.position().y() <= self._ruler_size
                and event.position().x() > self._ruler_size
            ):
                self._interaction = "guide_horizontal"
                self._ruler_guide_preview = (
                    "horizontal",
                    float(event.position().y()),
                )
                self.setCursor(Qt.CursorShape.SplitVCursor)
                event.accept()
                return
            if (
                event.position().x() <= self._ruler_size
                and event.position().y() > self._ruler_size
            ):
                self._interaction = "guide_vertical"
                self._ruler_guide_preview = (
                    "vertical",
                    float(event.position().x()),
                )
                self.setCursor(Qt.CursorShape.SplitHCursor)
                event.accept()
                return

        guide = self._guide_at(event.position())
        if guide is not None:
            orientation, value = guide
            self._interaction = f"guide_move_{orientation}"
            self._active_guide_position = value
            screen_position = (
                float(event.position().y())
                if orientation == "horizontal"
                else float(event.position().x())
            )
            self._ruler_guide_preview = (orientation, screen_position)
            self.setCursor(
                Qt.CursorShape.SplitVCursor
                if orientation == "horizontal"
                else Qt.CursorShape.SplitHCursor
            )
            event.accept()
            return

        controls = self._auto_layout_canvas_controls()
        auto_layout_target = (
            controls.hit_test(QPointF(event.position()))
            if controls is not None
            else ""
        )
        if auto_layout_target:
            from app.painter_ui_auto_layout_overlay import (
                apply_auto_layout_canvas_click,
            )

            self._active_object_id = controls.object_id
            self._auto_layout_active_target = auto_layout_target
            self._auto_layout_drag_original = copy.deepcopy(controls.layout)
            if auto_layout_target == "gap" or auto_layout_target.startswith(
                "padding_"
            ):
                self._interaction = "auto_layout_drag"
                self.setCursor(
                    Qt.CursorShape.SizeHorCursor
                    if auto_layout_target in {
                        "gap",
                        "padding_left",
                        "padding_right",
                    }
                    else Qt.CursorShape.SizeVerCursor
                )
            else:
                layout = apply_auto_layout_canvas_click(
                    controls.layout,
                    auto_layout_target,
                )
                self._preview_auto_layout(controls.object_id, layout)
                self.object_changes_requested.emit(
                    controls.object_id,
                    {"layout": layout},
                )
                self._cancel_interaction()
            event.accept()
            return

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

        multi_rows = self._multi_transform_rows()
        multi_bounds = self._selection_bounds(multi_rows)
        if not multi_bounds.isNull():
            for name in _HANDLE_NAMES:
                if self._handle_rects(multi_bounds)[name].contains(
                    event.position()
                ):
                    self._interaction = "resize_multi"
                    self._active_object_id = str(
                        self._document["selection"]["object_id"]
                        or multi_rows[0]["id"]
                    )
                    self._active_handle = name
                    self._original_rect = QRectF(multi_bounds)
                    self._resize_original_geometries = {
                        str(row["id"]): (
                            float(row["x"]),
                            float(row["y"]),
                            float(row["width"]),
                            float(row["height"]),
                        )
                        for row in multi_rows
                    }
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
            if (
                selected_row["kind"] == "path"
                and selected_row["id"] == self._vector_edit_object_id
            ):
                node_id, handle = self._vector_control_at(
                    selected_row,
                    local_position,
                )
                if node_id:
                    self._interaction = (
                        "vector_node"
                        if handle == "node"
                        else "vector_handle"
                    )
                    self._active_object_id = str(selected_row["id"])
                    self._vector_active_node_id = node_id
                    self._vector_active_handle = handle
                    self._vector_active_segment_id = ""
                    self._vector_original_content = copy.deepcopy(
                        selected_row["content"]
                    )
                    self.vector_edit_changed.emit(
                        self._vector_edit_state(selected_row)
                    )
                    event.accept()
                    return
                segment_id = self._vector_segment_at(
                    selected_row,
                    local_position,
                )
                if segment_id:
                    self._vector_active_node_id = ""
                    self._vector_active_handle = ""
                    self._vector_active_segment_id = segment_id
                    self.vector_edit_changed.emit(
                        self._vector_edit_state(selected_row)
                    )
                    self.update()
                    event.accept()
                    return
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

        hit_ids = self.object_ids_at(
            float(event.position().x()),
            float(event.position().y()),
        )
        selected = hit_ids[0] if hit_ids else ""
        if (
            hit_ids
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            current = str(self._document["selection"]["object_id"] or "")
            selected = (
                hit_ids[(hit_ids.index(current) + 1) % len(hit_ids)]
                if current in hit_ids
                else hit_ids[0]
            )
        selected_row = next(
            (
                row
                for row in self._document["objects"]
                if row["id"] == selected
            ),
            None,
        )
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
        if self._interaction == "ruler_origin":
            self._ruler_origin_preview = QPointF(event.position())
            self.update()
            event.accept()
            return
        if self._interaction in {
            "guide_horizontal",
            "guide_vertical",
            "guide_move_horizontal",
            "guide_move_vertical",
        }:
            orientation = (
                "horizontal"
                if self._interaction in {
                    "guide_horizontal",
                    "guide_move_horizontal",
                }
                else "vertical"
            )
            position = (
                float(event.position().y())
                if orientation == "horizontal"
                else float(event.position().x())
            )
            self._ruler_guide_preview = (orientation, position)
            self.update()
            event.accept()
            return
        if (
            self._interaction == "auto_layout_drag"
            and self._auto_layout_drag_original is not None
        ):
            from app.painter_ui_auto_layout_overlay import (
                apply_auto_layout_canvas_drag,
            )

            _viewport, scale = self._artboard_viewport()
            layout = apply_auto_layout_canvas_drag(
                self._auto_layout_drag_original,
                self._auto_layout_active_target,
                event.position() - self._press_position,
                scale=scale,
            )
            self._preview_auto_layout(self._active_object_id, layout)
            event.accept()
            return
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
        if self._interaction in {"vector_node", "vector_handle"}:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == self._active_object_id
                ),
                None,
            )
            if row is not None:
                rect = self._object_rect(row)
                local_position = self._unrotated_point(
                    event.position(),
                    rect,
                    float(row.get("rotation", 0.0)),
                    row.get("constraints"),
                )
                point = self._vector_normalized_point(row, local_position)
                from app.painter_ui_vector_network import (
                    normalize_vector_content,
                    update_vector_node,
                )

                content = copy.deepcopy(row["content"])
                changes = (
                    {"x": point["x"], "y": point["y"]}
                    if self._interaction == "vector_node"
                    else {self._vector_active_handle: point}
                )
                content["vector_network"] = update_vector_node(
                    content.get("vector_network"),
                    self._vector_active_node_id,
                    changes,
                )
                row["content"] = normalize_vector_content(content)
                self.update()
            event.accept()
            return
        if self._interaction == "pan":
            self._view_scale, _offset = self._view_transform()
            self._view_offset = self._pan_origin + (
                event.position() - self._pan_start
            )
            self.update()
            self._emit_view_changed()
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
        if self._interaction == "resize_multi":
            rect = self._resize_rect(
                QPointF(event.position()),
                event.modifiers(),
            )
            if rect.width() >= 8.0 and rect.height() >= 8.0:
                viewport, scale = self._artboard_viewport()
                original = self._original_rect
                old_x = (
                    original.x() - viewport.x()
                ) / max(0.0001, scale)
                old_y = (
                    original.y() - viewport.y()
                ) / max(0.0001, scale)
                old_width = original.width() / max(0.0001, scale)
                old_height = original.height() / max(0.0001, scale)
                new_x = (
                    rect.x() - viewport.x()
                ) / max(0.0001, scale)
                new_y = (
                    rect.y() - viewport.y()
                ) / max(0.0001, scale)
                new_width = rect.width() / max(0.0001, scale)
                new_height = rect.height() / max(0.0001, scale)
                scale_x = new_width / max(0.0001, old_width)
                scale_y = new_height / max(0.0001, old_height)
                by_id = {
                    str(row["id"]): row
                    for row in self._document["objects"]
                }
                for object_id, geometry in (
                    self._resize_original_geometries.items()
                ):
                    row = by_id.get(object_id)
                    if row is None:
                        continue
                    x, y, width, height = geometry
                    row["x"] = self._snap(
                        new_x + (x - old_x) * scale_x
                    )
                    row["y"] = self._snap(
                        new_y + (y - old_y) * scale_y
                    )
                    row["width"] = max(1.0, self._snap(width * scale_x))
                    row["height"] = max(1.0, self._snap(height * scale_y))
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
        controls = self._auto_layout_canvas_controls()
        target = (
            controls.hit_test(QPointF(event.position()))
            if controls is not None
            else ""
        )
        if target:
            from app.painter_ui_auto_layout_overlay import (
                auto_layout_canvas_tooltip,
            )

            self.setToolTip(auto_layout_canvas_tooltip(target))
            self.setCursor(
                Qt.CursorShape.SizeHorCursor
                if target in {"gap", "padding_left", "padding_right"}
                else Qt.CursorShape.SizeVerCursor
                if target in {"padding_top", "padding_bottom"}
                else Qt.CursorShape.PointingHandCursor
            )
            event.accept()
            return
        self.setToolTip("")
        if self._tool == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        interaction = self._interaction
        object_id = self._active_object_id
        if interaction in {"guide_horizontal", "guide_vertical"}:
            viewport, scale = self._artboard_viewport()
            orientation = (
                "horizontal"
                if interaction == "guide_horizontal"
                else "vertical"
            )
            screen_position = (
                float(event.position().y())
                if orientation == "horizontal"
                else float(event.position().x())
            )
            inside = (
                viewport.top() <= screen_position <= viewport.bottom()
                if orientation == "horizontal"
                else viewport.left() <= screen_position <= viewport.right()
            )
            if inside:
                origin = (
                    viewport.top()
                    if orientation == "horizontal"
                    else viewport.left()
                )
                self.guide_create_requested.emit(
                    orientation,
                    (screen_position - origin) / max(0.0001, scale),
                )
        elif interaction == "ruler_origin":
            viewport, scale = self._artboard_viewport()
            self.ruler_origin_requested.emit(
                (float(event.position().x()) - viewport.left())
                / max(0.0001, scale),
                (float(event.position().y()) - viewport.top())
                / max(0.0001, scale),
            )
        elif interaction in {
            "guide_move_horizontal",
            "guide_move_vertical",
        }:
            viewport, scale = self._artboard_viewport()
            orientation = (
                "horizontal"
                if interaction == "guide_move_horizontal"
                else "vertical"
            )
            screen_position = (
                float(event.position().y())
                if orientation == "horizontal"
                else float(event.position().x())
            )
            returned_to_ruler = (
                screen_position <= self._ruler_size
                if orientation == "horizontal"
                else screen_position <= self._ruler_size
            )
            if returned_to_ruler:
                self.guide_remove_requested.emit(
                    orientation,
                    self._active_guide_position,
                )
            else:
                origin = (
                    viewport.top()
                    if orientation == "horizontal"
                    else viewport.left()
                )
                maximum = (
                    float(self._active_artboard()["height"])
                    if orientation == "horizontal"
                    else float(self._active_artboard()["width"])
                )
                next_position = max(
                    0.0,
                    min(
                        maximum,
                        (screen_position - origin) / max(0.0001, scale),
                    ),
                )
                self.guide_update_requested.emit(
                    orientation,
                    self._active_guide_position,
                    next_position,
                )
        elif interaction in {"vector_node", "vector_handle"} and object_id:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == object_id
                ),
                None,
            )
            if row is not None:
                self.object_changes_requested.emit(
                    object_id,
                    {"content": copy.deepcopy(row["content"])},
                )
        elif interaction == "auto_layout_drag" and object_id:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == object_id
                ),
                None,
            )
            if row is not None:
                self.object_changes_requested.emit(
                    object_id,
                    {"layout": copy.deepcopy(row["layout"])},
                )
        elif interaction == "create":
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
        elif interaction == "resize_multi":
            self.objects_changes_requested.emit(
                {
                    object_id: {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "width": float(row["width"]),
                        "height": float(row["height"]),
                    }
                    for object_id in self._resize_original_geometries
                    for row in self._document["objects"]
                    if row["id"] == object_id
                }
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
        self._resize_original_geometries = {}
        self._vector_original_content = None
        if self._vector_edit_object_id:
            self.vector_edit_changed.emit(self._vector_edit_state())
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if (
            self._rulers_visible
            and event.button() == Qt.MouseButton.LeftButton
            and event.position().x() <= self._ruler_size
            and event.position().y() <= self._ruler_size
        ):
            self.ruler_origin_reset_requested.emit()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            hit_ids = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            selected = str(
                self._document["selection"]["object_id"] or ""
            )
            candidates = (
                [selected]
                if selected in hit_ids
                else []
            ) + [object_id for object_id in hit_ids if object_id != selected]
            text_target = next(
                (
                    object_id
                    for object_id in candidates
                    if next(
                        (
                            row["kind"]
                            for row in self._document["objects"]
                            if row["id"] == object_id
                        ),
                        "",
                    )
                    == "text"
                ),
                "",
            )
            if text_target and self.begin_text_edit(
                text_target,
                cursor_position=QPointF(event.position()),
            ):
                self.object_selection_requested.emit(text_target, "replace")
                event.accept()
                return
            path_target = next(
                (
                    object_id
                    for object_id in candidates
                    if next(
                        (
                            row["kind"]
                            for row in self._document["objects"]
                            if row["id"] == object_id
                        ),
                        "",
                    )
                    == "path"
                ),
                "",
            )
            if path_target:
                self._vector_edit_object_id = path_target
                self._vector_active_node_id = ""
                self._vector_active_handle = ""
                self._vector_active_segment_id = ""
                self.object_selection_requested.emit(path_target, "replace")
                self.vector_edit_changed.emit(self._vector_edit_state())
                self.update()
                event.accept()
                return
            parent_ids = {
                str(row.get("parent_id") or "")
                for row in self._document["objects"]
            }
            target = next(
                (
                    object_id
                    for object_id in candidates
                    if object_id in parent_ids
                    and next(
                        (
                            row["kind"]
                            for row in self._document["objects"]
                            if row["id"] == object_id
                        ),
                        "",
                    )
                    in {"frame", "group"}
                ),
                "",
            )
            if target:
                self.edit_scope_enter_requested.emit(target)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:
        pixel_delta = event.pixelDelta()
        angle_delta = event.angleDelta()
        delta_y = pixel_delta.y() if not pixel_delta.isNull() else angle_delta.y()
        if not delta_y and not pixel_delta.x():
            event.ignore()
            return
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            old_scale, _offset = self._view_transform()
            factor = (
                math.pow(1.0015, float(delta_y))
                if not pixel_delta.isNull()
                else 1.15 if delta_y > 0 else 1.0 / 1.15
            )
            self.set_zoom_percent(
                old_scale * factor * 100.0,
                anchor=QPointF(event.position()),
            )
        else:
            unit = 1.0 if not pixel_delta.isNull() else 0.5
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.pan_view(dx=float(delta_y) * unit)
            else:
                self.pan_view(
                    dx=float(pixel_delta.x()) if not pixel_delta.isNull() else 0.0,
                    dy=float(delta_y) * unit,
                )
        event.accept()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if key == Qt.Key.Key_Delete:
            if self._vector_edit_object_id and self._vector_active_node_id:
                row = next(
                    (
                        item
                        for item in self._document["objects"]
                        if item["id"] == self._vector_edit_object_id
                    ),
                    None,
                )
                if row is not None:
                    from app.painter_ui_vector_network import (
                        normalize_vector_content,
                        remove_vector_node,
                    )

                    content = copy.deepcopy(row["content"])
                    content["vector_network"] = remove_vector_node(
                        content.get("vector_network"),
                        self._vector_active_node_id,
                    )
                    self.object_changes_requested.emit(
                        row["id"],
                        {"content": normalize_vector_content(content)},
                    )
                self._vector_active_node_id = ""
                self._vector_active_handle = ""
                self._vector_active_segment_id = ""
                event.accept()
                return
            self.key_command.emit("delete", False)
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._vector_edit_object_id:
            self.exit_vector_edit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._edit_scope_id:
            self.edit_scope_exit_requested.emit()
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

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = False
            if self._interaction != "pan":
                self.setCursor(
                    Qt.CursorShape.CrossCursor
                    if self._tool in _CREATE_TOOLS
                    else Qt.CursorShape.ArrowCursor
                )
            event.accept()
            return
        super().keyReleaseEvent(event)


__all__ = ["PainterUIDesignOverlay"]
