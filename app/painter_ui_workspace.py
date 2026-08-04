"""Interactive canvas overlay for Painter's UI Design workspace."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Mapping

from PySide6.QtCore import QEvent, QPointF, QRectF, Signal, Qt
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
from app.painter_i18n import painter_text
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
    "section",
    "slice",
    "rectangle",
    "ellipse",
    "line",
    "arrow",
    "polygon",
    "star",
    "arc",
    "path",
    "pencil",
    "text",
    "image",
    "button",
    "progress",
}

_STICKY_SHAPE_TOOLS = {
    "rectangle",
    "ellipse",
    "line",
    "arrow",
    "polygon",
    "star",
    "arc",
}
_HANDLE_NAMES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")


def _document_render_fingerprint(document: Mapping[str, Any]) -> str:
    payload = dict(document)
    payload.pop("selection", None)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class PainterUIDesignOverlay(QWidget):
    object_selected = Signal(str)
    object_selection_requested = Signal(str, str)
    object_geometry_requested = Signal(str, float, float, float, float)
    object_changes_requested = Signal(str, object)
    objects_changes_requested = Signal(object)
    objects_scale_requested = Signal(object)
    objects_continuation_changes_requested = Signal(object)
    objects_duplicate_requested = Signal(object)
    object_create_requested = Signal(str, float, float, float, float)
    pencil_create_requested = Signal(object)
    section_create_requested = Signal(float, float, float, float)
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
    image_focal_requested = Signal(str, float, float)
    objects_move_reparent_requested = Signal(object, str, object)
    auto_layout_reorder_requested = Signal(str, int)
    prototype_connection_requested = Signal(str, str, str)
    prototype_trigger_requested = Signal(str, str, str)
    comment_placement_requested = Signal(object)
    comment_selected = Signal(str)
    comment_move_requested = Signal(str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._effective_document = self._document
        self._document_render_signature: tuple[Any, ...] | None = None
        self._effective_objects_by_id: dict[str, dict[str, Any]] = {}
        self._mask_source_by_target: dict[
            str,
            tuple[dict[str, Any], dict[str, Any]],
        ] = {}
        self._boolean_operand_id_cache: set[str] = set()
        self._boolean_path_cache: dict[str, QPainterPath | None] = {}
        self._tool = "select"
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._press_position = QPointF()
        self._original_rect = QRectF()
        self._preview_rect = QRectF()
        self._preview_line_end = QPointF()
        self._pencil_points: list[QPointF] = []
        self._drag_offset = QPointF()
        self._move_original_positions: dict[str, tuple[float, float]] = {}
        self._hierarchy_drop_preview_id = ""
        self._alt_duplicate_cycle_id = ""
        self._alt_duplicate_source_ids: list[str] = []
        self._alt_duplicate_drag_active = False
        self._resize_original_geometries: dict[
            str,
            tuple[float, float, float, float],
        ] = {}
        self._original_rotation = 0.0
        self._rotation_start_angle = 0.0
        self._rotation_label = ""
        self._rotation_original_values: dict[str, float] = {}
        self._radius_original = 0.0
        self._radius_preview = 0.0
        self._radius_active_corner = ""
        self._radius_hover_corner = ""
        self._arc_active_handle = ""
        self._arc_hover_handle = ""
        self._arc_label = ""
        self._arc_drag_last_angle = 0.0
        self._arc_drag_unwrapped_angle = 0.0
        self._arc_drag_direction = 0
        self._arc_original_content: dict[str, Any] = {}
        self._shape_gizmo_active = ""
        self._shape_gizmo_hover = ""
        self._shape_gizmo_label = ""
        self._shape_gizmo_original_content: dict[str, Any] = {}
        self._shape_gizmo_original_style: dict[str, Any] = {}
        self._shape_gizmo_original_geometry = (0.0, 0.0, 0.0, 0.0)
        self._snap_enabled = False
        self._object_snap_enabled = True
        self._pixel_grid_visible = False
        self._layout_guides_visible = True
        self._pixel_preview_enabled = False
        self._layer_outlines_visible = False
        self._outline_include_hidden = False
        self._outline_include_bounds = False
        self._empty_page_mode = False
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
        self._marquee_include_nested = False
        self._guide_x: float | None = None
        self._guide_y: float | None = None
        self._smart_guide_plan: dict[str, Any] = {}
        self._smart_selection_hovered = False
        self._smart_gap_axis = ""
        self._smart_gap_label = ""
        self._smart_gap_label_position = QPointF()
        self._smart_gap_original_gap = 0.0
        self._smart_gap_other_gap = 0.0
        self._smart_gap_original_document: dict[str, Any] | None = None
        self._smart_marked_ids: set[str] = set()
        self._smart_reorder_original_document: dict[str, Any] | None = None
        self._smart_reorder_axis = ""
        self._smart_reorder_target_index = -1
        self._smart_reorder_indicator = QRectF()
        self._smart_reorder_indicator_mode = ""
        self._auto_layout_reorder_context: dict[str, Any] = {}
        self._auto_layout_reorder_target_index = -1
        self._auto_layout_reorder_indicator = QRectF()
        self._smart_resize_original_document: dict[str, Any] | None = None
        self._measurements_visible = False
        self._active_artboard_drag_id = ""
        self._artboard_drag_origin = QPointF()
        self._rulers_visible = True
        self._artboard_labels_visible = True
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
        self._image_focal_edit_object_id = ""
        self._prototype_drag_position: QPointF | None = None
        self._prototype_hover_artboard_id = ""
        self._prototype_authoring_visible = False
        self._prototype_preview_enabled = False
        self._prototype_preview_state: dict[str, Any] = {}
        self._prototype_pressed_object_id = ""
        self._prototype_hover_object_id = ""
        self._layer_hover_object_id = ""
        self._prototype_focus_object_id = ""
        self._active_comment_id = ""
        self._comment_drag_position: QPointF | None = None
        self._comment_press_target: dict[str, Any] = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        document = normalize_ui_document(value)
        signature = (
            str(document.get("document_id") or ""),
            int(document.get("revision") or 0),
            str(document.get("active_page_id") or ""),
            str(document.get("active_artboard_id") or ""),
            len(document.get("objects") or []),
            len(document.get("artboards") or []),
            _document_render_fingerprint(document),
        )
        reuse_resolved = (
            signature == self._document_render_signature
            and bool(self._effective_objects_by_id)
        )
        self._document = document
        selected_ids = {
            str(value)
            for value in document["selection"]["object_ids"]
        }
        self._smart_marked_ids.intersection_update(selected_ids)
        if self._layer_hover_object_id and not any(
            str(row.get("id") or "") == self._layer_hover_object_id
            and bool(row.get("visible", True))
            for row in document.get("objects", [])
        ):
            self._layer_hover_object_id = ""
        if reuse_resolved:
            self._effective_document["selection"] = copy.deepcopy(
                document["selection"]
            )
        else:
            self._rebuild_effective_document()
            self._document_render_signature = signature
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

    def _rebuild_effective_document(self) -> None:
        from app.painter_ui_themes import resolve_ui_theme_document

        source = self._document
        if self._prototype_preview_enabled:
            from app.painter_ui_prototype import (
                resolve_ui_component_prototype_document,
            )

            source = resolve_ui_component_prototype_document(
                source,
                self._prototype_preview_state,
            )
        self._effective_document = resolve_ui_theme_document(
            source,
            normalize=False,
        )
        self._resolved_geometry = resolve_ui_constraints(
            self._effective_document,
            resolved_ui_geometry(
                self._effective_document,
                normalize=False,
                resolve_responsive=False,
            ),
        )
        self._rebuild_document_indexes()
        self._boolean_path_cache.clear()

    def set_empty_page_mode(self, enabled: bool) -> None:
        """Hide the internal root artboard for a Figma-style empty page."""
        self._empty_page_mode = bool(enabled)
        self.update()

    def _rebuild_document_indexes(self) -> None:
        objects = list(self._effective_document.get("objects") or [])
        self._effective_objects_by_id = {
            str(row["id"]): row for row in objects
        }
        self._mask_source_by_target = {}
        for row in objects:
            mask = row.get("mask")
            if not isinstance(mask, dict) or not mask.get("enabled"):
                continue
            normalized_mask = dict(mask)
            for target_id in mask.get("target_ids", []):
                key = str(target_id or "")
                if key and key not in self._mask_source_by_target:
                    self._mask_source_by_target[key] = (
                        row,
                        normalized_mask,
                    )
        from app.painter_ui_boolean_geometry import boolean_operand_ids

        self._boolean_operand_id_cache = boolean_operand_ids(objects)

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
            editor.textChanged.connect(self._resize_text_editor_to_content)
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

    def _resize_text_editor_to_content(self) -> None:
        editor = self._text_editor
        target = self._text_edit_object_id
        if editor is None or not target:
            return
        row = next(
            (item for item in self._document["objects"] if item["id"] == target),
            None,
        )
        if row is None:
            return
        from app.painter_ui_text_layout import (
            normalize_text_resize_mode,
            text_content_geometry,
        )

        mode = normalize_text_resize_mode(
            (row.get("content") or {}).get("text_resize")
        )
        width, height = text_content_geometry(
            editor.toPlainText(),
            row.get("style"),
            mode=mode,
            width=float(row.get("width") or 1.0),
            height=float(row.get("height") or 1.0),
        )
        _viewport, scale = self._artboard_viewport(
            next(
                artboard
                for artboard in self._document["artboards"]
                if artboard["id"] == row["artboard_id"]
            )
        )
        geometry = editor.geometry()
        if mode == "auto_width":
            geometry.setWidth(max(80, round(width * scale) + 6))
        if mode in {"auto_width", "auto_height"}:
            geometry.setHeight(max(32, round(height * scale) + 6))
        editor.setGeometry(geometry)

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
            from app.painter_ui_boolean import is_ui_boolean_group

            if row is None or (
                row["kind"] not in {"frame", "group"}
                and not is_ui_boolean_group(row)
            ):
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
        *,
        layout_guides_visible: bool = True,
        pixel_grid_visible: bool = False,
    ) -> None:
        from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

        layout = normalize_ui_artboard_layout(
            artboard,
            width=float(artboard["width"]),
            height=float(artboard["height"]),
        )
        painter.save()
        painter.setClipRect(viewport)
        for grid in layout["layout_grids"] if layout_guides_visible else []:
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
        if pixel_grid_visible and scale >= 8.0:
            pixel_pen = QPen(QColor("#8994A344"), 1.0)
            painter.setPen(pixel_pen)
            x = viewport.left() + scale
            while x < viewport.right():
                painter.drawLine(QPointF(x, viewport.top()), QPointF(x, viewport.bottom()))
                x += scale
            y = viewport.top() + scale
            while y < viewport.bottom():
                painter.drawLine(QPointF(viewport.left(), y), QPointF(viewport.right(), y))
                y += scale
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

    def set_view_options(
        self,
        *,
        pixel_grid: bool | None = None,
        layout_guides: bool | None = None,
        pixel_preview: bool | None = None,
        layer_outlines: bool | None = None,
        outline_include_hidden: bool | None = None,
        outline_include_bounds: bool | None = None,
    ) -> None:
        if pixel_grid is not None:
            self._pixel_grid_visible = bool(pixel_grid)
        if layout_guides is not None:
            self._layout_guides_visible = bool(layout_guides)
        if pixel_preview is not None:
            self._pixel_preview_enabled = bool(pixel_preview)
        if layer_outlines is not None:
            self._layer_outlines_visible = bool(layer_outlines)
        if outline_include_hidden is not None:
            self._outline_include_hidden = bool(outline_include_hidden)
        if outline_include_bounds is not None:
            self._outline_include_bounds = bool(outline_include_bounds)
        self.update()

    def set_motion_preview(
        self,
        states: Mapping[str, Mapping[str, Any]] | None,
    ) -> None:
        self._motion_preview = {
            str(object_id): dict(state)
            for object_id, state in (states or {}).items()
            if isinstance(state, Mapping)
        }
        self._boolean_path_cache.clear()
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

    def set_image_focal_edit(self, object_id: str, enabled: bool) -> None:
        target = str(object_id or "") if enabled else ""
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == target
            ),
            None,
        )
        content = (row or {}).get("content") or {}
        self._image_focal_edit_object_id = (
            target
            if row is not None
            and str(content.get("source_path") or "")
            and str(content.get("image_fit") or "fit") == "fill"
            else ""
        )
        self.update()

    def image_focal_edit_object_id(self) -> str:
        return self._image_focal_edit_object_id

    def set_tool(self, tool: str) -> str:
        requested = str(tool or "select").strip().casefold()
        self._tool = (
            requested
            if requested in _CREATE_TOOLS or requested in {"scale", "pan", "comment"}
            else "select"
        )
        self._cancel_interaction()
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if self._tool == "pan"
            else (
                Qt.CursorShape.CrossCursor
                if self._tool in _CREATE_TOOLS or self._tool == "comment"
                else Qt.CursorShape.ArrowCursor
            )
        )
        return self._tool

    def tool(self) -> str:
        return self._tool

    def set_snap(self, enabled: bool, size: float = 8.0) -> None:
        self._snap_enabled = bool(enabled)
        self._snap_size = max(1.0, float(size))

    def set_object_snap(self, enabled: bool) -> None:
        self._object_snap_enabled = bool(enabled)
        if not self._object_snap_enabled:
            self._guide_x = None
            self._guide_y = None
            self._smart_guide_plan = {}
            self.update()

    def object_snap_enabled(self) -> bool:
        return self._object_snap_enabled

    def snap_enabled(self) -> bool:
        return self._snap_enabled

    def set_rulers_visible(self, visible: bool) -> None:
        self._rulers_visible = bool(visible)
        self.update()

    def set_artboard_labels_visible(self, visible: bool) -> None:
        self._artboard_labels_visible = bool(visible)
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

        selected_frame_rect = self._selected_frame_ruler_rect()
        if selected_frame_rect is not None:
            highlight = QColor("#2488D8")
            highlight.setAlpha(72)
            painter.fillRect(
                QRectF(
                    selected_frame_rect.left(),
                    0.0,
                    selected_frame_rect.width(),
                    size,
                ),
                highlight,
            )
            painter.fillRect(
                QRectF(
                    0.0,
                    selected_frame_rect.top(),
                    size,
                    selected_frame_rect.height(),
                ),
                highlight,
            )
            painter.setPen(QPen(QColor("#35A5FF"), 1.0))
            for x_value in (
                selected_frame_rect.left(),
                selected_frame_rect.right(),
            ):
                painter.drawLine(
                    QPointF(x_value, 0.0),
                    QPointF(x_value, size),
                )
            for y_value in (
                selected_frame_rect.top(),
                selected_frame_rect.bottom(),
            ):
                painter.drawLine(
                    QPointF(0.0, y_value),
                    QPointF(size, y_value),
                )

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

    def _selected_frame_ruler_rect(self) -> QRectF | None:
        selected_id = str(
            self._document.get("selection", {}).get("object_id") or ""
        )
        if not selected_id:
            return None
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == selected_id
                and str(item.get("kind") or "") == "frame"
            ),
            None,
        )
        return self._object_rect(row) if row is not None else None

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

    def _clamped_view_offset(
        self,
        scale: float,
        offset: QPointF,
    ) -> QPointF:
        bounds = self._scene_bounds()
        if bounds.isEmpty() or self.width() <= 0 or self.height() <= 0:
            return QPointF(offset)
        visible_edge = max(
            24.0,
            min(96.0, min(float(self.width()), float(self.height())) * 0.16),
        )
        minimum_x = visible_edge - bounds.right() * scale
        maximum_x = (
            float(self.width()) - visible_edge - bounds.left() * scale
        )
        minimum_y = visible_edge - bounds.bottom() * scale
        maximum_y = (
            float(self.height()) - visible_edge - bounds.top() * scale
        )
        return QPointF(
            max(minimum_x, min(maximum_x, float(offset.x()))),
            max(minimum_y, min(maximum_y, float(offset.y()))),
        )

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
        self._view_offset = self._clamped_view_offset(
            self._view_scale,
            QPointF(
                point.x() - world.x() * self._view_scale,
                point.y() - world.y() * self._view_scale,
            ),
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
        self._view_offset = self._clamped_view_offset(
            scale,
            QPointF(
                float(offset.x() + dx) if x is None else float(x),
                float(offset.y() + dy) if y is None else float(y),
            ),
        )
        self.update()
        self._emit_view_changed()
        return self.view_state()

    def set_view_state(
        self,
        value: Mapping[str, Any] | None,
        *,
        emit: bool = True,
    ) -> dict[str, Any]:
        state = value if isinstance(value, Mapping) else {}
        def _view_number(key: str, default: float) -> float:
            try:
                return float(state.get(key, default) or default)
            except (TypeError, ValueError):
                return float(default)

        percent = state.get("zoom_percent")
        if percent is None:
            percent = _view_number("scale", 1.0) * 100.0
        try:
            percent = float(percent)
        except (TypeError, ValueError):
            percent = 100.0
        scale = max(0.03, min(8.0, percent / 100.0))
        if "center_x" in state or "center_y" in state:
            center_x = _view_number("center_x", 0.0)
            center_y = _view_number("center_y", 0.0)
            offset = QPointF(
                float(self.width()) * 0.5 - center_x * scale,
                float(self.height()) * 0.5 - center_y * scale,
            )
        else:
            offset = QPointF(
                _view_number("offset_x", 0.0),
                _view_number("offset_y", 0.0),
            )
        self._view_scale = scale
        self._view_offset = self._clamped_view_offset(scale, offset)
        self.update()
        if emit:
            self._emit_view_changed()
        return self.view_state()

    def _emit_view_changed(self) -> None:
        self._position_text_editor()
        self.view_changed.emit(self.view_state())

    def view_state(self) -> dict[str, Any]:
        scale, offset = self._view_transform()
        center_x = (float(self.width()) * 0.5 - offset.x()) / max(
            0.0001,
            scale,
        )
        center_y = (float(self.height()) * 0.5 - offset.y()) / max(
            0.0001,
            scale,
        )
        return {
            "scale": scale,
            "zoom_percent": round(scale * 100.0, 2),
            "offset_x": offset.x(),
            "offset_y": offset.y(),
            "center_x": center_x,
            "center_y": center_y,
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

    def _review_comments(self) -> list[dict[str, Any]]:
        linked = self._document.get("linked_targets") or {}
        review = linked.get("review") if isinstance(linked, Mapping) else {}
        comments = review.get("comments") if isinstance(review, Mapping) else []
        return [dict(row) for row in comments or [] if isinstance(row, Mapping)]

    def _comment_position(self, comment: Mapping[str, Any]) -> QPointF | None:
        anchor = comment.get("anchor") or {}
        ax = max(0.0, min(1.0, float(anchor.get("x", 0.5))))
        ay = max(0.0, min(1.0, float(anchor.get("y", 0.5))))
        object_id = str(comment.get("object_id") or "")
        if object_id:
            row = next(
                (item for item in self._document["objects"] if item["id"] == object_id),
                None,
            )
            if row is None:
                return None
            rect = self._object_rect(row)
        else:
            artboard_id = str(comment.get("artboard_id") or "")
            artboard = next(
                (item for item in self._document["artboards"] if item["id"] == artboard_id),
                None,
            )
            if artboard is None:
                return None
            rect, _scale = self._artboard_viewport(artboard)
        return QPointF(rect.left() + rect.width() * ax, rect.top() + rect.height() * ay)

    def _comment_target_rect(self, comment: Mapping[str, Any]) -> QRectF | None:
        object_id = str(comment.get("object_id") or "")
        if object_id:
            row = next(
                (item for item in self._document["objects"] if item["id"] == object_id),
                None,
            )
            return self._object_rect(row) if row is not None else None
        artboard_id = str(comment.get("artboard_id") or "")
        artboard = next(
            (item for item in self._document["artboards"] if item["id"] == artboard_id),
            None,
        )
        return self._artboard_viewport(artboard)[0] if artboard is not None else None

    def _comment_region_rect(self, comment: Mapping[str, Any]) -> QRectF:
        region = comment.get("region")
        target = self._comment_target_rect(comment)
        if not isinstance(region, Mapping) or target is None:
            return QRectF()
        return QRectF(
            target.left() + float(region.get("x", 0.0)) * target.width(),
            target.top() + float(region.get("y", 0.0)) * target.height(),
            float(region.get("width", 0.0)) * target.width(),
            float(region.get("height", 0.0)) * target.height(),
        ).normalized()

    def _comment_placement(self, point: QPointF, area: QRectF | None = None) -> dict[str, Any] | None:
        artboard_point = self.artboard_point_at(point)
        if artboard_point is None:
            return None
        artboard_id, local_point = artboard_point
        object_ids = self.object_ids_at(float(point.x()), float(point.y()))
        object_id = str(object_ids[0] if object_ids else "")
        if object_id:
            row = next(item for item in self._document["objects"] if item["id"] == object_id)
            target_rect = self._object_rect(row)
        else:
            artboard = next(item for item in self._document["artboards"] if item["id"] == artboard_id)
            target_rect = self._artboard_viewport(artboard)[0]
        x = (point.x() - target_rect.left()) / max(1.0, target_rect.width())
        y = (point.y() - target_rect.top()) / max(1.0, target_rect.height())
        payload: dict[str, Any] = {
            "object_id": object_id,
            "artboard_id": artboard_id,
            "x": max(0.0, min(1.0, float(x))),
            "y": max(0.0, min(1.0, float(y))),
            "screen_x": float(point.x()),
            "screen_y": float(point.y()),
        }
        normalized = (area or QRectF()).normalized()
        if normalized.width() >= 4.0 and normalized.height() >= 4.0:
            left = (normalized.left() - target_rect.left()) / max(1.0, target_rect.width())
            top = (normalized.top() - target_rect.top()) / max(1.0, target_rect.height())
            right = (normalized.right() - target_rect.left()) / max(1.0, target_rect.width())
            bottom = (normalized.bottom() - target_rect.top()) / max(1.0, target_rect.height())
            payload["region"] = {
                "x": max(0.0, min(1.0, left)),
                "y": max(0.0, min(1.0, top)),
                "width": max(0.0, min(1.0, right) - max(0.0, min(1.0, left))),
                "height": max(0.0, min(1.0, bottom) - max(0.0, min(1.0, top))),
            }
            payload["x"] = payload["region"]["x"]
            payload["y"] = payload["region"]["y"]
        return payload

    def _comment_at(self, point: QPointF) -> dict[str, Any] | None:
        for comment in reversed(self._review_comments()):
            position = self._comment_position(comment)
            if position is not None and QRectF(
                position.x() - 12.0, position.y() - 12.0, 24.0, 24.0
            ).contains(point):
                return comment
        return None

    def set_active_comment(self, comment_id: str) -> None:
        self._active_comment_id = str(comment_id or "")
        self.update()

    def _paint_comments(self, painter: QPainter) -> None:
        for index, comment in enumerate(self._review_comments(), 1):
            position = self._comment_position(comment)
            if position is None:
                continue
            active = str(comment.get("id") or "") == self._active_comment_id
            resolved = bool(comment.get("resolved"))
            region_rect = self._comment_region_rect(comment)
            if not region_rect.isNull():
                painter.save()
                painter.setBrush(QColor(13, 153, 255, 26 if not resolved else 12))
                painter.setPen(QPen(QColor("#0D99FF"), 1.0, Qt.PenStyle.DashLine))
                painter.drawRoundedRect(region_rect, 3.0, 3.0)
                painter.restore()
            if (
                self._interaction == "comment_move"
                and str(comment.get("id") or "") == self._active_comment_id
                and self._comment_drag_position is not None
            ):
                position = QPointF(self._comment_drag_position)
            radius = 11.0 if active else 9.0
            painter.save()
            painter.setPen(QPen(QColor("#FFFFFF"), 2.0))
            painter.setBrush(QColor("#8A8A8A") if resolved else QColor("#0D99FF"))
            painter.drawEllipse(position, radius, radius)
            painter.setPen(QColor("#FFFFFF"))
            font = painter.font()
            font.setPixelSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(position.x() - radius, position.y() - radius, radius * 2, radius * 2),
                Qt.AlignmentFlag.AlignCenter,
                str(index),
            )
            painter.restore()

    def prototype_connection_handle_rect(self) -> QRectF:
        if not self._prototype_authoring_visible:
            return QRectF()
        row = self._selected_row()
        if row is None or bool(row.get("locked", False)):
            return QRectF()
        rect = self._object_rect(row)
        center = QPointF(rect.right() + 13.0, rect.center().y())
        return QRectF(center.x() - 7.0, center.y() - 7.0, 14.0, 14.0)

    def set_prototype_authoring_visible(self, visible: bool) -> None:
        value = bool(visible)
        if self._prototype_authoring_visible == value:
            return
        self._prototype_authoring_visible = value
        if not value and self._interaction == "prototype_connection":
            self._cancel_interaction()
        self.update()

    def set_prototype_preview(
        self,
        enabled: bool,
        state: Mapping[str, Any] | None = None,
    ) -> None:
        self._prototype_preview_enabled = bool(enabled)
        self._prototype_preview_state = (
            copy.deepcopy(dict(state))
            if isinstance(state, Mapping)
            else {}
        )
        self._prototype_pressed_object_id = ""
        self._prototype_hover_object_id = ""
        self._prototype_focus_object_id = ""
        if self._prototype_preview_enabled:
            self._cancel_interaction()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._rebuild_effective_document()
        self.update()

    def set_prototype_preview_state(
        self,
        state: Mapping[str, Any] | None,
    ) -> None:
        self._prototype_preview_state = (
            copy.deepcopy(dict(state))
            if isinstance(state, Mapping)
            else {}
        )
        self._rebuild_effective_document()
        self.update()

    def prototype_preview_enabled(self) -> bool:
        return bool(self._prototype_preview_enabled)

    def _prototype_target_artboard(self, point: QPointF) -> str:
        for artboard in reversed(self._document["artboards"]):
            viewport, _scale = self._artboard_viewport(artboard)
            if viewport.contains(point):
                return str(artboard["id"])
        return ""

    def _prototype_connection_endpoint(
        self,
        interaction: Mapping[str, Any],
    ) -> QPointF | None:
        target_object_id = str(interaction.get("target_object_id") or "")
        if target_object_id:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == target_object_id
                ),
                None,
            )
            if row is not None:
                return self._object_rect(row).center()
        target_artboard_id = str(
            interaction.get("target_artboard_id") or ""
        )
        artboard = next(
            (
                item
                for item in self._document["artboards"]
                if item["id"] == target_artboard_id
            ),
            None,
        )
        if artboard is None:
            return None
        viewport, _scale = self._artboard_viewport(artboard)
        return QPointF(viewport.left(), viewport.center().y())

    @staticmethod
    def _paint_prototype_curve(
        painter: QPainter,
        start: QPointF,
        end: QPointF,
        *,
        preview: bool = False,
    ) -> None:
        path = QPainterPath(start)
        bend = max(48.0, abs(end.x() - start.x()) * 0.42)
        direction = 1.0 if end.x() >= start.x() else -1.0
        path.cubicTo(
            QPointF(start.x() + bend * direction, start.y()),
            QPointF(end.x() - bend * direction, end.y()),
            end,
        )
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                QColor("#8CB8FF") if preview else QColor("#6FA0F5"),
                2.0,
                Qt.PenStyle.DashLine if preview else Qt.PenStyle.SolidLine,
            )
        )
        painter.drawPath(path)
        painter.setBrush(QColor("#8CB8FF"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(end, 4.0, 4.0)
        painter.restore()

    def _paint_prototype_connections(self, painter: QPainter) -> None:
        selected = str(self._document["selection"]["object_id"] or "")
        handle = self.prototype_connection_handle_rect()
        if not selected or handle.isNull():
            return
        start = handle.center()
        for interaction in self._document.get("interactions", []):
            if (
                not bool(interaction.get("enabled", True))
                or str(interaction.get("source_object_id") or "") != selected
            ):
                continue
            endpoint = self._prototype_connection_endpoint(interaction)
            if endpoint is not None:
                self._paint_prototype_curve(painter, start, endpoint)
        if self._prototype_drag_position is not None:
            self._paint_prototype_curve(
                painter,
                start,
                self._prototype_drag_position,
                preview=True,
            )
        painter.save()
        painter.setPen(QPen(QColor("#DCEAFF"), 1.5))
        painter.setBrush(QColor("#2F73D9"))
        painter.drawEllipse(handle)
        painter.restore()

    def object_ids_at(self, x: float, y: float) -> list[str]:
        position = QPointF(float(x), float(y))
        hits: list[str] = []
        scope_ids = self._edit_scope_object_ids()
        candidates = (
            self._outline_objects(reverse=True)
            if self._layer_outlines_visible
            else self._visible_objects(reverse=True)
        )
        for row in candidates:
            if scope_ids and str(row["id"]) not in scope_ids:
                continue
            if (
                not self._layer_outlines_visible
                and not self._point_visible_in_parent_clips(row, position)
            ):
                continue
            if (
                not self._layer_outlines_visible
                and not self._point_visible_in_object_mask(row, position)
            ):
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

    def set_layer_hover_object(self, object_id: str = "") -> None:
        target = str(object_id or "")
        if target and not any(
            str(row.get("id") or "") == target
            and bool(row.get("visible", True))
            for row in self._document.get("objects", [])
        ):
            target = ""
        if target == self._layer_hover_object_id:
            return
        self._layer_hover_object_id = target
        self.update()

    def layer_hover_object_id(self) -> str:
        return str(self._layer_hover_object_id)

    def _selection_target_from_hits(
        self,
        hit_ids: list[str],
        *,
        deep: bool = False,
    ) -> str:
        """Resolve a canvas hit using Figma's documented nesting rules."""
        by_id = {
            str(row["id"]): row
            for row in self._document["objects"]
        }
        for hit_id in hit_ids:
            row = by_id.get(str(hit_id))
            if row is None or bool(row.get("locked")):
                continue
            if deep:
                return str(row["id"])
            current = row
            seen: set[str] = set()
            while True:
                parent_id = str(current.get("parent_id") or "")
                if not parent_id or parent_id == self._edit_scope_id:
                    break
                if parent_id in seen:
                    break
                seen.add(parent_id)
                parent = by_id.get(parent_id)
                if parent is None:
                    break
                current = parent
            if not bool(current.get("locked")):
                return str(current["id"])
        return ""

    def _child_target_from_hits(
        self,
        parent_id: str,
        hit_ids: list[str],
    ) -> str:
        """Return the hit object exactly one hierarchy level below parent."""
        target_parent = str(parent_id or "")
        if not target_parent:
            return ""
        by_id = {
            str(row["id"]): row
            for row in self._document["objects"]
        }
        for hit_id in hit_ids:
            current = by_id.get(str(hit_id))
            candidate = ""
            seen: set[str] = set()
            while current is not None and str(current["id"]) not in seen:
                current_id = str(current["id"])
                seen.add(current_id)
                parent = str(current.get("parent_id") or "")
                if parent == target_parent:
                    candidate = current_id
                    break
                current = by_id.get(parent)
            row = by_id.get(candidate)
            if row is not None and not bool(row.get("locked")):
                return candidate
        return ""

    def _top_child_id(self, parent_id: str) -> str:
        children = [
            row
            for row in self._document["objects"]
            if str(row.get("parent_id") or "") == str(parent_id or "")
            and bool(row.get("visible", True))
            and not bool(row.get("locked"))
        ]
        if not children:
            return ""
        return str(max(children, key=lambda row: int(row.get("z_index", 0)))["id"])

    def _display_rotation(self, row: Mapping[str, Any]) -> float:
        preview = self._motion_preview.get(str(row["id"]))
        if preview is not None:
            return float(preview.get("rotation", row.get("rotation", 0.0)))
        return float(row.get("rotation", 0.0))

    def _display_opacity(self, row: Mapping[str, Any]) -> float:
        if self._prototype_preview_enabled:
            values = self._prototype_preview_state.get("object_opacity") or {}
            if str(row["id"]) in values:
                return max(
                    0.0,
                    min(1.0, float(values[str(row["id"])])),
                )
        preview = self._motion_preview.get(str(row["id"]))
        if preview is not None:
            return max(0.0, min(1.0, float(preview.get("opacity", 1.0))))
        return max(0.0, min(1.0, float(row.get("opacity", 1.0))))

    @staticmethod
    def _handle_rects(rect: QRectF) -> dict[str, QRectF]:
        extent = min(abs(float(rect.width())), abs(float(rect.height())))
        radius = min(5.0, max(2.5, extent * 0.10))
        return {
            name: QRectF(
                point.x() - radius,
                point.y() - radius,
                radius * 2.0,
                radius * 2.0,
            )
            for name, point in (
                ("nw", rect.topLeft()),
                ("n", QPointF(rect.center().x(), rect.top())),
                ("ne", rect.topRight()),
                ("e", QPointF(rect.right(), rect.center().y())),
                ("se", rect.bottomRight()),
                ("s", QPointF(rect.center().x(), rect.bottom())),
                ("sw", rect.bottomLeft()),
                ("w", QPointF(rect.left(), rect.center().y())),
            )
        }

    @staticmethod
    def _radius_eligible(row: Mapping[str, Any]) -> bool:
        return str(row.get("kind") or "").casefold() in {
            "rectangle", "button", "image",
        }

    def _radius_handle_centers(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> dict[str, QPointF]:
        _viewport, scale = self._artboard_viewport()
        radius = max(0.0, float((row.get("style") or {}).get("radius") or 0.0))
        maximum = max(12.0, min(rect.width(), rect.height()) * 0.5 - 10.0)
        inset = min(maximum, 18.0 + radius * max(0.0001, scale))
        return {
            "nw": QPointF(rect.left() + inset, rect.top() + inset),
            "ne": QPointF(rect.right() - inset, rect.top() + inset),
            "sw": QPointF(rect.left() + inset, rect.bottom() - inset),
            "se": QPointF(rect.right() - inset, rect.bottom() - inset),
        }

    def _radius_handle_at(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
        point: QPointF,
    ) -> str:
        if not self._radius_eligible(row):
            return ""
        for corner, center in self._radius_handle_centers(row, rect).items():
            if QRectF(center.x() - 8, center.y() - 8, 16, 16).contains(point):
                return corner
        return ""

    def _paint_radius_controls(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> None:
        if not self._radius_eligible(row):
            return
        centers = self._radius_handle_centers(row, rect)
        painter.save()
        painter.setPen(QPen(QColor("#168BFF"), 1.5))
        painter.setBrush(QColor("#FFFFFF"))
        for center in centers.values():
            painter.drawEllipse(center, 6.0, 6.0)
        if self._interaction == "radius" or self._radius_hover_corner:
            radius = max(0.0, float((row.get("style") or {}).get("radius") or 0.0))
            label = f"Radius {round(radius):g}"
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(label) + 12
            height = metrics.height() + 5
            if self._interaction == "radius":
                anchor = centers.get(self._radius_active_corner, rect.center())
                x = anchor.x() + 10
                y = anchor.y() - height * 0.5
            else:
                x = rect.left() + 34
                y = rect.top() - height - 2
            badge = QRectF(x, y, width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#168BFF"))
            painter.drawRoundedRect(badge, 3.0, 3.0)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    @staticmethod
    def _arc_point(rect: QRectF, angle: float, ratio: float = 1.0) -> QPointF:
        radians = math.radians(float(angle))
        return QPointF(
            rect.center().x() + math.cos(radians) * rect.width() * 0.5 * ratio,
            rect.center().y() + math.sin(radians) * rect.height() * 0.5 * ratio,
        )

    def _arc_handle_positions(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> dict[str, QPointF]:
        kind = str(row.get("kind") or "").casefold()
        if kind not in {"ellipse", "arc"}:
            return {}
        content = dict(row.get("content") or {})
        start = float(content.get("start_angle", 0.0 if kind == "ellipse" else -90.0))
        sweep = float(content.get("sweep_angle", 360.0 if kind == "ellipse" else 270.0))
        inner = float(content.get("inner_radius", 0.0))
        if kind == "ellipse":
            edge = self._arc_point(rect, start)
            center = rect.center()
            vector = edge - center
            length = max(0.0001, math.hypot(vector.x(), vector.y()))
            extent = min(abs(float(rect.width())), abs(float(rect.height())))
            inset = min(
                min(28.0, max(14.0, extent * 0.16)),
                max(4.0, extent * 0.30),
            )
            return {
                "sweep": QPointF(
                    edge.x() - vector.x() / length * inset,
                    edge.y() - vector.y() / length * inset,
                )
            }
        if abs(sweep) >= 359.999:
            edge = self._arc_point(rect, start)
            center = rect.center()
            vector = edge - center
            length = max(0.0001, math.hypot(vector.x(), vector.y()))
            extent = min(abs(float(rect.width())), abs(float(rect.height())))
            inset = min(
                min(28.0, max(14.0, extent * 0.16)),
                max(4.0, extent * 0.30),
            )
            return {
                "start": edge,
                "sweep": QPointF(
                    edge.x() - vector.x() / length * inset,
                    edge.y() - vector.y() / length * inset,
                ),
                "ratio": self._arc_point(rect, start + 180.0, inner),
            }
        middle = start + sweep * 0.5
        return {
            "start": self._arc_point(rect, start),
            "sweep": self._arc_point(rect, start + sweep),
            "ratio": self._arc_point(rect, middle, inner),
        }

    def _arc_handle_at(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
        point: QPointF,
    ) -> str:
        # Keep the interactive target comfortably larger than the painted
        # handle at normal zoom, but do not let it consume most of a small
        # ellipse.  A fixed 18 px box made compact ellipses almost impossible
        # to move because every ordinary press started an arc edit.
        extent = min(abs(float(rect.width())), abs(float(rect.height())))
        hit_radius = min(9.0, max(4.0, extent * 0.12))
        for name, center in self._arc_handle_positions(row, rect).items():
            if QRectF(
                center.x() - hit_radius,
                center.y() - hit_radius,
                hit_radius * 2.0,
                hit_radius * 2.0,
            ).contains(point):
                return name
        return ""

    def _paint_arc_controls(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> None:
        positions = self._arc_handle_positions(row, rect)
        if not positions:
            return
        painter.save()
        painter.setPen(QPen(QColor("#168BFF"), 1.5))
        painter.setBrush(QColor("#FFFFFF"))
        if len(positions) > 1:
            for name in ("start", "sweep"):
                if name in positions:
                    painter.drawLine(rect.center(), positions[name])
        for name, center in positions.items():
            handle_radius = 7.0 if len(positions) == 1 else 6.0
            painter.drawEllipse(center, handle_radius, handle_radius)
            if name == "start":
                painter.setBrush(QColor("#168BFF")); painter.drawEllipse(center, 2.2, 2.2); painter.setBrush(QColor("#FFFFFF"))
        highlighted = self._arc_active_handle or self._arc_hover_handle
        label = self._arc_label
        content = dict(row.get("content") or {})
        if highlighted == "sweep" and not label:
            sweep = float(
                content.get(
                    "sweep_angle",
                    360.0 if row.get("kind") == "ellipse" else 270.0,
                )
            )
            label = f"Sweep {round(sweep / 360.0 * 100.0):g}%"
        elif highlighted == "start" and not label:
            label = f"Start {round(float(content.get('start_angle', 0.0))):g}°"
        elif highlighted == "ratio" and not label:
            label = f"Ratio {round(float(content.get('inner_radius', 0.0)) * 100.0):g}%"
        if highlighted and label:
            anchor = positions.get(highlighted, rect.center())
            metrics = painter.fontMetrics()
            badge = QRectF(
                anchor.x() + 10, anchor.y() - 13,
                metrics.horizontalAdvance(label) + 12,
                metrics.height() + 5,
            )
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor("#168BFF"))
            painter.drawRoundedRect(badge, 3, 3)
            painter.setPen(QColor("#FFFFFF")); painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def _shape_gizmo_positions(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> dict[str, QPointF]:
        kind = str(row.get("kind") or "").casefold()
        content = dict(row.get("content") or {})
        if kind == "line":
            start_anchor = content.get("start_anchor", [0.0, 0.0])
            end_anchor = content.get("end_anchor", [1.0, 1.0])
            def anchor(value) -> QPointF:
                values = list(value) if isinstance(value, (list, tuple)) else [0.0, 0.0]
                return QPointF(
                    rect.left() + float(values[0]) * rect.width(),
                    rect.top() + float(values[1]) * rect.height(),
                )
            return {"line_start": anchor(start_anchor), "line_end": anchor(end_anchor)}
        if kind not in {"polygon", "star"}:
            return {}
        count = max(3, int(content.get("point_count", 5)))
        rotation = float(content.get("rotation_offset", -90.0))
        radius = float(content.get("corner_radius", 0.0))
        result: dict[str, QPointF] = {}
        outer = self._arc_point(rect, rotation)
        center = rect.center()
        vector = outer - center
        length = max(0.0001, math.hypot(vector.x(), vector.y()))
        _viewport, scale = self._artboard_viewport()
        radius_inset = min(length * 0.78, 14.0 + radius * scale)
        result["shape_radius"] = QPointF(
            outer.x() - vector.x() / length * radius_inset,
            outer.y() - vector.y() / length * radius_inset,
        )
        if kind == "star":
            inner = max(0.05, min(0.95, float(content.get("inner_radius", 0.45))))
            result["shape_ratio"] = self._arc_point(
                rect, rotation + 180.0 / count, inner
            )
            result["shape_count"] = self._arc_point(
                rect, rotation + 360.0 / count, 0.82
            )
        return result

    def _shape_gizmo_at(
        self, row: Mapping[str, Any], rect: QRectF, point: QPointF
    ) -> str:
        for name, center in self._shape_gizmo_positions(row, rect).items():
            if QRectF(center.x() - 9, center.y() - 9, 18, 18).contains(point):
                return name
        return ""

    def _paint_shape_gizmos(
        self, painter: QPainter, row: Mapping[str, Any], rect: QRectF
    ) -> None:
        positions = self._shape_gizmo_positions(row, rect)
        if not positions:
            return
        painter.save()
        painter.setPen(QPen(QColor("#168BFF"), 1.5))
        painter.setBrush(QColor("#FFFFFF"))
        for center in positions.values():
            painter.drawEllipse(center, 6.0, 6.0)
        highlighted = self._shape_gizmo_active or self._shape_gizmo_hover
        label = self._shape_gizmo_label
        if highlighted == "shape_radius":
            outer = self._arc_point(
                rect,
                float((row.get("content") or {}).get("rotation_offset", -90.0)),
            )
            painter.drawLine(outer, positions["shape_radius"])
            if not label:
                label = (
                    f"Radius {round(float((row.get('content') or {}).get('corner_radius', 0.0))):g}"
                )
        elif highlighted == "shape_ratio" and not label:
            label = (
                f"Ratio {round(float((row.get('content') or {}).get('inner_radius', 0.45)) * 100):g}%"
            )
        elif highlighted == "shape_count" and not label:
            label = f"Count {int((row.get('content') or {}).get('point_count', 5))}"
        if highlighted and label:
            anchor = positions.get(highlighted, rect.center())
            metrics = painter.fontMetrics()
            badge = QRectF(
                anchor.x() + 10,
                anchor.y() - 13,
                metrics.horizontalAdvance(label) + 12,
                metrics.height() + 5,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#168BFF"))
            painter.drawRoundedRect(badge, 3, 3)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

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
        # Stored rotation follows Figma's inspector convention: positive
        # angles are counterclockwise. Qt's screen-space positive rotation is
        # clockwise, so the visual transform uses the opposite sign and this
        # inverse mapping uses the stored sign directly.
        transform.rotate(float(angle))
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
        self._smart_guide_plan = {}
        if not self._object_snap_enabled:
            return x, y
        from app.painter_ui_smart_guides import plan_ui_move_guides

        viewport, scale = self._artboard_viewport()
        report = plan_ui_move_guides(
            self._effective_document,
            object_id=str(row["id"]),
            x=float(x),
            y=float(y),
            excluded_object_ids=list(self._move_original_positions),
            tolerance=6.0 / max(0.0001, scale),
            geometry=self._resolved_geometry,
        )
        self._smart_guide_plan = report
        for guide in report["guides"]:
            position = (
                viewport.left() + float(guide["position"]) * scale
                if guide["axis"] == "horizontal"
                else viewport.top() + float(guide["position"]) * scale
            )
            if guide["axis"] == "horizontal":
                self._guide_x = position
            else:
                self._guide_y = position
        return float(report["x"]), float(report["y"])

    def _smart_snap_resize_rect(
        self,
        row: Mapping[str, Any],
        rect: QRectF,
    ) -> QRectF:
        self._guide_x = None
        self._guide_y = None
        self._smart_guide_plan = {}
        if not self._object_snap_enabled:
            return rect
        from app.painter_ui_smart_guides import plan_ui_resize_guides

        viewport, scale = self._artboard_viewport()
        x = (rect.x() - viewport.x()) / max(0.0001, scale)
        y = (rect.y() - viewport.y()) / max(0.0001, scale)
        width = rect.width() / max(0.0001, scale)
        height = rect.height() / max(0.0001, scale)
        report = plan_ui_resize_guides(
            self._effective_document,
            object_id=str(row["id"]),
            x=x,
            y=y,
            width=width,
            height=height,
            excluded_object_ids=[str(row["id"])],
            tolerance=6.0 / max(0.0001, scale),
            geometry=self._resolved_geometry,
            active_handle=self._active_handle,
        )
        x = float(report["x"])
        y = float(report["y"])
        width = float(report["width"])
        height = float(report["height"])
        for guide in report["guides"]:
            position = (
                viewport.left() + float(guide["position"]) * scale
                if guide["axis"] == "horizontal"
                else viewport.top() + float(guide["position"]) * scale
            )
            if guide["axis"] == "horizontal":
                self._guide_x = position
            else:
                self._guide_y = position
        self._smart_guide_plan = report
        return QRectF(
            viewport.x() + x * scale,
            viewport.y() + y * scale,
            width * scale,
            height * scale,
        )

    def _smart_snap_create_rect(self, rect: QRectF) -> QRectF:
        """Snap a newly drawn shape's active edges to peer edge/center anchors."""
        self._guide_x = None
        self._guide_y = None
        self._smart_guide_plan = {}
        if not self._object_snap_enabled or rect.isNull():
            return rect
        active = self._active_artboard()["id"]
        dragging_left = self._press_position.x() > rect.center().x()
        dragging_top = self._press_position.y() > rect.center().y()
        x_anchor = rect.left() if dragging_left else rect.right()
        y_anchor = rect.top() if dragging_top else rect.bottom()
        x_options: list[tuple[float, float, QRectF]] = []
        y_options: list[tuple[float, float, QRectF]] = []
        for row in self._visible_objects():
            if str(row.get("artboard_id")) != str(active):
                continue
            other = self._object_rect(row)
            for target in (other.left(), other.center().x(), other.right()):
                delta = target - x_anchor
                if abs(delta) <= 6.0:
                    x_options.append((abs(delta), delta, other))
            for target in (other.top(), other.center().y(), other.bottom()):
                delta = target - y_anchor
                if abs(delta) <= 6.0:
                    y_options.append((abs(delta), delta, other))
        guides: list[dict[str, Any]] = []
        snapped = QRectF(rect)
        viewport, scale = self._artboard_viewport()
        if x_options:
            _distance, delta, other = min(x_options, key=lambda item: item[0])
            if dragging_left:
                snapped.setLeft(snapped.left() + delta)
            else:
                snapped.setRight(snapped.right() + delta)
            position = (snapped.left() if dragging_left else snapped.right())
            self._guide_x = position
            guides.append({
                "axis": "horizontal", "kind": "edge",
                "position": (position - viewport.left()) / max(0.0001, scale),
                "extent_start": (min(snapped.top(), other.top()) - viewport.top()) / max(0.0001, scale),
                "extent_end": (max(snapped.bottom(), other.bottom()) - viewport.top()) / max(0.0001, scale),
                "markers": [
                    (snapped.center().y() - viewport.top()) / max(0.0001, scale),
                    (other.center().y() - viewport.top()) / max(0.0001, scale),
                ],
            })
        if y_options:
            _distance, delta, other = min(y_options, key=lambda item: item[0])
            if dragging_top:
                snapped.setTop(snapped.top() + delta)
            else:
                snapped.setBottom(snapped.bottom() + delta)
            position = (snapped.top() if dragging_top else snapped.bottom())
            self._guide_y = position
            guides.append({
                "axis": "vertical", "kind": "edge",
                "position": (position - viewport.top()) / max(0.0001, scale),
                "extent_start": (min(snapped.left(), other.left()) - viewport.left()) / max(0.0001, scale),
                "extent_end": (max(snapped.right(), other.right()) - viewport.left()) / max(0.0001, scale),
                "markers": [
                    (snapped.center().x() - viewport.left()) / max(0.0001, scale),
                    (other.center().x() - viewport.left()) / max(0.0001, scale),
                ],
            })
        self._smart_guide_plan = {
            "schema": "tigerstudio.painter.ui.smart_guides.v1",
            "operation": "create",
            "guides": guides,
        }
        return snapped.normalized()

    def _resize_rect(self, point: QPointF, modifiers) -> QRectF:
        original = QRectF(self._original_rect)
        center_based = bool(modifiers & Qt.KeyboardModifier.AltModifier)
        force_ratio = (
            self._tool == "scale"
            or bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        )
        row = (
            None
            if self._interaction in {"resize_multi", "scale_multi"}
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
            half_width = (
                original.width() * 0.5
                if self._active_handle in {"n", "s"}
                else abs(point.x() - center.x())
            )
            half_height = (
                original.height() * 0.5
                if self._active_handle in {"e", "w"}
                else abs(point.y() - center.y())
            )
            raw = QRectF(
                center.x() - half_width,
                center.y() - half_height,
                half_width * 2.0,
                half_height * 2.0,
            )
        else:
            if self._active_handle == "n":
                raw = QRectF(
                    original.left(),
                    point.y(),
                    original.width(),
                    original.bottom() - point.y(),
                ).normalized()
            elif self._active_handle == "s":
                raw = QRectF(
                    original.left(),
                    original.top(),
                    original.width(),
                    point.y() - original.top(),
                ).normalized()
            elif self._active_handle == "w":
                raw = QRectF(
                    point.x(),
                    original.top(),
                    original.right() - point.x(),
                    original.height(),
                ).normalized()
            elif self._active_handle == "e":
                raw = QRectF(
                    original.left(),
                    original.top(),
                    point.x() - original.left(),
                    original.height(),
                ).normalized()
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

    def _image_focal_control(
        self,
    ) -> tuple[dict[str, Any], QRectF, QPointF] | None:
        object_id = str(self._image_focal_edit_object_id or "")
        if not object_id:
            return None
        row = next(
            (
                item
                for item in self._document["objects"]
                if item["id"] == object_id
            ),
            None,
        )
        if (
            row is None
            or row["id"] != self._document["selection"]["object_id"]
            or len(self._selected_rows()) != 1
        ):
            return None
        content = row.get("content") or {}
        if (
            not str(content.get("source_path") or "")
            or str(content.get("image_fit") or "fit") != "fill"
        ):
            return None
        rect = self._object_rect(row)
        focal = QPointF(
            rect.left()
            + float(content.get("focal_x", 0.5)) * rect.width(),
            rect.top()
            + float(content.get("focal_y", 0.5)) * rect.height(),
        )
        return row, rect, focal

    def _paint_image_focal_control(self, painter: QPainter) -> None:
        control = self._image_focal_control()
        if control is None:
            return
        row, rect, focal = control
        painter.save()
        rotation = self._display_rotation(row)
        pivot = ui_pivot_point(rect, row.get("constraints"))
        if abs(rotation) >= 0.001:
            painter.translate(pivot)
            painter.rotate(-rotation)
            painter.translate(-pivot)
        painter.setBrush(QColor("#111923CC"))
        painter.setPen(QPen(QColor("#F5F8FC"), 1.5))
        painter.drawEllipse(focal, 8.0, 8.0)
        painter.setPen(QPen(QColor("#72A7FF"), 1.5))
        painter.drawLine(
            QPointF(focal.x() - 12.0, focal.y()),
            QPointF(focal.x() + 12.0, focal.y()),
        )
        painter.drawLine(
            QPointF(focal.x(), focal.y() - 12.0),
            QPointF(focal.x(), focal.y() + 12.0),
        )
        painter.restore()

    def _begin_object_move(
        self,
        row: Mapping[str, Any],
        position: QPointF,
    ) -> None:
        from app.painter_ui_auto_layout_flow import inspect_auto_layout_child

        flow = inspect_auto_layout_child(self._document, str(row["id"]))
        if flow["eligible"] and len(flow["ordered_child_ids"]) > 1:
            self._interaction = "auto_layout_reorder"
            self._active_object_id = str(row["id"])
            self._press_position = QPointF(position)
            self._auto_layout_reorder_context = flow
            self._auto_layout_reorder_target_index = int(flow["index"])
            self._auto_layout_reorder_indicator = QRectF()
            return
        self._interaction = "move"
        self._active_object_id = str(row["id"])
        self._original_rect = QRectF(self._object_rect(row))
        self._drag_offset = position - self._original_rect.topLeft()
        selected_ids = list(self._document["selection"]["object_ids"])
        if row["id"] not in selected_ids:
            selected_ids = [str(row["id"])]
        descendants = set(selected_ids)
        changed = True
        while changed:
            before = len(descendants)
            descendants.update(
                str(item["id"])
                for item in self._document["objects"]
                if str(item["parent_id"]) in descendants
            )
            for item in self._document["objects"]:
                if str(item["id"]) not in descendants:
                    continue
                boolean = (item.get("content") or {}).get("boolean") or {}
                mask = item.get("mask") or {}
                descendants.update(
                    str(object_id)
                    for object_id in boolean.get("operand_ids", [])
                )
                descendants.update(
                    str(object_id)
                    for object_id in mask.get("target_ids", [])
                )
            changed = len(descendants) != before
        self._move_original_positions = {
            str(item["id"]): (float(item["x"]), float(item["y"]))
            for item in self._document["objects"]
            if str(item["id"]) in descendants and not item["locked"]
        }
        self._hierarchy_drop_preview_id = ""

    def _canvas_reparent_target(self, position: QPointF) -> str:
        moving_ids = set(self._move_original_positions)
        selected_ids = set(self._document["selection"]["object_ids"])
        by_id = {row["id"]: row for row in self._document["objects"]}
        for row in reversed(self._visible_objects()):
            object_id = str(row["id"])
            if (
                object_id in moving_ids
                or row["kind"] not in {"frame", "group"}
                or not self._object_rect(row).contains(position)
            ):
                continue
            parent_id = str(row.get("parent_id") or "")
            invalid = object_id in selected_ids
            while parent_id and not invalid:
                invalid = parent_id in selected_ids
                parent_id = str(
                    (by_id.get(parent_id) or {}).get("parent_id") or ""
                )
            if not invalid:
                return object_id
        return ""

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
        self._boolean_path_cache.clear()
        self.update()

    def _multi_transform_rows(self) -> list[dict[str, Any]]:
        rows = self._selected_rows()
        if (
            len(rows) < 2
            or any(bool(row["locked"]) for row in rows)
            or len(
                {
                    (str(row["artboard_id"]), str(row["parent_id"]))
                    for row in rows
                }
            )
            != 1
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

    def _smart_selection_report(self) -> dict[str, Any] | None:
        rows = self._multi_transform_rows()
        if len(rows) < 2:
            return None
        from app.painter_ui_smart_selection import inspect_ui_selection_spacing

        report = inspect_ui_selection_spacing(
            self._document,
            object_ids=[str(row["id"]) for row in rows],
            axis="auto",
        )
        return report if report["eligible"] and report["uniform"] else None

    def smart_marked_object_ids(self) -> list[str]:
        """Return marked Smart-selection IDs in stable visual order."""

        report = self._smart_selection_report()
        if report is None:
            return []
        return [
            str(object_id)
            for object_id in report["ordered_object_ids"]
            if str(object_id) in self._smart_marked_ids
        ]

    def _smart_selection_gap_handles(self) -> list[dict[str, Any]]:
        report = self._smart_selection_report()
        if report is None:
            return []
        by_id = {
            str(row["id"]): row
            for row in self._document["objects"]
        }
        handles: list[dict[str, Any]] = []

        def add_horizontal(left_id: str, right_id: str) -> None:
            left = self._object_rect(by_id[left_id])
            right = self._object_rect(by_id[right_id])
            center_x = (left.right() + right.left()) * 0.5
            overlap_top = max(left.top(), right.top())
            overlap_bottom = min(left.bottom(), right.bottom())
            center_y = (
                (overlap_top + overlap_bottom) * 0.5
                if overlap_bottom > overlap_top
                else (left.center().y() + right.center().y()) * 0.5
            )
            handles.append(
                {
                    "axis": "horizontal",
                    "rect": QRectF(center_x - 5.0, center_y - 12.0, 10.0, 24.0),
                }
            )

        def add_vertical(top_id: str, bottom_id: str) -> None:
            top = self._object_rect(by_id[top_id])
            bottom = self._object_rect(by_id[bottom_id])
            center_y = (top.bottom() + bottom.top()) * 0.5
            overlap_left = max(top.left(), bottom.left())
            overlap_right = min(top.right(), bottom.right())
            center_x = (
                (overlap_left + overlap_right) * 0.5
                if overlap_right > overlap_left
                else (top.center().x() + bottom.center().x()) * 0.5
            )
            handles.append(
                {
                    "axis": "vertical",
                    "rect": QRectF(center_x - 12.0, center_y - 5.0, 24.0, 10.0),
                }
            )

        if report["axis"] == "horizontal":
            ordered = report["ordered_object_ids"]
            for left_id, right_id in zip(ordered, ordered[1:]):
                add_horizontal(left_id, right_id)
        elif report["axis"] == "vertical":
            ordered = report["ordered_object_ids"]
            for top_id, bottom_id in zip(ordered, ordered[1:]):
                add_vertical(top_id, bottom_id)
        else:
            grid_rows = report["grid_rows"]
            for group in grid_rows:
                for left_id, right_id in zip(group, group[1:]):
                    add_horizontal(left_id, right_id)
            for upper, lower in zip(grid_rows, grid_rows[1:]):
                for top_id, bottom_id in zip(upper, lower):
                    add_vertical(top_id, bottom_id)
        return handles

    def _smart_selection_center_handles(self) -> list[dict[str, Any]]:
        report = self._smart_selection_report()
        if report is None:
            return []
        by_id = {
            str(row["id"]): row
            for row in self._document["objects"]
        }
        return [
            {
                "object_id": object_id,
                "rect": QRectF(
                    self._object_rect(by_id[object_id]).center().x() - 7.0,
                    self._object_rect(by_id[object_id]).center().y() - 7.0,
                    14.0,
                    14.0,
                ),
            }
            for object_id in report["ordered_object_ids"]
            if object_id in by_id
        ]

    def _preview_smart_reorder(
        self,
        position: QPointF,
        modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
    ) -> None:
        original = self._smart_reorder_original_document
        if original is None or self._smart_reorder_axis not in {
            "horizontal",
            "vertical",
            "grid",
        }:
            return
        from app.painter_ui_smart_selection import (
            inspect_ui_selection_spacing,
            plan_ui_smart_grid_reorder,
            plan_ui_smart_reorder,
        )

        report = inspect_ui_selection_spacing(
            original,
            axis=(
                "auto"
                if self._smart_reorder_axis == "grid"
                else self._smart_reorder_axis
            ),
        )
        by_id = {str(row["id"]): row for row in original["objects"]}
        document_point = self._document_point(position)
        if self._smart_reorder_axis == "grid":
            marked_id = next(iter(self._smart_marked_ids), "")
            grid_rows = [list(group) for group in report["grid_rows"]]
            swap_mode = bool(
                modifiers & Qt.KeyboardModifier.ControlModifier
            )
            swap_target_id = ""
            if swap_mode:
                candidates = [
                    object_id
                    for group in grid_rows
                    for object_id in group
                    if object_id != marked_id
                ]
                if candidates:
                    swap_target_id = min(
                        candidates,
                        key=lambda object_id: math.hypot(
                            document_point.x()
                            - (
                                float(by_id[object_id]["x"])
                                + float(by_id[object_id]["width"]) * 0.5
                            ),
                            document_point.y()
                            - (
                                float(by_id[object_id]["y"])
                                + float(by_id[object_id]["height"]) * 0.5
                            ),
                        ),
                    )
                target_row = 0
                target_column = 0
            else:
                target_row = min(
                    range(len(grid_rows)),
                    key=lambda index: abs(
                        document_point.y()
                        - sum(
                            float(by_id[object_id]["y"])
                            + float(by_id[object_id]["height"]) * 0.5
                            for object_id in grid_rows[index]
                        )
                        / max(1, len(grid_rows[index]))
                    ),
                )
                target_group = [
                    object_id
                    for object_id in grid_rows[target_row]
                    if object_id != marked_id
                ]
                target_column = sum(
                    1
                    for object_id in target_group
                    if document_point.x()
                    > float(by_id[object_id]["x"])
                    + float(by_id[object_id]["width"]) * 0.5
                )
            plan = plan_ui_smart_grid_reorder(
                original,
                marked_id=marked_id,
                target_row=target_row,
                target_column=target_column,
                swap_target_id=swap_target_id,
            )
            changes = plan.get("changes_by_id") or {}
            for document in (self._document, self._effective_document):
                document_by_id = {
                    str(row["id"]): row
                    for row in document["objects"]
                }
                for object_id, geometry in changes.items():
                    row = document_by_id.get(str(object_id))
                    if row is None:
                        continue
                    row.update({key: float(value) for key, value in geometry.items()})
                    if document is self._document:
                        self._sync_preview_geometry(row)
            viewport, scale = self._artboard_viewport()
            if swap_target_id:
                target = next(
                    row
                    for row in self._document["objects"]
                    if str(row["id"]) == swap_target_id
                )
                self._smart_reorder_indicator = self._object_rect(target)
                self._smart_reorder_indicator_mode = "swap"
            else:
                preview_by_id = {
                    str(row["id"]): row
                    for row in self._document["objects"]
                }
                planned_group = next(
                    (
                        list(group)
                        for group in plan.get("grid_rows", [])
                        if marked_id in group
                    ),
                    [marked_id],
                )
                marked = preview_by_id[marked_id]
                value = float(marked["x"])
                row_top = min(
                    float(preview_by_id[object_id]["y"])
                    for object_id in planned_group
                )
                row_bottom = max(
                    float(preview_by_id[object_id]["y"])
                    + float(preview_by_id[object_id]["height"])
                    for object_id in planned_group
                )
                screen_x = viewport.left() + value * scale
                self._smart_reorder_indicator = QRectF(
                    screen_x - 1.0,
                    viewport.top() + row_top * scale,
                    2.0,
                    max(2.0, (row_bottom - row_top) * scale),
                )
                self._smart_reorder_indicator_mode = "insert"
            self.update()
            return
        remaining_ids = [
            object_id
            for object_id in report["ordered_object_ids"]
            if object_id not in self._smart_marked_ids
        ]
        coordinate = (
            document_point.x()
            if self._smart_reorder_axis == "horizontal"
            else document_point.y()
        )
        position_key = "x" if self._smart_reorder_axis == "horizontal" else "y"
        size_key = "width" if self._smart_reorder_axis == "horizontal" else "height"
        target_index = sum(
            1
            for object_id in remaining_ids
            if coordinate
            > float(by_id[object_id][position_key])
            + float(by_id[object_id][size_key]) * 0.5
        )
        self._smart_reorder_target_index = target_index
        plan = plan_ui_smart_reorder(
            original,
            marked_ids=list(self._smart_marked_ids),
            target_index=target_index,
            axis=self._smart_reorder_axis,
        )
        changes = plan.get("changes_by_id") or {}
        for document in (self._document, self._effective_document):
            document_by_id = {
                str(row["id"]): row
                for row in document["objects"]
            }
            for object_id, geometry in changes.items():
                row = document_by_id.get(str(object_id))
                if row is None:
                    continue
                row.update({key: float(value) for key, value in geometry.items()})
                if document is self._document:
                    self._sync_preview_geometry(row)
        bounds = self._selection_bounds(self._multi_transform_rows())
        viewport, scale = self._artboard_viewport()
        if remaining_ids:
            if target_index == 0:
                value = float(by_id[remaining_ids[0]][position_key])
            elif target_index >= len(remaining_ids):
                last = by_id[remaining_ids[-1]]
                value = float(last[position_key]) + float(last[size_key])
            else:
                previous = by_id[remaining_ids[target_index - 1]]
                following = by_id[remaining_ids[target_index]]
                value = (
                    float(previous[position_key])
                    + float(previous[size_key])
                    + float(following[position_key])
                ) * 0.5
            screen_value = (
                viewport.left() + value * scale
                if self._smart_reorder_axis == "horizontal"
                else viewport.top() + value * scale
            )
            self._smart_reorder_indicator = (
                QRectF(screen_value - 1.0, bounds.top(), 2.0, bounds.height())
                if self._smart_reorder_axis == "horizontal"
                else QRectF(bounds.left(), screen_value - 1.0, bounds.width(), 2.0)
            )
            self._smart_reorder_indicator_mode = "insert"
        self.update()

    def _paint_smart_selection(self, painter: QPainter) -> None:
        report = self._smart_selection_report()
        if report is None:
            return
        painter.save()
        pink = QColor("#F24E9C")
        painter.setPen(QPen(pink, 1.5))
        painter.setBrush(QColor("#FFFFFF"))
        by_id = {
            str(row["id"]): row
            for row in self._document["objects"]
        }
        for object_id in report["ordered_object_ids"]:
            row = by_id.get(object_id)
            if row is not None:
                painter.setBrush(
                    pink
                    if object_id in self._smart_marked_ids
                    else QColor("#FFFFFF")
                )
                painter.drawEllipse(self._object_rect(row).center(), 4.0, 4.0)
        if self._smart_selection_hovered or self._interaction.startswith(
            "smart_gap_"
        ):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pink)
            for handle in self._smart_selection_gap_handles():
                rect = handle["rect"]
                if handle["axis"] == "horizontal":
                    painter.drawRoundedRect(
                        QRectF(rect.center().x() - 1.5, rect.top(), 3.0, rect.height()),
                        1.5,
                        1.5,
                    )
                else:
                    painter.drawRoundedRect(
                        QRectF(rect.left(), rect.center().y() - 1.5, rect.width(), 3.0),
                        1.5,
                        1.5,
                    )
        painter.restore()

    @staticmethod
    def _geometry_bounds(
        rows: list[Mapping[str, Any]],
    ) -> QRectF:
        bounds = QRectF()
        for row in rows:
            rect = QRectF(
                float(row["x"]),
                float(row["y"]),
                float(row["width"]),
                float(row["height"]),
            )
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    def _sync_preview_geometry(self, row: Mapping[str, Any]) -> None:
        geometry = self._resolved_geometry.setdefault(str(row["id"]), {})
        geometry.update(
            {
                "x": float(row["x"]),
                "y": float(row["y"]),
                "width": float(row["width"]),
                "height": float(row["height"]),
            }
        )

    def set_measurements_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._measurements_visible:
            return
        self._measurements_visible = visible
        self.update()

    def measurement_report(self) -> dict[str, Any]:
        from app.painter_ui_measurements import (
            inspect_ui_selection_measurements,
        )

        return inspect_ui_selection_measurements(self._effective_document)

    def _paint_measurements(self, painter: QPainter) -> None:
        if not self._measurements_visible:
            return
        report = self.measurement_report()
        if not report["eligible"]:
            return
        artboard = next(
            row
            for row in self._document["artboards"]
            if row["id"] == report["artboard_id"]
        )
        viewport, scale = self._artboard_viewport(artboard)

        def point(value) -> QPointF:
            return QPointF(
                viewport.left() + float(value[0]) * scale,
                viewport.top() + float(value[1]) * scale,
            )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        line_color = QColor("#F06C76")
        painter.setPen(QPen(line_color, 1.25))
        font = QFont(painter.font())
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        for distance in report["distances"]:
            start = point(distance["start"])
            end = point(distance["end"])
            painter.drawLine(start, end)
            if distance["axis"] == "horizontal":
                painter.drawLine(
                    start + QPointF(0.0, -4.0),
                    start + QPointF(0.0, 4.0),
                )
                painter.drawLine(
                    end + QPointF(0.0, -4.0),
                    end + QPointF(0.0, 4.0),
                )
            else:
                painter.drawLine(
                    start + QPointF(-4.0, 0.0),
                    start + QPointF(4.0, 0.0),
                )
                painter.drawLine(
                    end + QPointF(-4.0, 0.0),
                    end + QPointF(4.0, 0.0),
                )
            label = f"{float(distance['value']):g} px"
            metrics = painter.fontMetrics()
            width = metrics.horizontalAdvance(label) + 12
            height = metrics.height() + 6
            center = (start + end) * 0.5
            label_rect = QRectF(
                center.x() - width * 0.5,
                center.y() - height * 0.5,
                width,
                height,
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#B83F4A"))
            painter.drawRoundedRect(label_rect, 4.0, 4.0)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
            painter.setPen(QPen(line_color, 1.25))
        painter.restore()

    def _visible_objects(self, *, reverse: bool = False) -> list[dict[str, Any]]:
        boolean_operands = set(self._boolean_operand_id_cache)
        active_boolean_group = self._active_boolean_edit_group_id()
        if active_boolean_group:
            group = self._effective_objects_by_id.get(active_boolean_group) or {}
            boolean = (group.get("content") or {}).get("boolean") or {}
            boolean_operands.difference_update(
                str(value)
                for value in boolean.get("operand_ids", [])
                if str(value or "")
            )
        hidden_boolean_hosts = {active_boolean_group} if active_boolean_group else set()
        parent_id = active_boolean_group
        while parent_id:
            parent_row = self._effective_objects_by_id.get(parent_id) or {}
            parent_id = str(parent_row.get("parent_id") or "")
            if parent_id:
                from app.painter_ui_boolean import is_ui_boolean_group

                parent = self._effective_objects_by_id.get(parent_id) or {}
                if is_ui_boolean_group(parent):
                    hidden_boolean_hosts.add(parent_id)
        preview_artboards: set[str] | None = None
        preview_visibility: Mapping[str, Any] = {}
        if self._prototype_preview_enabled:
            current = str(
                self._prototype_preview_state.get("artboard_id") or ""
            )
            overlays = {
                str(value)
                for value in (
                    self._prototype_preview_state.get(
                        "overlay_artboard_ids"
                    )
                    or []
                )
            }
            preview_artboards = ({current} if current else set()) | overlays
            preview_visibility = (
                self._prototype_preview_state.get("object_visibility") or {}
            )
        return sorted(
            (
                row
                for row in self._effective_document["objects"]
                if row["visible"] and row["id"] not in boolean_operands
                and row["id"] not in hidden_boolean_hosts
                and (
                    preview_artboards is None
                    or row["artboard_id"] in preview_artboards
                )
                and bool(preview_visibility.get(row["id"], True))
            ),
            key=lambda row: row["z_index"],
            reverse=reverse,
        )

    def _outline_objects(self, *, reverse: bool = False) -> list[dict[str, Any]]:
        """Expose nested Boolean and optionally hidden rows for x-ray outlines."""
        preview_artboards: set[str] | None = None
        if self._prototype_preview_enabled:
            current = str(self._prototype_preview_state.get("artboard_id") or "")
            preview_artboards = {current} if current else set()
            preview_artboards.update(
                str(value)
                for value in self._prototype_preview_state.get(
                    "overlay_artboard_ids", []
                )
            )
        return sorted(
            (
                row
                for row in self._effective_document["objects"]
                if (bool(row["visible"]) or self._outline_include_hidden)
                and (
                    preview_artboards is None
                    or row["artboard_id"] in preview_artboards
                )
            ),
            key=lambda row: row["z_index"],
            reverse=reverse,
        )

    def _active_boolean_edit_group_id(self) -> str:
        from app.painter_ui_boolean import is_ui_boolean_group

        scope = self._effective_objects_by_id.get(str(self._edit_scope_id or ""))
        if scope is not None and is_ui_boolean_group(scope):
            return str(scope["id"])
        selected_ids = {
            str(value)
            for value in self._document["selection"].get("object_ids", [])
            if str(value or "")
        }
        parents = {
            str(self._effective_objects_by_id[object_id].get("parent_id") or "")
            for object_id in selected_ids
            if object_id in self._effective_objects_by_id
        }
        if len(parents) != 1:
            return ""
        parent = self._effective_objects_by_id.get(next(iter(parents)))
        return str(parent["id"]) if parent is not None and is_ui_boolean_group(parent) else ""

    def _boolean_operand_ids(self) -> set[str]:
        from app.painter_ui_boolean_geometry import boolean_operand_ids

        return boolean_operand_ids(self._effective_document["objects"])

    def _clipping_ancestors(
        self,
        row: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        parent_id = str(row.get("parent_id") or "")
        while parent_id and parent_id not in seen:
            seen.add(parent_id)
            parent = self._effective_objects_by_id.get(parent_id)
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
            transform.rotate(-rotation)
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
        from app.painter_ui_boolean_geometry import ui_object_shape_path

        rect = self._object_rect(row)
        scale = rect.width() / max(0.001, float(row["width"]))
        return ui_object_shape_path(row, rect, geometry_scale=scale)

    def _mask_source_for_target(
        self,
        target_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        return self._mask_source_by_target.get(str(target_id))

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
        from app.painter_ui_boolean_geometry import resolve_ui_boolean_path

        object_id = str(row.get("id") or "")
        if object_id in self._boolean_path_cache:
            return self._boolean_path_cache[object_id]
        path = resolve_ui_boolean_path(
            self._effective_document["objects"],
            row,
            self._object_rect,
            geometry_scale_for_object=lambda operand: (
                self._object_rect(operand).width()
                / max(0.001, float(operand["width"]))
            ),
        )
        self._boolean_path_cache[object_id] = path
        return path

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
        boolean_enabled = bool(
            isinstance(content.get("boolean"), Mapping)
            and content["boolean"].get("enabled")
        )
        if (
            kind == "path"
            and not boolean_enabled
            and not has_ui_vector_geometry(content)
        ):
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
            start_anchor = content.get("start_anchor", [0.0, 0.0])
            end_anchor = content.get("end_anchor", [1.0, 1.0])
            start = QPointF(
                rect.left() + float(start_anchor[0]) * rect.width(),
                rect.top() + float(start_anchor[1]) * rect.height(),
            )
            end = QPointF(
                rect.left() + float(end_anchor[0]) * rect.width(),
                rect.top() + float(end_anchor[1]) * rect.height(),
            )
            painter.drawLine(start, end)
            if bool(content.get("arrow_end", False)):
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                length = max(0.001, math.hypot(dx, dy))
                ux, uy = dx / length, dy / length
                size = max(8.0, 10.0 * scale)
                base_x = end.x() - ux * size
                base_y = end.y() - uy * size
                wing = size * 0.52
                arrow = QPainterPath(end)
                arrow.lineTo(base_x - uy * wing, base_y + ux * wing)
                arrow.lineTo(base_x + uy * wing, base_y - ux * wing)
                arrow.closeSubpath()
                painter.fillPath(arrow, fill)
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
            image_shape = self._object_shape_path(row)
            painter.drawPath(image_shape)
            painter.save()
            painter.setClipPath(
                image_shape,
                Qt.ClipOperation.IntersectClip,
            )
            image_drawn = draw_ui_image(painter, rect, row.get("content"))
            painter.restore()
            if not image_drawn:
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
            painter.drawPath(image_shape)
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
                text_resize=str(row["content"].get("text_resize") or ""),
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

    def _paint_creation_preview(self, painter: QPainter) -> None:
        """Paint the geometry being created instead of a generic drag box."""
        rect = self._preview_rect.normalized()
        tool = str(self._tool or "").casefold()
        if tool not in {"line", "arrow"} and rect.isNull():
            return
        outline = QColor("#168BFF")
        fill = QColor(217, 217, 217, 190)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(outline, 1.5))
        painter.setBrush(fill)
        if tool in {"line", "arrow"}:
            start = QPointF(self._press_position)
            end = QPointF(self._preview_line_end)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(outline, 2.0))
            painter.drawLine(start, end)
            if tool == "arrow":
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                length = math.hypot(dx, dy)
                if length > 0.001:
                    ux, uy = dx / length, dy / length
                    size = 10.0
                    base_x = end.x() - ux * size
                    base_y = end.y() - uy * size
                    wing = size * 0.52
                    head = QPainterPath(end)
                    head.lineTo(base_x - uy * wing, base_y + ux * wing)
                    head.lineTo(base_x + uy * wing, base_y - ux * wing)
                    head.closeSubpath()
                    painter.fillPath(head, outline)
        elif tool in {"ellipse", "arc"}:
            painter.drawEllipse(rect)
        elif tool in {"polygon", "star"}:
            from app.painter_ui_parametric_shapes import parametric_shape_path

            painter.drawPath(parametric_shape_path(rect, tool, {}))
        else:
            painter.drawRect(rect)
        painter.restore()

    def _paint_object_outline(
        self,
        painter: QPainter,
        row: Mapping[str, Any],
    ) -> None:
        from app.painter_ui_boolean_geometry import (
            ui_object_boolean_geometry_path,
        )

        rect = self._object_rect(row)
        path = self._boolean_path(row)
        if path is None:
            scale = rect.width() / max(0.001, float(row["width"]))
            outline_row = dict(row)
            outline_row["rotation"] = 0.0
            path = ui_object_boolean_geometry_path(
                outline_row,
                rect,
                geometry_scale=scale,
            )
        selected = str(row["id"]) in set(
            self._document.get("selection", {}).get("object_ids", [])
        )
        hidden = not bool(row.get("visible", True))
        color = QColor(
            "#168BFF" if selected else "#8A96A8" if hidden else "#37A4FF"
        )
        painter.save()
        painter.setOpacity(0.72 if hidden else 1.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                color,
                1.5 if selected else 1.0,
                Qt.PenStyle.DashLine if hidden else Qt.PenStyle.SolidLine,
            )
        )
        if not path.isEmpty():
            painter.drawPath(path)
        if self._outline_include_bounds or path.isEmpty():
            bounds_pen = QPen(color, 1.0, Qt.PenStyle.DotLine)
            painter.setPen(bounds_pen)
            painter.drawRect(rect)
        painter.restore()

    def paintEvent(self, _event) -> None:
        empty_page = bool(self._empty_page_mode and not self._document["objects"])
        canvas_color = QColor("#F5F5F5" if empty_page else "#3F4145")
        surface = QImage(
            max(1, self.width()),
            max(1, self.height()),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        surface.fill(canvas_color)
        scene_painter = QPainter(surface)
        scene_painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            not self._pixel_preview_enabled,
        )
        scene_painter.fillRect(self.rect(), canvas_color)
        active_id = self._document["active_artboard_id"]
        preview_artboards: set[str] | None = None
        if self._prototype_preview_enabled:
            current = str(
                self._prototype_preview_state.get("artboard_id") or ""
            )
            preview_artboards = {
                str(value)
                for value in (
                    self._prototype_preview_state.get(
                        "overlay_artboard_ids"
                    )
                    or []
                )
            }
            if current:
                preview_artboards.add(current)
        for artboard in self._document["artboards"]:
            if empty_page:
                continue
            if (
                preview_artboards is not None
                and artboard["id"] not in preview_artboards
            ):
                continue
            viewport, scale = self._artboard_viewport(artboard)
            scaffold_artboard = bool(
                str(artboard.get("id") or "") == "artboard-1"
                and str(artboard.get("name") or "").strip().casefold()
                == "main"
            )
            if scaffold_artboard and not self._prototype_preview_enabled:
                continue
            scene_painter.fillRect(
                viewport,
                QColor(str(artboard.get("background") or "#FFFFFF")),
            )
            if not self._prototype_preview_enabled:
                self._paint_artboard_layout(
                    scene_painter,
                    artboard,
                    viewport,
                    scale,
                    layout_guides_visible=self._layout_guides_visible,
                    pixel_grid_visible=self._pixel_grid_visible,
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
                if self._artboard_labels_visible:
                    scene_painter.setPen(QColor("#B7C0CD"))
                    scene_painter.drawText(
                        QPointF(viewport.left(), viewport.top() - 7.0),
                        str(artboard["name"]),
                    )
        scale, offset = self._view_transform()
        for section in (
            [] if self._prototype_preview_enabled
            else self._document.get("sections", [])
        ):
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
            if self._artboard_labels_visible:
                section_name = str(section["name"])
                metrics = scene_painter.fontMetrics()
                label_rect = QRectF(
                    section_rect.left(),
                    section_rect.top() - metrics.height() - 12.0,
                    metrics.horizontalAdvance(section_name) + 18.0,
                    metrics.height() + 8.0,
                )
                scene_painter.setPen(QPen(QColor("#D4D7DC"), 1.0))
                scene_painter.setBrush(QColor("#FFFFFF"))
                scene_painter.drawRoundedRect(label_rect, 6.0, 6.0)
                scene_painter.setPen(QColor("#303238"))
                scene_painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    section_name,
                )
        if not self._prototype_preview_enabled:
            from app.painter_ui_components import component_set_canvas_bounds

            for component in self._document.get("components", []):
                if component.get("base_component_id") or not component.get("variant_ids"):
                    continue
                bounds = component_set_canvas_bounds(
                    self._document,
                    component_id=str(component["id"]),
                )
                if not bounds:
                    continue
                rect = self._object_rect(bounds)
                scene_painter.save()
                scene_painter.setBrush(Qt.BrushStyle.NoBrush)
                pen = QPen(QColor("#9747FF"), 1.5, Qt.PenStyle.DashLine)
                pen.setDashPattern([6.0, 4.0])
                scene_painter.setPen(pen)
                scene_painter.drawRect(rect)
                scene_painter.setPen(QColor("#9747FF"))
                scene_painter.drawText(
                    QPointF(rect.left(), rect.top() - 8.0),
                    str(bounds.get("name") or "Component Set"),
                )
                scene_painter.restore()
        paint_rows = (
            self._outline_objects()
            if self._layer_outlines_visible
            else self._visible_objects()
        )
        for row in paint_rows:
            scene_painter.save()
            if not self._layer_outlines_visible:
                self._apply_parent_clips(scene_painter, row)
                self._apply_object_mask(scene_painter, row)
            rect = self._object_rect(row)
            rotation = self._display_rotation(row)
            pivot = ui_pivot_point(rect, row.get("constraints"))
            if abs(rotation) >= 0.001:
                scene_painter.translate(pivot)
                scene_painter.rotate(-rotation)
                scene_painter.translate(-pivot)
            content = dict(row.get("content") or {})
            flip_x = bool(content.get("flip_x", False))
            flip_y = bool(content.get("flip_y", False))
            if flip_x or flip_y:
                scene_painter.translate(pivot)
                scene_painter.scale(-1.0 if flip_x else 1.0, -1.0 if flip_y else 1.0)
                scene_painter.translate(-pivot)
            display_row = dict(row)
            display_row["opacity"] = self._display_opacity(row)
            if not self._row_in_edit_scope(row):
                display_row["opacity"] *= 0.2
            if self._layer_outlines_visible:
                self._paint_object_outline(scene_painter, display_row)
            else:
                self._paint_object(
                    scene_painter,
                    display_row,
                    surface=surface,
                )
            scene_painter.restore()
        if self._artboard_labels_visible and not self._prototype_preview_enabled:
            selected_ids = set(
                self._document.get("selection", {}).get("object_ids", [])
            )
            for row in self._visible_objects():
                if str(row.get("kind") or "") != "frame":
                    continue
                if bool((row.get("content") or {}).get("export_slice", False)):
                    continue
                rect = self._object_rect(row)
                selected = str(row.get("id") or "") in selected_ids
                scene_painter.setPen(
                    QColor("#168BFF") if selected else QColor("#B8BABE")
                )
                scene_painter.drawText(
                    QPointF(rect.left(), rect.top() - 9.0),
                    str(row.get("name") or "Frame"),
                )
        scene_painter.end()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawImage(0, 0, surface)
        if self._prototype_preview_enabled:
            painter.end()
            return
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
        if self._layer_hover_object_id:
            hover_row = next(
                (
                    row
                    for row in self._visible_objects()
                    if str(row["id"]) == self._layer_hover_object_id
                ),
                None,
            )
            if hover_row is not None:
                painter.save()
                hover_rect = self._object_rect(hover_row)
                hover_rotation = self._display_rotation(hover_row)
                hover_pivot = ui_pivot_point(
                    hover_rect,
                    hover_row.get("constraints"),
                )
                if abs(hover_rotation) >= 0.001:
                    painter.translate(hover_pivot)
                    painter.rotate(-hover_rotation)
                    painter.translate(-hover_pivot)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#168BFF"), 1.5))
                painter.drawRect(hover_rect)
                painter.restore()
        selected = (
            ""
            if self._prototype_preview_enabled
            else self._document["selection"]["object_id"]
        )
        selected_ids = (
            set()
            if self._prototype_preview_enabled
            else set(self._document["selection"]["object_ids"])
        )
        selected_rows = (
            [] if self._prototype_preview_enabled else self._selected_rows()
        )
        multi_rows = (
            [] if self._prototype_preview_enabled else self._multi_transform_rows()
        )
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
                painter.rotate(-rotation)
                painter.translate(-pivot)
            is_selected = row["id"] in selected_ids
            if is_selected:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#72A7FF"), 2.0))
                painter.drawRect(rect)
                if self._radius_eligible(row):
                    _viewport, scale = self._artboard_viewport()
                    radius = max(
                        0.0,
                        float((row.get("style") or {}).get("radius") or 0.0)
                        * max(0.0001, scale),
                    )
                    if radius > 0.0:
                        painter.drawRoundedRect(rect, radius, radius)
                self._paint_clip_indicator(painter, row, rect)
                self._paint_mask_indicator(painter, row)
                if row["id"] in self._smart_marked_ids and len(selected_ids) > 1:
                    painter.setBrush(QColor("#F4F7FC"))
                    painter.setPen(QPen(QColor("#356FC7"), 1.0))
                    for handle in self._handle_rects(rect).values():
                        painter.drawRect(handle)
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
                    self._paint_radius_controls(painter, row, rect)
                    self._paint_arc_controls(painter, row, rect)
                    self._paint_shape_gizmos(painter, row, rect)
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
        if len(selected_rows) == 1:
            row = selected_rows[0]
            rect = self._object_rect(row)
            label = (
                f"{float(row['width']):g} × {float(row['height']):g}"
            )
            metrics = painter.fontMetrics()
            badge_width = metrics.horizontalAdvance(label) + 14
            badge_height = metrics.height() + 6
            badge_x = rect.center().x() - badge_width * 0.5
            badge_y = rect.bottom() + 8.0
            if badge_y + badge_height > self.height() - 4:
                badge_y = max(4.0, rect.bottom() - badge_height - 8.0)
            badge = QRectF(
                badge_x,
                badge_y,
                float(badge_width),
                float(badge_height),
            )
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#168BFF"))
            painter.drawRoundedRect(badge, 4.0, 4.0)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
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
                rotate_handle = self._rotation_handle_rect(multi_bounds)
                painter.drawLine(
                    multi_bounds.center(),
                    QPointF(multi_bounds.center().x(), rotate_handle.bottom()),
                )
                painter.drawEllipse(rotate_handle)
            painter.restore()
            self._paint_smart_selection(painter)
            smart_report = self._smart_selection_report()
            marked_rows = [
                row for row in multi_rows
                if str(row["id"]) in self._smart_marked_ids
            ]
            if (
                smart_report is not None
                and smart_report["axis"] in {"horizontal", "vertical"}
                and len(marked_rows) > 1
            ):
                marked_bounds = self._selection_bounds(marked_rows)
                painter.save()
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#168BFF"), 2.0))
                painter.drawRect(marked_bounds)
                painter.setBrush(QColor("#F4F7FC"))
                painter.setPen(QPen(QColor("#356FC7"), 1.0))
                for handle in self._handle_rects(marked_bounds).values():
                    painter.drawRect(handle)
                painter.restore()
        if not self._auto_layout_reorder_indicator.isNull():
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#0D99FF"), 3.0))
            if self._auto_layout_reorder_context.get("mode") == "horizontal":
                x = self._auto_layout_reorder_indicator.center().x()
                painter.drawLine(
                    QPointF(x, self._auto_layout_reorder_indicator.top()),
                    QPointF(x, self._auto_layout_reorder_indicator.bottom()),
                )
            else:
                y = self._auto_layout_reorder_indicator.center().y()
                painter.drawLine(
                    QPointF(self._auto_layout_reorder_indicator.left(), y),
                    QPointF(self._auto_layout_reorder_indicator.right(), y),
                )
            painter.restore()
        if not self._smart_reorder_indicator.isNull():
            painter.save()
            painter.setPen(QPen(QColor("#168BFF"), 3.0))
            if self._smart_reorder_indicator_mode == "swap":
                painter.setBrush(QColor(22, 139, 255, 24))
                painter.drawRect(self._smart_reorder_indicator)
            elif self._smart_reorder_axis == "horizontal":
                x = self._smart_reorder_indicator.center().x()
                painter.drawLine(
                    QPointF(x, self._smart_reorder_indicator.top()),
                    QPointF(x, self._smart_reorder_indicator.bottom()),
                )
            else:
                y = self._smart_reorder_indicator.center().y()
                painter.drawLine(
                    QPointF(self._smart_reorder_indicator.left(), y),
                    QPointF(self._smart_reorder_indicator.right(), y),
                )
            painter.restore()
        if self._smart_gap_label and self._interaction.startswith("smart_gap_"):
            metrics = painter.fontMetrics()
            badge = QRectF(
                self._smart_gap_label_position.x() + 12.0,
                self._smart_gap_label_position.y() - metrics.height() - 12.0,
                metrics.horizontalAdvance(self._smart_gap_label) + 14.0,
                metrics.height() + 6.0,
            )
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F24E9C"))
            painter.drawRoundedRect(badge, 4.0, 4.0)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                badge,
                Qt.AlignmentFlag.AlignCenter,
                self._smart_gap_label,
            )
            painter.restore()
        if self._rotation_label and self._interaction in {"rotate", "rotate_multi"}:
            metrics = painter.fontMetrics()
            badge = QRectF(
                self._press_position.x() + 12.0,
                self._press_position.y() - metrics.height() - 12.0,
                metrics.horizontalAdvance(self._rotation_label) + 14.0,
                metrics.height() + 6.0,
            )
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#168BFF"))
            painter.drawRoundedRect(badge, 4.0, 4.0)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                badge,
                Qt.AlignmentFlag.AlignCenter,
                self._rotation_label,
            )
            painter.restore()
        if not self._prototype_preview_enabled:
            self._paint_prototype_connections(painter)
        self._paint_image_focal_control(painter)
        if self._prototype_hover_artboard_id:
            target_artboard = next(
                (
                    row
                    for row in self._document["artboards"]
                    if row["id"] == self._prototype_hover_artboard_id
                ),
                None,
            )
            if target_artboard is not None:
                viewport, _scale = self._artboard_viewport(target_artboard)
                painter.save()
                painter.setBrush(QColor(111, 160, 245, 24))
                painter.setPen(QPen(QColor("#8CB8FF"), 2.0))
                painter.drawRect(viewport)
                painter.restore()
        if self._hierarchy_drop_preview_id:
            target = next(
                (
                    row
                    for row in self._document["objects"]
                    if row["id"] == self._hierarchy_drop_preview_id
                ),
                None,
            )
            if target is not None:
                target_rect = self._object_rect(target)
                painter.save()
                painter.setBrush(QColor(71, 197, 142, 30))
                painter.setPen(
                    QPen(
                        QColor("#47C58E"),
                        2.0,
                        Qt.PenStyle.DashLine,
                    )
                )
                painter.drawRoundedRect(target_rect, 6.0, 6.0)
                painter.setPen(QColor("#D8FFF0"))
                painter.drawText(
                    target_rect.topLeft() + QPointF(8.0, 18.0),
                    painter_text("Move inside"),
                )
                painter.restore()

        if self._interaction == "create" and (
            not self._preview_rect.isNull()
            or self._tool in {"line", "arrow"}
        ):
            self._paint_creation_preview(painter)
        elif self._interaction == "pencil_draw" and len(self._pencil_points) >= 2:
            preview = QPainterPath(self._pencil_points[0])
            for point in self._pencil_points[1:]:
                preview.lineTo(point)
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    QColor("#168BFF"),
                    2.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            painter.drawPath(preview)
            painter.restore()
        elif self._interaction == "comment_place" and not self._preview_rect.isNull():
            painter.save()
            painter.setBrush(QColor(13, 153, 255, 24))
            painter.setPen(QPen(QColor("#0D99FF"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(self._preview_rect.normalized(), 3.0, 3.0)
            painter.restore()
        elif self._interaction == "marquee" and not self._preview_rect.isNull():
            painter.setBrush(QColor(71, 124, 210, 34))
            painter.setPen(QPen(QColor("#6FA0F5"), 1.0, Qt.PenStyle.DashLine))
            painter.drawRect(self._preview_rect.normalized())
        if self._guide_x is not None or self._guide_y is not None:
            viewport, scale = self._artboard_viewport()
            guide_color = QColor("#F2483D")
            painter.setPen(QPen(guide_color, 1.0))
            guides = list(self._smart_guide_plan.get("guides", []))
            drawn_axes: set[str] = set()
            for guide in guides:
                axis = str(guide.get("axis") or "")
                if "extent_start" not in guide or "extent_end" not in guide:
                    continue
                drawn_axes.add(axis)
                if axis == "horizontal" and self._guide_x is not None:
                    start = viewport.top() + float(guide["extent_start"]) * scale
                    end = viewport.top() + float(guide["extent_end"]) * scale
                    painter.drawLine(QPointF(self._guide_x, start), QPointF(self._guide_x, end))
                    marker_points = [viewport.top() + float(value) * scale for value in guide.get("markers", [])]
                    for marker in marker_points:
                        painter.drawLine(QPointF(self._guide_x - 3, marker - 3), QPointF(self._guide_x + 3, marker + 3))
                        painter.drawLine(QPointF(self._guide_x - 3, marker + 3), QPointF(self._guide_x + 3, marker - 3))
                elif axis == "vertical" and self._guide_y is not None:
                    start = viewport.left() + float(guide["extent_start"]) * scale
                    end = viewport.left() + float(guide["extent_end"]) * scale
                    painter.drawLine(QPointF(start, self._guide_y), QPointF(end, self._guide_y))
                    marker_points = [viewport.left() + float(value) * scale for value in guide.get("markers", [])]
                    for marker in marker_points:
                        painter.drawLine(QPointF(marker - 3, self._guide_y - 3), QPointF(marker + 3, self._guide_y + 3))
                        painter.drawLine(QPointF(marker - 3, self._guide_y + 3), QPointF(marker + 3, self._guide_y - 3))
            if self._guide_x is not None and "horizontal" not in drawn_axes:
                painter.drawLine(QPointF(self._guide_x, viewport.top()), QPointF(self._guide_x, viewport.bottom()))
            if self._guide_y is not None and "vertical" not in drawn_axes:
                painter.drawLine(QPointF(viewport.left(), self._guide_y), QPointF(viewport.right(), self._guide_y))
            label_names = {
                "baseline": painter_text("Baseline"),
                "padding": painter_text("Padding"),
                "equal_gap": painter_text("Equal gap"),
                "equal_width": painter_text("Equal width"),
                "equal_height": painter_text("Equal height"),
            }
            for guide in self._smart_guide_plan.get("guides", []):
                kind = str(guide.get("kind") or "")
                if kind not in label_names:
                    continue
                label = label_names[kind]
                if kind in {"equal_gap", "equal_width", "equal_height"}:
                    label += f" {float(guide.get('value') or 0.0):g}px"
                metrics = painter.fontMetrics()
                label_rect = QRectF(
                    (
                        self._guide_x + 7.0
                        if guide["axis"] == "horizontal"
                        else viewport.left() + 7.0
                    ),
                    (
                        viewport.top() + 7.0
                        if guide["axis"] == "horizontal"
                        else self._guide_y + 7.0
                    ),
                    metrics.horizontalAdvance(label) + 12.0,
                    metrics.height() + 6.0,
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#D83B32"))
                painter.drawRoundedRect(label_rect, 4.0, 4.0)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
                painter.setPen(QPen(guide_color, 1.0))
        self._paint_comments(painter)
        self._paint_measurements(painter)
        self._paint_rulers(painter)

    def _cancel_interaction(self) -> None:
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self._preview_rect = QRectF()
        self._preview_line_end = QPointF()
        self._pencil_points = []
        self._guide_x = None
        self._guide_y = None
        self._smart_guide_plan = {}
        self._smart_gap_axis = ""
        self._smart_gap_label = ""
        self._smart_gap_label_position = QPointF()
        self._smart_gap_original_gap = 0.0
        self._smart_gap_other_gap = 0.0
        self._smart_gap_original_document = None
        self._smart_reorder_original_document = None
        self._smart_reorder_axis = ""
        self._smart_reorder_target_index = -1
        self._smart_reorder_indicator = QRectF()
        self._smart_reorder_indicator_mode = ""
        self._auto_layout_reorder_context = {}
        self._auto_layout_reorder_target_index = -1
        self._auto_layout_reorder_indicator = QRectF()
        self._ruler_guide_preview = None
        self._ruler_origin_preview = None
        self._active_guide_position = 0.0
        self._auto_layout_active_target = ""
        self._auto_layout_drag_original = None
        self._alt_duplicate_cycle_id = ""
        self._alt_duplicate_source_ids = []
        self._alt_duplicate_drag_active = False
        self._prototype_drag_position = None
        self._prototype_hover_artboard_id = ""
        self._arc_active_handle = ""
        self._arc_label = ""
        self._arc_drag_last_angle = 0.0
        self._arc_drag_unwrapped_angle = 0.0
        self._arc_drag_direction = 0
        self._arc_original_content = {}
        self._shape_gizmo_active = ""
        self._shape_gizmo_label = ""
        self._rotation_label = ""
        self._comment_drag_position = None
        self._comment_press_target = {}
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
            and (self._space_pan_active or self._tool == "pan")
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
        if self._prototype_preview_enabled:
            hit_ids = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            target = hit_ids[0] if hit_ids else ""
            self._prototype_pressed_object_id = target
            self._prototype_focus_object_id = target
            if target:
                self.prototype_trigger_requested.emit(target, "press", "")
                self.prototype_trigger_requested.emit(target, "focus", "")
            event.accept()
            return
        viewport, _scale = self._artboard_viewport()
        # At very small zoom levels a selected object or one of its handles
        # can visually overlap the ruler band. Canvas controls must retain
        # pointer priority there; a ruler starts a guide only on otherwise
        # empty ruler space.
        ruler_control_override = bool(
            self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
        )
        selected_for_ruler = self._selected_row()
        if selected_for_ruler is not None and not selected_for_ruler.get(
            "locked", False
        ):
            selected_rect_for_ruler = self._object_rect(selected_for_ruler)
            local_for_ruler = self._unrotated_point(
                event.position(),
                selected_rect_for_ruler,
                float(selected_for_ruler.get("rotation", 0.0)),
                selected_for_ruler.get("constraints"),
            )
            ruler_control_override = ruler_control_override or any(
                handle.contains(local_for_ruler)
                for handle in self._handle_rects(
                    selected_rect_for_ruler
                ).values()
            ) or self._rotation_handle_rect(
                selected_rect_for_ruler,
                selected_for_ruler.get("constraints"),
            ).contains(local_for_ruler)
        multi_for_ruler = self._multi_transform_rows()
        multi_bounds_for_ruler = self._selection_bounds(multi_for_ruler)
        if not multi_bounds_for_ruler.isNull():
            ruler_control_override = ruler_control_override or any(
                handle.contains(event.position())
                for handle in self._handle_rects(
                    multi_bounds_for_ruler
                ).values()
            ) or self._rotation_handle_rect(
                multi_bounds_for_ruler
            ).contains(event.position())
        if self._rulers_visible and not ruler_control_override:
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

        if self._tool == "comment":
            existing = self._comment_at(QPointF(event.position()))
            if existing is not None:
                comment_id = str(existing.get("id") or "")
                self.set_active_comment(comment_id)
                self._interaction = "comment_move"
                self._comment_drag_position = QPointF(event.position())
                event.accept()
                return
            placement = self._comment_placement(QPointF(event.position()))
            if placement is None:
                event.accept()
                return
            self._interaction = "comment_place"
            self._comment_press_target = placement
            self._preview_rect = QRectF(event.position(), event.position())
            event.accept()
            return

        image_control = self._image_focal_control()
        if image_control is not None:
            row, rect, focal = image_control
            local_position = self._unrotated_point(
                event.position(),
                rect,
                float(row.get("rotation", 0.0)),
                row.get("constraints"),
            )
            if QRectF(
                focal.x() - 13.0,
                focal.y() - 13.0,
                26.0,
                26.0,
            ).contains(local_position):
                self._interaction = "image_focal"
                self._active_object_id = str(row["id"])
                self.setCursor(Qt.CursorShape.SizeAllCursor)
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
            if auto_layout_target in {"gap", "cross_gap"} or auto_layout_target.startswith(
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
            if self._tool == "select":
                smart_report = self._smart_selection_report()
                for center_handle in self._smart_selection_center_handles():
                    if center_handle["rect"].contains(event.position()):
                        object_id = str(center_handle["object_id"])
                        add_mark = bool(
                            smart_report is not None
                            and smart_report["axis"] in {"horizontal", "vertical"}
                            and event.modifiers()
                            & Qt.KeyboardModifier.ShiftModifier
                        )
                        if add_mark:
                            self._smart_marked_ids.add(object_id)
                        else:
                            self._smart_marked_ids = {object_id}
                        if smart_report is not None and smart_report["axis"] in {
                            "horizontal",
                            "vertical",
                            "grid",
                        }:
                            self._interaction = "smart_reorder_pending"
                            self._smart_reorder_axis = str(smart_report["axis"])
                            self._smart_reorder_original_document = copy.deepcopy(
                                self._document
                            )
                            self._smart_reorder_target_index = -1
                        self.update()
                        event.accept()
                        return
                for smart_handle in self._smart_selection_gap_handles():
                    if smart_handle["rect"].contains(event.position()):
                        axis = str(smart_handle["axis"])
                        self._interaction = f"smart_gap_{axis}"
                        self._smart_gap_axis = axis
                        self._smart_gap_original_document = copy.deepcopy(
                            self._document
                        )
                        if smart_report is not None and smart_report["axis"] == "grid":
                            self._smart_gap_original_gap = float(
                                smart_report[f"{axis}_gap"]
                            )
                            other_axis = (
                                "vertical" if axis == "horizontal" else "horizontal"
                            )
                            self._smart_gap_other_gap = float(
                                smart_report[f"{other_axis}_gap"]
                            )
                        elif smart_report is not None:
                            self._smart_gap_original_gap = float(
                                smart_report["gap"] or 0.0
                            )
                            self._smart_gap_other_gap = 0.0
                        self._smart_gap_label = (
                            f"{self._smart_gap_original_gap:g}px"
                        )
                        self._smart_gap_label_position = QPointF(
                            event.position()
                        )
                        self.setCursor(
                            Qt.CursorShape.SizeHorCursor
                            if axis == "horizontal"
                            else Qt.CursorShape.SizeVerCursor
                        )
                        event.accept()
                        return
                marked_rows = [
                    row for row in multi_rows
                    if str(row["id"]) in self._smart_marked_ids
                ]
                if (
                    smart_report is not None
                    and smart_report["axis"] in {"horizontal", "vertical"}
                    and len(marked_rows) > 1
                ):
                    marked_bounds = self._selection_bounds(marked_rows)
                    for name, handle in self._handle_rects(marked_bounds).items():
                        if handle.contains(event.position()):
                            self._interaction = "smart_resize_multi"
                            self._active_object_id = str(marked_rows[-1]["id"])
                            self._active_handle = name
                            self._original_rect = QRectF(marked_bounds)
                            self._resize_original_geometries = {
                                str(row["id"]): (
                                    float(row["x"]), float(row["y"]),
                                    float(row["width"]), float(row["height"]),
                                )
                                for row in marked_rows
                            }
                            self._smart_resize_original_document = copy.deepcopy(self._document)
                            event.accept()
                            return
                if len(marked_rows) == 1:
                    marked_row = marked_rows[0]
                    marked_rect = self._object_rect(marked_row)
                    for name, handle in self._handle_rects(marked_rect).items():
                        if handle.contains(event.position()):
                            self._interaction = "smart_resize"
                            self._active_object_id = str(marked_row["id"])
                            self._active_handle = name
                            self._original_rect = QRectF(marked_rect)
                            self._resize_original_geometries = {
                                str(marked_row["id"]): (
                                    float(marked_row["x"]), float(marked_row["y"]),
                                    float(marked_row["width"]), float(marked_row["height"]),
                                )
                            }
                            self._smart_resize_original_document = copy.deepcopy(self._document)
                            event.accept()
                            return
            for name in _HANDLE_NAMES:
                if self._handle_rects(multi_bounds)[name].contains(
                    event.position()
                ):
                    self._interaction = (
                        "scale_multi"
                        if self._tool == "scale"
                        else "resize_multi"
                    )
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
            rotate_handle = self._rotation_handle_rect(multi_bounds)
            if rotate_handle.contains(event.position()):
                self._interaction = "rotate_multi"
                self._active_object_id = str(
                    self._document["selection"]["object_id"]
                    or multi_rows[0]["id"]
                )
                self._original_rect = QRectF(multi_bounds)
                delta = event.position() - multi_bounds.center()
                self._rotation_start_angle = math.degrees(
                    math.atan2(delta.y(), delta.x())
                )
                self._resize_original_geometries = {
                    str(row["id"]): (
                        float(row["x"]),
                        float(row["y"]),
                        float(row["width"]),
                        float(row["height"]),
                    )
                    for row in multi_rows
                }
                self._rotation_original_values = {
                    str(row["id"]): float(row.get("rotation", 0.0))
                    for row in multi_rows
                }
                self._rotation_label = "0°"
                event.accept()
                return

        if self._tool == "pencil":
            if (
                self._rulers_visible
                and (
                    self._press_position.x() <= self._ruler_size
                    or self._press_position.y() <= self._ruler_size
                )
            ):
                event.ignore()
                return
            self._interaction = "pencil_draw"
            self._pencil_points = [QPointF(self._press_position)]
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return

        if self._tool in _CREATE_TOOLS - _STICKY_SHAPE_TOOLS:
            if (
                self._rulers_visible
                and (
                    self._press_position.x() <= self._ruler_size
                    or self._press_position.y() <= self._ruler_size
                )
            ):
                event.ignore()
                return
            # Structural/content tools are one-shot and must be able to draw
            # over existing objects (notably a new frame around a selection).
            self._interaction = "create"
            self._preview_rect = QRectF(
                self._press_position, self._press_position
            )
            self._preview_line_end = QPointF(self._press_position)
            event.accept()
            return

        selected_row = self._selected_row()
        if selected_row is not None and not selected_row["locked"]:
            prototype_handle = self.prototype_connection_handle_rect()
            if prototype_handle.contains(event.position()):
                self._interaction = "prototype_connection"
                self._active_object_id = str(selected_row["id"])
                self._prototype_drag_position = QPointF(event.position())
                self._prototype_hover_artboard_id = ""
                self.setCursor(Qt.CursorShape.CrossCursor)
                event.accept()
                return
            selected_rect = self._object_rect(selected_row)
            local_position = self._unrotated_point(
                event.position(),
                selected_rect,
                float(selected_row.get("rotation", 0.0)),
                selected_row.get("constraints"),
            )
            if (
                event.modifiers() & Qt.KeyboardModifier.AltModifier
                and selected_rect.contains(local_position)
            ):
                # At very small zoom levels every resize handle can overlap
                # the object's center. Alt-drag remains an unambiguous
                # duplicate gesture and takes priority over those handles.
                self._interaction = "alt_duplicate_pending"
                self._active_object_id = str(selected_row["id"])
                self._original_rect = QRectF(selected_rect)
                self._drag_offset = event.position() - selected_rect.topLeft()
                self._alt_duplicate_source_ids = list(
                    self._document["selection"]["object_ids"]
                ) or [str(selected_row["id"])]
                event.accept()
                return
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
            radius_corner = self._radius_handle_at(
                selected_row,
                selected_rect,
                local_position,
            )
            if radius_corner:
                self._interaction = "radius"
                self._active_object_id = str(selected_row["id"])
                self._radius_active_corner = radius_corner
                self._radius_hover_corner = radius_corner
                self._radius_original = max(
                    0.0,
                    float((selected_row.get("style") or {}).get("radius") or 0.0),
                )
                self._radius_preview = self._radius_original
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                event.accept()
                return
            arc_handle = self._arc_handle_at(
                selected_row,
                selected_rect,
                local_position,
            )
            if arc_handle:
                self._interaction = f"arc_{arc_handle}"
                self._active_object_id = str(selected_row["id"])
                self._arc_active_handle = arc_handle
                self._arc_hover_handle = arc_handle
                self._arc_label = ""
                self._arc_original_content = copy.deepcopy(
                    dict(selected_row.get("content") or {})
                )
                if arc_handle == "sweep":
                    self._arc_drag_last_angle = 0.0
                    self._arc_drag_unwrapped_angle = 0.0
                    self._arc_drag_direction = 0
                self.setCursor(Qt.CursorShape.CrossCursor)
                event.accept()
                return
            shape_gizmo = self._shape_gizmo_at(
                selected_row, selected_rect, local_position
            )
            if shape_gizmo:
                self._interaction = shape_gizmo
                self._active_object_id = str(selected_row["id"])
                self._shape_gizmo_active = shape_gizmo
                self._shape_gizmo_hover = shape_gizmo
                self._shape_gizmo_label = ""
                self._shape_gizmo_original_content = copy.deepcopy(
                    dict(selected_row.get("content") or {})
                )
                self._shape_gizmo_original_style = copy.deepcopy(
                    dict(selected_row.get("style") or {})
                )
                self._shape_gizmo_original_geometry = (
                    float(selected_row["x"]), float(selected_row["y"]),
                    float(selected_row["width"]), float(selected_row["height"]),
                )
                self.setCursor(Qt.CursorShape.CrossCursor)
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
                self._rotation_label = f"{self._original_rotation:g}°"
                event.accept()
                return
            for name in _HANDLE_NAMES:
                if self._handle_rects(selected_rect)[name].contains(local_position):
                    self._interaction = (
                        "scale"
                        if self._tool == "scale"
                        else "resize"
                    )
                    self._active_object_id = selected_row["id"]
                    self._active_handle = name
                    self._original_rect = QRectF(selected_rect)
                    self._resize_original_geometries = {
                        str(selected_row["id"]): (
                            float(selected_row["x"]),
                            float(selected_row["y"]),
                            float(selected_row["width"]),
                            float(selected_row["height"]),
                        )
                    }
                    event.accept()
                    return

        if self._tool in _STICKY_SHAPE_TOOLS:
            if (
                self._rulers_visible
                and (
                    self._press_position.x() <= self._ruler_size
                    or self._press_position.y() <= self._ruler_size
                )
            ):
                event.ignore()
                return
            # Shape tools stay active. Existing objects and their gizmos keep
            # pointer priority; only a drag that starts on empty canvas creates
            # another shape of the active kind.
            creation_hits = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            hit_rows = [
                row
                for object_id in creation_hits
                for row in self._document["objects"]
                if row["id"] == object_id
            ]
            # A frame is a container surface, not a blocking shape. Dragging
            # on an otherwise empty part of a frame creates a child inside it.
            frame_surface_only = bool(hit_rows) and all(
                str(row.get("kind") or "") == "frame"
                for row in hit_rows
            )
            if not creation_hits or frame_surface_only:
                self._interaction = "create"
                self._preview_rect = QRectF(
                    self._press_position, self._press_position
                )
                self._preview_line_end = QPointF(self._press_position)
                event.accept()
                return

        hit_ids = self.object_ids_at(
            float(event.position().x()),
            float(event.position().y()),
        )
        modifiers = event.modifiers()
        deep_select = bool(
            modifiers & Qt.KeyboardModifier.ControlModifier
        )
        selected = self._selection_target_from_hits(
            hit_ids,
            deep=deep_select,
        )
        alt_pressed = bool(
            event.modifiers() & Qt.KeyboardModifier.AltModifier
        )
        current = str(self._document["selection"]["object_id"] or "")
        if hit_ids and alt_pressed and current in hit_ids:
            selected = current
            self._alt_duplicate_cycle_id = hit_ids[
                (hit_ids.index(current) + 1) % len(hit_ids)
            ]
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
        if selected and deep_select:
            self.object_selection_requested.emit(selected, "replace")
            self._cancel_interaction()
            event.accept()
            return
        if selected and modifiers & Qt.KeyboardModifier.ShiftModifier:
            self.object_selection_requested.emit(selected, "toggle")
            self._cancel_interaction()
            event.accept()
            return
        if not selected:
            self._interaction = "marquee"
            self._preview_rect = QRectF(
                self._press_position,
                self._press_position,
            )
            self._marquee_include_nested = deep_select
            self._marquee_mode = (
                "toggle"
                if modifiers & Qt.KeyboardModifier.ShiftModifier
                else "replace"
            )
        else:
            if selected not in self._document["selection"]["object_ids"]:
                self.object_selection_requested.emit(selected, "replace")
            if selected_row is not None and not selected_row["locked"]:
                if alt_pressed:
                    self._interaction = "alt_duplicate_pending"
                    self._active_object_id = selected
                    self._original_rect = QRectF(
                        self._object_rect(selected_row)
                    )
                    self._drag_offset = (
                        event.position() - self._original_rect.topLeft()
                    )
                    self._alt_duplicate_source_ids = list(
                        self._document["selection"]["object_ids"]
                    )
                    if selected not in self._alt_duplicate_source_ids:
                        self._alt_duplicate_source_ids = [selected]
                else:
                    self._begin_object_move(
                        selected_row,
                        QPointF(event.position()),
                    )
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self.set_measurements_visible(
            bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        )
        if self._prototype_preview_enabled:
            hit_ids = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            target = hit_ids[0] if hit_ids else ""
            if target != self._prototype_hover_object_id:
                if self._prototype_hover_object_id:
                    self.prototype_trigger_requested.emit(
                        self._prototype_hover_object_id,
                        "mouse_leave",
                        "",
                    )
                self._prototype_hover_object_id = target
                if target:
                    self.prototype_trigger_requested.emit(
                        target,
                        "mouse_enter",
                        "",
                    )
                    self.prototype_trigger_requested.emit(
                        target,
                        "hover",
                        "",
                    )
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
                if target
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return
        if self._interaction in {"smart_reorder_pending", "smart_reorder"}:
            if self._interaction == "smart_reorder_pending":
                delta = event.position() - self._press_position
                if abs(delta.x()) + abs(delta.y()) < 4.0:
                    event.accept()
                    return
                self._interaction = "smart_reorder"
            self._preview_smart_reorder(
                QPointF(event.position()),
                event.modifiers(),
            )
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if self._interaction.startswith("smart_gap_"):
            original_document = self._smart_gap_original_document
            if original_document is not None:
                _viewport, scale = self._artboard_viewport()
                delta = (
                    event.position().x() - self._press_position.x()
                    if self._smart_gap_axis == "horizontal"
                    else event.position().y() - self._press_position.y()
                ) / max(0.0001, scale)
                target_gap = self._smart_gap_original_gap + float(delta)
                from app.painter_ui_smart_selection import (
                    inspect_ui_selection_spacing,
                    plan_ui_selection_tidy,
                )

                original_report = inspect_ui_selection_spacing(
                    original_document,
                    axis="auto",
                )
                if original_report["axis"] == "grid":
                    other_axis = (
                        "vertical"
                        if self._smart_gap_axis == "horizontal"
                        else "horizontal"
                    )
                    gap: object = {
                        self._smart_gap_axis: target_gap,
                        other_axis: self._smart_gap_other_gap,
                    }
                    plan_axis = "auto"
                else:
                    gap = target_gap
                    plan_axis = self._smart_gap_axis
                plan = plan_ui_selection_tidy(
                    original_document,
                    axis=plan_axis,
                    gap=gap,
                )
                changes = plan.get("changes_by_id") or {}
                for document in (self._document, self._effective_document):
                    by_id = {
                        str(row["id"]): row
                        for row in document["objects"]
                    }
                    for object_id, geometry in changes.items():
                        row = by_id.get(str(object_id))
                        if row is None:
                            continue
                        row.update(
                            {
                                key: float(value)
                                for key, value in geometry.items()
                                if key in {"x", "y"}
                            }
                        )
                        if document is self._document:
                            self._sync_preview_geometry(row)
                self._smart_gap_label = f"{target_gap:g}px"
                self._smart_gap_label_position = QPointF(event.position())
                self.update()
            event.accept()
            return
        if self._interaction == "comment_place":
            self._preview_rect = QRectF(self._press_position, event.position()).normalized()
            self.update()
            event.accept()
            return
        if self._interaction == "comment_move":
            self._comment_drag_position = QPointF(event.position())
            self.update()
            event.accept()
            return
        if self._interaction == "prototype_connection":
            self._prototype_drag_position = QPointF(event.position())
            target = self._prototype_target_artboard(event.position())
            source_row = next(
                (
                    row
                    for row in self._document["objects"]
                    if row["id"] == self._active_object_id
                ),
                None,
            )
            self._prototype_hover_artboard_id = (
                target
                if source_row is not None
                and target != str(source_row["artboard_id"])
                else ""
            )
            self.update()
            event.accept()
            return
        if self._interaction == "alt_duplicate_pending":
            delta = event.position() - self._press_position
            if abs(delta.x()) + abs(delta.y()) < 4.0:
                event.accept()
                return
            self.objects_duplicate_requested.emit(
                list(self._alt_duplicate_source_ids)
            )
            selected = str(
                self._document["selection"]["object_id"] or ""
            )
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == selected
                ),
                None,
            )
            if row is None:
                self._cancel_interaction()
                event.accept()
                return
            original_offset = QPointF(self._drag_offset)
            self._begin_object_move(row, QPointF(self._press_position))
            self._drag_offset = original_offset
            self._alt_duplicate_drag_active = True
        if self._interaction == "image_focal":
            row = next(
                item
                for item in self._document["objects"]
                if item["id"] == self._active_object_id
            )
            rect = self._object_rect(row)
            local_position = self._unrotated_point(
                event.position(),
                rect,
                float(row.get("rotation", 0.0)),
                row.get("constraints"),
            )
            focal_x = max(
                0.0,
                min(
                    1.0,
                    (local_position.x() - rect.left())
                    / max(0.0001, rect.width()),
                ),
            )
            focal_y = max(
                0.0,
                min(
                    1.0,
                    (local_position.y() - rect.top())
                    / max(0.0001, rect.height()),
                ),
            )
            for document in (self._document, self._effective_document):
                target = next(
                    item
                    for item in document["objects"]
                    if item["id"] == self._active_object_id
                )
                content = copy.deepcopy(dict(target.get("content") or {}))
                content["focal_x"] = focal_x
                content["focal_y"] = focal_y
                target["content"] = content
            self.update()
            event.accept()
            return
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
                big_nudge=bool(
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                ),
                opposite=bool(
                    event.modifiers() & Qt.KeyboardModifier.AltModifier
                ),
                all_sides=bool(
                    event.modifiers() & Qt.KeyboardModifier.AltModifier
                    and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                ),
            )
            self._preview_auto_layout(self._active_object_id, layout)
            event.accept()
            return
        if self._interaction == "pencil_draw":
            point = QPointF(event.position())
            if (
                not self._pencil_points
                or math.hypot(
                    point.x() - self._pencil_points[-1].x(),
                    point.y() - self._pencil_points[-1].y(),
                )
                >= 1.5
            ):
                self._pencil_points.append(point)
                self.update()
            event.accept()
            return
        if self._interaction == "create":
            raw_end = QPointF(event.position())
            self._preview_rect = QRectF(
                self._press_position,
                raw_end,
            ).normalized()
            if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._preview_rect = self._smart_snap_create_rect(
                    self._preview_rect
                )
                self._preview_line_end = QPointF(
                    self._preview_rect.right()
                    if raw_end.x() >= self._press_position.x()
                    else self._preview_rect.left(),
                    self._preview_rect.bottom()
                    if raw_end.y() >= self._press_position.y()
                    else self._preview_rect.top(),
                )
            else:
                self._preview_line_end = raw_end
                self._guide_x = None
                self._guide_y = None
                self._smart_guide_plan = {}
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
            self._view_offset = self._clamped_view_offset(
                self._view_scale,
                self._pan_origin + (event.position() - self._pan_start),
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
        if self._interaction == "auto_layout_reorder":
            context = self._auto_layout_reorder_context
            active_id = self._active_object_id
            by_id = {
                str(row["id"]): row for row in self._document["objects"]
            }
            sibling_ids = [
                object_id
                for object_id in context.get("ordered_child_ids", [])
                if object_id != active_id and object_id in by_id
            ]
            axis = "x" if context.get("mode") == "horizontal" else "y"
            pointer = (
                float(event.position().x())
                if axis == "x"
                else float(event.position().y())
            )
            centers = [
                (
                    float(self._object_rect(by_id[object_id]).center().x())
                    if axis == "x"
                    else float(self._object_rect(by_id[object_id]).center().y())
                )
                for object_id in sibling_ids
            ]
            target = sum(1 for center in centers if pointer > center)
            self._auto_layout_reorder_target_index = target
            parent = by_id.get(str(context.get("parent_id") or ""))
            sibling_rects = [self._object_rect(by_id[object_id]) for object_id in sibling_ids]
            if parent is not None and sibling_rects:
                parent_rect = self._object_rect(parent)
                if axis == "x":
                    boundary = (
                        sibling_rects[0].left()
                        if target == 0
                        else sibling_rects[-1].right()
                        if target >= len(sibling_rects)
                        else (sibling_rects[target - 1].right() + sibling_rects[target].left()) * 0.5
                    )
                    self._auto_layout_reorder_indicator = QRectF(
                        boundary - 1.0, parent_rect.top(), 2.0, parent_rect.height()
                    )
                else:
                    boundary = (
                        sibling_rects[0].top()
                        if target == 0
                        else sibling_rects[-1].bottom()
                        if target >= len(sibling_rects)
                        else (sibling_rects[target - 1].bottom() + sibling_rects[target].top()) * 0.5
                    )
                    self._auto_layout_reorder_indicator = QRectF(
                        parent_rect.left(), boundary - 1.0, parent_rect.width(), 2.0
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
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self._guide_x = None; self._guide_y = None; self._smart_guide_plan = {}
            else:
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
                effective_row = next(
                    (
                        item
                        for item in self._effective_document["objects"]
                        if item["id"] == moving_row["id"]
                    ),
                    None,
                )
                if effective_row is not None:
                    effective_row["x"] = moving_row["x"]
                    effective_row["y"] = moving_row["y"]
                geometry = self._resolved_geometry.get(moving_row["id"])
                if geometry is not None:
                    geometry["x"] = moving_row["x"]
                    geometry["y"] = moving_row["y"]
            self._hierarchy_drop_preview_id = (
                ""
                if self._alt_duplicate_drag_active
                else self._canvas_reparent_target(event.position())
            )
            self.update()
            event.accept()
            return
        if self._interaction == "radius":
            row = next(
                (
                    item for item in self._document["objects"]
                    if item["id"] == self._active_object_id
                ),
                None,
            )
            if row is not None:
                _viewport, scale = self._artboard_viewport()
                delta = event.position() - self._press_position
                sign_x = -1.0 if self._radius_active_corner in {"ne", "se"} else 1.0
                sign_y = -1.0 if self._radius_active_corner in {"sw", "se"} else 1.0
                inward = (delta.x() * sign_x + delta.y() * sign_y) * 0.5
                maximum = max(0.0, min(float(row["width"]), float(row["height"])) * 0.5)
                radius = max(
                    0.0,
                    min(maximum, self._radius_original + inward / max(0.0001, scale)),
                )
                self._radius_preview = radius
                for document in (self._document, self._effective_document):
                    target = next(
                        (
                            item for item in document["objects"]
                            if item["id"] == self._active_object_id
                        ),
                        None,
                    )
                    if target is None:
                        continue
                    style = copy.deepcopy(dict(target.get("style") or {}))
                    style["radius"] = radius
                    style["corner_radii"] = {
                        key: radius
                        for key in (
                            "top_left", "top_right",
                            "bottom_right", "bottom_left",
                        )
                    }
                    target["style"] = style
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
                self.update()
            event.accept()
            return
        if self._interaction.startswith("arc_"):
            row = next(
                (
                    item for item in self._document["objects"]
                    if item["id"] == self._active_object_id
                ),
                None,
            )
            if row is not None:
                rect = self._object_rect(row)
                local = self._unrotated_point(
                    event.position(),
                    rect,
                    float(row.get("rotation", 0.0)),
                    row.get("constraints"),
                )
                center = rect.center()
                dx = (local.x() - center.x()) / max(0.0001, rect.width() * 0.5)
                dy = (local.y() - center.y()) / max(0.0001, rect.height() * 0.5)
                angle = math.degrees(math.atan2(dy, dx))
                source = dict(row.get("content") or {})
                start = float(source.get("start_angle", 0.0)) % 360.0
                sweep = max(
                    -360.0,
                    min(360.0, float(source.get("sweep_angle", 360.0))),
                )
                if abs(sweep) < 1.0:
                    sweep = -1.0 if sweep < 0.0 else 1.0
                inner = max(0.0, min(0.95, float(source.get("inner_radius", 0.0))))
                handle = self._arc_active_handle
                if handle == "sweep":
                    relative_angle = (
                        (angle - start + 180.0) % 360.0
                    ) - 180.0
                    delta = (
                        (
                            relative_angle
                            - self._arc_drag_last_angle
                            + 180.0
                        )
                        % 360.0
                    ) - 180.0
                    self._arc_drag_last_angle = relative_angle
                    self._arc_drag_unwrapped_angle += delta
                    if self._arc_drag_direction == 0 and abs(delta) >= 0.05:
                        # Screen Y grows downward. Figma reports upward as a
                        # positive sweep and downward as a negative sweep.
                        self._arc_drag_direction = 1 if delta > 0.0 else -1
                    if self._arc_drag_direction > 0:
                        sweep = max(
                            -359.999,
                            min(-1.0, self._arc_drag_unwrapped_angle - 360.0),
                        )
                    elif self._arc_drag_direction < 0:
                        sweep = min(
                            359.999,
                            max(1.0, 360.0 + self._arc_drag_unwrapped_angle),
                        )
                    self._arc_label = f"Sweep {round(sweep / 360.0 * 100.0):g}%"
                elif handle == "start":
                    end = (start + sweep) % 360.0
                    start = angle % 360.0
                    remaining = (end - start) % 360.0
                    sweep = remaining - 360.0 if sweep < 0.0 else remaining
                    if abs(sweep) < 1.0:
                        sweep = -1.0 if sweep < 0.0 else 1.0
                    self._arc_label = f"Start {round(start):g}°"
                elif handle == "ratio":
                    original = (
                        self._arc_original_content
                        if self._arc_original_content
                        else source
                    )
                    start = float(original.get("start_angle", start)) % 360.0
                    original_sweep = max(
                        -360.0,
                        min(360.0, float(original.get("sweep_angle", sweep))),
                    )
                    inner = max(0.0, min(0.95, math.hypot(dx, dy)))
                    if abs(original_sweep) < 359.999:
                        middle = math.radians(start + original_sweep * 0.5)
                        same_side = (
                            dx * math.cos(middle) + dy * math.sin(middle)
                        ) >= 0.0
                        sweep = (
                            original_sweep
                            if same_side
                            else original_sweep
                            - math.copysign(360.0, original_sweep)
                        )
                    self._arc_label = f"Ratio {round(inner * 100.0):g}%"
                content = copy.deepcopy(source)
                content.update(
                    {
                        "start_angle": start,
                        "sweep_angle": sweep,
                        "inner_radius": inner,
                    }
                )
                for document in (self._document, self._effective_document):
                    target = next(
                        (
                            item for item in document["objects"]
                            if item["id"] == self._active_object_id
                        ),
                        None,
                    )
                    if target is not None:
                        target["kind"] = "arc"
                        target["content"] = copy.deepcopy(content)
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
            event.accept()
            return
        if self._interaction in {
            "shape_count", "shape_ratio", "shape_radius",
            "line_start", "line_end",
        }:
            row = next(
                (item for item in self._document["objects"] if item["id"] == self._active_object_id),
                None,
            )
            if row is not None:
                rect = self._object_rect(row)
                local = self._unrotated_point(
                    event.position(), rect, float(row.get("rotation", 0.0)), row.get("constraints")
                )
                content = copy.deepcopy(dict(row.get("content") or {}))
                style = copy.deepcopy(dict(row.get("style") or {}))
                if self._interaction == "shape_count":
                    original = int(self._shape_gizmo_original_content.get("point_count", 5))
                    count = max(3, min(60, original + round((local.x() - self._press_position.x()) / 12.0)))
                    content["point_count"] = count
                    self._shape_gizmo_label = f"Count {count}"
                elif self._interaction == "shape_ratio":
                    center = rect.center()
                    dx = (local.x() - center.x()) / max(0.0001, rect.width() * 0.5)
                    dy = (local.y() - center.y()) / max(0.0001, rect.height() * 0.5)
                    ratio = max(0.05, min(0.95, math.hypot(dx, dy)))
                    content["inner_radius"] = ratio
                    self._shape_gizmo_label = f"Ratio {round(ratio * 100):g}%"
                elif self._interaction == "shape_radius":
                    outer = self._arc_point(
                        rect, float(content.get("rotation_offset", -90.0))
                    )
                    center = rect.center()
                    inward = center - outer
                    inward_length = max(
                        0.0001,
                        math.hypot(inward.x(), inward.y()),
                    )
                    inward = QPointF(
                        inward.x() / inward_length,
                        inward.y() / inward_length,
                    )
                    offset = local - outer
                    projected = (
                        offset.x() * inward.x() + offset.y() * inward.y()
                    )
                    _viewport, scale = self._artboard_viewport()
                    radius = max(
                        0.0,
                        min(
                            min(float(row["width"]), float(row["height"])) * 0.45,
                            (projected - 14.0) / max(0.0001, scale),
                        ),
                    )
                    content["corner_radius"] = radius
                    style["radius"] = radius
                    self._shape_gizmo_label = f"Radius {round(radius):g}"
                else:
                    viewport, scale = self._artboard_viewport()
                    point = QPointF(
                        (local.x() - viewport.left()) / max(0.0001, scale),
                        (local.y() - viewport.top()) / max(0.0001, scale),
                    )
                    x, y, width, height = self._shape_gizmo_original_geometry
                    original_start = QPointF(x, y)
                    original_end = QPointF(x + width, y + height)
                    start = point if self._interaction == "line_start" else original_start
                    end = point if self._interaction == "line_end" else original_end
                    left, top = min(start.x(), end.x()), min(start.y(), end.y())
                    next_width = max(1.0, abs(end.x() - start.x()))
                    next_height = max(1.0, abs(end.y() - start.y()))
                    content["start_anchor"] = [
                        (start.x() - left) / next_width,
                        (start.y() - top) / next_height,
                    ]
                    content["end_anchor"] = [
                        (end.x() - left) / next_width,
                        (end.y() - top) / next_height,
                    ]
                    row.update({"x": left, "y": top, "width": next_width, "height": next_height})
                    self._shape_gizmo_label = f"{round(next_width):g} × {round(next_height):g}"
                row["content"] = content
                row["style"] = style
                effective = next(
                    (item for item in self._effective_document["objects"] if item["id"] == row["id"]),
                    None,
                )
                if effective is not None:
                    effective.update(copy.deepcopy(row))
                self.update()
            event.accept()
            return
        if self._interaction in {"resize", "scale", "smart_resize"}:
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
            if (
                self._interaction in {"resize", "smart_resize"}
                and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            ):
                rect = self._smart_snap_resize_rect(row, rect)
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
                self._sync_preview_geometry(row)
                self.update()
            event.accept()
            return
        if self._interaction in {"resize_multi", "scale_multi", "smart_resize_multi"}:
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
                    if self._interaction == "scale_multi":
                        self._sync_preview_geometry(row)
                self.update()
            event.accept()
            return
        if self._interaction in {"rotate", "rotate_multi"}:
            row = next(
                row
                for row in self._document["objects"]
                if row["id"] == self._active_object_id
            )
            pivot = (
                self._original_rect.center()
                if self._interaction == "rotate_multi"
                else ui_pivot_point(
                    self._original_rect,
                    row.get("constraints"),
                )
            )
            delta = event.position() - pivot
            angle = math.degrees(math.atan2(delta.y(), delta.x()))
            pointer_delta = (
                (angle - self._rotation_start_angle + 180.0) % 360.0
            ) - 180.0
            rotation_delta = -pointer_delta
            if self._interaction == "rotate_multi":
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    rotation_delta = round(rotation_delta / 15.0) * 15.0
                viewport, scale = self._artboard_viewport()
                pivot_doc = QPointF(
                    (pivot.x() - viewport.x()) / max(0.0001, scale),
                    (pivot.y() - viewport.y()) / max(0.0001, scale),
                )
                radians = math.radians(rotation_delta)
                cosine = math.cos(radians)
                sine = math.sin(radians)
                for moving in self._document["objects"]:
                    original = self._resize_original_geometries.get(
                        str(moving["id"])
                    )
                    if original is None:
                        continue
                    x, y, width, height = original
                    dx = x + width * 0.5 - pivot_doc.x()
                    dy = y + height * 0.5 - pivot_doc.y()
                    center_x = pivot_doc.x() + cosine * dx + sine * dy
                    center_y = pivot_doc.y() - sine * dx + cosine * dy
                    moving["x"] = center_x - width * 0.5
                    moving["y"] = center_y - height * 0.5
                    original_rotation = self._rotation_original_values.get(
                        str(moving["id"]),
                        float(moving.get("rotation", 0.0)),
                    )
                    moving["rotation"] = (
                        (original_rotation + rotation_delta + 180.0) % 360.0
                    ) - 180.0
                    self._sync_preview_geometry(moving)
                self._rotation_label = f"{rotation_delta:g}°"
            else:
                rotation = self._original_rotation + rotation_delta
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    rotation = round(rotation / 15.0) * 15.0
                row["rotation"] = ((rotation + 180.0) % 360.0) - 180.0
                self._rotation_label = f"{row['rotation']:g}°"
            self.update()
            event.accept()
            return
        smart_report = self._smart_selection_report()
        smart_bounds = self._selection_bounds(self._multi_transform_rows())
        smart_hovered = bool(
            smart_report is not None
            and not smart_bounds.isNull()
            and smart_bounds.adjusted(-8.0, -8.0, 8.0, 8.0).contains(
                event.position()
            )
        )
        if smart_hovered != self._smart_selection_hovered:
            self._smart_selection_hovered = smart_hovered
            self.update()
        if smart_hovered:
            for center_handle in self._smart_selection_center_handles():
                if center_handle["rect"].contains(event.position()):
                    self.setToolTip("Mark and reorder layer")
                    self.setCursor(Qt.CursorShape.PointingHandCursor)
                    event.accept()
                    return
            for smart_handle in self._smart_selection_gap_handles():
                if smart_handle["rect"].contains(event.position()):
                    self.setToolTip("Adjust space between")
                    self.setCursor(
                        Qt.CursorShape.SizeHorCursor
                        if smart_handle["axis"] == "horizontal"
                        else Qt.CursorShape.SizeVerCursor
                    )
                    event.accept()
                    return
        selected_row = self._selected_row()
        hover_corner = ""
        hover_arc = ""
        hover_shape = ""
        if selected_row is not None and not selected_row.get("locked", False):
            rect = self._object_rect(selected_row)
            local = self._unrotated_point(
                event.position(),
                rect,
                float(selected_row.get("rotation", 0.0)),
                selected_row.get("constraints"),
            )
            hover_corner = self._radius_handle_at(selected_row, rect, local)
            hover_arc = self._arc_handle_at(selected_row, rect, local)
            hover_shape = self._shape_gizmo_at(selected_row, rect, local)
        if hover_shape:
            self._shape_gizmo_hover = hover_shape
            self.setToolTip(
                {
                    "shape_count": "Point count",
                    "shape_ratio": "Inner ratio",
                    "shape_radius": "Corner radius",
                    "line_start": "Line start",
                    "line_end": "Line end",
                }.get(hover_shape, "Shape control")
            )
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        self._shape_gizmo_hover = ""
        if hover_arc:
            if hover_arc != self._arc_hover_handle:
                self._arc_hover_handle = hover_arc
                self.update()
            self.setToolTip(
                {
                    "start": "Arc start angle",
                    "sweep": "Arc sweep",
                    "ratio": "Inner radius",
                }.get(hover_arc, "Arc")
            )
            self.setCursor(Qt.CursorShape.CrossCursor)
            event.accept()
            return
        if self._arc_hover_handle:
            self._arc_hover_handle = ""
            self.update()
        if hover_corner:
            if hover_corner != self._radius_hover_corner:
                self._radius_hover_corner = hover_corner
                self.update()
            self.setToolTip("모서리 반경 드래그")
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            event.accept()
            return
        if self._radius_hover_corner:
            self._radius_hover_corner = ""
            self.update()
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
        if self._tool == "pan":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._tool == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:
        if self._prototype_preview_enabled:
            hit_ids = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            target = hit_ids[0] if hit_ids else ""
            if target and target == self._prototype_pressed_object_id:
                self.prototype_trigger_requested.emit(target, "click", "")
            self._prototype_pressed_object_id = ""
            event.accept()
            return
        interaction = self._interaction
        object_id = self._active_object_id
        if interaction == "comment_place":
            area = QRectF(self._press_position, event.position()).normalized()
            placement = self._comment_placement(self._press_position, area)
            self._cancel_interaction()
            if placement is not None:
                self.comment_placement_requested.emit(placement)
            event.accept()
            return
        if interaction == "comment_move" and self._active_comment_id:
            comment_id = self._active_comment_id
            distance = event.position() - self._press_position
            placement = self._comment_placement(QPointF(event.position()))
            self._cancel_interaction()
            self._active_comment_id = comment_id
            self._comment_drag_position = None
            if placement is not None and abs(distance.x()) + abs(distance.y()) >= 4.0:
                self.comment_move_requested.emit(
                    comment_id,
                    {
                        "object_id": placement["object_id"],
                        "artboard_id": placement["artboard_id"],
                        "anchor": {"x": placement["x"], "y": placement["y"]},
                        "region": None,
                    },
                )
            else:
                self.comment_selected.emit(comment_id)
            self.update()
            event.accept()
            return
        if interaction == "prototype_connection" and object_id:
            target_artboard_id = self._prototype_target_artboard(
                event.position()
            )
            source_row = next(
                (
                    row
                    for row in self._document["objects"]
                    if row["id"] == object_id
                ),
                None,
            )
            if (
                source_row is not None
                and target_artboard_id
                and target_artboard_id != str(source_row["artboard_id"])
            ):
                self.prototype_connection_requested.emit(
                    object_id,
                    target_artboard_id,
                    "",
                )
        elif interaction == "alt_duplicate_pending":
            if self._alt_duplicate_cycle_id:
                self.object_selection_requested.emit(
                    self._alt_duplicate_cycle_id,
                    "replace",
                )
        elif interaction in {"guide_horizontal", "guide_vertical"}:
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
        elif interaction == "image_focal" and object_id:
            row = next(
                (
                    item
                    for item in self._document["objects"]
                    if item["id"] == object_id
                ),
                None,
            )
            if row is not None:
                content = row.get("content") or {}
                self.image_focal_requested.emit(
                    object_id,
                    float(content.get("focal_x", 0.5)),
                    float(content.get("focal_y", 0.5)),
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
        elif interaction == "pencil_draw":
            if len(self._pencil_points) >= 2:
                viewport, scale = self._artboard_viewport()
                logical_points = [
                    (
                        (point.x() - viewport.x()) / max(0.0001, scale),
                        (point.y() - viewport.y()) / max(0.0001, scale),
                    )
                    for point in self._pencil_points
                ]
                if math.dist(logical_points[0], logical_points[-1]) >= 1.0:
                    self.pencil_create_requested.emit(logical_points)
        elif interaction == "create":
            rect = self._preview_rect.normalized()
            line_like = self._tool in {"line", "arrow"}
            text_click = (
                self._tool == "text"
                and rect.width() < 6.0
                and rect.height() < 6.0
            )
            line_length = math.hypot(
                self._preview_line_end.x() - self._press_position.x(),
                self._preview_line_end.y() - self._press_position.y(),
            )
            if (
                text_click
                or line_like and line_length >= 6.0
                or not line_like
                and rect.width() >= 6.0
                and rect.height() >= 6.0
            ):
                viewport, scale = self._artboard_viewport()
                if line_like:
                    values = (
                        self._snap(
                            (self._press_position.x() - viewport.x())
                            / max(0.0001, scale)
                        ),
                        self._snap(
                            (self._press_position.y() - viewport.y())
                            / max(0.0001, scale)
                        ),
                        self._snap(
                            (self._preview_line_end.x() - self._press_position.x())
                            / max(0.0001, scale)
                        ),
                        self._snap(
                            (self._preview_line_end.y() - self._press_position.y())
                            / max(0.0001, scale)
                        ),
                    )
                elif text_click:
                    values = (
                        self._snap(
                            (self._press_position.x() - viewport.x())
                            / max(0.0001, scale)
                        ),
                        self._snap(
                            (self._press_position.y() - viewport.y())
                            / max(0.0001, scale)
                        ),
                        1.0,
                        1.0,
                    )
                else:
                    values = (
                        self._snap((rect.x() - viewport.x()) / max(0.0001, scale)),
                        self._snap((rect.y() - viewport.y()) / max(0.0001, scale)),
                        max(1.0, self._snap(rect.width() / max(0.0001, scale))),
                        max(1.0, self._snap(rect.height() / max(0.0001, scale))),
                    )
                if self._tool == "section":
                    self.section_create_requested.emit(*values)
                else:
                    self.object_create_requested.emit(self._tool, *values)
        elif interaction == "marquee":
            rect = self._preview_rect.normalized()
            active = self._document["active_artboard_id"]
            scope_parent = str(self._edit_scope_id or "")
            selected_ids = [
                row["id"]
                for row in self._visible_objects()
                if row["artboard_id"] == active
                and not bool(row.get("locked"))
                and (
                    self._marquee_include_nested
                    or str(row.get("parent_id") or "") == scope_parent
                )
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
        elif interaction == "smart_reorder":
            selected_ids = set(
                str(value)
                for value in self._document["selection"]["object_ids"]
            )
            self.objects_changes_requested.emit(
                {
                    str(row["id"]): {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                    }
                    for row in self._document["objects"]
                    if str(row["id"]) in selected_ids
                }
            )
        elif interaction.startswith("smart_gap_"):
            selected_ids = set(
                str(value)
                for value in self._document["selection"]["object_ids"]
            )
            self.objects_changes_requested.emit(
                {
                    str(row["id"]): {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                    }
                    for row in self._document["objects"]
                    if str(row["id"]) in selected_ids
                }
            )
        elif interaction in {"scale", "scale_multi"}:
            rows_by_id = {
                str(row["id"]): row for row in self._document["objects"]
            }
            target_ids = list(self._resize_original_geometries)
            current_bounds = self._geometry_bounds(
                [
                    rows_by_id[target_id]
                    for target_id in target_ids
                    if target_id in rows_by_id
                ]
            )
            original_bounds = self._geometry_bounds(
                [
                    {
                        "x": geometry[0],
                        "y": geometry[1],
                        "width": geometry[2],
                        "height": geometry[3],
                    }
                    for geometry in self._resize_original_geometries.values()
                ]
            )
            if target_ids and not current_bounds.isNull():
                self.objects_scale_requested.emit(
                    {
                        "object_ids": target_ids,
                        "scale_x": float(current_bounds.width())
                        / max(0.0001, float(original_bounds.width())),
                        "scale_y": float(current_bounds.height())
                        / max(0.0001, float(original_bounds.height())),
                        "origin": (
                            "center"
                            if event.modifiers()
                            & Qt.KeyboardModifier.AltModifier
                            else {
                                "nw": "bottom_right",
                                "n": "bottom_center",
                                "ne": "bottom_left",
                                "e": "left_center",
                                "se": "top_left",
                                "s": "top_center",
                                "sw": "top_right",
                                "w": "right_center",
                            }[self._active_handle]
                        ),
                        "scale_visuals": True,
                    }
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
        elif interaction in {"smart_resize", "smart_resize_multi"} and object_id:
            from app.painter_ui_smart_selection import (
                capture_ui_smart_layout,
                plan_ui_smart_mutation_reflow,
            )

            layout = capture_ui_smart_layout(self._smart_resize_original_document)
            plan = plan_ui_smart_mutation_reflow(
                self._document, layout=layout, resize=True
            )
            by_id = {str(row["id"]): row for row in self._document["objects"]}
            changes = dict(plan.get("changes_by_id") or {})
            for resized_id in self._resize_original_geometries:
                resized = by_id[resized_id]
                changes[resized_id] = {
                    **changes.get(resized_id, {}),
                    "width": float(resized["width"]),
                    "height": float(resized["height"]),
                }
            self.objects_changes_requested.emit(changes)
        elif interaction == "auto_layout_reorder" and object_id:
            original_index = int(
                self._auto_layout_reorder_context.get("index", -1)
            )
            target_index = int(self._auto_layout_reorder_target_index)
            if target_index >= 0 and target_index != original_index:
                self.auto_layout_reorder_requested.emit(
                    object_id,
                    target_index,
                )
        elif interaction == "radius" and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                self.object_changes_requested.emit(
                    object_id,
                    {"style": copy.deepcopy(dict(row.get("style") or {}))},
                )
        elif interaction.startswith("arc_") and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                self.object_changes_requested.emit(
                    object_id,
                    {
                        "kind": str(row.get("kind") or "arc"),
                        "content": copy.deepcopy(dict(row.get("content") or {})),
                    },
                )
        elif interaction in {
            "shape_count", "shape_ratio", "shape_radius",
            "line_start", "line_end",
        } and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                self.object_changes_requested.emit(
                    object_id,
                    {
                        "x": float(row["x"]), "y": float(row["y"]),
                        "width": float(row["width"]), "height": float(row["height"]),
                        "content": copy.deepcopy(dict(row.get("content") or {})),
                        "style": copy.deepcopy(dict(row.get("style") or {})),
                    },
                )
        elif interaction == "rotate_multi":
            self.objects_changes_requested.emit(
                {
                    row_id: {
                        "x": float(row["x"]),
                        "y": float(row["y"]),
                        "rotation": float(row.get("rotation", 0.0)),
                    }
                    for row_id in self._rotation_original_values
                    for row in self._document["objects"]
                    if str(row["id"]) == row_id
                }
            )
        elif interaction in {"move", "resize", "rotate"} and object_id:
            row = next(
                (row for row in self._document["objects"] if row["id"] == object_id),
                None,
            )
            if row is not None:
                if interaction == "move" and self._hierarchy_drop_preview_id:
                    changes = {
                        selected_id: {
                            "x": float(selected_row["x"]),
                            "y": float(selected_row["y"]),
                        }
                        for selected_id in self._move_original_positions
                        for selected_row in self._document["objects"]
                        if selected_row["id"] == selected_id
                    }
                    self.objects_move_reparent_requested.emit(
                        changes,
                        self._hierarchy_drop_preview_id,
                        list(self._document["selection"]["object_ids"]),
                    )
                elif interaction == "move" and len(self._move_original_positions) > 1:
                    changes = {
                        selected_id: {
                            "x": float(selected_row["x"]),
                            "y": float(selected_row["y"]),
                        }
                        for selected_id in self._move_original_positions
                        for selected_row in self._document["objects"]
                        if selected_row["id"] == selected_id
                    }
                    (
                        self.objects_continuation_changes_requested
                        if self._alt_duplicate_drag_active
                        else self.objects_changes_requested
                    ).emit(changes)
                elif interaction == "rotate":
                    self.object_changes_requested.emit(
                        object_id,
                        {"rotation": float(row["rotation"])},
                    )
                else:
                    if self._alt_duplicate_drag_active:
                        self.objects_continuation_changes_requested.emit(
                            {
                                object_id: {
                                    "x": float(row["x"]),
                                    "y": float(row["y"]),
                                    "width": float(row["width"]),
                                    "height": float(row["height"]),
                                }
                            }
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
        if self._tool == "pan":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._tool == "select":
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self._move_original_positions = {}
        self._hierarchy_drop_preview_id = ""
        self._resize_original_geometries = {}
        self._smart_resize_original_document = None
        self._rotation_original_values = {}
        self._radius_active_corner = ""
        self._radius_original = 0.0
        self._vector_original_content = None
        if self._vector_edit_object_id:
            self.vector_edit_changed.emit(self._vector_edit_state())
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if self._prototype_preview_enabled:
            hit_ids = self.object_ids_at(
                float(event.position().x()),
                float(event.position().y()),
            )
            if hit_ids:
                self.prototype_trigger_requested.emit(
                    hit_ids[0],
                    "double_click",
                    "",
                )
            event.accept()
            return
        if (
            self._rulers_visible
            and event.button() == Qt.MouseButton.LeftButton
            and event.position().x() <= self._ruler_size
            and event.position().y() <= self._ruler_size
        ):
            self.ruler_origin_reset_requested.emit()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._tool == "select":
            smart_report = self._smart_selection_report()
            if smart_report is not None:
                hit_ids = self.object_ids_at(
                    float(event.position().x()),
                    float(event.position().y()),
                )
                smart_ids = set(smart_report["ordered_object_ids"])
                target = next(
                    (object_id for object_id in hit_ids if object_id in smart_ids),
                    "",
                )
                if target and smart_report["axis"] in {"horizontal", "vertical"}:
                    self._smart_marked_ids = smart_ids
                    self._cancel_interaction()
                    self.update()
                    event.accept()
                    return
                if target and smart_report["axis"] == "grid":
                    grid_rows = [
                        set(group) for group in smart_report.get("grid_rows", [])
                    ]
                    marked_axis = next(
                        (
                            group for group in grid_rows
                            if group and group.issubset(self._smart_marked_ids)
                        ),
                        set(),
                    )
                    if marked_axis:
                        self._smart_marked_ids = smart_ids
                        self._cancel_interaction()
                        self.update()
                        event.accept()
                        return
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        axis_group = next(
                            (group for group in grid_rows if target in group),
                            set(),
                        )
                        if axis_group:
                            self._smart_marked_ids = set(axis_group)
                            self._cancel_interaction()
                            self.update()
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
            child_target = self._child_target_from_hits(selected, hit_ids)
            # Double-click edits a directly hit leaf as well as a child of the
            # currently selected container.  Restricting candidates to only a
            # child target made top-level Text and Vector layers impossible to
            # enter from the canvas.
            candidates = [child_target] if child_target else list(hit_ids)
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
            if child_target:
                self.object_selection_requested.emit(child_target, "replace")
                event.accept()
                return
            from app.painter_ui_boolean import is_ui_boolean_group

            parent_ids = {
                str(row.get("parent_id") or "")
                for row in self._document["objects"]
            }
            rows_by_id = {
                str(row["id"]): row for row in self._document["objects"]
            }
            scope_target = next(
                (
                    object_id
                    for object_id in hit_ids
                    if object_id in parent_ids
                    and (
                        str(rows_by_id.get(object_id, {}).get("kind") or "")
                        in {"frame", "group"}
                        or is_ui_boolean_group(rows_by_id.get(object_id, {}))
                    )
                ),
                "",
            )
            if scope_target:
                self.edit_scope_enter_requested.emit(scope_target)
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

    def apply_native_gesture(
        self,
        gesture_type: Qt.NativeGestureType,
        *,
        value: float = 0.0,
        delta: QPointF | None = None,
        position: QPointF | None = None,
    ) -> bool:
        if gesture_type in {
            Qt.NativeGestureType.BeginNativeGesture,
            Qt.NativeGestureType.EndNativeGesture,
        }:
            return True
        if gesture_type == Qt.NativeGestureType.PanNativeGesture:
            movement = QPointF(delta) if delta is not None else QPointF()
            self.pan_view(dx=movement.x(), dy=movement.y())
            return True
        if gesture_type == Qt.NativeGestureType.ZoomNativeGesture:
            old_scale, _offset = self._view_transform()
            factor = math.exp(max(-1.5, min(1.5, float(value))))
            anchor = (
                QPointF(position)
                if position is not None
                else QPointF(
                    float(self.width()) * 0.5,
                    float(self.height()) * 0.5,
                )
            )
            self.set_zoom_percent(
                old_scale * factor * 100.0,
                anchor=anchor,
            )
            return True
        if gesture_type == Qt.NativeGestureType.SmartZoomNativeGesture:
            if not self.fit_selection():
                self.fit_artboard()
            return True
        return False

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.NativeGesture:
            handled = self.apply_native_gesture(
                event.gestureType(),
                value=float(event.value()),
                delta=QPointF(event.delta()),
                position=QPointF(event.position()),
            )
            if handled:
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if self._prototype_preview_enabled:
            if self._prototype_focus_object_id:
                self.prototype_trigger_requested.emit(
                    self._prototype_focus_object_id,
                    "keyboard",
                    str(event.text() or event.key()),
                )
            event.accept()
            return
        if key == Qt.Key.Key_Alt and not event.isAutoRepeat():
            self.set_measurements_visible(True)
            event.accept()
            return
        if key == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if key in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
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
        if key == Qt.Key.Key_Escape and self._tool == "comment":
            self.key_command.emit("select_tool", False)
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.object_selection_requested.emit("", "replace")
            event.accept()
            return
        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and (
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            selected = self._selected_row()
            if selected is not None:
                from app.painter_ui_selection_navigation import (
                    parent_ui_object_id,
                )

                parent_id = parent_ui_object_id(
                    self._document,
                    str(selected["id"]),
                )
                if parent_id and parent_id != str(selected["id"]):
                    self.object_selection_requested.emit(parent_id, "replace")
            event.accept()
            return
        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            selected = self._selected_row()
            if selected is not None and selected.get("kind") == "text":
                if self.begin_text_edit(str(selected["id"])):
                    event.accept()
                    return
            if selected is not None:
                child_id = self._top_child_id(str(selected["id"]))
                if child_id:
                    self.object_selection_requested.emit(child_id, "replace")
                    event.accept()
                    return
        if key == Qt.Key.Key_Tab:
            selected = self._selected_row()
            if selected is not None:
                from app.painter_ui_selection_navigation import (
                    sibling_ui_object_id,
                )

                sibling_id = sibling_ui_object_id(
                    self._document,
                    str(selected["id"]),
                    previous=bool(
                        event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                    ),
                )
                if sibling_id:
                    self.object_selection_requested.emit(sibling_id, "replace")
            event.accept()
            return
        alignment_shortcuts = {
            Qt.Key.Key_A: "left",
            Qt.Key.Key_H: "hcenter",
            Qt.Key.Key_D: "right",
            Qt.Key.Key_W: "top",
            Qt.Key.Key_V: "vcenter",
            Qt.Key.Key_S: "bottom",
        }
        boolean_shortcuts = {
            Qt.Key.Key_U: "union",
            Qt.Key.Key_S: "subtract",
            Qt.Key.Key_I: "intersect",
            Qt.Key.Key_E: "exclude",
        }
        if (
            key == Qt.Key.Key_F
            and event.modifiers()
            == (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        ):
            self.key_command.emit("boolean_flatten", False)
            event.accept()
            return
        if (
            key == Qt.Key.Key_O
            and event.modifiers()
            == (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        ):
            self.key_command.emit("toggle_layer_outlines", False)
            event.accept()
            return
        if (
            key in boolean_shortcuts
            and event.modifiers()
            == (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        ):
            self.key_command.emit(
                f"boolean_{boolean_shortcuts[key]}",
                False,
            )
            event.accept()
            return
        if (
            key in alignment_shortcuts
            and event.modifiers() == Qt.KeyboardModifier.AltModifier
        ):
            self.key_command.emit(
                f"align_{alignment_shortcuts[key]}",
                False,
            )
            event.accept()
            return
        if (
            key == Qt.Key.Key_A
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            self.key_command.emit("add_auto_layout", False)
            event.accept()
            return
        if (
            key == Qt.Key.Key_A
            and event.modifiers()
            == (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.ShiftModifier
            )
        ):
            self.key_command.emit("remove_auto_layout", False)
            event.accept()
            return
        if (
            key == Qt.Key.Key_K
            and not event.isAutoRepeat()
            and not event.modifiers()
        ):
            self.key_command.emit("scale_tool", False)
            event.accept()
            return
        if key == Qt.Key.Key_P and not event.isAutoRepeat():
            command = (
                "pencil_tool"
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                else "pen_tool"
            )
            self.key_command.emit(command, False)
            event.accept()
            return
        if (
            key == Qt.Key.Key_C
            and not event.isAutoRepeat()
            and not event.modifiers()
        ):
            self.key_command.emit("comment_tool", False)
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

    def leaveEvent(self, event) -> None:
        if self._prototype_preview_enabled and self._prototype_hover_object_id:
            self.prototype_trigger_requested.emit(
                self._prototype_hover_object_id,
                "mouse_leave",
                "",
            )
            self._prototype_hover_object_id = ""
        super().leaveEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Alt and not event.isAutoRepeat():
            self.set_measurements_visible(False)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = False
            if self._interaction != "pan":
                self.setCursor(
                    Qt.CursorShape.OpenHandCursor
                    if self._tool == "pan"
                    else (
                        Qt.CursorShape.CrossCursor
                        if self._tool in _CREATE_TOOLS
                        else Qt.CursorShape.ArrowCursor
                    )
                )
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self.set_measurements_visible(False)
        super().focusOutEvent(event)


__all__ = ["PainterUIDesignOverlay"]
