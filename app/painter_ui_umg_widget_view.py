"""Non-destructive side-by-side Painter and simulated UMG widget preview."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.painter_i18n import painter_text
from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_constraints import (
    capture_ui_constraints,
    constraint_parent_geometry,
    normalize_ui_constraints,
)
from app.painter_ui_document import (
    active_ui_page_document,
    normalize_ui_document,
)
from app.painter_ui_inspector import PainterUIDragDoubleSpinBox
from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets
from app.painter_ui_workspace import PainterUIDesignOverlay


_UMG_ANCHOR_DECORATION_SCHEMA = (
    "tigerstudio.painter.ui.umg_anchor_decoration.v1"
)


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _vector(
    value: Any,
    default: tuple[float, float],
) -> tuple[float, float]:
    if isinstance(value, Mapping):
        return (
            _number(value.get("x", value.get("X")), default[0]),
            _number(value.get("y", value.get("Y")), default[1]),
        )
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (
            _number(value[0], default[0]),
            _number(value[1], default[1]),
        )
    return float(default[0]), float(default[1])


def _point_payload(point: QPointF) -> dict[str, float]:
    return {"x": float(point.x()), "y": float(point.y())}


def _rect_payload(rect: QRectF) -> dict[str, float]:
    return {
        "x": float(rect.x()),
        "y": float(rect.y()),
        "width": float(rect.width()),
        "height": float(rect.height()),
    }


class _UMGAnchorPreviewOverlay(PainterUIDesignOverlay):
    """UMG slot decoration over a locked or selection-only Painter surface."""

    transform_previewed = Signal(object)
    anchor_changes_previewed = Signal(str, object)
    anchor_changes_committed = Signal(str, object)
    anchor_drag_canceled = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        surface: str,
        require_rendered: bool,
        selection_enabled: bool,
    ) -> None:
        super().__init__(parent)
        self._umg_surface = str(surface)
        self._umg_require_rendered = bool(require_rendered)
        self._umg_selection_enabled = bool(selection_enabled)
        self._umg_selected_id = ""
        self._umg_widget: dict[str, Any] = {}
        self._umg_pending_drag_id = ""
        self._umg_transform_changed = False
        self._umg_anchor_drag: dict[str, Any] | None = None
        self._umg_hover_anchor_handle = ""

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self.cancel_anchor_drag(emit=False)
        super().set_document(value)

    def set_anchor_widget(
        self,
        widget: Mapping[str, Any] | None,
        *,
        selected_id: str,
    ) -> None:
        self._umg_selected_id = str(selected_id or "")
        self._umg_widget = (
            copy.deepcopy(dict(widget))
            if isinstance(widget, Mapping)
            else {}
        )
        self.update()

    def _empty_anchor_decoration(self, reason: str) -> dict[str, Any]:
        widget = self._umg_widget
        return {
            "schema": _UMG_ANCHOR_DECORATION_SCHEMA,
            "visible": False,
            "read_only": not self._umg_selection_enabled,
            "editable": False,
            "surface": self._umg_surface,
            "object_id": str(self._umg_selected_id),
            "disposition": str(widget.get("disposition") or ""),
            "rendered": bool(widget.get("rendered", False)),
            "reason": str(reason),
        }

    def anchor_decoration(self) -> dict[str, Any]:
        """Return the current screen-space UMG anchor/pivot paint plan."""
        selected_id = str(self._umg_selected_id or "")
        if not selected_id:
            return self._empty_anchor_decoration("no_selection")
        widget = self._umg_widget
        if str(widget.get("id") or "") != selected_id:
            return self._empty_anchor_decoration("no_widget_record")

        disposition = str(widget.get("disposition") or "")
        rendered = bool(widget.get("rendered", disposition == "Native"))
        if self._umg_require_rendered and not rendered:
            return self._empty_anchor_decoration(
                "blocked" if disposition == "Blocked" else "not_rendered"
            )

        slot = widget.get("slot")
        if not isinstance(slot, Mapping):
            return self._empty_anchor_decoration("missing_slot")
        anchors = (
            slot.get("anchors")
            if isinstance(slot.get("anchors"), Mapping)
            else {}
        )
        anchor_minimum = _vector(
            slot.get("anchor_minimum", anchors.get("minimum")),
            (0.0, 0.0),
        )
        anchor_maximum = _vector(
            slot.get("anchor_maximum", anchors.get("maximum")),
            anchor_minimum,
        )
        alignment = _vector(slot.get("alignment"), (0.5, 0.5))
        render_transform_pivot = _vector(
            widget.get("render_transform_pivot"),
            alignment,
        )

        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == selected_id
            ),
            None,
        )
        if row is None:
            return self._empty_anchor_decoration("selection_not_on_surface")
        widget_rect = self._object_rect(row)

        parent_id = str(widget.get("effective_parent_id") or "")
        parent_row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == parent_id
            ),
            None,
        )
        if parent_row is not None:
            parent_rect = self._object_rect(parent_row)
        else:
            artboard_id = str(row.get("artboard_id") or "")
            artboard = next(
                (
                    item
                    for item in self._document.get("artboards", [])
                    if str(item.get("id") or "") == artboard_id
                ),
                None,
            )
            if artboard is None:
                return self._empty_anchor_decoration(
                    "missing_parent_geometry"
                )
            parent_rect, _scale = self._artboard_viewport(artboard)

        parent_matches = str(row.get("parent_id") or "") == parent_id
        flow_child = bool(
            parent_row is not None
            and normalize_ui_auto_layout(parent_row.get("layout"))["mode"]
            != "none"
            and normalize_ui_auto_layout(row.get("layout"))["positioning"]
            != "absolute"
        )
        editable = bool(
            self._umg_selection_enabled
            and not row.get("locked", False)
            and parent_matches
            and not flow_child
        )
        edit_reason = (
            "auto_layout_flow_child"
            if flow_child
            else "effective_parent_mismatch"
            if not parent_matches
            else "locked"
            if row.get("locked", False)
            else "read_only"
            if not self._umg_selection_enabled
            else ""
        )

        def parent_point(value: tuple[float, float]) -> QPointF:
            return QPointF(
                parent_rect.left() + parent_rect.width() * value[0],
                parent_rect.top() + parent_rect.height() * value[1],
            )

        minimum_point = parent_point(anchor_minimum)
        maximum_point = parent_point(anchor_maximum)
        anchor_center = QPointF(
            (minimum_point.x() + maximum_point.x()) * 0.5,
            (minimum_point.y() + maximum_point.y()) * 0.5,
        )
        alignment_point = QPointF(
            widget_rect.left() + widget_rect.width() * alignment[0],
            widget_rect.top() + widget_rect.height() * alignment[1],
        )
        pivot_point = QPointF(
            widget_rect.left()
            + widget_rect.width() * render_transform_pivot[0],
            widget_rect.top()
            + widget_rect.height() * render_transform_pivot[1],
        )
        stretched = (
            abs(anchor_minimum[0] - anchor_maximum[0]) > 0.0001
            or abs(anchor_minimum[1] - anchor_maximum[1]) > 0.0001
        )
        return {
            "schema": _UMG_ANCHOR_DECORATION_SCHEMA,
            "visible": True,
            "read_only": not self._umg_selection_enabled,
            "editable": editable,
            "edit_reason": edit_reason,
            "surface": self._umg_surface,
            "object_id": selected_id,
            "disposition": disposition,
            "rendered": rendered,
            "reason": "",
            "parent_object_id": parent_id,
            "parent_bounds": _rect_payload(parent_rect),
            "widget_bounds": _rect_payload(widget_rect),
            "anchor_minimum": {
                "x": anchor_minimum[0],
                "y": anchor_minimum[1],
            },
            "anchor_maximum": {
                "x": anchor_maximum[0],
                "y": anchor_maximum[1],
            },
            "anchor_minimum_point": _point_payload(minimum_point),
            "anchor_maximum_point": _point_payload(maximum_point),
            "anchor_center_point": _point_payload(anchor_center),
            "alignment": {"x": alignment[0], "y": alignment[1]},
            "alignment_point": _point_payload(alignment_point),
            "render_transform_pivot": {
                "x": render_transform_pivot[0],
                "y": render_transform_pivot[1],
            },
            "pivot_point": _point_payload(pivot_point),
            "stretched": stretched,
        }

    @staticmethod
    def _payload_point(value: Mapping[str, Any]) -> QPointF:
        return QPointF(float(value["x"]), float(value["y"]))

    def _anchor_handle_at(self, position: QPointF) -> str:
        plan = self.anchor_decoration()
        if not plan.get("visible") or not plan.get("editable"):
            return ""
        candidates = (
            (
                ("minimum", self._payload_point(plan["anchor_minimum_point"])),
                ("maximum", self._payload_point(plan["anchor_maximum_point"])),
            )
            if bool(plan.get("stretched"))
            else (("point", self._payload_point(plan["anchor_center_point"])),)
        )
        nearest = ""
        nearest_distance = 10.0 * 10.0
        for handle, point in candidates:
            distance = (
                (float(position.x()) - float(point.x())) ** 2
                + (float(position.y()) - float(point.y())) ** 2
            )
            if distance <= nearest_distance:
                nearest = str(handle)
                nearest_distance = distance
        return nearest

    def _begin_anchor_drag(
        self,
        handle: str,
        position: QPointF,
        plan: Mapping[str, Any],
    ) -> None:
        self._interaction = "umg_anchor"
        self._umg_pending_drag_id = ""
        self._umg_transform_changed = False
        self._active_object_id = str(plan.get("object_id") or "")
        self._active_handle = str(handle)
        self._press_position = QPointF(position)
        self._umg_anchor_drag = {
            "object_id": self._active_object_id,
            "handle": str(handle),
            "press_position": QPointF(position),
            "parent_bounds": dict(plan.get("parent_bounds") or {}),
            "original_minimum": dict(plan.get("anchor_minimum") or {}),
            "original_maximum": dict(plan.get("anchor_maximum") or {}),
            "preview_constraints": None,
            "started": False,
        }
        self._umg_hover_anchor_handle = str(handle)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.update()

    @staticmethod
    def _snap_anchor_value(
        value: float,
        *,
        screen_size: float,
        modifiers: Qt.KeyboardModifier,
    ) -> float:
        result = max(0.0, min(1.0, float(value)))
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            result = round(result / 0.05) * 0.05
        if not modifiers & Qt.KeyboardModifier.ShiftModifier:
            for snap in (0.0, 0.5, 1.0):
                if abs(result - snap) * max(1.0, float(screen_size)) <= 8.0:
                    result = snap
                    break
        return max(0.0, min(1.0, result))

    def _anchor_constraints_for_position(
        self,
        position: QPointF,
        modifiers: Qt.KeyboardModifier,
    ) -> dict[str, Any] | None:
        drag = self._umg_anchor_drag
        if not isinstance(drag, Mapping):
            return None
        parent_bounds = dict(drag.get("parent_bounds") or {})
        parent_width = max(1.0, _number(parent_bounds.get("width"), 1.0))
        parent_height = max(1.0, _number(parent_bounds.get("height"), 1.0))
        minimum = dict(drag.get("original_minimum") or {})
        maximum = dict(drag.get("original_maximum") or {})
        next_x = self._snap_anchor_value(
            (
                float(position.x())
                - _number(parent_bounds.get("x"), 0.0)
            )
            / parent_width,
            screen_size=parent_width,
            modifiers=modifiers,
        )
        next_y = self._snap_anchor_value(
            (
                float(position.y())
                - _number(parent_bounds.get("y"), 0.0)
            )
            / parent_height,
            screen_size=parent_height,
            modifiers=modifiers,
        )
        handle = str(drag.get("handle") or "")
        if handle == "point":
            minimum = {"x": next_x, "y": next_y}
            maximum = dict(minimum)
        elif handle == "minimum":
            minimum = {
                "x": min(next_x, _number(maximum.get("x"), 0.0)),
                "y": min(next_y, _number(maximum.get("y"), 0.0)),
            }
        elif handle == "maximum":
            maximum = {
                "x": max(next_x, _number(minimum.get("x"), 0.0)),
                "y": max(next_y, _number(minimum.get("y"), 0.0)),
            }
        else:
            return None

        original_minimum = dict(drag.get("original_minimum") or {})
        original_maximum = dict(drag.get("original_maximum") or {})
        changed = any(
            abs(_number(candidate.get(axis), 0.0) - _number(original.get(axis), 0.0))
            > 0.000001
            for candidate, original in (
                (minimum, original_minimum),
                (maximum, original_maximum),
            )
            for axis in ("x", "y")
        )
        if not changed:
            return {}

        object_id = str(drag.get("object_id") or "")
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == object_id
            ),
            None,
        )
        if row is None or row.get("locked", False):
            return None
        resolved = self._resolved_geometry.get(object_id, row)
        candidate = copy.deepcopy(dict(row))
        for key in ("x", "y", "width", "height"):
            candidate[key] = float(resolved[key])
        updates = {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": float(minimum["x"]),
            "anchor_min_y": float(minimum["y"]),
            "anchor_max_x": float(maximum["x"]),
            "anchor_max_y": float(maximum["y"]),
        }
        return capture_ui_constraints(
            candidate,
            constraint_parent_geometry(
                self._document,
                row,
                self._resolved_geometry,
            ),
            updates,
        )

    def _update_anchor_drag(
        self,
        position: QPointF,
        modifiers: Qt.KeyboardModifier,
    ) -> None:
        drag = self._umg_anchor_drag
        if not isinstance(drag, dict):
            return
        if not bool(drag.get("started")):
            delta = position - drag["press_position"]
            if abs(delta.x()) + abs(delta.y()) < QApplication.startDragDistance():
                return
            drag["started"] = True
        constraints = self._anchor_constraints_for_position(
            position,
            modifiers,
        )
        if constraints is None:
            return
        if not constraints:
            if drag.get("preview_constraints") is not None:
                drag["preview_constraints"] = None
                self.anchor_drag_canceled.emit()
            return
        if constraints == drag.get("preview_constraints"):
            return
        drag["preview_constraints"] = copy.deepcopy(constraints)
        self.anchor_changes_previewed.emit(
            str(drag.get("object_id") or ""),
            {"constraints": copy.deepcopy(constraints)},
        )

    def cancel_anchor_drag(self, *, emit: bool = True) -> bool:
        drag = self._umg_anchor_drag
        if not isinstance(drag, Mapping):
            return False
        had_preview = drag.get("preview_constraints") is not None
        self._umg_anchor_drag = None
        self._umg_hover_anchor_handle = ""
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        if emit and had_preview:
            self.anchor_drag_canceled.emit()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        return True

    def _finish_anchor_drag(self) -> None:
        drag = self._umg_anchor_drag
        if not isinstance(drag, Mapping):
            return
        object_id = str(drag.get("object_id") or "")
        constraints = drag.get("preview_constraints")
        self._umg_anchor_drag = None
        self._umg_hover_anchor_handle = ""
        self._interaction = ""
        self._active_object_id = ""
        self._active_handle = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        if isinstance(constraints, Mapping):
            self.anchor_changes_committed.emit(
                object_id,
                {"constraints": copy.deepcopy(dict(constraints))},
            )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        document_selection = None
        effective_selection = None
        if self._umg_selection_enabled:
            document_selection = self._document.get("selection")
            effective_selection = self._effective_document.get("selection")
            empty = {"object_id": "", "object_ids": []}
            self._document["selection"] = empty
            self._effective_document["selection"] = copy.deepcopy(empty)
        try:
            super().paintEvent(event)
        finally:
            if document_selection is not None:
                self._document["selection"] = document_selection
            if effective_selection is not None:
                self._effective_document["selection"] = effective_selection

        plan = self.anchor_decoration()
        selected_row = self._selected_row() if self._umg_selection_enabled else None
        if not plan["visible"] and selected_row is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipRect(self.rect())
        if selected_row is not None:
            selection_rect = self._object_rect(selected_row)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#35A5FF"), 1.5))
            painter.drawRect(selection_rect)
            if not selected_row.get("locked", False):
                painter.setBrush(QColor("#F7FBFF"))
                painter.setPen(QPen(QColor("#35A5FF"), 1.25))
                for handle in ("nw", "ne", "sw", "se"):
                    painter.drawRect(self._handle_rects(selection_rect)[handle])
        if not plan["visible"]:
            painter.end()
            return

        minimum = self._payload_point(plan["anchor_minimum_point"])
        maximum = self._payload_point(plan["anchor_maximum_point"])
        center = self._payload_point(plan["anchor_center_point"])
        alignment = self._payload_point(plan["alignment_point"])
        pivot = self._payload_point(plan["pivot_point"])
        anchor_color = QColor("#F0B84A")
        active_handle = str(
            (self._umg_anchor_drag or {}).get("handle")
            or self._umg_hover_anchor_handle
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(anchor_color, 1.25, Qt.PenStyle.DashLine)
        )
        painter.drawLine(center, alignment)

        painter.setPen(QPen(anchor_color, 1.5))
        if bool(plan["stretched"]):
            anchor_rect = QRectF(minimum, maximum).normalized()
            painter.setBrush(QColor("#F0B84A1A"))
            painter.drawRect(anchor_rect)
            for handle, point in (("minimum", minimum), ("maximum", maximum)):
                painter.setBrush(
                    anchor_color
                    if active_handle == handle
                    else QColor("#10151D")
                )
                painter.setPen(
                    QPen(anchor_color, 2.0 if active_handle == handle else 1.5)
                )
                painter.drawRect(
                    QRectF(point.x() - 5.0, point.y() - 5.0, 10.0, 10.0)
                )
        else:
            painter.drawLine(
                QPointF(center.x() - 8.0, center.y()),
                QPointF(center.x() + 8.0, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 8.0),
                QPointF(center.x(), center.y() + 8.0),
            )
            painter.setBrush(
                anchor_color
                if active_handle == "point"
                else QColor("#10151D")
            )
            painter.setPen(
                QPen(anchor_color, 2.0 if active_handle == "point" else 1.5)
            )
            painter.drawRect(
                QRectF(center.x() - 5.0, center.y() - 5.0, 10.0, 10.0)
            )

        painter.setBrush(QColor("#63D5FF"))
        painter.setPen(QPen(QColor("#0D1721"), 1.0))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(alignment.x(), alignment.y() - 4.5),
                    QPointF(alignment.x() + 4.5, alignment.y()),
                    QPointF(alignment.x(), alignment.y() + 4.5),
                    QPointF(alignment.x() - 4.5, alignment.y()),
                ]
            )
        )

        painter.setBrush(QColor("#FF6EDB"))
        painter.setPen(QPen(QColor("#211426"), 1.0))
        painter.drawEllipse(pivot, 4.0, 4.0)
        painter.setPen(QPen(QColor("#FFF2FC"), 1.0))
        painter.drawLine(
            QPointF(pivot.x() - 2.0, pivot.y()),
            QPointF(pivot.x() + 2.0, pivot.y()),
        )
        painter.drawLine(
            QPointF(pivot.x(), pivot.y() - 2.0),
            QPointF(pivot.x(), pivot.y() + 2.0),
        )
        painter.end()

    def _selection_at(self, position: QPointF, _modifiers) -> str:
        hit_ids = self.object_ids_at(float(position.x()), float(position.y()))
        # Unreal's UMG Designer selects the concrete widget under the pointer.
        # The regular Painter canvas intentionally promotes a nested hit to its
        # top-level frame (Figma-style), but that hides the per-CanvasPanelSlot
        # anchor for controls such as a Button inside a CanvasPanel.
        return str(
            self._selection_target_from_hits(
                hit_ids,
                deep=True,
            )
            or ""
        )

    def _request_selection_at(self, position: QPointF, modifiers) -> str:
        selected = self._selection_at(position, modifiers)
        mode = (
            "toggle"
            if modifiers & Qt.KeyboardModifier.ShiftModifier
            else "replace"
        )
        self.object_selection_requested.emit(selected, mode)
        return selected

    def _begin_resize(
        self,
        row: Mapping[str, Any],
        handle: str,
        position: QPointF,
    ) -> None:
        self._interaction = "resize"
        self._umg_pending_drag_id = ""
        self._umg_transform_changed = False
        self._active_object_id = str(row["id"])
        self._active_handle = str(handle)
        self._press_position = QPointF(position)
        self._original_rect = QRectF(self._object_rect(row))
        self._resize_original_geometries = {
            str(row["id"]): (
                float(row["x"]),
                float(row["y"]),
                float(row["width"]),
                float(row["height"]),
            )
        }

    def _transform_preview(self) -> dict[str, dict[str, float]]:
        if self._interaction == "move":
            object_ids = list(self._move_original_positions)
        elif self._interaction == "resize":
            object_ids = [str(self._active_object_id)]
        else:
            object_ids = []
        return {
            str(row["id"]): {
                key: float(row[key])
                for key in ("x", "y", "width", "height")
            }
            for row in self._document.get("objects", [])
            if str(row.get("id") or "") in object_ids
        }

    def _hover_cursor(self, position: QPointF) -> Qt.CursorShape:
        if self._anchor_handle_at(position):
            return Qt.CursorShape.SizeAllCursor
        row = self._selected_row()
        if row is not None and not row.get("locked", False):
            rect = self._object_rect(row)
            local = self._unrotated_point(
                position,
                rect,
                float(row.get("rotation", 0.0)),
                row.get("constraints"),
            )
            for handle, cursor in (
                ("nw", Qt.CursorShape.SizeFDiagCursor),
                ("se", Qt.CursorShape.SizeFDiagCursor),
                ("ne", Qt.CursorShape.SizeBDiagCursor),
                ("sw", Qt.CursorShape.SizeBDiagCursor),
            ):
                if self._handle_rects(rect)[handle].contains(local):
                    return cursor
        if self.object_ids_at(float(position.x()), float(position.y())):
            return Qt.CursorShape.SizeAllCursor
        return Qt.CursorShape.ArrowCursor

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._umg_selection_enabled:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and self._space_pan_active
        ):
            self._umg_pending_drag_id = ""
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        position = QPointF(event.position())
        self._press_position = QPointF(position)
        anchor_handle = self._anchor_handle_at(position)
        if anchor_handle:
            self._begin_anchor_drag(
                anchor_handle,
                position,
                self.anchor_decoration(),
            )
            event.accept()
            return
        selected_row = self._selected_row()
        if selected_row is not None and not selected_row.get("locked", False):
            rect = self._object_rect(selected_row)
            local = self._unrotated_point(
                position,
                rect,
                float(selected_row.get("rotation", 0.0)),
                selected_row.get("constraints"),
            )
            for handle in ("nw", "ne", "sw", "se"):
                if self._handle_rects(rect)[handle].contains(local):
                    self._begin_resize(selected_row, handle, position)
                    event.accept()
                    return

        selected = self._selection_at(position, event.modifiers())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.object_selection_requested.emit(selected, "toggle")
            event.accept()
            return
        current_ids = list(
            self._document.get("selection", {}).get("object_ids", [])
        )
        if selected != str(
            self._document.get("selection", {}).get("object_id") or ""
        ) or len(current_ids) != 1:
            self.object_selection_requested.emit(selected, "replace")
        if not selected:
            event.accept()
            return
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == selected
            ),
            None,
        )
        if row is not None and not row.get("locked", False):
            self._umg_pending_drag_id = str(row["id"])
            self._umg_transform_changed = False
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._interaction == "umg_anchor":
            self._update_anchor_drag(
                QPointF(event.position()),
                event.modifiers(),
            )
            event.accept()
            return
        if self._umg_pending_drag_id and not self._interaction:
            delta = QPointF(event.position()) - self._press_position
            if abs(delta.x()) + abs(delta.y()) < QApplication.startDragDistance():
                event.accept()
                return
            row = next(
                (
                    item
                    for item in self._document.get("objects", [])
                    if str(item.get("id") or "")
                    == self._umg_pending_drag_id
                ),
                None,
            )
            self._umg_pending_drag_id = ""
            if row is not None and not row.get("locked", False):
                self._begin_object_move(row, self._press_position)
        if self._interaction in {"pan", "move", "resize"}:
            super().mouseMoveEvent(event)
            if self._interaction in {"move", "resize"}:
                self._umg_transform_changed = True
                # The UMG comparison window edits geometry only; it does not
                # perform hierarchy reparenting from this compact surface.
                self._hierarchy_drop_preview_id = ""
                changes = self._transform_preview()
                if changes:
                    self.transform_previewed.emit(changes)
            return
        if not self._umg_selection_enabled:
            event.ignore()
            return
        position = QPointF(event.position())
        anchor_handle = self._anchor_handle_at(position)
        if anchor_handle != self._umg_hover_anchor_handle:
            self._umg_hover_anchor_handle = anchor_handle
            self.update()
        self.setToolTip(
            painter_text("Drag the orange anchor to set UMG Min/Max")
            if anchor_handle
            else ""
        )
        self.setCursor(self._hover_cursor(position))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._interaction == "umg_anchor":
            self._finish_anchor_drag()
            event.accept()
            return
        if self._umg_pending_drag_id:
            self._umg_pending_drag_id = ""
            self._umg_transform_changed = False
            event.accept()
            return
        if (
            self._interaction in {"move", "resize"}
            and not self._umg_transform_changed
        ):
            self._cancel_interaction()
            event.accept()
            return
        if self._interaction in {"pan", "move", "resize"}:
            super().mouseReleaseEvent(event)
            self._umg_transform_changed = False
            return
        if self._umg_selection_enabled:
            event.accept()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self._umg_selection_enabled
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._request_selection_at(
                QPointF(event.position()),
                event.modifiers(),
            )
            event.accept()
            return
        event.ignore()

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if not self._umg_selection_enabled:
            event.ignore()
            return
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_pan_active = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self.cancel_anchor_drag():
                event.accept()
                return
            self._umg_pending_drag_id = ""
            self._umg_transform_changed = False
            self.object_selection_requested.emit("", "replace")
            event.accept()
            return
        event.ignore()

    def keyReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self._umg_selection_enabled
            and event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
        ):
            self._space_pan_active = False
            if self._interaction != "pan":
                self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        event.ignore()


class _UMGPreviewPane(QFrame):
    """Canvas card used by the source/UMG comparison window."""

    def __init__(
        self,
        title: str,
        subtitle: str,
        *,
        object_name: str,
        surface: str,
        require_rendered: bool,
        selection_enabled: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(painter_text(title), self)
        self.title_label.setObjectName("PainterUMGPaneTitle")
        self.subtitle_label = QLabel(painter_text(subtitle), self)
        self.subtitle_label.setObjectName("PainterUMGPaneSubtitle")
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.subtitle_label, 1)
        root.addLayout(title_row)

        self.preview = _UMGAnchorPreviewOverlay(
            self,
            surface=surface,
            require_rendered=require_rendered,
            selection_enabled=selection_enabled,
        )
        self.preview.setObjectName(f"{object_name}Canvas")
        # The source accepts selection only. Layout edits travel through the
        # explicit controls and the owner's canonical mutation/undo path.
        self.preview.setEnabled(bool(selection_enabled))
        self.preview.set_rulers_visible(False)
        self.preview.set_artboard_labels_visible(False)
        # Leave useful travel for a bottom material-graph dock.  The previous
        # 190 px floor made the native QMainWindow separator technically
        # draggable but left almost no practical upper/lower resize range.
        self.preview.setMinimumSize(260, 128)
        root.addWidget(self.preview, 1)

    def set_document(self, document: Mapping[str, Any]) -> None:
        self.preview.set_document(document)

    def set_anchor_widget(
        self,
        widget: Mapping[str, Any] | None,
        *,
        selected_id: str,
    ) -> None:
        self.preview.set_anchor_widget(widget, selected_id=selected_id)

    def anchor_decoration(self) -> dict[str, Any]:
        return self.preview.anchor_decoration()

    def fit(self) -> None:
        if self.preview.width() > 0 and self.preview.height() > 0:
            self.preview.fit_artboard()


class _UMGLayoutControls(QFrame):
    """Canonical Painter constraint controls expressed as UMG layout terms."""

    layout_changes_requested = Signal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUMGLayoutControls")
        self._document: dict[str, Any] = {}
        self._selected_id = ""
        self._syncing = False
        self._layout_dirty = False
        self._geometry_dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 7, 8, 7)
        root.setSpacing(5)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(7)
        geometry_row = QHBoxLayout()
        geometry_row.setContentsMargins(0, 0, 0, 0)
        geometry_row.setSpacing(7)
        anchor_row = QHBoxLayout()
        anchor_row.setContentsMargins(0, 0, 0, 0)
        anchor_row.setSpacing(7)
        root.addLayout(header_row)
        root.addLayout(geometry_row)
        root.addLayout(anchor_row)

        title = QLabel(painter_text("UMG Layout"), self)
        title.setObjectName("PainterUMGControlsTitle")
        header_row.addWidget(title)
        self.selection_label = QLabel(
            painter_text("Select an object on the left"),
            self,
        )
        self.selection_label.setObjectName("PainterUMGControlsSelection")
        self.selection_label.setMinimumWidth(150)
        header_row.addWidget(self.selection_label, 1)
        self.drag_hint = QLabel(
            painter_text(
                "Drag values horizontally or drag the orange anchor"
            ),
            self,
        )
        self.drag_hint.setObjectName("PainterUMGControlsHint")
        header_row.addWidget(self.drag_hint)

        self.geometry_spins: dict[str, PainterUIDragDoubleSpinBox] = {}
        for label, keys in (
            ("Position", ("x", "y")),
            ("Size", ("width", "height")),
        ):
            geometry_row.addWidget(QLabel(painter_text(label), self))
            for prefix, key in zip(("X ", "Y ") if label == "Position" else ("W ", "H "), keys):
                spin = PainterUIDragDoubleSpinBox(self)
                spin.setObjectName(
                    "PainterUMGGeometry"
                    + key.replace("width", "Width").replace(
                        "height", "Height"
                    ).title()
                    + "Spin"
                )
                spin.setRange(
                    -100000.0 if key in {"x", "y"} else 1.0,
                    100000.0,
                )
                spin.setDecimals(1)
                spin.setSingleStep(1.0)
                spin.setKeyboardTracking(False)
                spin.setPrefix(prefix)
                spin.setSuffix(" px")
                spin.setAlignment(Qt.AlignmentFlag.AlignRight)
                spin.setGroupSeparatorShown(True)
                spin.setFixedWidth(118)
                spin.setToolTip(
                    painter_text(
                        "Drag horizontally - Shift fine - Ctrl fast - click to type"
                    )
                )
                self.geometry_spins[key] = spin
                geometry_row.addWidget(spin)
        geometry_row.addStretch(1)

        self.horizontal_combo = QComboBox(self)
        self.horizontal_combo.setObjectName(
            "PainterUMGHorizontalAnchorCombo"
        )
        for label, value in (
            ("Left", "left"),
            ("Center", "center"),
            ("Right", "right"),
            ("Stretch", "stretch"),
            ("Scale", "scale"),
            ("Custom", "custom"),
        ):
            self.horizontal_combo.addItem(painter_text(label), value)
        anchor_row.addWidget(
            QLabel(painter_text("Horizontal Anchor"), self)
        )
        anchor_row.addWidget(self.horizontal_combo)

        self.vertical_combo = QComboBox(self)
        self.vertical_combo.setObjectName("PainterUMGVerticalAnchorCombo")
        for label, value in (
            ("Top", "top"),
            ("Center", "center"),
            ("Bottom", "bottom"),
            ("Stretch", "stretch"),
            ("Scale", "scale"),
            ("Custom", "custom"),
        ):
            self.vertical_combo.addItem(painter_text(label), value)
        anchor_row.addWidget(QLabel(painter_text("Vertical Anchor"), self))
        anchor_row.addWidget(self.vertical_combo)

        anchor_row.addWidget(QLabel(painter_text("Alignment / Pivot"), self))
        self.pivot_x_spin = PainterUIDragDoubleSpinBox(self)
        self.pivot_x_spin.setObjectName("PainterUMGAlignmentPivotXSpin")
        self.pivot_y_spin = PainterUIDragDoubleSpinBox(self)
        self.pivot_y_spin.setObjectName("PainterUMGAlignmentPivotYSpin")
        for prefix, spin in (
            ("X ", self.pivot_x_spin),
            ("Y ", self.pivot_y_spin),
        ):
            spin.setRange(0.0, 1.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.01)
            spin.setKeyboardTracking(False)
            spin.setPrefix(prefix)
            spin.setAlignment(Qt.AlignmentFlag.AlignRight)
            spin.setFixedWidth(96)
            spin.setToolTip(
                painter_text(
                    "Drag horizontally - Shift fine - Ctrl fast - click to type"
                )
            )
            anchor_row.addWidget(spin)
        self.anchor_hint = QLabel(
            painter_text(
                "Anchors preserve the current layout at this parent size"
            ),
            self,
        )
        self.anchor_hint.setObjectName("PainterUMGControlsHint")
        anchor_row.addWidget(self.anchor_hint)
        anchor_row.addStretch(1)

        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(120)
        self._commit_timer.timeout.connect(self._commit_changes)
        self.horizontal_combo.currentIndexChanged.connect(
            self._commit_changes
        )
        self.vertical_combo.currentIndexChanged.connect(
            self._commit_changes
        )
        self.pivot_x_spin.valueChanged.connect(self._schedule_commit)
        self.pivot_y_spin.valueChanged.connect(self._schedule_commit)
        self.pivot_x_spin.editingFinished.connect(self.flush_pending_changes)
        self.pivot_y_spin.editingFinished.connect(self.flush_pending_changes)
        self._geometry_commit_timer = QTimer(self)
        self._geometry_commit_timer.setSingleShot(True)
        self._geometry_commit_timer.setInterval(120)
        self._geometry_commit_timer.timeout.connect(
            self._commit_geometry_changes
        )
        for spin in self.geometry_spins.values():
            spin.valueChanged.connect(self._schedule_geometry_commit)
            spin.editingFinished.connect(
                self.flush_pending_geometry_changes
            )
        self._set_controls_enabled(False)

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(str(value))
        combo.setCurrentIndex(max(0, index))

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.horizontal_combo,
            self.vertical_combo,
            self.pivot_x_spin,
            self.pivot_y_spin,
            *self.geometry_spins.values(),
        ):
            control.setEnabled(bool(enabled))

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._commit_timer.stop()
        self._geometry_commit_timer.stop()
        self._layout_dirty = False
        self._geometry_dirty = False
        self._document = copy.deepcopy(dict(value or {}))
        selection = self._document.get("selection")
        selected_id = str(
            (selection if isinstance(selection, Mapping) else {}).get(
                "object_id"
            )
            or ""
        )
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == selected_id
            ),
            None,
        )
        self._selected_id = selected_id if row is not None else ""
        editable = bool(row is not None and not row.get("locked", False))
        self._set_controls_enabled(editable)
        if row is None:
            self.selection_label.setText(
                painter_text("Select an object on the left")
            )
            return
        name = str(row.get("name") or row.get("kind") or selected_id)
        suffix = (
            f" - {painter_text('Locked')}"
            if row.get("locked", False)
            else ""
        )
        self.selection_label.setText(name + suffix)
        constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=float(row.get("width") or 1.0),
            height=float(row.get("height") or 1.0),
        )
        self._syncing = True
        controls = (
            self.horizontal_combo,
            self.vertical_combo,
            self.pivot_x_spin,
            self.pivot_y_spin,
            *self.geometry_spins.values(),
        )
        previous = [control.blockSignals(True) for control in controls]
        try:
            self._set_combo_data(
                self.horizontal_combo,
                str(constraints["horizontal"]),
            )
            self._set_combo_data(
                self.vertical_combo,
                str(constraints["vertical"]),
            )
            self.pivot_x_spin.setValue(float(constraints["pivot_x"]))
            self.pivot_y_spin.setValue(float(constraints["pivot_y"]))
            for key, spin in self.geometry_spins.items():
                spin.setValue(float(row.get(key) or 0.0))
        finally:
            for control, was_blocked in zip(controls, previous):
                control.blockSignals(was_blocked)
            self._syncing = False

    def _schedule_commit(self, _value: float) -> None:
        if not self._syncing:
            self._layout_dirty = True
            self._commit_timer.start()

    def flush_pending_changes(self) -> None:
        if self._commit_timer.isActive():
            self._commit_timer.stop()
        self._commit_changes()

    def _schedule_geometry_commit(self, _value: float) -> None:
        if not self._syncing:
            self._geometry_dirty = True
            self._geometry_commit_timer.start()

    def flush_pending_geometry_changes(self) -> None:
        if self._geometry_commit_timer.isActive():
            self._geometry_commit_timer.stop()
        self._commit_geometry_changes()

    def _commit_geometry_changes(self) -> None:
        if (
            self._syncing
            or not self._geometry_dirty
            or not self._selected_id
        ):
            return
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == self._selected_id
            ),
            None,
        )
        if row is None or row.get("locked", False):
            self._geometry_dirty = False
            return
        changes = {
            key: (
                max(1.0, float(spin.value()))
                if key in {"width", "height"}
                else float(spin.value())
            )
            for key, spin in self.geometry_spins.items()
        }
        if all(
            abs(float(row.get(key) or 0.0) - value) < 0.0001
            for key, value in changes.items()
        ):
            self._geometry_dirty = False
            return
        self._geometry_dirty = False
        self.layout_changes_requested.emit(self._selected_id, changes)

    def preview_geometry(self, changes_by_id: Mapping[str, Any]) -> None:
        changes = changes_by_id.get(self._selected_id)
        if not isinstance(changes, Mapping):
            return
        controls = tuple(self.geometry_spins.values())
        previous = [control.blockSignals(True) for control in controls]
        self._syncing = True
        try:
            for key, spin in self.geometry_spins.items():
                if key in changes:
                    spin.setValue(float(changes[key]))
        finally:
            for control, was_blocked in zip(controls, previous):
                control.blockSignals(was_blocked)
            self._syncing = False

    def preview_constraints(
        self,
        object_id: str,
        constraints: Mapping[str, Any],
    ) -> None:
        if str(object_id or "") != self._selected_id:
            return
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == self._selected_id
            ),
            None,
        )
        if row is None:
            return
        normalized = normalize_ui_constraints(
            constraints,
            width=float(row.get("width") or 1.0),
            height=float(row.get("height") or 1.0),
        )
        controls = (
            self.horizontal_combo,
            self.vertical_combo,
            self.pivot_x_spin,
            self.pivot_y_spin,
        )
        previous = [control.blockSignals(True) for control in controls]
        self._syncing = True
        try:
            self._set_combo_data(
                self.horizontal_combo,
                str(normalized["horizontal"]),
            )
            self._set_combo_data(
                self.vertical_combo,
                str(normalized["vertical"]),
            )
            self.pivot_x_spin.setValue(float(normalized["pivot_x"]))
            self.pivot_y_spin.setValue(float(normalized["pivot_y"]))
        finally:
            for control, was_blocked in zip(controls, previous):
                control.blockSignals(was_blocked)
            self._syncing = False

    def _commit_changes(self, _index: int | None = None) -> None:
        if _index is not None and not self._syncing:
            self._layout_dirty = True
        if (
            self._syncing
            or not self._layout_dirty
            or not self._selected_id
        ):
            return
        row = next(
            (
                item
                for item in self._document.get("objects", [])
                if str(item.get("id") or "") == self._selected_id
            ),
            None,
        )
        if row is None or row.get("locked", False):
            self._layout_dirty = False
            return
        updates = {
            "horizontal": str(
                self.horizontal_combo.currentData() or "left"
            ),
            "vertical": str(self.vertical_combo.currentData() or "top"),
            "pivot_x": float(self.pivot_x_spin.value()),
            "pivot_y": float(self.pivot_y_spin.value()),
        }
        current = normalize_ui_constraints(
            row.get("constraints"),
            width=float(row.get("width") or 1.0),
            height=float(row.get("height") or 1.0),
        )
        if all(current.get(key) == value for key, value in updates.items()):
            self._layout_dirty = False
            return
        constraints = capture_ui_constraints(
            row,
            constraint_parent_geometry(self._document, row),
            updates,
        )
        self._layout_dirty = False
        self.layout_changes_requested.emit(
            self._selected_id,
            {"constraints": constraints},
        )

    def control_state(self) -> dict[str, Any]:
        return {
            "object_id": self._selected_id,
            "enabled": self.horizontal_combo.isEnabled(),
            "horizontal": str(
                self.horizontal_combo.currentData() or "left"
            ),
            "vertical": str(self.vertical_combo.currentData() or "top"),
            "pivot_x": float(self.pivot_x_spin.value()),
            "pivot_y": float(self.pivot_y_spin.value()),
            **{
                key: float(spin.value())
                for key, spin in self.geometry_spins.items()
            },
        }


class PainterUMGWidgetView(QDialog):
    """Compare the Painter source with the current Tiger UMG projection."""

    visibility_changed = Signal(bool)
    refresh_requested = Signal()
    selection_requested = Signal(str, str)
    object_changes_requested = Signal(str, object)
    objects_changes_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUMGWidgetView")
        self.setWindowTitle(painter_text("UMG Widget View"))
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(1120, 720)
        self.setMinimumSize(820, 520)
        self._report: dict[str, Any] = {}
        self._source_document: dict[str, Any] = {}
        self._source_signature: tuple[Any, ...] | None = None
        self._artboard_id = ""
        self._has_document = False
        self._selected_material: dict[str, Any] = {}
        self._material_graph_panel: QWidget | None = None
        self._material_dock: QDockWidget | None = None
        self._material_graph_panel_state: dict[str, Any] = {}
        self._material_dock_workspace_state: Any = None
        self._material_dock_floating_geometry: Any = None
        self._material_dock_area = Qt.DockWidgetArea.BottomDockWidgetArea
        self._material_dock_was_floating = False
        self._material_dock_needs_default_size = False
        self._material_panel_needs_layout = False
        self._material_graph_requested_visible = False
        self._material_dock_lifecycle_guard = 0
        self._material_dock_visibility_serial = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel(painter_text("UMG Widget View"), self)
        title.setObjectName("PainterUMGViewTitle")
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("PainterUMGViewSummary")
        self.summary_label.setText(
            painter_text("Edit the source - UMG follows live")
        )
        refresh_button = QPushButton(painter_text("Refresh"), self)
        refresh_button.setObjectName("PainterUMGViewButton")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        self.material_button = QPushButton(
            painter_text("Material Graph"),
            self,
        )
        self.material_button.setObjectName("PainterUMGMaterialGraphButton")
        self.material_button.setCheckable(True)
        self.material_button.setEnabled(False)
        self.material_button.setToolTip(
            painter_text("Select a generated Material layer")
        )
        self.material_button.toggled.connect(
            self._set_material_graph_visible
        )
        close_button = QPushButton(painter_text("Close"), self)
        close_button.setObjectName("PainterUMGViewButton")
        close_button.clicked.connect(self.close)
        header.addWidget(title)
        header.addWidget(self.summary_label, 1)
        header.addWidget(self.material_button)
        header.addWidget(refresh_button)
        header.addWidget(close_button)
        root.addLayout(header)

        self.workspace = QMainWindow(self)
        self.workspace.setWindowFlags(Qt.WindowType.Widget)
        self.workspace.setObjectName("PainterUMGWidgetViewWorkspace")
        self.workspace.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
        )
        self.comparison_panel = QWidget(self.workspace)
        self.comparison_panel.setObjectName("PainterUMGComparisonPanel")
        comparison_layout = QVBoxLayout(self.comparison_panel)
        comparison_layout.setContentsMargins(0, 0, 0, 0)
        comparison_layout.setSpacing(8)

        self.splitter = QSplitter(
            Qt.Orientation.Horizontal,
            self.comparison_panel,
        )
        self.splitter.setObjectName("PainterUMGWidgetViewSplitter")
        self.source_pane = _UMGPreviewPane(
            "Source Design",
            "Move, resize and drag anchors",
            object_name="PainterUMGSourcePreview",
            surface="source",
            require_rendered=False,
            selection_enabled=True,
            parent=self.splitter,
        )
        self.target_pane = _UMGPreviewPane(
            "UMG Widgets",
            "Locked UMG projection",
            object_name="PainterUMGTargetPreview",
            surface="target",
            require_rendered=True,
            selection_enabled=False,
            parent=self.splitter,
        )
        self.splitter.addWidget(self.source_pane)
        self.splitter.addWidget(self.target_pane)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([540, 540])
        comparison_layout.addWidget(self.splitter, 1)

        self.layout_controls = _UMGLayoutControls(self.comparison_panel)
        self.layout_controls.layout_changes_requested.connect(
            self.object_changes_requested.emit
        )
        comparison_layout.addWidget(self.layout_controls)
        self.source_pane.preview.object_selection_requested.connect(
            self.selection_requested.emit
        )
        self.source_pane.preview.view_changed.connect(
            self._sync_target_view
        )
        self.source_pane.preview.object_geometry_requested.connect(
            self._forward_object_geometry
        )
        self.source_pane.preview.objects_changes_requested.connect(
            self.objects_changes_requested.emit
        )
        self.source_pane.preview.transform_previewed.connect(
            self._preview_transforms
        )
        self.source_pane.preview.anchor_changes_previewed.connect(
            self._preview_anchor_changes
        )
        self.source_pane.preview.anchor_changes_committed.connect(
            self.object_changes_requested.emit
        )
        self.source_pane.preview.anchor_drag_canceled.connect(
            self._restore_anchor_preview
        )

        self.issue_label = QLabel(self.comparison_panel)
        self.issue_label.setObjectName("PainterUMGViewIssues")
        self.issue_label.setWordWrap(True)
        self.issue_label.hide()
        comparison_layout.addWidget(self.issue_label)

        self.workspace.setCentralWidget(self.comparison_panel)
        root.addWidget(self.workspace, 1)
        controls_minimum_width = self.layout_controls.minimumSizeHint().width()
        self.setMinimumSize(max(960, controls_minimum_width + 20), 640)

        self.setStyleSheet(
            """
            QDialog#PainterUMGWidgetView {
                background: #10151D;
                color: #E7EDF5;
            }
            QLabel#PainterUMGViewTitle {
                color: #F3F7FC;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#PainterUMGViewSummary,
            QLabel#PainterUMGPaneSubtitle {
                color: #91A0B4;
                font-size: 11px;
            }
            QLabel#PainterUMGPaneTitle {
                color: #DDE7F2;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#PainterUMGViewIssues {
                color: #FFC86B;
                background: #251E13;
                border: 1px solid #5D4722;
                border-radius: 5px;
                padding: 6px;
            }
            QFrame#PainterUMGSourcePreview,
            QFrame#PainterUMGTargetPreview {
                background: #151C25;
                border: 1px solid #2A3748;
                border-radius: 6px;
            }
            QFrame#PainterUMGLayoutControls {
                background: #151C25;
                border: 1px solid #34475D;
                border-radius: 6px;
            }
            QLabel#PainterUMGControlsTitle {
                color: #F0B84A;
                font-weight: 700;
            }
            QLabel#PainterUMGControlsSelection {
                color: #B8C5D6;
            }
            QLabel#PainterUMGControlsHint {
                color: #73849A;
                font-size: 10px;
            }
            QFrame#PainterUMGLayoutControls QComboBox,
            QFrame#PainterUMGLayoutControls QDoubleSpinBox {
                color: #E8EEF6;
                background: #101720;
                border: 1px solid #3A4C62;
                border-radius: 4px;
                min-height: 28px;
                padding: 3px 8px;
                font-size: 12px;
                font-weight: 600;
            }
            QFrame#PainterUMGLayoutControls QComboBox:hover,
            QFrame#PainterUMGLayoutControls QDoubleSpinBox:hover {
                background: #162232;
                border-color: #5B7899;
            }
            QFrame#PainterUMGLayoutControls QComboBox:focus,
            QFrame#PainterUMGLayoutControls QDoubleSpinBox:focus {
                background: #172536;
                border: 1px solid #35A5FF;
            }
            QFrame#PainterUMGLayoutControls QDoubleSpinBox QLineEdit {
                selection-background-color: #2469A8;
                selection-color: #FFFFFF;
            }
            QFrame#PainterUMGLayoutControls QComboBox:disabled,
            QFrame#PainterUMGLayoutControls QDoubleSpinBox:disabled {
                color: #617084;
                border-color: #273444;
            }
            QPushButton#PainterUMGViewButton,
            QPushButton#PainterUMGMaterialGraphButton {
                color: #DCE7F4;
                background: #1B2633;
                border: 1px solid #34475D;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton#PainterUMGViewButton:hover,
            QPushButton#PainterUMGMaterialGraphButton:hover {
                background: #243448;
                border-color: #59789E;
            }
            QPushButton#PainterUMGMaterialGraphButton:disabled {
                color: #617084;
                background: #141C26;
                border-color: #273444;
            }
            QPushButton#PainterUMGMaterialGraphButton:checked {
                color: #FFFFFF;
                background: #245D8E;
                border-color: #35A5FF;
            }
            QSplitter#PainterUMGWidgetViewSplitter::handle {
                background: #263344;
                width: 3px;
            }
            QMainWindow#PainterUMGWidgetViewWorkspace {
                background: #10151D;
            }
            QMainWindow#PainterUMGWidgetViewWorkspace::separator {
                background: #26384C;
                border-top: 1px solid #38516C;
                border-bottom: 1px solid #111923;
                width: 8px;
                height: 8px;
            }
            QMainWindow#PainterUMGWidgetViewWorkspace::separator:hover,
            QMainWindow#PainterUMGWidgetViewWorkspace::separator:pressed {
                background: #35A5FF;
                border-color: #78C7FF;
            }
            QDockWidget#PainterUMGMaterialGraphDock {
                color: #DCE7F4;
                background: #10151D;
                border: 1px solid #34475D;
            }
            QDockWidget#PainterUMGMaterialGraphDock::title {
                background: #182331;
                border-bottom: 1px solid #34475D;
                padding: 5px 8px;
                text-align: left;
            }
            """
        )

    def set_document(
        self,
        value: Mapping[str, Any] | None,
        *,
        artboard_id: str = "",
        force: bool = False,
    ) -> None:
        """Refresh both panes without mutating the canonical Painter document."""
        self.source_pane.preview.cancel_anchor_drag(emit=False)
        source = normalize_ui_document(value)
        selected_artboard_id = str(
            artboard_id or source.get("active_artboard_id") or ""
        )
        selection = dict(source.get("selection") or {})
        signature = (
            str(source.get("document_id") or ""),
            int(source.get("revision") or 0),
            selected_artboard_id,
            str(selection.get("object_id") or ""),
            tuple(str(value) for value in selection.get("object_ids", [])),
        )
        if not force and signature == self._source_signature:
            return
        if selected_artboard_id and any(
            str(row.get("id") or "") == selected_artboard_id
            for row in source.get("artboards", [])
        ):
            source["active_artboard_id"] = selected_artboard_id
        projection = project_painter_ui_umg_widgets(
            source,
            artboard_id=selected_artboard_id,
        )

        same_artboard = bool(
            self._has_document
            and self._artboard_id == selected_artboard_id
        )
        old_state = self.view_state() if same_artboard else {}
        source_canvas = active_ui_page_document(source)
        self.source_pane.set_document(source_canvas)
        self.target_pane.set_document(projection["document"])
        widgets_by_id = projection.get("widgets_by_id")
        if not isinstance(widgets_by_id, Mapping):
            widgets_by_id = {
                str(row.get("id") or ""): row
                for row in projection.get("widgets", [])
                if isinstance(row, Mapping)
            }
        selected_id = str(selection.get("object_id") or "")
        selected_widget = widgets_by_id.get(selected_id)
        self.source_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self.target_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self._source_document = copy.deepcopy(source)
        self.layout_controls.set_document(source)
        self._source_signature = signature
        self._report = copy.deepcopy(projection)
        self._artboard_id = selected_artboard_id
        self._has_document = True
        self._update_report_labels()

        if same_artboard and old_state:
            self.set_view_state(old_state)
        else:
            QTimer.singleShot(0, self.fit_views)

    def _update_report_labels(self) -> None:
        self._update_material_button()
        counts = dict(self._report.get("counts") or {})
        self.summary_label.setText(
            f"Native {int(counts.get('Native', 0))}  |  "
            f"Material {int(counts.get('Material', 0))}  |  "
            f"Baked {int(counts.get('Baked', 0))}  |  "
            f"Blocked {int(counts.get('Blocked', 0))}"
        )
        blockers = list(self._report.get("blockers") or [])
        resource_warnings = list(
            self._report.get("resource_warnings") or []
        )
        if not blockers and not resource_warnings:
            self.issue_label.hide()
            self.issue_label.clear()
            return
        sections: list[str] = []
        if blockers:
            preview = []
            for row in blockers[:3]:
                reasons = ", ".join(
                    str(value) for value in row.get("reasons", [])
                )
                preview.append(
                    f"{row.get('name') or row.get('object_id')}: {reasons}"
                )
            if len(blockers) > 3:
                preview.append(f"+{len(blockers) - 3} more")
            sections.append("Blocked: " + "  |  ".join(preview))
        if resource_warnings:
            preview = []
            for row in resource_warnings[:3]:
                name = str(row.get("name") or row.get("object_id") or "Image")
                message = str(
                    row.get("message")
                    or row.get("status")
                    or "Image preview unavailable"
                )
                preview.append(f"{name}: {message}")
            if len(resource_warnings) > 3:
                preview.append(f"+{len(resource_warnings) - 3} more")
            sections.append("Images: " + "  |  ".join(preview))
        self.issue_label.setText("\n".join(sections))
        self.issue_label.show()

    def _update_material_button(self) -> None:
        selection = self._source_document.get("selection")
        if not isinstance(selection, Mapping):
            selection = {}
        selected_id = str(selection.get("object_id") or "")
        selected_widget = self._widgets_by_id(self._report).get(selected_id)
        material: dict[str, Any] = {}
        if (
            isinstance(selected_widget, Mapping)
            and str(selected_widget.get("disposition") or "") == "Material"
            and bool(selected_widget.get("rendered"))
            and isinstance(selected_widget.get("material"), Mapping)
        ):
            material = copy.deepcopy(dict(selected_widget["material"]))
        available = bool(material)
        previous = self._selected_material
        was_visible = self.material_button.isChecked()
        self._selected_material = material
        self.material_button.setEnabled(available)
        self.material_button.setToolTip(
            painter_text("Open the generated Custom HLSL material graph")
            if available
            else painter_text("Select a generated Material layer")
        )
        if not available:
            self._material_graph_requested_visible = False
            self._set_material_button_checked(False)
            self._set_material_graph_visible(False)
            self._destroy_material_dock()
        elif previous != material:
            dock = self._material_dock
            if dock is not None:
                self._replace_material_graph_panel(dock)
            elif was_visible:
                self._set_material_graph_visible(True)

    def _set_material_button_checked(self, checked: bool) -> None:
        if self.material_button.isChecked() == bool(checked):
            return
        self.material_button.blockSignals(True)
        try:
            self.material_button.setChecked(bool(checked))
        finally:
            self.material_button.blockSignals(False)

    def _capture_material_graph_panel_state(self) -> None:
        panel = self._material_graph_panel
        if panel is None:
            return
        state_reader = getattr(panel, "view_state", None)
        if callable(state_reader):
            state = state_reader()
            if isinstance(state, Mapping):
                self._material_graph_panel_state = copy.deepcopy(dict(state))

    def _remember_material_dock_state(self) -> None:
        dock = self._material_dock
        if dock is None:
            return
        area = self.workspace.dockWidgetArea(dock)
        if area in {
            Qt.DockWidgetArea.BottomDockWidgetArea,
            Qt.DockWidgetArea.RightDockWidgetArea,
        }:
            self._material_dock_area = area
        self._material_dock_was_floating = dock.isFloating()
        self._material_dock_workspace_state = self.workspace.saveState(1)
        if dock.isFloating():
            self._material_dock_floating_geometry = dock.saveGeometry()

    def _replace_material_graph_panel(self, dock: QDockWidget) -> QWidget:
        self._capture_material_graph_panel_state()
        old_panel = self._material_graph_panel
        from app.painter_ui_umg_material_editor import (
            PainterUMGMaterialEditorPanel,
        )

        panel = PainterUMGMaterialEditorPanel(
            self._selected_material,
            dock,
        )
        panel.close_requested.connect(dock.close)
        dock.setWidget(panel)
        self._material_graph_panel = panel
        self._material_panel_needs_layout = True
        if old_panel is not None and old_panel is not panel:
            old_panel.deleteLater()
        if dock.isVisible():
            QTimer.singleShot(0, self._layout_material_dock_panel)
        return panel

    def _ensure_material_dock(self) -> QDockWidget | None:
        if not self._selected_material:
            return None
        dock = self._material_dock
        if dock is not None:
            return dock
        dock = QDockWidget(painter_text("Material Graph"), self.workspace)
        dock.setObjectName("PainterUMGMaterialGraphDock")
        dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self._material_dock = dock
        self.workspace.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            dock,
        )
        dock.hide()
        self._replace_material_graph_panel(dock)
        restored = False
        if self._material_dock_workspace_state is not None:
            restored = bool(
                self.workspace.restoreState(
                    self._material_dock_workspace_state,
                    1,
                )
            )
            if self._material_dock_was_floating:
                dock.setFloating(True)
            else:
                self.workspace.addDockWidget(self._material_dock_area, dock)
            if (
                self._material_dock_was_floating
                and self._material_dock_floating_geometry
            ):
                dock.restoreGeometry(self._material_dock_floating_geometry)
        dock.hide()
        self._material_dock_needs_default_size = not restored
        dock.visibilityChanged.connect(
            self._on_material_dock_visibility_changed
        )
        dock.dockLocationChanged.connect(
            lambda _area: self._remember_material_dock_state()
        )
        dock.topLevelChanged.connect(
            lambda _floating: self._remember_material_dock_state()
        )
        return dock

    def _destroy_material_dock(self) -> None:
        dock = self._material_dock
        if dock is None:
            self._material_graph_panel = None
            return
        self._capture_material_graph_panel_state()
        self._remember_material_dock_state()
        self._material_dock_lifecycle_guard += 1
        try:
            dock.hide()
            self.workspace.removeDockWidget(dock)
        finally:
            self._material_dock_lifecycle_guard -= 1
        dock.deleteLater()
        self._material_dock = None
        self._material_graph_panel = None
        self._material_panel_needs_layout = False

    def _on_material_dock_visibility_changed(self, visible: bool) -> None:
        dock = self._material_dock
        if dock is None:
            return
        if visible and not self._selected_material:
            dock.hide()
            return
        self._material_dock_visibility_serial += 1
        serial = self._material_dock_visibility_serial
        QTimer.singleShot(
            0,
            lambda: self._reconcile_material_dock_visibility(dock, serial),
        )

    def _reconcile_material_dock_visibility(
        self,
        dock: QDockWidget,
        serial: int,
    ) -> None:
        if (
            dock is not self._material_dock
            or serial != self._material_dock_visibility_serial
            or self._material_dock_lifecycle_guard > 0
            or not self.isVisible()
        ):
            return
        visible = bool(dock.isVisible() and self._selected_material)
        self._material_graph_requested_visible = visible
        self._set_material_button_checked(visible)
        if visible:
            QTimer.singleShot(0, self._layout_material_dock_panel)
        else:
            self._remember_material_dock_state()
            QTimer.singleShot(0, self.fit_views)

    def _set_material_graph_visible(self, visible: bool) -> None:
        show = bool(visible and self._selected_material)
        self._material_graph_requested_visible = show
        if not show:
            dock = self._material_dock
            if dock is not None:
                dock.close()
            if visible:
                self._set_material_button_checked(False)
            return
        dock = self._ensure_material_dock()
        if dock is None:
            self._set_material_button_checked(False)
            return
        dock.show()
        panel = self._material_graph_panel
        if panel is not None:
            panel.show()
        if dock.isFloating():
            dock.raise_()
        QTimer.singleShot(0, self._layout_material_dock_panel)

    def _layout_material_dock_panel(self) -> None:
        dock = self._material_dock
        panel = self._material_graph_panel
        if dock is None or panel is None or not dock.isVisible():
            return
        if self._material_dock_needs_default_size and not dock.isFloating():
            area = self.workspace.dockWidgetArea(dock)
            orientation = (
                Qt.Orientation.Vertical
                if area == Qt.DockWidgetArea.BottomDockWidgetArea
                else Qt.Orientation.Horizontal
            )
            extent = (
                max(220, int(self.workspace.height() * 0.38))
                if orientation == Qt.Orientation.Vertical
                else max(300, int(self.workspace.width() * 0.32))
            )
            self.workspace.resizeDocks([dock], [extent], orientation)
            self._material_dock_needs_default_size = False
        # Fit only after QMainWindow has applied the dock allocation; doing it
        # before resizeDocks leaves both the graph and comparison canvases
        # fitted to their previous viewport sizes.
        QTimer.singleShot(0, self.fit_views)
        if not self._material_panel_needs_layout:
            return
        self._material_panel_needs_layout = False
        state = copy.deepcopy(self._material_graph_panel_state)
        if state:
            self._material_graph_panel_state = {}
            QTimer.singleShot(
                0,
                lambda: (
                    panel.set_view_state(state)
                    if self._material_graph_panel is panel
                    else None
                ),
            )
        else:
            QTimer.singleShot(
                0,
                lambda: (
                    panel.graph_view.fit_graph()
                    if self._material_graph_panel is panel
                    else None
                ),
            )

    def material_graph_panel(self) -> QWidget | None:
        """Return the embedded graph panel, if it has been constructed."""
        return self._material_graph_panel

    def material_dock(self) -> QDockWidget | None:
        """Return the real Qt dock hosting the material graph, if created."""
        return self._material_dock

    def material_graph_visible(self) -> bool:
        dock = self._material_dock
        return bool(dock is not None and dock.isVisible())

    def report(self) -> dict[str, Any]:
        return copy.deepcopy(self._report)

    def anchor_decoration(self) -> dict[str, dict[str, Any]]:
        """Return the UMG decoration plan for both canvases."""
        return {
            "source": self.source_pane.anchor_decoration(),
            "target": self.target_pane.anchor_decoration(),
        }

    def control_state(self) -> dict[str, Any]:
        """Return the selected source object's editable UMG layout state."""
        return self.layout_controls.control_state()

    def _forward_object_geometry(
        self,
        object_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        self.object_changes_requested.emit(
            str(object_id),
            {
                "x": float(x),
                "y": float(y),
                "width": max(1.0, float(width)),
                "height": max(1.0, float(height)),
            },
        )

    def _preview_transforms(self, changes_by_id: object) -> None:
        if not isinstance(changes_by_id, Mapping) or not changes_by_id:
            return
        source = copy.deepcopy(self._source_document)
        rows_by_id = {
            str(row.get("id") or ""): row
            for row in source.get("objects", [])
        }
        changed_rows: list[dict[str, Any]] = []
        for object_id, changes in changes_by_id.items():
            row = rows_by_id.get(str(object_id))
            if row is None or not isinstance(changes, Mapping):
                continue
            for key in ("x", "y", "width", "height"):
                if key in changes:
                    row[key] = (
                        max(1.0, float(changes[key]))
                        if key in {"width", "height"}
                        else float(changes[key])
                    )
            changed_rows.append(row)
        if not changed_rows:
            return
        for row in changed_rows:
            row["constraints"] = capture_ui_constraints(
                row,
                constraint_parent_geometry(source, row),
                row.get("constraints"),
            )
        projection = project_painter_ui_umg_widgets(
            source,
            artboard_id=self._artboard_id,
        )
        self.target_pane.set_document(projection["document"])
        selected_id = str(
            source.get("selection", {}).get("object_id") or ""
        )
        widgets_by_id = projection.get("widgets_by_id")
        if not isinstance(widgets_by_id, Mapping):
            widgets_by_id = {
                str(row.get("id") or ""): row
                for row in projection.get("widgets", [])
                if isinstance(row, Mapping)
            }
        self.target_pane.set_anchor_widget(
            widgets_by_id.get(selected_id),
            selected_id=selected_id,
        )
        self.layout_controls.preview_geometry(changes_by_id)
        self._report = copy.deepcopy(projection)
        self._update_report_labels()

    @staticmethod
    def _widgets_by_id(projection: Mapping[str, Any]) -> Mapping[str, Any]:
        widgets_by_id = projection.get("widgets_by_id")
        if isinstance(widgets_by_id, Mapping):
            return widgets_by_id
        return {
            str(row.get("id") or ""): row
            for row in projection.get("widgets", [])
            if isinstance(row, Mapping)
        }

    def _preview_anchor_changes(
        self,
        object_id: str,
        changes: object,
    ) -> None:
        if not isinstance(changes, Mapping):
            return
        constraints = changes.get("constraints")
        if not isinstance(constraints, Mapping):
            return
        source = copy.deepcopy(self._source_document)
        row = next(
            (
                item
                for item in source.get("objects", [])
                if str(item.get("id") or "") == str(object_id or "")
            ),
            None,
        )
        if row is None:
            return
        row["constraints"] = copy.deepcopy(dict(constraints))
        projection = project_painter_ui_umg_widgets(
            source,
            artboard_id=self._artboard_id,
        )
        widgets_by_id = self._widgets_by_id(projection)
        selected_id = str(
            source.get("selection", {}).get("object_id") or ""
        )
        selected_widget = widgets_by_id.get(selected_id)
        self.source_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self.target_pane.set_document(projection["document"])
        self.target_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self.layout_controls.preview_constraints(object_id, constraints)
        self._report = copy.deepcopy(projection)
        self._update_report_labels()

    def _restore_anchor_preview(self) -> None:
        if not self._source_document:
            return
        projection = project_painter_ui_umg_widgets(
            self._source_document,
            artboard_id=self._artboard_id,
        )
        selected_id = str(
            self._source_document.get("selection", {}).get("object_id") or ""
        )
        selected_widget = self._widgets_by_id(projection).get(selected_id)
        self.source_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self.target_pane.set_document(projection["document"])
        self.target_pane.set_anchor_widget(
            selected_widget,
            selected_id=selected_id,
        )
        self.layout_controls.set_document(self._source_document)
        self._report = copy.deepcopy(projection)
        self._update_report_labels()

    def _sync_target_view(self, state: Mapping[str, Any]) -> None:
        self.target_pane.preview.set_view_state(state, emit=False)

    def fit_views(self) -> None:
        self.source_pane.fit()
        state = self.source_pane.preview.view_state()
        self.target_pane.preview.set_view_state(state, emit=False)

    def set_view_state(self, value: Mapping[str, Any] | None) -> None:
        state = value if isinstance(value, Mapping) else {}
        source_state = state.get("source") if isinstance(state.get("source"), Mapping) else state
        target_state = state.get("target") if isinstance(state.get("target"), Mapping) else source_state
        self.source_pane.preview.set_view_state(source_state, emit=False)
        self.target_pane.preview.set_view_state(target_state, emit=False)

    def view_state(self) -> dict[str, Any]:
        return {
            "source": self.source_pane.preview.view_state(),
            "target": self.target_pane.preview.view_state(),
        }

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self.visibility_changed.emit(True)
        if self._has_document:
            QTimer.singleShot(0, self.fit_views)
        if (
            self._material_graph_requested_visible
            and self._selected_material
        ):
            QTimer.singleShot(0, self._restore_requested_material_dock)

    def _restore_requested_material_dock(self) -> None:
        if (
            not self.isVisible()
            or not self._selected_material
            or not self._material_graph_requested_visible
        ):
            return
        dock = self._ensure_material_dock()
        if dock is None:
            return
        self._set_material_button_checked(True)
        self._material_dock_lifecycle_guard += 1
        try:
            dock.show()
            panel = self._material_graph_panel
            if panel is not None:
                panel.show()
        finally:
            self._material_dock_lifecycle_guard -= 1
        if dock.isFloating():
            dock.raise_()
        QTimer.singleShot(0, self._layout_material_dock_panel)

    def hideEvent(self, event) -> None:  # noqa: N802 - Qt API
        dock = self._material_dock
        if dock is not None and dock.isVisible():
            self._material_graph_requested_visible = bool(
                self._selected_material
                and (
                    self._material_graph_requested_visible
                    or self.material_button.isChecked()
                )
            )
            self._remember_material_dock_state()
            self._material_dock_lifecycle_guard += 1
            try:
                dock.hide()
            finally:
                self._material_dock_lifecycle_guard -= 1
        super().hideEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.layout_controls.flush_pending_changes()
        self.layout_controls.flush_pending_geometry_changes()
        self.visibility_changed.emit(False)
        super().closeEvent(event)

    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.WindowActivate and self._has_document:
            self._update_report_labels()
        return result


def _sync_owner_action(owner: Any, visible: bool) -> None:
    action = getattr(owner, "_painter_umg_widget_view_action", None)
    if action is None or action.isChecked() == bool(visible):
        return
    action.blockSignals(True)
    try:
        action.setChecked(bool(visible))
    finally:
        action.blockSignals(False)


def ensure_painter_umg_widget_view(owner: Any) -> PainterUMGWidgetView:
    view = getattr(owner, "_painter_umg_widget_view", None)
    if isinstance(view, PainterUMGWidgetView):
        return view
    view = PainterUMGWidgetView(owner)
    view.visibility_changed.connect(
        lambda visible: _sync_owner_action(owner, visible)
    )
    view.refresh_requested.connect(
        lambda: refresh_painter_umg_widget_view(owner, force=True)
    )
    view.selection_requested.connect(owner._select_painter_ui_object)
    view.object_changes_requested.connect(
        lambda object_id, changes: owner._update_painter_ui_object_changes(
            object_id,
            changes,
            label="Edit UMG layout",
        )
    )
    view.objects_changes_requested.connect(
        lambda changes: owner._update_painter_ui_objects_batch(
            changes,
            label="Transform UMG widgets",
        )
    )
    owner._painter_umg_widget_view = view
    return view


def refresh_painter_umg_widget_view(
    owner: Any,
    *,
    force: bool = False,
) -> bool:
    view = getattr(owner, "_painter_umg_widget_view", None)
    if not isinstance(view, PainterUMGWidgetView):
        return False
    if not force and not view.isVisible():
        return False
    document = getattr(owner, "_painter_ui_document", None)
    view.set_document(document, force=force)
    return True


def set_painter_umg_widget_view_enabled(owner: Any, enabled: bool) -> bool:
    visible = bool(enabled)
    if visible and str(
        getattr(owner, "_canvas_workspace_mode", "paint") or "paint"
    ) != "ui_design":
        owner._set_canvas_workspace_mode("ui_design")
    view = getattr(owner, "_painter_umg_widget_view", None)
    if visible:
        view = ensure_painter_umg_widget_view(owner)
        refresh_painter_umg_widget_view(owner, force=True)
        view.show()
        view.raise_()
        view.activateWindow()
    elif isinstance(view, PainterUMGWidgetView):
        view.hide()
    _sync_owner_action(owner, visible)
    return visible


__all__ = [
    "PainterUMGWidgetView",
    "ensure_painter_umg_widget_view",
    "refresh_painter_umg_widget_view",
    "set_painter_umg_widget_view_enabled",
]
