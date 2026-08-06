"""Layers and Inspect panel for Painter's UI Design workspace."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import QEvent, QRect, QSize, Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QValidator
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_constraints import (
    capture_ui_constraints,
    constrain_ui_size,
    constraint_parent_geometry,
    normalize_ui_constraints,
)
from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_document import normalize_ui_document
from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text
from app.painter_ui_sizing_control import PainterUISizingControl
from app.painter_ui_umg_panel_selector import PainterUIUMGPanelSelector
from app.color_picker_widget import ColorPaletteStrip, color_edit_with_picker


class PainterUILayerList(QListWidget):
    hierarchy_drop_requested = Signal(object, str, str)
    hovered_object_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._hierarchy_drop_preview: tuple[str, str, QRect] | None = None
        self._hovered_object_id = ""
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.itemEntered.connect(
            lambda item: self._set_hovered_object(
                str(item.data(Qt.ItemDataRole.UserRole) or "")
            )
        )

    def _set_hovered_object(self, object_id: str) -> None:
        target = str(object_id or "")
        if target == self._hovered_object_id:
            return
        self._hovered_object_id = target
        self.hovered_object_changed.emit(target)

    def clear_hover(self) -> None:
        self._set_hovered_object("")

    def viewportEvent(self, event) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            item = self.itemAt(event.position().toPoint())
            self._set_hovered_object(
                str(item.data(Qt.ItemDataRole.UserRole) or "")
                if item is not None
                else ""
            )
        elif event.type() == QEvent.Type.Leave:
            self.clear_hover()
        return super().viewportEvent(event)

    def _hierarchy_drop_plan(
        self,
        point,
    ) -> tuple[str, str, QRect]:
        target = self.itemAt(point)
        if target is None:
            return "", "root", QRect()
        target_id = str(target.data(Qt.ItemDataRole.UserRole) or "")
        rect = self.visualItemRect(target)
        relative_y = point.y() - rect.top()
        if relative_y < rect.height() * 0.25:
            placement = "before"
        elif relative_y > rect.height() * 0.75:
            placement = "after"
        elif str(
            target.data(int(Qt.ItemDataRole.UserRole) + 1) or ""
        ) in {"group", "frame"}:
            placement = "inside"
        else:
            placement = "after"
        return target_id, placement, rect

    def dragMoveEvent(self, event) -> None:
        super().dragMoveEvent(event)
        point = event.position().toPoint()
        target_id, placement, rect = self._hierarchy_drop_plan(point)
        selected_ids = {
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in self.selectedItems()
        }
        self._hierarchy_drop_preview = (
            None
            if target_id in selected_ids
            else (target_id, placement, rect)
        )
        self.viewport().update()

    def dragLeaveEvent(self, event) -> None:
        self._hierarchy_drop_preview = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        preview = self._hierarchy_drop_preview
        if preview is None:
            return
        _target_id, placement, rect = preview
        painter = QPainter(self.viewport())
        if placement == "inside" and not rect.isNull():
            painter.setBrush(QColor(71, 197, 142, 30))
            painter.setPen(QPen(QColor("#47C58E"), 2.0))
            painter.drawRoundedRect(rect.adjusted(2, 1, -2, -1), 4.0, 4.0)
        else:
            y = (
                rect.top()
                if placement == "before"
                else rect.bottom()
                if placement == "after"
                else self.viewport().height() - 2
            )
            painter.setPen(QPen(QColor("#72A7FF"), 2.0))
            painter.drawLine(4, y, self.viewport().width() - 4, y)
        painter.end()

    def dropEvent(self, event) -> None:
        selected_ids = [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in self.selectedItems()
            if str(item.data(Qt.ItemDataRole.UserRole) or "")
        ]
        if not selected_ids:
            event.ignore()
            return
        point = event.position().toPoint()
        target_id, placement, _rect = self._hierarchy_drop_plan(point)
        if not target_id:
            self.hierarchy_drop_requested.emit(selected_ids, "", "root")
            self._hierarchy_drop_preview = None
            event.acceptProposedAction()
            return
        if not target_id or target_id in selected_ids:
            self._hierarchy_drop_preview = None
            event.ignore()
            return
        self.hierarchy_drop_requested.emit(selected_ids, target_id, placement)
        self._hierarchy_drop_preview = None
        event.acceptProposedAction()


class _PainterUIDragValueMixin:
    """Studio-style numeric field: type a value or drag horizontally."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._drag_origin_x: float | None = None
        self._drag_origin_value = 0.0
        self._dragging_value = False
        self._edit_origin_value = float(self.value())
        self._reset_value: float | None = None
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def setResetValue(self, value: float | None) -> None:
        self._reset_value = None if value is None else float(value)

    def resetToDefault(self) -> bool:
        if self._reset_value is None:
            return False
        value = (
            int(round(self._reset_value))
            if isinstance(self, QSpinBox)
            else float(self._reset_value)
        )
        self.setValue(value)
        self.editingFinished.emit()
        return True

    def focusInEvent(self, event) -> None:
        self._edit_origin_value = float(self.value())
        super().focusInEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin_x = float(event.globalPosition().x())
            self._drag_origin_value = float(self.value())
            self._edit_origin_value = float(self.value())
            self._dragging_value = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._drag_origin_x is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            delta = float(event.globalPosition().x()) - self._drag_origin_x
            if abs(delta) >= 3.0:
                self._dragging_value = True
                scale = 0.1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    scale = 10.0
                self.setValue(
                    self._drag_origin_value
                    + delta * max(0.01, float(self.singleStep())) * scale
                )
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        dragged = self._dragging_value
        self._drag_origin_x = None
        self._dragging_value = False
        if dragged and event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _numeric_expression(self, text: str) -> str:
        expression = str(text or "").strip()
        prefix = str(self.prefix() or "")
        suffix = str(self.suffix() or "")
        if prefix and expression.startswith(prefix):
            expression = expression[len(prefix):].strip()
        if suffix and expression.endswith(suffix):
            expression = expression[:-len(suffix)].strip()
        return expression

    def validate(self, text: str, pos: int):
        expression = self._numeric_expression(text)
        allowed = set("0123456789.+-*/()% ×÷")
        if expression and all(char in allowed for char in expression):
            from app.painter_ui_numeric_input import (
                evaluate_painter_numeric_input,
            )

            try:
                evaluate_painter_numeric_input(
                    expression,
                    origin=self._edit_origin_value,
                )
            except ValueError:
                return QValidator.State.Intermediate, text, pos
            return QValidator.State.Acceptable, text, pos
        return super().validate(text, pos)

    def valueFromText(self, text: str):
        from app.painter_ui_numeric_input import evaluate_painter_numeric_input

        expression = self._numeric_expression(text)
        try:
            value = evaluate_painter_numeric_input(
                expression,
                origin=self._edit_origin_value,
            )
        except ValueError:
            return super().valueFromText(text)
        if isinstance(self, QSpinBox):
            return int(round(value))
        return float(value)

    def contextMenuEvent(self, event) -> None:
        menu = self.lineEdit().createStandardContextMenu()
        reset_action = None
        if self._reset_value is not None:
            menu.addSeparator()
            reset_action = menu.addAction(painter_text("Reset"))
        chosen = menu.exec(event.globalPos())
        if chosen is reset_action and self._reset_value is not None:
            self.resetToDefault()
        menu.deleteLater()


class PainterUIDragSpinBox(_PainterUIDragValueMixin, QSpinBox):
    pass


class PainterUIDragDoubleSpinBox(_PainterUIDragValueMixin, QDoubleSpinBox):
    pass


class PainterUIInspector(QWidget):
    context_mode_changed = Signal(str)
    template_apply_requested = Signal(str)
    template_save_requested = Signal(str, str)
    template_install_requested = Signal(str)
    review_comment_add_requested = Signal(str)
    review_comment_update_requested = Signal(str, object)
    review_comment_remove_requested = Signal(str)
    review_comment_selected = Signal(str)
    review_checkpoint_requested = Signal(str)
    review_export_requested = Signal(str)
    prototype_export_requested = Signal(str)
    web_preflight_requested = Signal()
    web_package_requested = Signal(str)
    ppt_preflight_requested = Signal(str)
    ppt_send_requested = Signal(str)
    assets_export_requested = Signal(str, object, object, bool)
    figma_document_imported = Signal(object, str, object)
    figma_export_requested = Signal(str)
    umg_preflight_requested = Signal()
    umg_package_requested = Signal(str)
    umg_generate_requested = Signal(str, str)
    ai_plan_requested = Signal(str)
    ai_apply_requested = Signal(object)
    ai_audit_requested = Signal()
    ai_prototype_plan_requested = Signal(str)
    ai_prototype_apply_requested = Signal(object)
    artifact_open_requested = Signal(str)
    artboard_selected = Signal(str)
    artboard_add_requested = Signal(str, int, int, str)
    artboard_delete_requested = Signal(str)
    artboard_layout_changed = Signal(str, object)
    layout_grid_style_add_requested = Signal(str)
    layout_grid_style_update_requested = Signal(str, str)
    layout_grid_style_apply_requested = Signal(str, str)
    layout_grid_style_remove_requested = Signal(str)
    responsive_override_changed = Signal(str, str, str, object)
    responsive_override_remove_requested = Signal(str, str, str)
    responsive_preview_requested = Signal()
    component_create_requested = Signal(str, str)
    component_instantiate_requested = Signal(str, str, float, float)
    component_playground_requested = Signal(str)
    component_variant_create_requested = Signal(str, str)
    component_variants_combine_requested = Signal(object)
    component_variant_switch_requested = Signal(str, str)
    component_variant_values_set_requested = Signal(str, object)
    component_instance_variant_values_set_requested = Signal(str, object)
    component_instance_property_set_requested = Signal(str, str, object)
    component_instance_swap_preferred_edit_requested = Signal(str, str)
    component_slot_reset_requested = Signal(str, str)
    component_detach_requested = Signal(str, bool, str)
    component_override_reset_requested = Signal(str, str, str)
    component_override_reset_all_requested = Signal(str)
    component_update_requested = Signal(str, object)
    token_add_requested = Signal(object)
    token_update_requested = Signal(str, object)
    token_remove_requested = Signal(str, bool)
    style_add_requested = Signal(object)
    style_update_requested = Signal(str, object)
    style_remove_requested = Signal(str, bool)
    style_apply_requested = Signal(str, str)
    style_unlink_requested = Signal(str, str)
    library_package_export_requested = Signal(object)
    library_package_install_requested = Signal(str)
    library_update_apply_requested = Signal(str)
    library_update_defer_requested = Signal(str, int)
    library_rollback_requested = Signal(str)
    library_component_insert_requested = Signal(str, str, int)
    library_asset_insert_requested = Signal(str, str, str, int)
    token_binding_requested = Signal(str, str, str)
    token_import_requested = Signal(str)
    token_export_requested = Signal()
    variable_collection_add_requested = Signal(object)
    variable_collection_update_requested = Signal(str, object)
    variable_collection_remove_requested = Signal(str, bool)
    variable_mode_add_requested = Signal(str, str)
    variable_mode_update_requested = Signal(str, str, str)
    variable_mode_remove_requested = Signal(str, str, bool)
    variable_mode_set_requested = Signal(str, str, str)
    object_selected = Signal(str)
    selection_changed = Signal(object, str)
    layer_hover_changed = Signal(str)
    geometry_changed = Signal(str, object)
    properties_changed = Signal(str, object)
    batch_properties_changed = Signal(object)
    selection_tidy_requested = Signal(str, object)
    auto_layout_entry_requested = Signal(str)
    clip_changed = Signal(str, bool)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    arrange_requested = Signal(str, str)
    group_requested = Signal(object)
    ungroup_requested = Signal(str)
    reorder_requested = Signal(object, str)
    hierarchy_drop_requested = Signal(object, str, str)
    text_range_requested = Signal(str, int, int, object, bool)
    remote_component_requested = Signal(str, str, object)
    boolean_requested = Signal(str, str, object)
    section_requested = Signal(str, str, object)
    motion_open_requested = Signal(str)
    motion_preview_hover_requested = Signal(str)
    motion_bake_flipbook_requested = Signal(str)
    motion_binding_migrate_requested = Signal(str)
    motion_binding_relink_requested = Signal(str, str, str)
    motion_binding_detach_requested = Signal(str)
    prototype_connection_add_requested = Signal(object)
    prototype_connection_remove_requested = Signal(str)
    prototype_connection_reorder_requested = Signal(str, int)
    prototype_transition_set_requested = Signal(str, object)
    prototype_flow_add_requested = Signal(object)
    prototype_flow_activate_requested = Signal(str)
    prototype_preview_changed = Signal(bool)
    prototype_preview_reset_requested = Signal()
    prototype_device_changed = Signal(object)
    prototype_background_changed = Signal(str)
    frame_preset_requested = Signal(str, int, int)
    stress_preview_requested = Signal(str, str)
    dev_ready_set_requested = Signal(str, str, bool, str)
    dev_annotation_add_requested = Signal(str, str, str, str)
    dev_annotation_update_requested = Signal(str, object)
    dev_annotation_remove_requested = Signal(str)
    dev_revision_compare_requested = Signal()
    collapsed_changed = Signal(bool)
    dock_toggle_requested = Signal()
    temporary_close_requested = Signal()
    auto_hide_changed = Signal(bool)
    zoom_requested = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._syncing = False
        self._active_tool_context = "select"
        self._selection_count = 0
        self._appearance_style: dict[str, Any] = {}
        self._collapsed = False
        self._temporary_expanded = False
        self._auto_hide = False
        self.setObjectName("PainterUIInspector")
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        title_bar = QFrame()
        title_bar.setObjectName("PainterUIInspectorTitleBar")
        self.title_bar = title_bar
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(7, 3, 5, 3)
        title_layout.setSpacing(4)
        title = QLabel("UI DESIGN")
        title.setObjectName("PaintSectionTitle")
        self.title_label = title
        title_layout.addWidget(title)
        title_layout.addStretch(1)
        self.dock_button = QPushButton("")
        self.dock_button.setObjectName("PainterUIPanelCollapse")
        self.dock_button.setFixedSize(22, 22)
        self.dock_button.setIcon(
            app_icon("popout", size=12, color="#B8C4D3")
        )
        self.dock_button.setIconSize(icon_size(12))
        self.dock_button.setToolTip("Detach inspector")
        self.dock_button.setAccessibleName("Detach inspector")
        self.dock_button.clicked.connect(self.dock_toggle_requested)
        title_layout.addWidget(self.dock_button)
        self.collapse_button = QPushButton("")
        self.collapse_button.setObjectName("PainterUIPanelCollapse")
        self.collapse_button.setFixedSize(22, 22)
        self.collapse_button.clicked.connect(self._on_collapse_clicked)
        title_layout.addWidget(self.collapse_button)
        root.addWidget(title_bar)
        self.artboard_combo = QComboBox()
        self.artboard_combo.setToolTip("Active UI artboard")
        self.artboard_combo.currentIndexChanged.connect(self._on_artboard_changed)
        artboard_bar = QFrame()
        artboard_bar.setObjectName("PainterUIArtboardBar")
        self.artboard_bar = artboard_bar
        artboard_add_row = QHBoxLayout()
        artboard_add_row.setContentsMargins(5, 3, 5, 4)
        artboard_add_row.setSpacing(3)
        artboard_bar.setLayout(artboard_add_row)
        self.artboard_preset_combo = QComboBox(self)
        for name, width, height, breakpoint in (
            ("iPhone 390 x 844", 390, 844, "mobile"),
            ("Android 412 x 915", 412, 915, "mobile"),
            ("Desktop 1440 x 900", 1440, 900, "desktop"),
            ("Console 1920 x 1080", 1920, 1080, "console"),
            ("Broadcast 1920 x 1080", 1920, 1080, "broadcast"),
        ):
            self.artboard_preset_combo.addItem(
                name,
                (name.split(" ", 1)[0], width, height, breakpoint),
            )
        self.artboard_preset_combo.setToolTip("New artboard size")
        self.artboard_preset_combo.hide()
        add_artboard = QPushButton("")
        add_artboard.setObjectName("PainterUIIconButton")
        add_artboard.setFixedSize(28, 26)
        add_artboard.setIcon(app_icon("plus", size=13, color="#D9E2ED"))
        add_artboard.setIconSize(icon_size(13))
        add_artboard.setToolTip("Add artboard from preset")
        add_artboard.setAccessibleName("Add artboard")
        preset_menu = QMenu(add_artboard)
        preset_menu.setObjectName("PainterUIArtboardPresetMenu")
        for index in range(self.artboard_preset_combo.count()):
            action = preset_menu.addAction(self.artboard_preset_combo.itemText(index))
            action.triggered.connect(
                lambda _checked=False, preset_index=index: (
                    self._emit_add_artboard_preset(preset_index)
                )
            )
        add_artboard.setMenu(preset_menu)
        self.add_artboard_button = add_artboard
        self.delete_artboard_button = QPushButton("")
        self.delete_artboard_button.setObjectName("PainterUIIconButton")
        self.delete_artboard_button.setFixedSize(28, 26)
        self.delete_artboard_button.setIcon(
            app_icon("trash", size=13, color="#D9DEE6")
        )
        self.delete_artboard_button.setIconSize(icon_size(13))
        self.delete_artboard_button.setToolTip("Delete active artboard")
        self.delete_artboard_button.setAccessibleName("Delete active artboard")
        self.delete_artboard_button.setEnabled(False)
        self.delete_artboard_button.clicked.connect(self._emit_delete_artboard)
        self.responsive_preview_button = QPushButton("")
        self.responsive_preview_button.setObjectName("PainterUIIconButton")
        self.responsive_preview_button.setFixedSize(28, 26)
        self.responsive_preview_button.setIcon(
            app_icon("grid", size=13, color="#D9E2ED")
        )
        self.responsive_preview_button.setIconSize(icon_size(13))
        self.responsive_preview_button.setToolTip(
            painter_text("Responsive Preview")
        )
        self.responsive_preview_button.setAccessibleName(
            painter_text("Responsive Preview")
        )
        self.responsive_preview_button.clicked.connect(
            self.responsive_preview_requested
        )
        artboard_add_row.addWidget(self.artboard_combo, 1)
        artboard_add_row.addWidget(self.responsive_preview_button)
        artboard_add_row.addWidget(add_artboard)
        artboard_add_row.addWidget(self.delete_artboard_button)
        root.addWidget(artboard_bar)

        artboard_layout_frame = QFrame()
        artboard_layout_frame.setObjectName("PainterUIArtboardLayout")
        artboard_layout_form = QFormLayout(artboard_layout_frame)
        artboard_layout_form.setContentsMargins(4, 4, 4, 4)
        artboard_layout_form.setSpacing(3)
        context_row = QFrame()
        context_layout = QHBoxLayout(context_row)
        context_layout.setContentsMargins(0, 0, 0, 0)
        context_layout.setSpacing(3)
        self.artboard_breakpoint_combo = QComboBox()
        self.artboard_breakpoint_combo.setEditable(True)
        for breakpoint in ("custom", "mobile", "desktop", "console", "broadcast"):
            self.artboard_breakpoint_combo.addItem(breakpoint.title(), breakpoint)
        self.artboard_orientation_combo = QComboBox()
        self.artboard_orientation_combo.addItem("Portrait", "portrait")
        self.artboard_orientation_combo.addItem("Landscape", "landscape")
        self.artboard_breakpoint_combo.currentIndexChanged.connect(
            self._emit_artboard_context
        )
        self.artboard_breakpoint_combo.lineEdit().editingFinished.connect(
            self._emit_artboard_context
        )
        self.artboard_orientation_combo.currentIndexChanged.connect(
            self._emit_artboard_context
        )
        context_layout.addWidget(self.artboard_breakpoint_combo)
        context_layout.addWidget(self.artboard_orientation_combo)
        artboard_layout_form.addRow("Context", context_row)
        self.artboard_theme_combo = QComboBox()
        self.artboard_theme_combo.addItem("Light", "light")
        self.artboard_theme_combo.addItem("Dark", "dark")
        self.artboard_theme_combo.addItem("High Contrast", "high_contrast")
        self.artboard_theme_combo.setToolTip(
            "Preview token values for this artboard theme"
        )
        self.artboard_theme_combo.currentIndexChanged.connect(
            self._emit_artboard_context
        )
        artboard_layout_form.addRow("Theme", self.artboard_theme_combo)
        grid_style_row = QFrame()
        grid_style_layout = QHBoxLayout(grid_style_row)
        grid_style_layout.setContentsMargins(0, 0, 0, 0)
        grid_style_layout.setSpacing(3)
        self.artboard_grid_style_combo = QComboBox()
        self.artboard_grid_style_combo.addItem("Local", "")
        self.artboard_grid_style_combo.currentIndexChanged.connect(
            self._emit_layout_grid_style_apply
        )
        grid_style_layout.addWidget(self.artboard_grid_style_combo, 1)
        self.artboard_grid_style_add_button = QPushButton()
        self.artboard_grid_style_add_button.setIcon(
            app_icon("plus", size=12, color="#CBD5E2")
        )
        self.artboard_grid_style_add_button.setToolTip("Save as grid style")
        self.artboard_grid_style_add_button.clicked.connect(
            self._emit_layout_grid_style_add
        )
        grid_style_layout.addWidget(self.artboard_grid_style_add_button)
        self.artboard_grid_style_update_button = QPushButton()
        self.artboard_grid_style_update_button.setIcon(
            app_icon("save", size=12, color="#CBD5E2")
        )
        self.artboard_grid_style_update_button.setToolTip(
            "Update linked grid style"
        )
        self.artboard_grid_style_update_button.clicked.connect(
            self._emit_layout_grid_style_update
        )
        grid_style_layout.addWidget(self.artboard_grid_style_update_button)
        self.artboard_grid_style_remove_button = QPushButton()
        self.artboard_grid_style_remove_button.setIcon(
            app_icon("trash", size=12, color="#CBD5E2")
        )
        self.artboard_grid_style_remove_button.setToolTip("Remove grid style")
        self.artboard_grid_style_remove_button.clicked.connect(
            self._emit_layout_grid_style_remove
        )
        grid_style_layout.addWidget(self.artboard_grid_style_remove_button)
        artboard_layout_form.addRow("Grid Style", grid_style_row)
        self.artboard_grid_mode_combo = QComboBox()
        for label, mode in (
            ("No layout grid", "none"),
            ("Uniform grid", "grid"),
            ("Columns", "columns"),
            ("Rows", "rows"),
        ):
            self.artboard_grid_mode_combo.addItem(label, mode)
        self.artboard_grid_mode_combo.currentIndexChanged.connect(
            self._emit_artboard_layout
        )
        artboard_layout_form.addRow("Layout", self.artboard_grid_mode_combo)
        self.artboard_grid_alignment_combo = QComboBox()
        self.artboard_grid_alignment_combo.addItem("Stretch", "stretch")
        self.artboard_grid_alignment_combo.addItem("Center", "center")
        self.artboard_grid_alignment_combo.currentIndexChanged.connect(
            self._emit_artboard_layout
        )
        artboard_layout_form.addRow(
            "Grid Alignment",
            self.artboard_grid_alignment_combo,
        )
        grid_metrics = QFrame()
        grid_metrics.setObjectName("PainterUICompactGrid")
        grid_metrics_layout = QGridLayout(grid_metrics)
        grid_metrics_layout.setContentsMargins(0, 0, 0, 0)
        grid_metrics_layout.setSpacing(3)
        self.artboard_grid_count_spin = PainterUIDragSpinBox()
        self.artboard_grid_count_spin.setRange(1, 64)
        self.artboard_grid_count_spin.setPrefix("C ")
        self.artboard_grid_size_spin = PainterUIDragDoubleSpinBox()
        self.artboard_grid_size_spin.setRange(2.0, 512.0)
        self.artboard_grid_size_spin.setPrefix("S ")
        self.artboard_grid_size_spin.setSuffix(" px")
        self.artboard_grid_gutter_spin = PainterUIDragDoubleSpinBox()
        self.artboard_grid_gutter_spin.setRange(0.0, 10000.0)
        self.artboard_grid_gutter_spin.setPrefix("G ")
        self.artboard_grid_gutter_spin.setSuffix(" px")
        self.artboard_grid_margin_spin = PainterUIDragDoubleSpinBox()
        self.artboard_grid_margin_spin.setRange(0.0, 10000.0)
        self.artboard_grid_margin_spin.setPrefix("M ")
        self.artboard_grid_margin_spin.setSuffix(" px")
        metric_controls = (
            self.artboard_grid_count_spin,
            self.artboard_grid_size_spin,
            self.artboard_grid_gutter_spin,
            self.artboard_grid_margin_spin,
        )
        for index, control in enumerate(metric_controls):
            control.editingFinished.connect(self._emit_artboard_layout)
            grid_metrics_layout.addWidget(control, index // 2, index % 2)
        artboard_layout_form.addRow("Metrics", grid_metrics)
        safe_row = QFrame()
        safe_row.setObjectName("PainterUICompactGrid")
        safe_layout = QGridLayout(safe_row)
        safe_layout.setContentsMargins(0, 0, 0, 0)
        safe_layout.setSpacing(3)
        self.artboard_safe_visible_check = QCheckBox("Safe")
        self.artboard_safe_visible_check.toggled.connect(
            self._emit_artboard_layout
        )
        safe_layout.addWidget(self.artboard_safe_visible_check, 0, 0, 1, 2)
        self.artboard_safe_controls: dict[str, QSpinBox] = {}
        for index, (prefix, edge) in enumerate((
            ("L ", "left"),
            ("T ", "top"),
            ("R ", "right"),
            ("B ", "bottom"),
        )):
            spin = PainterUIDragSpinBox()
            spin.setRange(0, 16384)
            spin.setPrefix(prefix)
            spin.editingFinished.connect(self._emit_artboard_layout)
            self.artboard_safe_controls[edge] = spin
            safe_layout.addWidget(spin, 1 + index // 2, index % 2)
        artboard_layout_form.addRow("Safe Area", safe_row)
        guide_row = QFrame()
        guide_row.setObjectName("PainterUICompactGrid")
        guide_layout = QGridLayout(guide_row)
        guide_layout.setContentsMargins(0, 0, 0, 0)
        guide_layout.setSpacing(3)
        self.artboard_guides_visible_check = QCheckBox("Guides")
        self.artboard_guides_visible_check.toggled.connect(
            self._emit_artboard_layout
        )
        self.artboard_vertical_guides_edit = QLineEdit()
        self.artboard_vertical_guides_edit.setPlaceholderText("V: 120, 240")
        self.artboard_horizontal_guides_edit = QLineEdit()
        self.artboard_horizontal_guides_edit.setPlaceholderText("H: 80, 160")
        self.artboard_vertical_guides_edit.editingFinished.connect(
            self._emit_artboard_layout
        )
        self.artboard_horizontal_guides_edit.editingFinished.connect(
            self._emit_artboard_layout
        )
        guide_layout.addWidget(self.artboard_guides_visible_check, 0, 0, 1, 2)
        guide_layout.addWidget(self.artboard_vertical_guides_edit, 1, 0)
        guide_layout.addWidget(self.artboard_horizontal_guides_edit, 1, 1)
        artboard_layout_form.addRow("Guides", guide_row)
        self.artboard_layout_status_label = QLabel("Layout: Ready")
        self.artboard_layout_status_label.setObjectName("PaintMuted")
        self.artboard_layout_status_label.setWordWrap(True)
        artboard_layout_form.addRow("Status", self.artboard_layout_status_label)
        self.artboard_settings_toggle = QPushButton("Artboard Settings")
        self.artboard_settings_toggle.setObjectName("PainterUISectionHeader")
        self.artboard_settings_toggle.setCheckable(True)
        self.artboard_settings_toggle.setChecked(False)
        self.artboard_settings_toggle.setIcon(
            app_icon("sliders", size=13, color="#BFCADC")
        )
        self.artboard_settings_toggle.setIconSize(icon_size(13))
        self.artboard_settings_toggle.setToolTip(
            "Show artboard context, layout grid, safe area, and guides"
        )
        self.artboard_settings_toggle.toggled.connect(
            artboard_layout_frame.setVisible
        )
        root.addWidget(self.artboard_settings_toggle)
        self.artboard_layout_frame = artboard_layout_frame
        artboard_layout_frame.setVisible(False)
        root.addWidget(artboard_layout_frame)

        tabs = QTabWidget()
        tabs.setObjectName("PainterUIInspectorTabs")
        tabs.setDocumentMode(True)
        tabs.setIconSize(QSize(15, 15))
        tabs.tabBar().setAutoHide(True)
        tabs.tabBar().setExpanding(True)
        tabs.tabBar().setUsesScrollButtons(False)
        tabs.tabBar().setDrawBase(False)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        tabs.setMinimumWidth(0)
        tabs.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self._tabs = tabs
        self._tabs.currentChanged.connect(self._emit_context_mode_changed)
        self.zoom_button = QPushButton("100%")
        self.zoom_button.setObjectName("PainterUIInspectorZoom")
        self.zoom_button.setFixedHeight(25)
        zoom_menu = QMenu(self.zoom_button)
        for percent in (25, 50, 75, 100, 150, 200):
            action = zoom_menu.addAction(f"{percent}%")
            action.triggered.connect(
                lambda _checked=False, value=percent: (
                    self.zoom_requested.emit(float(value))
                )
            )
        self.zoom_button.setMenu(zoom_menu)
        tabs.setCornerWidget(
            self.zoom_button,
            Qt.Corner.TopRightCorner,
        )
        root.addWidget(tabs, 1)
        self._collapsible_widgets = (
            artboard_bar,
            self.artboard_settings_toggle,
            self.artboard_layout_frame,
            tabs,
        )
        self._sync_collapse_button()

        def add_inspector_tab(widget: QWidget, label: str, icon_name: str) -> int:
            index = tabs.addTab(
                widget,
                app_icon(icon_name, size=15, color="#B9C4D5"),
                "",
            )
            tabs.setTabToolTip(index, label)
            tabs.setTabWhatsThis(index, label)
            return index

        layers_page = QWidget()
        self.layers_page = layers_page
        layers_layout = QVBoxLayout(layers_page)
        layers_layout.setContentsMargins(4, 4, 4, 4)
        self.layer_list = PainterUILayerList()
        self.layer_list.setObjectName("PaintLayerList")
        self.layer_list.setAccessibleName(painter_text("LAYERS"))
        self.layer_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.layer_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.layer_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.layer_list.setDragEnabled(True)
        self.layer_list.setAcceptDrops(True)
        self.layer_list.setDropIndicatorShown(False)
        self.layer_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.layer_list.hovered_object_changed.connect(
            self.layer_hover_changed
        )
        self.layer_list.hierarchy_drop_requested.connect(
            self.hierarchy_drop_requested
        )
        layers_layout.addWidget(self.layer_list, 1)
        actions = QHBoxLayout()
        duplicate = QPushButton("")
        duplicate.setObjectName("PainterUILayerAction")
        duplicate.setIcon(app_icon("duplicate", size=13, color="#CBD5E2"))
        duplicate.setIconSize(icon_size(13))
        duplicate.setToolTip("Duplicate")
        delete = QPushButton("")
        delete.setObjectName("PainterUILayerAction")
        delete.setIcon(app_icon("trash", size=13, color="#CBD5E2"))
        delete.setIconSize(icon_size(13))
        delete.setToolTip("Delete")
        duplicate.clicked.connect(self._emit_duplicate)
        delete.clicked.connect(self._emit_delete)
        group = QPushButton("")
        group.setObjectName("PainterUILayerAction")
        group.setIcon(app_icon("group", size=13, color="#CBD5E2"))
        group.setIconSize(icon_size(13))
        group.setToolTip("Group")
        ungroup = QPushButton("")
        ungroup.setObjectName("PainterUILayerAction")
        ungroup.setIcon(app_icon("ungroup", size=13, color="#CBD5E2"))
        ungroup.setIconSize(icon_size(13))
        ungroup.setToolTip("Ungroup")
        backward = QPushButton("")
        backward.setObjectName("PainterUILayerAction")
        backward.setIcon(app_icon("chevron-down", size=13, color="#CBD5E2"))
        backward.setIconSize(icon_size(13))
        backward.setToolTip("Move layer down")
        forward = QPushButton("")
        forward.setObjectName("PainterUILayerAction")
        forward.setIcon(app_icon("chevron-up", size=13, color="#CBD5E2"))
        forward.setIconSize(icon_size(13))
        forward.setToolTip("Move layer up")
        group.clicked.connect(self._emit_group)
        ungroup.clicked.connect(self._emit_ungroup)
        backward.clicked.connect(lambda: self._emit_reorder("backward"))
        forward.clicked.connect(lambda: self._emit_reorder("forward"))
        for button in (
            duplicate,
            group,
            ungroup,
            backward,
            forward,
            delete,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layers_layout.addLayout(actions)
        mask_actions = QHBoxLayout()
        self.use_as_mask_check = QCheckBox("Use as Mask")
        self.mask_invert_check = QCheckBox("Invert")
        self.mask_outline_check = QCheckBox("Outline")
        for control in (
            self.use_as_mask_check,
            self.mask_invert_check,
            self.mask_outline_check,
        ):
            control.toggled.connect(self._emit_properties)
            mask_actions.addWidget(control)
        layers_layout.addLayout(mask_actions)
        self._layers_tab_index = add_inspector_tab(
            layers_page,
            "Layers",
            "layers",
        )

        sections_page = QWidget()
        self.sections_page = sections_page
        sections_layout = QVBoxLayout(sections_page)
        sections_layout.setContentsMargins(4, 4, 4, 4)
        self.section_list = QListWidget()
        self.section_list.currentRowChanged.connect(
            self._sync_section_fields
        )
        sections_layout.addWidget(self.section_list, 1)
        self.section_name_edit = QLineEdit()
        self.section_name_edit.setPlaceholderText("Section name")
        sections_layout.addWidget(self.section_name_edit)
        self.section_object_ids_edit = QLineEdit()
        self.section_object_ids_edit.setPlaceholderText(
            "Object IDs, comma separated"
        )
        sections_layout.addWidget(self.section_object_ids_edit)
        section_buttons = QHBoxLayout()
        for label, operation in (
            ("New", "create"),
            ("Update", "update"),
            ("Delete", "remove"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, action=operation: self._emit_section(
                    action
                )
            )
            section_buttons.addWidget(button)
        sections_layout.addLayout(section_buttons)
        add_inspector_tab(sections_page, "Sections", "ui-frame")

        from app.painter_ui_component_library import PainterUIComponentLibrary

        self.component_library = PainterUIComponentLibrary()
        self.component_library.object_selected.connect(
            lambda object_id: self.selection_changed.emit(
                [str(object_id)],
                str(object_id),
            )
        )
        self.component_library.instantiate_requested.connect(
            self.component_instantiate_requested
        )
        self.component_library.variant_create_requested.connect(
            self.component_variant_create_requested
        )
        self.component_library.component_update_requested.connect(
            self.component_update_requested
        )
        add_inspector_tab(self.component_library, "Components", "grid")

        from app.painter_ui_style_library import PainterUIStyleLibrary

        self.style_library = PainterUIStyleLibrary()
        self.style_library.style_add_requested.connect(
            self.style_add_requested
        )
        self.style_library.style_update_requested.connect(
            self.style_update_requested
        )
        self.style_library.style_remove_requested.connect(
            self.style_remove_requested
        )
        self.style_library.style_apply_requested.connect(
            self.style_apply_requested
        )
        self.style_library.style_unlink_requested.connect(
            self.style_unlink_requested
        )
        add_inspector_tab(self.style_library, "Styles", "palette")

        from app.painter_ui_library_panel import PainterUILibraryPanel

        self.library_panel = PainterUILibraryPanel()
        self.library_panel.package_export_requested.connect(
            self.library_package_export_requested
        )
        self.library_panel.package_install_requested.connect(
            self.library_package_install_requested
        )
        self.library_panel.update_apply_requested.connect(
            self.library_update_apply_requested
        )
        self.library_panel.update_defer_requested.connect(
            self.library_update_defer_requested
        )
        self.library_panel.rollback_requested.connect(
            self.library_rollback_requested
        )
        self.library_panel.component_insert_requested.connect(
            self.library_component_insert_requested
        )
        self.library_panel.asset_insert_requested.connect(
            self.library_asset_insert_requested
        )
        add_inspector_tab(self.library_panel, "Libraries", "folder")

        from app.painter_ui_token_library import PainterUITokenLibrary

        self.token_library = PainterUITokenLibrary()
        self.token_library.token_add_requested.connect(self.token_add_requested)
        self.token_library.token_update_requested.connect(
            self.token_update_requested
        )
        self.token_library.token_remove_requested.connect(
            self.token_remove_requested
        )
        self.token_library.token_binding_requested.connect(
            self.token_binding_requested
        )
        self.token_library.token_import_requested.connect(
            self.token_import_requested
        )
        self.token_library.token_export_requested.connect(
            self.token_export_requested
        )
        self.token_library.collection_add_requested.connect(
            self.variable_collection_add_requested
        )
        self.token_library.collection_update_requested.connect(
            self.variable_collection_update_requested
        )
        self.token_library.collection_remove_requested.connect(
            self.variable_collection_remove_requested
        )
        self.token_library.mode_add_requested.connect(
            self.variable_mode_add_requested
        )
        self.token_library.mode_update_requested.connect(
            self.variable_mode_update_requested
        )
        self.token_library.mode_remove_requested.connect(
            self.variable_mode_remove_requested
        )
        self.token_library.mode_set_requested.connect(
            self.variable_mode_set_requested
        )
        add_inspector_tab(self.token_library, "Tokens", "sliders")

        from app.painter_ui_motion_delivery_panel import (
            PainterUIMotionDeliveryPanel,
        )
        from app.painter_ui_motion_binding_panel import (
            PainterUIMotionBindingPanel,
        )

        motion_page = QWidget()
        motion_page.setObjectName("PainterUIMotionPage")
        motion_page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        motion_layout = QVBoxLayout(motion_page)
        motion_layout.setContentsMargins(0, 0, 0, 0)
        motion_layout.setSpacing(4)
        from app.painter_ui_prototype_panel import PainterUIPrototypePanel

        self.prototype_panel = PainterUIPrototypePanel()
        self.prototype_panel.connection_add_requested.connect(
            self.prototype_connection_add_requested
        )
        self.prototype_panel.connection_remove_requested.connect(
            self.prototype_connection_remove_requested
        )
        self.prototype_panel.connection_reorder_requested.connect(
            self.prototype_connection_reorder_requested
        )
        self.prototype_panel.transition_set_requested.connect(
            self.prototype_transition_set_requested
        )
        self.prototype_panel.flow_add_requested.connect(
            self.prototype_flow_add_requested
        )
        self.prototype_panel.flow_activate_requested.connect(
            self.prototype_flow_activate_requested
        )
        self.prototype_panel.preview_changed.connect(
            self.prototype_preview_changed
        )
        self.prototype_panel.preview_reset_requested.connect(
            self.prototype_preview_reset_requested
        )
        self.prototype_panel.device_changed.connect(
            self.prototype_device_changed
        )
        self.prototype_panel.background_changed.connect(
            self.prototype_background_changed
        )
        motion_layout.addWidget(self.prototype_panel)
        self.motion_binding_panel = PainterUIMotionBindingPanel()
        self.motion_binding_panel.migrate_requested.connect(
            self.motion_binding_migrate_requested
        )
        self.motion_binding_panel.relink_requested.connect(
            self.motion_binding_relink_requested
        )
        self.motion_binding_panel.detach_requested.connect(
            self.motion_binding_detach_requested
        )
        self.motion_delivery_panel = PainterUIMotionDeliveryPanel()
        self.motion_delivery_panel.open_motion_requested.connect(
            self.motion_open_requested
        )
        self.motion_delivery_panel.preview_hover_requested.connect(
            self.motion_preview_hover_requested
        )
        self.motion_delivery_panel.bake_flipbook_requested.connect(
            self.motion_bake_flipbook_requested
        )
        motion_layout.addWidget(self.motion_binding_panel)
        motion_layout.addWidget(self.motion_delivery_panel)
        motion_layout.addStretch(1)
        motion_scroll = QScrollArea()
        motion_scroll.setObjectName("PainterUIMotionScroll")
        motion_scroll.setWidgetResizable(True)
        motion_scroll.setFrameShape(QFrame.Shape.NoFrame)
        motion_scroll.viewport().setObjectName("PainterUIMotionViewport")
        motion_scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )
        motion_scroll.setWidget(motion_page)
        add_inspector_tab(motion_scroll, "Motion", "motion")

        from app.painter_ui_production_panel import PainterUIProductionPanel

        self.production_panel = PainterUIProductionPanel()
        for source, target in (
            (self.production_panel.template_save_requested, self.template_save_requested),
            (self.production_panel.template_install_requested, self.template_install_requested),
            (self.production_panel.review_comment_add_requested, self.review_comment_add_requested),
            (self.production_panel.review_comment_update_requested, self.review_comment_update_requested),
            (self.production_panel.review_checkpoint_requested, self.review_checkpoint_requested),
            (self.production_panel.review_export_requested, self.review_export_requested),
            (self.production_panel.prototype_export_requested, self.prototype_export_requested),
            (self.production_panel.web_preflight_requested, self.web_preflight_requested),
            (self.production_panel.web_package_requested, self.web_package_requested),
            (self.production_panel.ppt_preflight_requested, self.ppt_preflight_requested),
            (self.production_panel.ppt_send_requested, self.ppt_send_requested),
            (self.production_panel.assets_export_requested, self.assets_export_requested),
            (self.production_panel.figma_document_imported, self.figma_document_imported),
            (self.production_panel.figma_export_requested, self.figma_export_requested),
            (self.production_panel.umg_preflight_requested, self.umg_preflight_requested),
            (self.production_panel.umg_package_requested, self.umg_package_requested),
            (self.production_panel.umg_generate_requested, self.umg_generate_requested),
            (self.production_panel.ai_plan_requested, self.ai_plan_requested),
            (self.production_panel.ai_apply_requested, self.ai_apply_requested),
            (self.production_panel.ai_audit_requested, self.ai_audit_requested),
            (
                self.production_panel.ai_prototype_plan_requested,
                self.ai_prototype_plan_requested,
            ),
            (
                self.production_panel.ai_prototype_apply_requested,
                self.ai_prototype_apply_requested,
            ),
            (self.production_panel.artifact_open_requested, self.artifact_open_requested),
        ):
            source.connect(target)
        add_inspector_tab(self.production_panel, "Publish", "export")

        from app.painter_ui_dev_panel import PainterUIDevPanel

        self.dev_panel = PainterUIDevPanel()
        self.dev_panel.ready_set_requested.connect(
            self.dev_ready_set_requested
        )
        self.dev_panel.annotation_add_requested.connect(
            self.dev_annotation_add_requested
        )
        self.dev_panel.annotation_update_requested.connect(
            self.dev_annotation_update_requested
        )
        self.dev_panel.annotation_remove_requested.connect(
            self.dev_annotation_remove_requested
        )
        self.dev_panel.revision_compare_requested.connect(
            self.dev_revision_compare_requested
        )
        self.dev_panel.component_playground_requested.connect(
            self.component_playground_requested
        )
        self.production_panel.tabs.insertTab(
            0,
            self.dev_panel,
            painter_text("Inspect / Dev"),
        )

        inspect_page = QWidget()
        inspect_layout = QVBoxLayout(inspect_page)
        inspect_layout.setContentsMargins(6, 6, 6, 6)
        self.selection_content_stack = QStackedWidget()
        self.selection_content_stack.setObjectName(
            "PainterUISelectionContentStack"
        )
        inspect_layout.addWidget(self.selection_content_stack, 1)
        from app.painter_ui_frame_presets import PainterUIFramePresetsPanel

        self.frame_presets_panel = PainterUIFramePresetsPanel()
        self.frame_presets_panel.preset_requested.connect(
            self.frame_preset_requested
        )
        self.frame_presets_panel.hide()
        self.selection_content_stack.addWidget(self.frame_presets_panel)
        from app.painter_ui_frame_selection_panel import (
            PainterUIFrameSelectionPanel,
        )

        self.frame_selection_panel = PainterUIFrameSelectionPanel()
        self.frame_selection_panel.geometry_changed.connect(
            self._emit_frame_panel_geometry
        )
        self.frame_selection_panel.properties_changed.connect(
            self._emit_frame_panel_properties
        )
        self.frame_selection_panel.align_requested.connect(
            self._emit_frame_panel_align
        )
        self.frame_selection_panel.hide()
        self.frame_selection_scroll = QScrollArea()
        self.frame_selection_scroll.setObjectName(
            "PainterUIFrameSelectionScroll"
        )
        self.frame_selection_scroll.setWidgetResizable(True)
        self.frame_selection_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_selection_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.frame_selection_scroll.setWidget(self.frame_selection_panel)
        self.frame_selection_scroll.hide()
        self.selection_content_stack.addWidget(self.frame_selection_scroll)
        from app.painter_ui_shape_selection_panel import (
            PainterUIShapeSelectionPanel,
        )

        self.shape_selection_panel = PainterUIShapeSelectionPanel()
        self.shape_selection_panel.geometry_changed.connect(
            self._emit_frame_panel_geometry
        )
        self.shape_selection_panel.properties_changed.connect(
            self._emit_frame_panel_properties
        )
        self.shape_selection_panel.align_requested.connect(
            self._emit_frame_panel_align
        )
        self.shape_selection_panel.advanced_appearance_requested.connect(
            self._edit_appearance
        )
        self.shape_selection_scroll = QScrollArea()
        self.shape_selection_scroll.setObjectName(
            "PainterUIShapeSelectionScroll"
        )
        self.shape_selection_scroll.setWidgetResizable(True)
        self.shape_selection_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.shape_selection_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.shape_selection_scroll.setWidget(self.shape_selection_panel)
        self.selection_content_stack.addWidget(self.shape_selection_scroll)
        from app.painter_ui_comments import PainterUICommentsPanel

        self.comments_panel = PainterUICommentsPanel()
        self.comments_panel.comment_update_requested.connect(
            self.review_comment_update_requested
        )
        self.comments_panel.comment_remove_requested.connect(
            self.review_comment_remove_requested
        )
        self.comments_panel.comment_selected.connect(
            self.review_comment_selected
        )
        self.selection_content_stack.addWidget(self.comments_panel)
        self.page_properties_panel = QFrame()
        self.page_properties_panel.setObjectName(
            "PainterUIPageProperties"
        )
        self.page_properties_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.page_properties_panel.setFixedHeight(152)
        page_layout = QVBoxLayout(self.page_properties_panel)
        page_layout.setContentsMargins(8, 8, 8, 8)
        page_layout.setSpacing(7)
        page_heading = QLabel(painter_text("Page"))
        page_heading.setObjectName("PainterUIPagePropertiesTitle")
        page_heading.setFixedHeight(18)
        page_layout.addWidget(page_heading)
        background_row = QFrame()
        background_row.setObjectName("PainterUIPageBackgroundRow")
        background_row.setFixedHeight(36)
        background_layout = QHBoxLayout(background_row)
        background_layout.setContentsMargins(6, 4, 6, 4)
        background_layout.setSpacing(6)
        self.page_background_swatch = QLabel("")
        self.page_background_swatch.setObjectName(
            "PainterUIPageBackgroundSwatch"
        )
        self.page_background_swatch.setFixedSize(18, 18)
        self.page_background_value = QLabel("F5F5F5")
        self.page_background_value.setObjectName(
            "PainterUIPageBackgroundValue"
        )
        self.page_background_opacity = QLabel("100 %")
        self.page_background_opacity.setObjectName(
            "PainterUIPageBackgroundOpacity"
        )
        background_layout.addWidget(self.page_background_swatch)
        background_layout.addWidget(self.page_background_value, 1)
        background_layout.addWidget(self.page_background_opacity)
        page_layout.addWidget(background_row)
        self.page_style_button = QPushButton(
            f"{painter_text('Style')}    +"
        )
        self.page_style_button.setObjectName("PainterUIPageSection")
        self.page_style_button.setFlat(True)
        self.page_style_button.setFixedHeight(30)
        self.page_style_button.clicked.connect(self._show_page_style_menu)
        page_layout.addWidget(self.page_style_button)
        self.page_style_menu = QMenu(self.page_style_button)
        self.page_style_menu.setObjectName("PainterUIPageStyleMenu")
        for label, kind, icon_name in (
            ("텍스트", "text", "caption"),
            ("색상", "color", "color"),
            ("효과", "effect", "effects"),
            ("레이아웃 가이드", "layout_grid", "grid"),
        ):
            action = self.page_style_menu.addAction(
                app_icon(icon_name, size=14, color="#E6EBF2"),
                label,
            )
            action.setData(kind)
            if kind == "text":
                action.triggered.connect(self._open_text_style_dialog)
        self.page_export_button = QPushButton(
            f"{painter_text('Export')}    +"
        )
        self.page_export_button.setObjectName("PainterUIPageSection")
        self.page_export_button.setFlat(True)
        self.page_export_button.setFixedHeight(30)
        page_layout.addWidget(self.page_export_button)
        self.selection_content_stack.addWidget(self.page_properties_panel)
        self.object_properties_host = QWidget()
        self.object_properties_host.setObjectName(
            "PainterUIObjectPropertiesHost"
        )
        # The generic property form contains several rich editors whose size
        # hints are wider than the dock. Ignore that horizontal hint so the
        # scroll viewport, not an off-screen child width, controls layout.
        self.object_properties_host.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.object_properties_host.setMinimumWidth(0)
        self.object_properties_host.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )
        object_properties_layout = QVBoxLayout(
            self.object_properties_host
        )
        object_properties_layout.setContentsMargins(0, 0, 0, 0)
        object_properties_layout.setSpacing(6)
        self.object_properties_scroll = QScrollArea()
        self.object_properties_scroll.setObjectName(
            "PainterUIObjectPropertiesScroll"
        )
        self.object_properties_scroll.setWidgetResizable(True)
        self.object_properties_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.object_properties_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.object_properties_scroll.viewport().setObjectName(
            "PainterUIObjectPropertiesViewport"
        )
        self.object_properties_scroll.viewport().setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground,
            True,
        )
        self.object_properties_scroll.setWidget(self.object_properties_host)
        self.selection_content_stack.addWidget(self.object_properties_scroll)
        self.selection_context = QFrame()
        self.selection_context.setObjectName("PainterUISelectionContext")
        context_summary_layout = QVBoxLayout(self.selection_context)
        context_summary_layout.setContentsMargins(7, 5, 7, 5)
        context_summary_layout.setSpacing(1)
        self.selection_context_title = QLabel("No selection")
        self.selection_context_title.setObjectName(
            "PainterUISelectionContextTitle"
        )
        self.selection_context_hint = QLabel(
            "Select an object to edit its properties."
        )
        self.selection_context_hint.setObjectName("PaintMuted")
        self.selection_context_hint.setWordWrap(True)
        context_summary_layout.addWidget(self.selection_context_title)
        context_summary_layout.addWidget(self.selection_context_hint)
        object_properties_layout.addWidget(self.selection_context)
        palette_field = QFrame()
        palette_field.setObjectName("PainterUISharedColorPalette")
        palette_layout = QHBoxLayout(palette_field)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(4)
        palette_layout.addWidget(QLabel("Palette"))
        self.palette_target_combo = QComboBox()
        self.palette_target_combo.addItem("Fill", "fill")
        self.palette_target_combo.addItem("Stroke", "stroke")
        self.shared_color_palette = ColorPaletteStrip(
            palette_field,
            # Four swatches fit a Figma-width inspector at 150% DPI without
            # pushing the right side outside the scroll viewport.
            maximum_colors=4,
        )
        self.shared_color_palette.color_selected.connect(
            self._apply_shared_palette_color
        )
        palette_layout.addWidget(self.palette_target_combo)
        palette_layout.addWidget(self.shared_color_palette, 1)
        object_properties_layout.addWidget(palette_field)
        self.advanced_properties_toggle = QPushButton("Advanced properties")
        self.advanced_properties_toggle.setObjectName(
            "PainterUISectionHeader"
        )
        self.advanced_properties_toggle.setCheckable(True)
        self.advanced_properties_toggle.setChecked(False)
        self.advanced_properties_toggle.setIcon(
            app_icon("chevron-right", size=11, color="#AEBACA")
        )
        self.advanced_properties_toggle.setIconSize(icon_size(11))
        self.advanced_properties_toggle.toggled.connect(
            self._on_advanced_properties_toggled
        )
        object_properties_layout.addWidget(
            self.advanced_properties_toggle
        )
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Name", self.name_edit)
        self.kind_label = QLabel("-")
        form.addRow("Type", self.kind_label)
        self.geometry_controls: dict[str, QDoubleSpinBox] = {}
        for key in ("x", "y", "width", "height", "rotation"):
            spin = PainterUIDragDoubleSpinBox()
            spin.setRange(
                -180.0 if key == "rotation" else 0.0,
                180.0 if key == "rotation" else 100000.0,
            )
            spin.setDecimals(1)
            spin.setResetValue(
                {
                    "x": 0.0,
                    "y": 0.0,
                    "width": 160.0,
                    "height": 64.0,
                    "rotation": 0.0,
                }[key]
            )
            spin.editingFinished.connect(self._emit_geometry)
            self.geometry_controls[key] = spin
            form.addRow(key.upper(), spin)
        pivot_row = QFrame()
        pivot_layout = QHBoxLayout(pivot_row)
        pivot_layout.setContentsMargins(0, 0, 0, 0)
        pivot_layout.setSpacing(3)
        self.pivot_x_spin = PainterUIDragDoubleSpinBox()
        self.pivot_y_spin = PainterUIDragDoubleSpinBox()
        for label, spin in (("X ", self.pivot_x_spin), ("Y ", self.pivot_y_spin)):
            spin.setRange(0.0, 1.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.setPrefix(label)
            spin.setResetValue(0.5)
            spin.editingFinished.connect(self._emit_properties)
            pivot_layout.addWidget(spin)
        form.addRow("Pivot", pivot_row)
        constraint_row = QFrame()
        constraint_layout = QHBoxLayout(constraint_row)
        constraint_layout.setContentsMargins(0, 0, 0, 0)
        constraint_layout.setSpacing(3)
        self.horizontal_constraint_combo = QComboBox()
        for label, value in (
            ("Left", "left"),
            ("Center", "center"),
            ("Right", "right"),
            ("Stretch", "stretch"),
            ("Scale", "scale"),
        ):
            self.horizontal_constraint_combo.addItem(label, value)
        self.horizontal_constraint_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        self.vertical_constraint_combo = QComboBox()
        for label, value in (
            ("Top", "top"),
            ("Center", "center"),
            ("Bottom", "bottom"),
            ("Stretch", "stretch"),
            ("Scale", "scale"),
        ):
            self.vertical_constraint_combo.addItem(label, value)
        self.vertical_constraint_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        constraint_layout.addWidget(self.horizontal_constraint_combo)
        constraint_layout.addWidget(self.vertical_constraint_combo)
        form.addRow("Constraints", constraint_row)
        self.size_limit_controls: dict[str, QDoubleSpinBox] = {}
        size_limit_rows: list[QWidget] = []
        for label, width_key, height_key in (
            ("Minimum", "min_width", "min_height"),
            ("Preferred", "preferred_width", "preferred_height"),
            ("Maximum", "max_width", "max_height"),
        ):
            row_widget = QFrame()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(3)
            for prefix, key in (("W ", width_key), ("H ", height_key)):
                spin = PainterUIDragDoubleSpinBox()
                spin.setRange(0.0, 100000.0)
                spin.setDecimals(1)
                spin.setPrefix(prefix)
                spin.setSuffix(" px")
                spin.editingFinished.connect(self._emit_properties)
                self.size_limit_controls[key] = spin
                row_layout.addWidget(spin)
            form.addRow(label, row_widget)
            size_limit_rows.append(row_widget)
        self.aspect_lock_check = QCheckBox("Lock aspect ratio")
        self.aspect_lock_check.toggled.connect(self._emit_properties)
        form.addRow("Ratio", self.aspect_lock_check)
        responsive_row = QFrame()
        responsive_layout = QHBoxLayout(responsive_row)
        responsive_layout.setContentsMargins(0, 0, 0, 0)
        responsive_layout.setSpacing(3)
        self.responsive_edit_check = QCheckBox("Edit current override")
        self.responsive_edit_check.toggled.connect(
            self._on_responsive_edit_toggled
        )
        self.responsive_clear_button = QPushButton("Clear")
        self.responsive_clear_button.clicked.connect(
            self._emit_responsive_override_remove
        )
        responsive_layout.addWidget(self.responsive_edit_check, 1)
        responsive_layout.addWidget(self.responsive_clear_button)
        form.addRow("Responsive", responsive_row)
        self.responsive_status_label = QLabel("Base values")
        self.responsive_status_label.setObjectName("PaintMuted")
        form.addRow("", self.responsive_status_label)
        component_row = QFrame()
        component_layout = QHBoxLayout(component_row)
        component_layout.setContentsMargins(0, 0, 0, 0)
        component_layout.setSpacing(3)
        self.component_create_button = QPushButton("Create")
        self.component_create_button.setToolTip(
            "Convert the selected object subtree into a component definition"
        )
        self.component_create_button.clicked.connect(self._emit_component_create)
        self.component_instance_button = QPushButton("Instance")
        self.component_instance_button.setToolTip(
            "Create another instance of the selected object's component"
        )
        self.component_instance_button.clicked.connect(
            self._emit_component_instantiate
        )
        self.component_combine_button = QPushButton("Combine")
        self.component_combine_button.setToolTip(
            "Combine selected independent components as variants"
        )
        self.component_combine_button.clicked.connect(
            self._emit_component_variants_combine
        )
        self.component_playground_button = QPushButton("")
        self.component_playground_button.setIcon(
            app_icon("play", size=12, color="#CBD5E2")
        )
        self.component_playground_button.setIconSize(icon_size(12))
        self.component_playground_button.setToolTip(
            painter_text("Component Playground")
        )
        self.component_playground_button.setAccessibleName(
            painter_text("Component Playground")
        )
        self.component_playground_button.clicked.connect(
            self._emit_component_playground
        )
        component_layout.addWidget(self.component_create_button)
        component_layout.addWidget(self.component_instance_button)
        component_layout.addWidget(self.component_combine_button)
        component_layout.addWidget(self.component_playground_button)
        # Component actions span the inspector width. Keeping them in the form
        # value column made the four controls overflow at Figma-sized docks.
        form.addRow(component_row)
        self.component_status_label = QLabel("Not a component")
        self.component_status_label.setObjectName("PaintMuted")
        form.addRow("", self.component_status_label)
        self.component_state_combo = QComboBox()
        for label, state in (
            ("Normal", "normal"),
            ("Hover", "hover"),
            ("Pressed", "pressed"),
            ("Focused", "focused"),
            ("Disabled", "disabled"),
            ("Selected", "selected"),
        ):
            self.component_state_combo.addItem(label, state)
        self.component_state_combo.setToolTip(
            "Preview this component instance in an interactive state"
        )
        self.component_state_combo.currentIndexChanged.connect(
            self._emit_component_state
        )
        form.addRow("State", self.component_state_combo)
        variant_row = QFrame()
        variant_layout = QHBoxLayout(variant_row)
        variant_layout.setContentsMargins(0, 0, 0, 0)
        variant_layout.setSpacing(3)
        self.component_variant_combo = QComboBox()
        self.component_variant_combo.setToolTip(
            "Choose another Variant from this component family"
        )
        self.component_variant_combo.currentIndexChanged.connect(
            self._emit_component_variant_switch
        )
        self.component_variant_new_button = QPushButton("New")
        self.component_variant_new_button.setToolTip(
            "Duplicate this definition as a new Variant"
        )
        self.component_variant_new_button.clicked.connect(
            self._emit_component_variant_create
        )
        variant_layout.addWidget(self.component_variant_combo, 1)
        variant_layout.addWidget(self.component_variant_new_button)
        form.addRow("Variant", variant_row)
        self.component_variant_properties_frame = QFrame()
        self.component_variant_properties_layout = QFormLayout(
            self.component_variant_properties_frame
        )
        self.component_variant_properties_layout.setContentsMargins(0, 0, 0, 0)
        self.component_variant_properties_layout.setHorizontalSpacing(6)
        self.component_variant_properties_layout.setVerticalSpacing(4)
        self.component_variant_property_combos: dict[str, QComboBox] = {}
        self.component_variant_properties_frame.setVisible(False)
        form.addRow(self.component_variant_properties_frame)
        self.component_definition_properties_frame = QFrame()
        self.component_definition_properties_layout = QFormLayout(
            self.component_definition_properties_frame
        )
        self.component_definition_properties_layout.setContentsMargins(0, 0, 0, 0)
        self.component_definition_properties_layout.setHorizontalSpacing(6)
        self.component_definition_properties_layout.setVerticalSpacing(4)
        self.component_definition_property_controls: dict[str, QWidget] = {}
        self.component_definition_properties_frame.setVisible(False)
        form.addRow(self.component_definition_properties_frame)
        self.component_instance_properties_frame = QFrame()
        self.component_instance_properties_layout = QFormLayout(
            self.component_instance_properties_frame
        )
        self.component_instance_properties_layout.setContentsMargins(0, 0, 0, 0)
        self.component_instance_properties_layout.setHorizontalSpacing(6)
        self.component_instance_properties_layout.setVerticalSpacing(4)
        self.component_instance_property_controls: dict[str, QWidget] = {}
        self.component_instance_properties_frame.setVisible(False)
        form.addRow(self.component_instance_properties_frame)
        detach_row = QFrame()
        detach_layout = QHBoxLayout(detach_row)
        detach_layout.setContentsMargins(0, 0, 0, 0)
        detach_layout.setSpacing(3)
        self.component_detach_button = QPushButton("Detach")
        self.component_detach_button.setToolTip(
            "Keep the current appearance as ordinary local objects"
        )
        self.component_detach_button.clicked.connect(
            lambda: self._emit_component_detach(False)
        )
        self.component_localize_button = QPushButton("Local")
        self.component_localize_button.setToolTip(
            "Keep the current appearance as a new local component"
        )
        self.component_localize_button.clicked.connect(
            lambda: self._emit_component_detach(True)
        )
        detach_layout.addWidget(self.component_detach_button)
        detach_layout.addWidget(self.component_localize_button)
        form.addRow("", detach_row)
        override_row = QFrame()
        override_layout = QHBoxLayout(override_row)
        override_layout.setContentsMargins(0, 0, 0, 0)
        override_layout.setSpacing(3)
        self.component_override_combo = QComboBox()
        self.component_override_combo.setToolTip(
            painter_text(
                "Local values that differ from the component definition"
            )
        )
        self.component_override_reset_button = QPushButton(
            painter_text("Reset")
        )
        self.component_override_reset_button.setToolTip(
            painter_text("Reset only the selected override")
        )
        self.component_override_reset_button.clicked.connect(
            self._emit_component_override_reset
        )
        self.component_override_reset_all_button = QPushButton(
            painter_text("Reset All")
        )
        self.component_override_reset_all_button.setToolTip(
            painter_text(
                "Reset every local override in this component instance"
            )
        )
        self.component_override_reset_all_button.clicked.connect(
            self._emit_component_override_reset_all
        )
        override_layout.addWidget(self.component_override_combo, 1)
        override_layout.addWidget(self.component_override_reset_button)
        override_layout.addWidget(self.component_override_reset_all_button)
        form.addRow(override_row)
        auto_layout_entry = QFrame()
        auto_layout_entry_row = QHBoxLayout(auto_layout_entry)
        auto_layout_entry_row.setContentsMargins(0, 0, 0, 0)
        auto_layout_entry_row.setSpacing(4)
        self.auto_layout_add_button = QPushButton("Add auto layout")
        self.auto_layout_add_button.setToolTip("Add Auto Layout (Shift+A)")
        self.auto_layout_add_button.clicked.connect(
            lambda: self.auto_layout_entry_requested.emit("add")
        )
        self.auto_layout_remove_button = QPushButton("Remove")
        self.auto_layout_remove_button.setToolTip(
            "Remove Auto Layout (Alt+Shift+A)"
        )
        self.auto_layout_remove_button.clicked.connect(
            lambda: self.auto_layout_entry_requested.emit("remove")
        )
        auto_layout_entry_row.addWidget(self.auto_layout_add_button, 1)
        auto_layout_entry_row.addWidget(self.auto_layout_remove_button)
        form.addRow("Auto Layout", auto_layout_entry)
        self.auto_layout_mode_combo = QComboBox()
        for label, mode in (
            ("None", "none"),
            ("Horizontal", "horizontal"),
            ("Vertical", "vertical"),
            ("Grid", "grid"),
            ("Overlay (UMG stack)", "overlay"),
        ):
            self.auto_layout_mode_combo.addItem(label, mode)
        self.auto_layout_mode_combo.currentIndexChanged.connect(
            self._sync_auto_layout_control_states
        )
        self.auto_layout_mode_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        # Keep the combo as the serialization source, but expose Figma's
        # immediately readable one-axis direction control instead of a menu.
        self.auto_layout_mode_combo.hide()
        self.auto_layout_flow_control = QFrame()
        flow_control_layout = QHBoxLayout(self.auto_layout_flow_control)
        flow_control_layout.setContentsMargins(0, 0, 0, 0)
        flow_control_layout.setSpacing(4)
        self.auto_layout_horizontal_button = QPushButton("→")
        self.auto_layout_vertical_button = QPushButton("↓")
        self.auto_layout_grid_button = QPushButton("▦")
        self.auto_layout_overlay_button = QPushButton("O")
        for button, tooltip in (
            (self.auto_layout_horizontal_button, "Horizontal flow"),
            (self.auto_layout_vertical_button, "Vertical flow"),
            (self.auto_layout_grid_button, "Grid flow (beta)"),
            (
                self.auto_layout_overlay_button,
                "Overlay stack (native UMG alignment and padding)",
            ),
        ):
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setMinimumHeight(28)
            flow_control_layout.addWidget(button, 1)
        self.auto_layout_horizontal_button.clicked.connect(
            lambda: self.auto_layout_mode_combo.setCurrentIndex(
                self.auto_layout_mode_combo.findData("horizontal")
            )
        )
        self.auto_layout_vertical_button.clicked.connect(
            lambda: self.auto_layout_mode_combo.setCurrentIndex(
                self.auto_layout_mode_combo.findData("vertical")
            )
        )
        self.auto_layout_grid_button.clicked.connect(
            lambda: self.auto_layout_mode_combo.setCurrentIndex(
                self.auto_layout_mode_combo.findData("grid")
            )
        )
        self.auto_layout_overlay_button.clicked.connect(
            lambda: self.auto_layout_mode_combo.setCurrentIndex(
                self.auto_layout_mode_combo.findData("overlay")
            )
        )
        form.addRow("Flow", self.auto_layout_flow_control)
        self.auto_layout_umg_panel_control = PainterUIUMGPanelSelector(
            show_title=False
        )
        self.auto_layout_umg_panel_control.mode_changed.connect(
            lambda _mode: self._emit_properties()
        )
        form.addRow("UMG Panel", self.auto_layout_umg_panel_control)
        self.auto_layout_umg_spacing_control = QFrame()
        umg_spacing_layout = QVBoxLayout(
            self.auto_layout_umg_spacing_control
        )
        umg_spacing_layout.setContentsMargins(0, 0, 0, 0)
        umg_spacing_layout.setSpacing(3)
        umg_spacing_row = QHBoxLayout()
        umg_spacing_row.setContentsMargins(0, 0, 0, 0)
        umg_spacing_row.setSpacing(4)
        umg_spacing_label = QLabel("간격 방식")
        self.auto_layout_umg_spacing_combo = QComboBox()
        for label, strategy in (
            ("Padding (슬롯 여백)", "padding"),
            ("Spacer Auto (고정)", "spacer_auto"),
            ("Spacer Fill (비례)", "spacer_fill"),
        ):
            self.auto_layout_umg_spacing_combo.addItem(label, strategy)
        self.auto_layout_umg_spacing_combo.currentIndexChanged.connect(
            self._sync_auto_layout_control_states
        )
        self.auto_layout_umg_spacing_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        self.auto_layout_umg_spacer_fill_spin = (
            PainterUIDragDoubleSpinBox()
        )
        self.auto_layout_umg_spacer_fill_spin.setRange(0.0001, 1000.0)
        self.auto_layout_umg_spacer_fill_spin.setDecimals(2)
        self.auto_layout_umg_spacer_fill_spin.setPrefix("Weight ")
        self.auto_layout_umg_spacer_fill_spin.setResetValue(1.0)
        self.auto_layout_umg_spacer_fill_spin.setValue(1.0)
        self.auto_layout_umg_spacer_fill_spin.valueChanged.connect(
            self._emit_properties
        )
        umg_spacing_row.addWidget(umg_spacing_label)
        umg_spacing_row.addWidget(self.auto_layout_umg_spacing_combo, 1)
        umg_spacing_row.addWidget(self.auto_layout_umg_spacer_fill_spin)
        umg_spacing_layout.addLayout(umg_spacing_row)
        self.auto_layout_umg_spacing_hint = QLabel()
        self.auto_layout_umg_spacing_hint.setObjectName("PaintMuted")
        self.auto_layout_umg_spacing_hint.setWordWrap(True)
        umg_spacing_layout.addWidget(self.auto_layout_umg_spacing_hint)
        form.addRow(self.auto_layout_umg_spacing_control)
        auto_grid = QFrame()
        auto_grid_layout = QGridLayout(auto_grid)
        auto_grid_layout.setContentsMargins(0, 0, 0, 0)
        auto_grid_layout.setSpacing(3)
        self.auto_layout_grid_columns_spin = QSpinBox()
        self.auto_layout_grid_columns_spin.setRange(1, 100)
        self.auto_layout_grid_columns_spin.setPrefix("Columns ")
        self.auto_layout_grid_columns_spin.valueChanged.connect(
            self._emit_properties
        )
        self.auto_layout_grid_column_span_spin = QSpinBox()
        self.auto_layout_grid_column_span_spin.setRange(1, 100)
        self.auto_layout_grid_column_span_spin.setPrefix("Column span ")
        self.auto_layout_grid_column_span_spin.valueChanged.connect(
            self._emit_properties
        )
        self.auto_layout_grid_row_span_spin = QSpinBox()
        self.auto_layout_grid_row_span_spin.setRange(1, 100)
        self.auto_layout_grid_row_span_spin.setPrefix("Row span ")
        self.auto_layout_grid_row_span_spin.valueChanged.connect(
            self._emit_properties
        )
        auto_grid_layout.addWidget(self.auto_layout_grid_columns_spin, 0, 0, 1, 2)
        auto_grid_layout.addWidget(self.auto_layout_grid_column_span_spin, 1, 0)
        auto_grid_layout.addWidget(self.auto_layout_grid_row_span_spin, 1, 1)
        form.addRow("Grid", auto_grid)
        self.auto_layout_grid_controls = auto_grid
        auto_sizing = QFrame()
        auto_sizing_layout = QVBoxLayout(auto_sizing)
        auto_sizing_layout.setContentsMargins(0, 0, 0, 0)
        auto_sizing_layout.setSpacing(3)
        self.auto_layout_width_sizing_combo = QComboBox(auto_sizing)
        self.auto_layout_height_sizing_combo = QComboBox(auto_sizing)
        for combo in (
            self.auto_layout_width_sizing_combo,
            self.auto_layout_height_sizing_combo,
        ):
            for label, sizing in (
                ("Fixed", "fixed"),
                ("Hug", "hug"),
                ("Fill", "fill"),
            ):
                combo.addItem(label, sizing)
            combo.currentIndexChanged.connect(self._emit_properties)
            combo.hide()
        self.auto_layout_width_sizing_control = PainterUISizingControl(
            "W",
            auto_sizing,
        )
        self.auto_layout_height_sizing_control = PainterUISizingControl(
            "H",
            auto_sizing,
        )
        self.auto_layout_width_sizing_control.value_changed.connect(
            lambda value: self._set_auto_layout_sizing(
                self.auto_layout_width_sizing_combo,
                value,
            )
        )
        self.auto_layout_height_sizing_control.value_changed.connect(
            lambda value: self._set_auto_layout_sizing(
                self.auto_layout_height_sizing_combo,
                value,
            )
        )
        self.auto_layout_width_sizing_combo.currentIndexChanged.connect(
            lambda _index: self.auto_layout_width_sizing_control.set_value(
                str(
                    self.auto_layout_width_sizing_combo.currentData()
                    or "fixed"
                )
            )
        )
        self.auto_layout_height_sizing_combo.currentIndexChanged.connect(
            lambda _index: self.auto_layout_height_sizing_control.set_value(
                str(
                    self.auto_layout_height_sizing_combo.currentData()
                    or "fixed"
                )
            )
        )
        auto_sizing_layout.addWidget(self.auto_layout_width_sizing_control)
        auto_sizing_layout.addWidget(self.auto_layout_height_sizing_control)
        self.auto_layout_wrap_check = QCheckBox("Wrap")
        self.auto_layout_wrap_check.toggled.connect(self._emit_properties)
        auto_sizing_layout.addWidget(self.auto_layout_wrap_check)
        form.addRow("Sizing", auto_sizing)
        self.auto_layout_status_label = QLabel("Layout ready")
        self.auto_layout_status_label.setObjectName("PaintMuted")
        self.auto_layout_status_label.setWordWrap(True)
        form.addRow("", self.auto_layout_status_label)
        self._stress_preview_report: dict[str, Any] = {}
        stress_preview = QFrame()
        stress_preview.setObjectName("PainterUIStressPreview")
        stress_layout = QVBoxLayout(stress_preview)
        stress_layout.setContentsMargins(0, 0, 0, 0)
        stress_layout.setSpacing(3)
        stress_controls = QHBoxLayout()
        stress_controls.setContentsMargins(0, 0, 0, 0)
        stress_controls.setSpacing(3)
        self.stress_preview_combo = QComboBox()
        for label, preset in (
            ("Off", "none"),
            ("Long Korean", "long_ko"),
            ("Long English", "long_en"),
            ("Large Type", "large_type"),
            ("Missing Image", "missing_image"),
            ("Empty List", "empty_list"),
        ):
            self.stress_preview_combo.addItem(
                painter_text(label),
                preset,
            )
        self.stress_preview_combo.currentIndexChanged.connect(
            self._emit_stress_preview
        )
        self.stress_preview_clear_button = QPushButton()
        self.stress_preview_clear_button.setObjectName(
            "PainterUIIconButton"
        )
        self.stress_preview_clear_button.setFixedSize(24, 24)
        self.stress_preview_clear_button.setIcon(
            app_icon("x", size=11, color="#AEBACA")
        )
        self.stress_preview_clear_button.setToolTip(
            painter_text("Clear content preview")
        )
        self.stress_preview_clear_button.clicked.connect(
            self._clear_stress_preview
        )
        stress_controls.addWidget(self.stress_preview_combo, 1)
        stress_controls.addWidget(self.stress_preview_clear_button)
        stress_layout.addLayout(stress_controls)
        self.stress_preview_status_label = QLabel(
            painter_text("Preview only - document is unchanged")
        )
        self.stress_preview_status_label.setObjectName("PaintMuted")
        self.stress_preview_status_label.setWordWrap(True)
        stress_layout.addWidget(self.stress_preview_status_label)
        form.addRow(painter_text("Content Test"), stress_preview)
        from app.painter_ui_token_suggestion import (
            PainterUITokenSuggestionPanel,
        )

        self.token_suggestion_panel = PainterUITokenSuggestionPanel()
        self.token_suggestion_panel.binding_requested.connect(
            self.token_binding_requested
        )
        form.addRow(
            painter_text("Suggested tokens"),
            self.token_suggestion_panel,
        )
        auto_padding = QFrame()
        auto_padding_layout = QHBoxLayout(auto_padding)
        auto_padding_layout.setContentsMargins(0, 0, 0, 0)
        auto_padding_layout.setSpacing(3)
        self.auto_layout_padding_controls: dict[str, QDoubleSpinBox] = {}
        for prefix, edge in (
            ("L ", "left"),
            ("T ", "top"),
            ("R ", "right"),
            ("B ", "bottom"),
        ):
            spin = PainterUIDragDoubleSpinBox()
            spin.setRange(0.0, 10000.0)
            spin.setDecimals(1)
            spin.setPrefix(prefix)
            spin.setSuffix(" px")
            spin.setResetValue(0.0)
            spin.editingFinished.connect(self._emit_properties)
            self.auto_layout_padding_controls[edge] = spin
            auto_padding_layout.addWidget(spin)
        form.addRow("Padding", auto_padding)
        auto_flow = QFrame()
        auto_flow_layout = QHBoxLayout(auto_flow)
        auto_flow_layout.setContentsMargins(0, 0, 0, 0)
        auto_flow_layout.setSpacing(3)
        self.auto_layout_gap_spin = PainterUIDragDoubleSpinBox()
        self.auto_layout_gap_spin.setRange(-10000.0, 10000.0)
        self.auto_layout_gap_spin.setDecimals(1)
        self.auto_layout_gap_spin.setPrefix("Gap ")
        self.auto_layout_gap_spin.setSuffix(" px")
        self.auto_layout_gap_spin.setResetValue(0.0)
        self.auto_layout_gap_spin.editingFinished.connect(
            self._emit_properties
        )
        self.auto_layout_cross_gap_spin = PainterUIDragDoubleSpinBox()
        self.auto_layout_cross_gap_spin.setRange(0.0, 10000.0)
        self.auto_layout_cross_gap_spin.setDecimals(1)
        self.auto_layout_cross_gap_spin.setPrefix("Rows ")
        self.auto_layout_cross_gap_spin.setSuffix(" px")
        self.auto_layout_cross_gap_spin.setResetValue(0.0)
        self.auto_layout_cross_gap_spin.setToolTip(
            "Spacing between wrapped rows or columns"
        )
        self.auto_layout_cross_gap_spin.editingFinished.connect(
            self._emit_properties
        )
        self.auto_layout_main_combo = QComboBox()
        for label, alignment in (
            ("Start", "start"),
            ("Center", "center"),
            ("End", "end"),
            ("Space Between", "space_between"),
        ):
            self.auto_layout_main_combo.addItem(label, alignment)
        self.auto_layout_main_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        self.auto_layout_gap_auto_button = QPushButton("Auto")
        self.auto_layout_gap_auto_button.setCheckable(True)
        self.auto_layout_gap_auto_button.setToolTip(
            "Distribute items using the largest available gap"
        )
        self.auto_layout_gap_auto_button.clicked.connect(
            self._set_auto_layout_gap_auto
        )
        auto_flow_layout.addWidget(self.auto_layout_gap_spin)
        auto_flow_layout.addWidget(self.auto_layout_cross_gap_spin)
        auto_flow_layout.addWidget(self.auto_layout_gap_auto_button)
        form.addRow("Flow", auto_flow)
        self.auto_layout_main_combo.hide()
        auto_cross = QFrame()
        auto_cross_layout = QHBoxLayout(auto_cross)
        auto_cross_layout.setContentsMargins(0, 0, 0, 0)
        auto_cross_layout.setSpacing(3)
        self.auto_layout_cross_combo = QComboBox()
        for label, alignment in (
            ("Start", "start"),
            ("Center", "center"),
            ("End", "end"),
            ("Stretch", "stretch"),
            ("Baseline", "baseline"),
        ):
            self.auto_layout_cross_combo.addItem(label, alignment)
        self.auto_layout_cross_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        self.auto_layout_cross_combo.hide()
        self.auto_layout_alignment_control = QFrame()
        alignment_layout = QGridLayout(self.auto_layout_alignment_control)
        alignment_layout.setContentsMargins(0, 0, 0, 0)
        alignment_layout.setHorizontalSpacing(3)
        alignment_layout.setVerticalSpacing(3)
        self.auto_layout_alignment_buttons: dict[tuple[int, int], QPushButton] = {}
        for alignment_row in range(3):
            for alignment_column in range(3):
                button = QPushButton("•")
                button.setCheckable(True)
                button.setFixedSize(28, 24)
                button.setToolTip("Set Auto Layout child alignment")
                button.clicked.connect(
                    lambda _checked=False, row_index=alignment_row,
                    column_index=alignment_column: self._set_auto_layout_alignment(
                        row_index,
                        column_index,
                    )
                )
                alignment_layout.addWidget(
                    button,
                    alignment_row,
                    alignment_column,
                )
                self.auto_layout_alignment_buttons[
                    (alignment_row, alignment_column)
                ] = button
        form.addRow("Alignment", self.auto_layout_alignment_control)
        self.auto_layout_positioning_combo = QComboBox()
        self.auto_layout_positioning_combo.addItem("In flow", "auto")
        self.auto_layout_positioning_combo.addItem(
            "Ignore auto layout", "absolute"
        )
        self.auto_layout_positioning_combo.setToolTip(
            "Ignore auto layout keeps the object in its parent but removes it "
            "from the automatic flow so constraints and free positioning apply."
        )
        self.auto_layout_positioning_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        self.auto_layout_baseline_button = QPushButton("Baseline")
        self.auto_layout_baseline_button.setCheckable(True)
        self.auto_layout_baseline_button.setToolTip(
            "Align horizontal Auto Layout children to their text baseline"
        )
        self.auto_layout_baseline_button.clicked.connect(
            self._set_auto_layout_baseline
        )
        auto_cross_layout.addWidget(self.auto_layout_cross_combo)
        auto_cross_layout.addWidget(self.auto_layout_baseline_button)
        auto_cross_layout.addWidget(self.auto_layout_positioning_combo)
        form.addRow("Align / Position", auto_cross)
        self.opacity_spin = PainterUIDragSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.setResetValue(100.0)
        self.opacity_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Opacity", self.opacity_spin)
        self.fill_edit = QLineEdit()
        self.fill_edit.setPlaceholderText("#RRGGBB")
        self.fill_edit.editingFinished.connect(self._emit_properties)
        self.fill_field, self.fill_color_picker = color_edit_with_picker(
            self.fill_edit,
            title="Choose fill color",
        )
        self.fill_color_picker.clicked.disconnect()
        self.fill_color_picker.clicked.connect(
            lambda: self._open_common_paint_editor(stroke=False)
        )
        form.addRow("Fill", self.fill_field)
        self.stroke_edit = QLineEdit()
        self.stroke_edit.setPlaceholderText("#RRGGBB")
        self.stroke_edit.editingFinished.connect(self._emit_properties)
        self.stroke_field, self.stroke_color_picker = color_edit_with_picker(
            self.stroke_edit,
            title="Choose stroke color",
        )
        self.stroke_color_picker.clicked.disconnect()
        self.stroke_color_picker.clicked.connect(
            lambda: self._open_common_paint_editor(stroke=True)
        )
        form.addRow("Stroke", self.stroke_field)
        self.stroke_width_spin = PainterUIDragDoubleSpinBox()
        self.stroke_width_spin.setRange(0.0, 64.0)
        self.stroke_width_spin.setDecimals(1)
        self.stroke_width_spin.setSuffix(" px")
        self.stroke_width_spin.setResetValue(0.0)
        self.stroke_width_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Stroke Width", self.stroke_width_spin)
        self.radius_spin = PainterUIDragDoubleSpinBox()
        self.radius_spin.setRange(0.0, 4096.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setSuffix(" px")
        self.radius_spin.setResetValue(0.0)
        self.radius_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Radius", self.radius_spin)
        self.appearance_button = QPushButton("Solid")
        self.appearance_button.setToolTip(
            "Edit fill gradient and ordered Drop/Inner Shadow effects"
        )
        self.appearance_button.clicked.connect(self._edit_appearance)
        form.addRow("Appearance", self.appearance_button)
        shape_controls = QFrame()
        shape_controls.setObjectName("PainterUIParametricShapeControls")
        self.shape_controls = shape_controls
        shape_layout = QVBoxLayout(shape_controls)
        shape_layout.setContentsMargins(0, 0, 0, 0)
        shape_layout.setSpacing(3)
        self.shape_parameter_rows: dict[str, QFrame] = {}

        def add_shape_parameter_row(
            key: str,
            label: str,
            controls: tuple[QWidget, ...],
        ) -> None:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.addWidget(QLabel(painter_text(label)))
            row_layout.addStretch(1)
            for control in controls:
                row_layout.addWidget(control)
            shape_layout.addWidget(row)
            self.shape_parameter_rows[key] = row

        self.shape_point_count_spin = PainterUIDragSpinBox()
        self.shape_point_count_spin.setRange(3, 60)
        self.shape_point_count_spin.setResetValue(5)
        self.shape_point_count_spin.editingFinished.connect(
            self._emit_properties
        )
        add_shape_parameter_row(
            "points",
            "Points",
            (self.shape_point_count_spin,),
        )
        self.shape_inner_radius_spin = PainterUIDragSpinBox()
        self.shape_inner_radius_spin.setRange(0, 95)
        self.shape_inner_radius_spin.setSuffix("%")
        self.shape_inner_radius_spin.setResetValue(45)
        self.shape_inner_radius_spin.editingFinished.connect(
            self._emit_properties
        )
        add_shape_parameter_row(
            "inner_radius",
            "Inner",
            (self.shape_inner_radius_spin,),
        )
        self.shape_corner_radius_spin = PainterUIDragDoubleSpinBox()
        self.shape_corner_radius_spin.setRange(0.0, 4096.0)
        self.shape_corner_radius_spin.setDecimals(1)
        self.shape_corner_radius_spin.setSuffix(" px")
        self.shape_corner_radius_spin.setResetValue(0.0)
        self.shape_corner_radius_spin.editingFinished.connect(
            self._emit_properties
        )
        add_shape_parameter_row(
            "corner_radius",
            "Radius",
            (self.shape_corner_radius_spin,),
        )
        self.shape_rotation_spin = PainterUIDragDoubleSpinBox()
        self.shape_rotation_spin.setRange(-360.0, 360.0)
        self.shape_rotation_spin.setDecimals(1)
        self.shape_rotation_spin.setSuffix(" deg")
        self.shape_rotation_spin.setResetValue(-90.0)
        self.shape_rotation_spin.editingFinished.connect(
            self._emit_properties
        )
        add_shape_parameter_row(
            "rotation",
            "Rotation",
            (self.shape_rotation_spin,),
        )
        self.shape_start_angle_spin = PainterUIDragDoubleSpinBox()
        self.shape_start_angle_spin.setRange(-360.0, 360.0)
        self.shape_start_angle_spin.setDecimals(1)
        self.shape_start_angle_spin.setPrefix("Start ")
        self.shape_start_angle_spin.setSuffix(" deg")
        self.shape_start_angle_spin.setResetValue(-90.0)
        self.shape_start_angle_spin.editingFinished.connect(
            self._emit_properties
        )
        self.shape_sweep_angle_spin = PainterUIDragDoubleSpinBox()
        self.shape_sweep_angle_spin.setRange(-360.0, 360.0)
        self.shape_sweep_angle_spin.setDecimals(1)
        self.shape_sweep_angle_spin.setPrefix("Sweep ")
        self.shape_sweep_angle_spin.setSuffix(" deg")
        self.shape_sweep_angle_spin.setResetValue(270.0)
        self.shape_sweep_angle_spin.editingFinished.connect(
            self._emit_properties
        )
        add_shape_parameter_row(
            "angles",
            "Arc",
            (self.shape_start_angle_spin, self.shape_sweep_angle_spin),
        )
        form.insertRow(7, painter_text("Shape"), shape_controls)
        multi_properties = QFrame()
        multi_properties.setObjectName("PainterUIMultiProperties")
        multi_layout = QGridLayout(multi_properties)
        multi_layout.setContentsMargins(0, 0, 0, 0)
        multi_layout.setHorizontalSpacing(4)
        multi_layout.setVerticalSpacing(3)
        self.multi_opacity_spin = PainterUIDragSpinBox()
        self.multi_opacity_spin.setRange(0, 100)
        self.multi_opacity_spin.setSuffix("%")
        self.multi_fill_edit = QLineEdit()
        self.multi_fill_edit.setPlaceholderText("#RRGGBB")
        self.multi_stroke_edit = QLineEdit()
        self.multi_stroke_edit.setPlaceholderText("#RRGGBB")
        (
            self.multi_fill_field,
            self.multi_fill_color_picker,
        ) = color_edit_with_picker(
            self.multi_fill_edit,
            title="Choose common fill color",
        )
        (
            self.multi_stroke_field,
            self.multi_stroke_color_picker,
        ) = color_edit_with_picker(
            self.multi_stroke_edit,
            title="Choose common stroke color",
        )
        self.multi_stroke_width_spin = PainterUIDragDoubleSpinBox()
        self.multi_stroke_width_spin.setRange(0.0, 64.0)
        self.multi_stroke_width_spin.setDecimals(1)
        self.multi_stroke_width_spin.setSuffix(" px")
        self.multi_radius_spin = PainterUIDragDoubleSpinBox()
        self.multi_radius_spin.setRange(0.0, 4096.0)
        self.multi_radius_spin.setDecimals(1)
        self.multi_radius_spin.setSuffix(" px")
        self.multi_visible_check = QCheckBox("Visible")
        self.multi_locked_check = QCheckBox("Locked")
        self._multi_mixed_keys: set[str] = set()
        self._multi_dirty_keys: set[str] = set()
        multi_controls = (
            ("Opacity", self.multi_opacity_spin, "opacity"),
            ("Fill", self.multi_fill_edit, "fill"),
            ("Stroke", self.multi_stroke_edit, "stroke"),
            ("Width", self.multi_stroke_width_spin, "stroke_width"),
            ("Radius", self.multi_radius_spin, "radius"),
        )
        for index, (label, control, key) in enumerate(multi_controls):
            row_index = index // 2
            column = (index % 2) * 2
            multi_layout.addWidget(QLabel(label), row_index, column)
            display_control = (
                self.multi_fill_field
                if control is self.multi_fill_edit
                else self.multi_stroke_field
                if control is self.multi_stroke_edit
                else control
            )
            multi_layout.addWidget(display_control, row_index, column + 1)
            if isinstance(control, QLineEdit):
                control.textEdited.connect(
                    lambda _text, value=key: self._mark_multi_dirty(value)
                )
                control.editingFinished.connect(
                    lambda value=key: self._emit_multi_property(value)
                )
            else:
                control.lineEdit().textEdited.connect(
                    lambda _text, value=key: self._mark_multi_dirty(value)
                )
                control.editingFinished.connect(
                    lambda value=key: self._emit_multi_property(value)
                )
        multi_flags = QFrame()
        multi_flags_layout = QHBoxLayout(multi_flags)
        multi_flags_layout.setContentsMargins(0, 0, 0, 0)
        multi_flags_layout.setSpacing(8)
        multi_flags_layout.addWidget(self.multi_visible_check)
        multi_flags_layout.addWidget(self.multi_locked_check)
        multi_layout.addWidget(multi_flags, 3, 0, 1, 4)
        self.multi_visible_check.stateChanged.connect(
            lambda _state: self._emit_multi_property(
                "visible",
                force=True,
            )
        )
        self.multi_locked_check.stateChanged.connect(
            lambda _state: self._emit_multi_property(
                "locked",
                force=True,
            )
        )
        self.multi_tidy_axis_combo = QComboBox()
        self.multi_tidy_axis_combo.addItem("Auto", "auto")
        self.multi_tidy_axis_combo.addItem("Horizontal", "horizontal")
        self.multi_tidy_axis_combo.addItem("Vertical", "vertical")
        self.multi_tidy_axis_combo.currentIndexChanged.connect(
            self._sync_multi_spacing
        )
        self.multi_gap_spin = PainterUIDragDoubleSpinBox()
        self.multi_gap_spin.setRange(-1.0, 4096.0)
        self.multi_gap_spin.setDecimals(1)
        self.multi_gap_spin.setSpecialValueText("—")
        self.multi_gap_spin.setSuffix(" px")
        self.multi_gap_y_spin = PainterUIDragDoubleSpinBox()
        self.multi_gap_y_spin.setRange(-1.0, 4096.0)
        self.multi_gap_y_spin.setDecimals(1)
        self.multi_gap_y_spin.setSpecialValueText("—")
        self.multi_gap_y_spin.setSuffix(" px")
        self.multi_gap_y_spin.hide()
        self.multi_tidy_button = QPushButton("Tidy Up")
        self.multi_tidy_button.setToolTip(
            "Make the selected object spacing uniform"
        )
        self.multi_tidy_button.clicked.connect(self._emit_tidy_selection)
        tidy_row = QFrame()
        tidy_layout = QHBoxLayout(tidy_row)
        tidy_layout.setContentsMargins(0, 0, 0, 0)
        tidy_layout.setSpacing(3)
        tidy_layout.addWidget(self.multi_tidy_axis_combo)
        tidy_layout.addWidget(self.multi_gap_spin)
        tidy_layout.addWidget(self.multi_gap_y_spin)
        tidy_layout.addWidget(self.multi_tidy_button)
        multi_layout.addWidget(tidy_row, 4, 0, 1, 4)
        form.addRow("Common", multi_properties)
        self.clip_content_check = QCheckBox("Clip child content")
        self.clip_content_check.setToolTip(
            "Hide child pixels and hit targets outside this frame"
        )
        self.clip_content_check.toggled.connect(self._emit_clip_content)
        form.addRow("Frame", self.clip_content_check)
        self.scroll_overflow_combo = QComboBox()
        for label, value in (
            ("No scrolling", "none"),
            ("Horizontal", "horizontal"),
            ("Vertical", "vertical"),
            ("Both directions", "both"),
        ):
            self.scroll_overflow_combo.addItem(label, value)
        self.scroll_overflow_combo.setToolTip(
            "Prototype overflow requires a frame with Clip content and content "
            "that extends beyond its bounds."
        )
        self.scroll_overflow_combo.currentIndexChanged.connect(
            self._emit_scroll_overflow
        )
        form.addRow("Overflow", self.scroll_overflow_combo)
        self.scroll_position_combo = QComboBox()
        for label, value in (
            ("Scroll with parent", "scroll"),
            ("Fixed", "fixed"),
            ("Sticky", "sticky"),
        ):
            self.scroll_position_combo.addItem(label, value)
        self.scroll_position_combo.setToolTip(
            "Fixed requires Ignore auto layout inside an Auto Layout frame; "
            "Sticky requires vertical overflow."
        )
        self.scroll_position_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        form.addRow("Scroll position", self.scroll_position_combo)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("Text")
        self.text_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Text", self.text_edit)
        text_range_row = QFrame()
        text_range_layout = QHBoxLayout(text_range_row)
        text_range_layout.setContentsMargins(0, 0, 0, 0)
        text_range_layout.setSpacing(3)
        self.text_range_start_spin = PainterUIDragSpinBox()
        self.text_range_end_spin = PainterUIDragSpinBox()
        self.text_range_start_spin.setPrefix("From ")
        self.text_range_end_spin.setPrefix("To ")
        self.text_range_weight_spin = PainterUIDragSpinBox()
        self.text_range_weight_spin.setRange(100, 900)
        self.text_range_weight_spin.setSingleStep(100)
        self.text_range_weight_spin.setValue(700)
        self.text_range_color_edit = QLineEdit("#FFFFFFFF")
        (
            self.text_range_color_field,
            self.text_range_color_picker,
        ) = color_edit_with_picker(
            self.text_range_color_edit,
            title="Choose text range color",
        )
        text_range_layout.addWidget(self.text_range_start_spin)
        text_range_layout.addWidget(self.text_range_end_spin)
        text_range_layout.addWidget(self.text_range_weight_spin)
        text_range_layout.addWidget(self.text_range_color_field)
        form.addRow("Text Range", text_range_row)
        text_range_actions = QFrame()
        text_range_actions_layout = QHBoxLayout(text_range_actions)
        text_range_actions_layout.setContentsMargins(0, 0, 0, 0)
        apply_text_range = QPushButton("Apply Range")
        remove_text_range = QPushButton("Clear Range")
        apply_text_range.clicked.connect(
            lambda: self._emit_text_range(False)
        )
        remove_text_range.clicked.connect(
            lambda: self._emit_text_range(True)
        )
        text_range_actions_layout.addWidget(apply_text_range)
        text_range_actions_layout.addWidget(remove_text_range)
        self.text_range_apply_button = apply_text_range
        self.text_range_remove_button = remove_text_range
        form.addRow("", text_range_actions)
        boolean_row = QFrame()
        boolean_layout = QHBoxLayout(boolean_row)
        boolean_layout.setContentsMargins(0, 0, 0, 0)
        boolean_layout.setSpacing(3)
        self.boolean_operation_combo = QComboBox()
        for value in ("union", "subtract", "intersect", "exclude"):
            self.boolean_operation_combo.addItem(value.title(), value)
        self.boolean_operand_ids_edit = QLineEdit()
        self.boolean_operand_ids_edit.setPlaceholderText("Operand IDs")
        boolean_set = QPushButton("Set")
        boolean_release = QPushButton("Release")
        boolean_set.clicked.connect(
            lambda: self._emit_boolean("set")
        )
        boolean_release.clicked.connect(
            lambda: self._emit_boolean("release")
        )
        boolean_layout.addWidget(self.boolean_operation_combo)
        boolean_layout.addWidget(self.boolean_operand_ids_edit, 1)
        boolean_layout.addWidget(boolean_set)
        boolean_layout.addWidget(boolean_release)
        form.addRow("Boolean", boolean_row)
        remote_row = QFrame()
        remote_layout = QHBoxLayout(remote_row)
        remote_layout.setContentsMargins(0, 0, 0, 0)
        remote_layout.setSpacing(3)
        self.remote_component_key_edit = QLineEdit()
        self.remote_component_key_edit.setPlaceholderText("Component key / local ID")
        for label, operation in (
            ("Relink", "relink"),
            ("Local", "localize"),
            ("Replace", "replace"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, action=operation: self._emit_remote(
                    action
                )
            )
            remote_layout.addWidget(button)
        remote_layout.insertWidget(0, self.remote_component_key_edit, 1)
        form.addRow("Remote Component", remote_row)
        image_source_row = QFrame()
        image_source_layout = QHBoxLayout(image_source_row)
        image_source_layout.setContentsMargins(0, 0, 0, 0)
        image_source_layout.setSpacing(3)
        self.image_source_edit = QLineEdit()
        self.image_source_edit.setPlaceholderText("PNG, WebP, or JPEG path")
        self.image_source_edit.editingFinished.connect(self._emit_properties)
        image_browse = QPushButton("...")
        image_browse.setFixedWidth(30)
        image_browse.setToolTip("Choose image source")
        image_browse.clicked.connect(self._choose_image_source)
        self.image_browse_button = image_browse
        image_source_layout.addWidget(self.image_source_edit, 1)
        image_source_layout.addWidget(image_browse)
        form.addRow("Image", image_source_row)
        image_layout_row = QFrame()
        image_layout = QHBoxLayout(image_layout_row)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(3)
        self.image_fit_combo = QComboBox()
        for label, value in (
            ("Fit", "fit"),
            ("Fill", "fill"),
            ("Stretch", "stretch"),
            ("Tile", "tile"),
        ):
            self.image_fit_combo.addItem(label, value)
        self.image_fit_combo.currentIndexChanged.connect(self._emit_properties)
        self.image_fit_combo.currentIndexChanged.connect(
            self._sync_image_control_states
        )
        self.image_tile_scale_spin = PainterUIDragDoubleSpinBox()
        self.image_tile_scale_spin.setRange(0.05, 16.0)
        self.image_tile_scale_spin.setDecimals(2)
        self.image_tile_scale_spin.setSingleStep(0.1)
        self.image_tile_scale_spin.setPrefix("Tile ")
        self.image_tile_scale_spin.setResetValue(1.0)
        self.image_tile_scale_spin.editingFinished.connect(
            self._emit_properties
        )
        image_layout.addWidget(self.image_fit_combo)
        image_layout.addWidget(self.image_tile_scale_spin)
        form.addRow("Image Fit", image_layout_row)
        image_focal_row = QFrame()
        image_focal_layout = QHBoxLayout(image_focal_row)
        image_focal_layout.setContentsMargins(0, 0, 0, 0)
        image_focal_layout.setSpacing(3)
        self.image_focal_x_spin = PainterUIDragDoubleSpinBox()
        self.image_focal_x_spin.setRange(0.0, 1.0)
        self.image_focal_x_spin.setDecimals(2)
        self.image_focal_x_spin.setSingleStep(0.05)
        self.image_focal_x_spin.setPrefix("X ")
        self.image_focal_x_spin.setResetValue(0.5)
        self.image_focal_x_spin.editingFinished.connect(
            self._emit_properties
        )
        self.image_focal_y_spin = PainterUIDragDoubleSpinBox()
        self.image_focal_y_spin.setRange(0.0, 1.0)
        self.image_focal_y_spin.setDecimals(2)
        self.image_focal_y_spin.setSingleStep(0.05)
        self.image_focal_y_spin.setPrefix("Y ")
        self.image_focal_y_spin.setResetValue(0.5)
        self.image_focal_y_spin.editingFinished.connect(
            self._emit_properties
        )
        self.image_original_size_button = QPushButton("Original size")
        self.image_original_size_button.clicked.connect(
            self._restore_image_original_size
        )
        image_focal_layout.addWidget(self.image_focal_x_spin)
        image_focal_layout.addWidget(self.image_focal_y_spin)
        image_focal_layout.addWidget(self.image_original_size_button)
        form.addRow("Focal Point", image_focal_row)
        self.nine_slice_check = QCheckBox("Enable 9-slice")
        self.nine_slice_check.toggled.connect(self._emit_properties)
        self.nine_slice_check.toggled.connect(
            self._sync_image_control_states
        )
        form.addRow("9-slice", self.nine_slice_check)
        slice_margin_row = QFrame()
        slice_margin_layout = QHBoxLayout(slice_margin_row)
        slice_margin_layout.setContentsMargins(0, 0, 0, 0)
        slice_margin_layout.setSpacing(3)
        self.nine_slice_controls: dict[str, QDoubleSpinBox] = {}
        for prefix, edge in (
            ("L ", "left"),
            ("T ", "top"),
            ("R ", "right"),
            ("B ", "bottom"),
        ):
            spin = PainterUIDragDoubleSpinBox()
            spin.setRange(0.0, 16384.0)
            spin.setDecimals(1)
            spin.setPrefix(prefix)
            spin.setSuffix(" px")
            spin.editingFinished.connect(self._emit_properties)
            self.nine_slice_controls[edge] = spin
            slice_margin_layout.addWidget(spin)
        form.addRow("Slice Margins", slice_margin_row)
        text_metrics = QFrame()
        text_metrics_layout = QHBoxLayout(text_metrics)
        text_metrics_layout.setContentsMargins(0, 0, 0, 0)
        text_metrics_layout.setSpacing(3)
        self.font_size_spin = PainterUIDragDoubleSpinBox()
        self.font_size_spin.setRange(1.0, 512.0)
        self.font_size_spin.setSuffix(" px")
        self.font_size_spin.setResetValue(14.0)
        self.font_size_spin.editingFinished.connect(self._emit_properties)
        self.font_weight_combo = QComboBox()
        for label, weight in (
            ("Regular", 400),
            ("Medium", 500),
            ("Semibold", 600),
            ("Bold", 700),
        ):
            self.font_weight_combo.addItem(label, weight)
        self.font_weight_combo.currentIndexChanged.connect(self._emit_properties)
        text_metrics_layout.addWidget(self.font_size_spin)
        text_metrics_layout.addWidget(self.font_weight_combo)
        form.addRow("Typography", text_metrics)
        self.text_resize_combo = QComboBox()
        for label, mode in (
            ("Auto width", "auto_width"),
            ("Auto height", "auto_height"),
            ("Fixed size", "fixed_size"),
        ):
            self.text_resize_combo.addItem(label, mode)
        self.text_resize_combo.currentIndexChanged.connect(self._emit_properties)
        form.addRow("Resizing", self.text_resize_combo)
        font_axes = QFrame()
        self.font_axes_frame = font_axes
        font_axes_layout = QHBoxLayout(font_axes)
        font_axes_layout.setContentsMargins(0, 0, 0, 0)
        font_axes_layout.setSpacing(3)
        self.font_axis_checks: dict[str, QCheckBox] = {}
        self.font_axis_controls: dict[str, PainterUIDragDoubleSpinBox] = {}
        for tag, minimum, maximum, default in (
            ("wght", 1.0, 1000.0, 400.0),
            ("wdth", 25.0, 200.0, 100.0),
            ("opsz", 1.0, 144.0, 14.0),
        ):
            cell = QFrame()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(1)
            check = QCheckBox(tag)
            check.setToolTip(f"Enable OpenType {tag} axis")
            spin = PainterUIDragDoubleSpinBox()
            spin.setRange(minimum, maximum)
            spin.setDecimals(1)
            spin.setSingleStep(1.0)
            spin.setResetValue(default)
            spin.setEnabled(False)
            check.toggled.connect(spin.setEnabled)
            check.toggled.connect(self._emit_properties)
            spin.editingFinished.connect(self._emit_properties)
            cell_layout.addWidget(check)
            cell_layout.addWidget(spin)
            font_axes_layout.addWidget(cell, 1)
            self.font_axis_checks[tag] = check
            self.font_axis_controls[tag] = spin
        form.addRow("Variable Axes", font_axes)
        text_layout = QFrame()
        text_layout_row = QHBoxLayout(text_layout)
        text_layout_row.setContentsMargins(0, 0, 0, 0)
        text_layout_row.setSpacing(3)
        self.text_align_combo = QComboBox()
        for label, alignment in (
            ("Left", "left"),
            ("Center", "center"),
            ("Right", "right"),
        ):
            self.text_align_combo.addItem(label, alignment)
        self.text_align_combo.currentIndexChanged.connect(self._emit_properties)
        self.line_height_spin = PainterUIDragDoubleSpinBox()
        self.line_height_spin.setRange(0.5, 1000.0)
        self.line_height_spin.setDecimals(2)
        self.line_height_spin.setSingleStep(0.05)
        self.line_height_spin.setPrefix("Line ")
        self.line_height_spin.setResetValue(1.2)
        self.line_height_spin.editingFinished.connect(self._emit_properties)
        text_layout_row.addWidget(self.text_align_combo)
        text_layout_row.addWidget(self.line_height_spin)
        form.addRow("Text Layout", text_layout)
        self.accessibility_role_combo = QComboBox()
        for label, role in (
            ("Auto", "auto"),
            ("None", "none"),
            ("Button", "button"),
            ("Checkbox", "checkbox"),
            ("Heading", "heading"),
            ("Image", "image"),
            ("Link", "link"),
            ("Progress", "progress"),
            ("Slider", "slider"),
            ("Text", "text"),
        ):
            self.accessibility_role_combo.addItem(label, role)
        self.accessibility_role_combo.currentIndexChanged.connect(
            self._emit_properties
        )
        form.addRow("A11y Role", self.accessibility_role_combo)
        self.accessibility_label_edit = QLineEdit()
        self.accessibility_label_edit.setPlaceholderText(
            "Screen reader label"
        )
        self.accessibility_label_edit.editingFinished.connect(
            self._emit_properties
        )
        form.addRow("A11y Label", self.accessibility_label_edit)
        self.focus_order_spin = PainterUIDragSpinBox()
        self.focus_order_spin.setRange(0, 9999)
        self.focus_order_spin.setSpecialValueText("Auto")
        self.focus_order_spin.setToolTip(
            "0 follows document order; positive values define an explicit order"
        )
        self.focus_order_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Focus Order", self.focus_order_spin)
        delivery_status = QFrame()
        delivery_layout = QVBoxLayout(delivery_status)
        delivery_layout.setContentsMargins(0, 2, 0, 2)
        delivery_layout.setSpacing(2)
        self.delivery_status_labels: dict[str, QLabel] = {}
        for target, title in (
            ("asset_export", "Asset"),
            ("design_handoff", "Handoff"),
            ("review_prototype", "Prototype"),
            ("unreal_umg", "Unreal UMG"),
        ):
            label = QLabel(f"{title}: -")
            label.setObjectName("PainterUIDeliveryStatus")
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            delivery_layout.addWidget(label)
            self.delivery_status_labels[target] = label
        form.addRow("Delivery", delivery_status)
        self.visible_check = QCheckBox("Visible")
        self.visible_check.toggled.connect(self._emit_properties)
        self.locked_check = QCheckBox("Locked")
        self.locked_check.toggled.connect(self._emit_properties)
        flags = QFrame()
        flags_layout = QHBoxLayout(flags)
        flags_layout.setContentsMargins(0, 0, 0, 0)
        flags_layout.addWidget(self.visible_check)
        flags_layout.addWidget(self.locked_check)
        form.addRow("State", flags)
        arrange = QFrame()
        arrange_layout = QHBoxLayout(arrange)
        arrange_layout.setContentsMargins(0, 0, 0, 0)
        arrange_layout.setSpacing(2)
        for label, command in (
            ("L", "left"),
            ("HC", "hcenter"),
            ("R", "right"),
            ("T", "top"),
            ("VC", "vcenter"),
            ("B", "bottom"),
            ("DH", "distribute_h"),
            ("DV", "distribute_v"),
        ):
            button = QPushButton(label)
            button.setFixedHeight(24)
            button.setToolTip(f"Align selected object {command} to artboard")
            button.clicked.connect(
                lambda _checked=False, value=command: self._emit_arrange(value)
            )
            arrange_layout.addWidget(button)
        form.addRow("Align", arrange)
        self._design_form = form
        self._design_context_rows = {
            "identity": (self.name_edit, self.kind_label),
            "geometry": (
                *self.geometry_controls.values(),
            ),
            "constraints": (
                pivot_row,
                constraint_row,
                *size_limit_rows,
                self.aspect_lock_check,
                responsive_row,
                self.responsive_status_label,
            ),
            "component": (
                component_row,
                self.component_status_label,
                self.component_state_combo,
                variant_row,
                self.component_variant_properties_frame,
                self.component_definition_properties_frame,
                self.component_instance_properties_frame,
                detach_row,
                override_row,
            ),
            "auto_layout": (
                auto_layout_entry,
                self.auto_layout_flow_control,
                self.auto_layout_umg_panel_control,
                self.auto_layout_grid_controls,
                auto_sizing,
                auto_padding,
                auto_flow,
                self.auto_layout_alignment_control,
                auto_cross,
            ),
            "content_stress": (stress_preview,),
            "token_suggestions": (self.token_suggestion_panel,),
            "appearance": (
                self.opacity_spin,
                self.fill_field,
                self.stroke_field,
                self.stroke_width_spin,
                self.radius_spin,
                self.appearance_button,
            ),
            "shape": (shape_controls,),
            "multi_properties": (multi_properties,),
            "frame": (self.clip_content_check,),
            "scroll_overflow": (self.scroll_overflow_combo,),
            "scroll_position": (self.scroll_position_combo,),
            "text": (
                self.text_edit,
                text_metrics,
                font_axes,
                text_layout,
            ),
            "text_advanced": (
                text_range_row,
                text_range_actions,
            ),
            "boolean": (boolean_row,),
            "remote": (remote_row,),
            "image": (
                image_source_row,
                image_layout_row,
                image_focal_row,
            ),
            "image_advanced": (
                self.nine_slice_check,
                slice_margin_row,
            ),
            "accessibility": (
                self.accessibility_role_combo,
                self.accessibility_label_edit,
                self.focus_order_spin,
            ),
            "delivery": (delivery_status,),
            "state": (flags,),
            "arrange": (arrange,),
        }
        self._design_all_rows = tuple(
            dict.fromkeys(
                widget
                for widgets in self._design_context_rows.values()
                for widget in widgets
            )
        )
        object_properties_layout.addLayout(form)
        object_properties_layout.addStretch(1)
        add_inspector_tab(inspect_page, "Inspect", "settings")
        self._configure_context_tabs(
            design_page=inspect_page,
            prototype_page=motion_scroll,
            inspect_page=self.production_panel,
        )

    def _configure_context_tabs(
        self,
        *,
        design_page: QWidget,
        prototype_page: QWidget,
        inspect_page: QWidget,
    ) -> None:
        ordered = (
            (design_page, "Design"),
            (prototype_page, "Prototype"),
            (inspect_page, "Inspect"),
        )
        for widget, _label in ordered:
            index = self._tabs.indexOf(widget)
            if index >= 0:
                self._tabs.removeTab(index)
        for widget, label in ordered:
            index = self._tabs.addTab(widget, label)
            self._tabs.setTabToolTip(index, label)
            self._tabs.setTabWhatsThis(index, label)
        self._context_pages = {
            "design": design_page,
            "prototype": prototype_page,
            "inspect": inspect_page,
        }
        self._tabs.setCurrentWidget(design_page)

    def _emit_context_mode_changed(self, _index: int = -1) -> None:
        current = self._tabs.currentWidget()
        for mode, page in (
            getattr(self, "_context_pages", {}) or {}
        ).items():
            if current is page:
                self.context_mode_changed.emit(str(mode))
                return

    def _sync_context_tabs(self, selection_count: int) -> None:
        """Expose only tools that make sense for the current canvas context."""
        pages = dict(getattr(self, "_context_pages", {}) or {})
        if not pages:
            return
        visible = {
            "design": True,
            "prototype": True,
            "inspect": selection_count > 0,
        }
        current = self._tabs.currentWidget()
        for key, page in pages.items():
            index = self._tabs.indexOf(page)
            if index >= 0:
                self._tabs.setTabVisible(index, bool(visible.get(key, True)))
        current_index = self._tabs.indexOf(current)
        if current_index < 0 or not self._tabs.isTabVisible(current_index):
            self._tabs.setCurrentWidget(pages["design"])

    def visible_context_tabs(self) -> tuple[str, ...]:
        context_pages = set(
            (getattr(self, "_context_pages", {}) or {}).values()
        )
        return tuple(
            self._tabs.tabWhatsThis(index).casefold()
            for index in range(self._tabs.count())
            if self._tabs.isTabVisible(index)
            and self._tabs.widget(index) in context_pages
        )

    def set_prototype_preview_state(
        self,
        state: Mapping[str, Any] | None,
        *,
        enabled: bool,
    ) -> None:
        self.prototype_panel.set_preview_state(state, enabled=enabled)

    def set_collapsed(self, collapsed: bool) -> None:
        value = bool(collapsed)
        if self._collapsed == value:
            return
        self._collapsed = value
        for widget in self._collapsible_widgets:
            if widget is self.artboard_layout_frame and not value:
                widget.setVisible(self.artboard_settings_toggle.isChecked())
            else:
                widget.setVisible(not value)
        self.title_label.setVisible(not value)
        self.dock_button.setVisible(not value)
        self._sync_collapse_button()
        self.collapsed_changed.emit(value)

    def set_auto_hide(self, auto_hide: bool) -> None:
        value = bool(auto_hide)
        changed = self._auto_hide != value
        if not changed and self._collapsed == value:
            return
        self._auto_hide = value
        self.set_collapsed(value)
        if changed:
            self.auto_hide_changed.emit(value)

    def is_auto_hide(self) -> bool:
        return bool(self._auto_hide)

    def set_temporary_expanded(self, expanded: bool) -> None:
        value = bool(expanded)
        if self._temporary_expanded == value:
            return
        self._temporary_expanded = value
        for widget in self._collapsible_widgets:
            if widget is self.artboard_layout_frame:
                widget.setVisible(
                    value
                    and self.artboard_settings_toggle.isVisible()
                    and self.artboard_settings_toggle.isChecked()
                )
            else:
                widget.setVisible(value or not self._collapsed)
        self.title_label.setVisible(value or not self._collapsed)
        self.dock_button.setVisible(not value)
        self._sync_collapse_button()

    def is_temporary_expanded(self) -> bool:
        return self._temporary_expanded

    def _on_collapse_clicked(self) -> None:
        if self._temporary_expanded:
            self.temporary_close_requested.emit()
            return
        self.set_auto_hide(not self._collapsed)

    def set_detached(self, detached: bool) -> None:
        value = bool(detached)
        self.dock_button.setToolTip(
            "Dock inspector" if value else "Detach inspector"
        )
        self.dock_button.setAccessibleName(self.dock_button.toolTip())
        self.dock_button.setIcon(
            app_icon(
                "relink" if value else "popout",
                size=12,
                color="#B8C4D3",
            )
        )

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _sync_collapse_button(self) -> None:
        self.collapse_button.setIcon(
            app_icon(
                (
                    "x"
                    if self._temporary_expanded
                    else "chevron-left"
                    if self._collapsed
                    else "chevron-right"
                ),
                size=12,
                color="#B8C4D3",
            )
        )
        self.collapse_button.setIconSize(icon_size(12))
        tooltip = painter_text(
            "Close temporary properties"
            if self._temporary_expanded
            else "Pin properties"
            if self._collapsed
            else "Auto-hide properties"
        )
        self.collapse_button.setToolTip(tooltip)
        self.collapse_button.setAccessibleName(tooltip)

    def take_layers_page(self) -> QWidget:
        """Detach the Layers page for the left UI Design navigator."""
        index = self._tabs.indexOf(self.layers_page)
        if index >= 0:
            self._tabs.removeTab(index)
        for tab_index in range(self._tabs.count()):
            if self._tabs.tabWhatsThis(tab_index) == "Design":
                self._tabs.setCurrentIndex(tab_index)
                break
        return self.layers_page

    def take_asset_pages(self) -> dict[str, QWidget]:
        """Detach reusable document assets for the left navigator."""
        pages: dict[str, QWidget] = {}
        for label, widget in (
            ("Sections", getattr(self, "sections_page", None)),
            ("Components", getattr(self, "component_library", None)),
            ("Styles", getattr(self, "style_library", None)),
            ("Libraries", getattr(self, "library_panel", None)),
            ("Tokens", getattr(self, "token_library", None)),
        ):
            if widget is None:
                continue
            index = self._tabs.indexOf(widget)
            if index >= 0:
                self._tabs.removeTab(index)
            pages[label] = widget
        return pages

    def _sync_layer_hierarchy_lists(self) -> None:
        """Refresh the lightweight Layers/Sections view from ``_document``.

        Canvas creation tools call this without rebuilding the expensive
        libraries, prototype reports, and property editors.  The left
        navigator owns ``layer_list`` visually, but the inspector remains its
        data/controller owner for compatibility.
        """
        selected = str(self._document["selection"]["object_id"] or "")
        selected_ids = set(self._document["selection"]["object_ids"])
        active = str(self._document["active_artboard_id"] or "")
        active_rows = [
            row
            for row in self._document["objects"]
            if row["artboard_id"] == active
        ]
        children_by_parent: dict[str, list[dict[str, Any]]] = {}
        for row in active_rows:
            children_by_parent.setdefault(row["parent_id"], []).append(row)
        for children in children_by_parent.values():
            children.sort(key=lambda row: row["z_index"], reverse=True)
        rows: list[dict[str, Any]] = []

        def append_children(parent_id: str) -> None:
            for row in children_by_parent.get(parent_id, []):
                rows.append(row)
                append_children(row["id"])

        append_children("")
        row_by_id = {row["id"]: row for row in rows}
        self.layer_list.clear_hover()
        self.layer_list.clear()
        for row in rows:
            depth = 0
            parent_id = row["parent_id"]
            visited = set()
            while parent_id and parent_id not in visited:
                visited.add(parent_id)
                parent = row_by_id.get(parent_id)
                if parent is None:
                    break
                depth += 1
                parent_id = parent["parent_id"]
            # QListWidget is retained for drag/reorder compatibility; use a
            # Figma-sized visual indent so children read as hierarchy instead
            # of appearing aligned with their parent.
            prefix = "    " * depth
            state = "" if row["visible"] else "hidden"
            mask_state = (
                "mask"
                if bool((row.get("mask") or {}).get("enabled", False))
                else ""
            )
            component_role = str(row.get("component_role") or "none")
            icon_name = {
                "frame": "ui-frame",
                "group": "group",
                "text": "caption",
                "image": "image",
                "ellipse": "ellipse",
                "line": "line",
                "button": "button",
                "progress": "progress",
            }.get(str(row["kind"]), "rectangle")
            item = QListWidgetItem(
                app_icon(icon_name, size=12, color="#AAB7C6"),
                f"{prefix}{row['name']}",
            )
            detail = " | ".join(
                value
                for value in (
                    str(row["kind"]),
                    component_role if component_role != "none" else "",
                    mask_state,
                    state,
                )
                if value
            )
            item.setToolTip(detail)
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            item.setData(int(Qt.ItemDataRole.UserRole) + 1, row["kind"])
            self.layer_list.addItem(item)
            if row["id"] in selected_ids:
                item.setSelected(True)
            if row["id"] == selected:
                self.layer_list.setCurrentItem(item)
        self.section_list.clear()
        for section in self._document.get("sections", []):
            item = QListWidgetItem(
                f"{section['name']}  ({len(section['object_ids'])})"
            )
            item.setData(Qt.ItemDataRole.UserRole, section["id"])
            self.section_list.addItem(item)

    def set_hierarchy_document(
        self,
        value: Mapping[str, Any] | None,
    ) -> None:
        """Update only the layer hierarchy during repeated canvas creation."""
        self._document = normalize_ui_document(value)
        self._syncing = True
        try:
            self._sync_layer_hierarchy_lists()
            # Keep the contextual shell live while a creation tool remains
            # active.  This swaps Frame/Shape pages and loads the selected
            # object's compact controls without rebuilding libraries or dev
            # reports on every drag.
            self._sync_design_context_visibility(self._selected_row())
        finally:
            self._syncing = False

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        # Every panel below is read-only, so they share this one canonical
        # document instead of each deep copying it.  On a large imported Figma
        # file those defensive copies were most of the cost of a single click.
        self.comments_panel.set_document(self._document)
        self._sync_token_suggestions()
        self.component_library.set_document(self._document, normalize=False)
        self.style_library.set_document(self._document, normalize=False)
        self.library_panel.set_document(self._document)
        self.token_library.set_document(self._document, normalize=False)
        self.prototype_panel.set_document(self._document, normalize=False)
        self.production_panel.set_document(self._document, normalize=False)
        from app.painter_ui_dev_handoff import inspect_ui_dev_handoff

        self.dev_panel.set_report(
            inspect_ui_dev_handoff(self._document, normalize=False)
        )
        active_page = self._document["active_page_id"]
        active = self._document["active_artboard_id"]
        self._syncing = True
        try:
            self.artboard_combo.clear()
            page_artboards = [
                artboard
                for artboard in self._document["artboards"]
                if artboard["page_id"] == active_page
            ]
            for artboard in page_artboards:
                self.artboard_combo.addItem(
                    f"{artboard['name']}  {artboard['width']} x {artboard['height']}",
                    artboard["id"],
                )
                if artboard["id"] == active:
                    self.artboard_combo.setCurrentIndex(
                        self.artboard_combo.count() - 1
                    )
            self.delete_artboard_button.setEnabled(
                len(page_artboards) > 1
            )
            self._sync_artboard_layout_fields()
            self._sync_layer_hierarchy_lists()
            self._sync_selected_fields()
        finally:
            self._syncing = False

    def set_motion_delivery_report(
        self,
        value: Mapping[str, Any] | None,
    ) -> None:
        self.motion_delivery_panel.set_report(value)

    def set_motion_binding_report(
        self,
        value: Mapping[str, Any] | None,
    ) -> None:
        self.motion_binding_panel.set_report(value)

    def set_stress_preview_report(
        self,
        value: Mapping[str, Any] | None,
    ) -> None:
        self._stress_preview_report = dict(value or {})
        self._sync_stress_preview_controls()

    def _sync_token_suggestions(self) -> None:
        from app.painter_ui_token_suggestion import suggest_ui_tokens

        self.token_suggestion_panel.set_report(
            suggest_ui_tokens(self._document, normalize=False)
        )

    def _selected_id(self) -> str:
        return str(self._document["selection"]["object_id"] or "")

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self._selected_id()
        return next(
            (row for row in self._document["objects"] if row["id"] == selected),
            None,
        )

    def _component_instance_root(
        self,
        row: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not row or str(row.get("component_role") or "") != "instance":
            return None
        component_id = str(row.get("component_id") or "")
        component = next(
            (
                item
                for item in self._document["components"]
                if item["id"] == component_id
            ),
            None,
        )
        if component is None:
            return None
        source_root_id = str(component.get("root_object_id") or "")
        objects = {item["id"]: item for item in self._document["objects"]}
        current = dict(row)
        while current:
            if (
                str(current.get("component_source_object_id") or "")
                == source_root_id
            ):
                return objects.get(str(current["id"]))
            current = objects.get(str(current.get("parent_id") or ""))
        return None

    def _sync_selected_fields(self) -> None:
        base_row = self._selected_row()
        row = base_row
        enabled = base_row is not None
        self._sync_design_context_visibility(base_row)
        breakpoint, orientation = self._responsive_context()
        if row is not None and row.get("component_role") == "instance":
            from app.painter_ui_components import resolve_ui_component_document

            component_document = resolve_ui_component_document(self._document)
            row = next(
                (
                    item
                    for item in component_document["objects"]
                    if item["id"] == row["id"]
                ),
                row,
            )
        if base_row is not None and self.responsive_edit_check.isChecked():
            from app.painter_ui_responsive import resolve_ui_responsive_object

            row = resolve_ui_responsive_object(
                row,
                breakpoint=breakpoint,
                orientation=orientation,
            )
        if row is not None:
            from app.painter_ui_themes import (
                resolve_ui_theme_object,
                ui_theme_for_artboard,
            )

            row = resolve_ui_theme_object(
                row,
                theme=ui_theme_for_artboard(self._active_artboard()),
                tokens={
                    token["id"]: token
                    for token in self._document["tokens"]
                },
            )
        for widget in (
            self.name_edit,
            self.opacity_spin,
            self.fill_edit,
            self.stroke_edit,
            self.stroke_width_spin,
            self.radius_spin,
            self.appearance_button,
            self.shape_point_count_spin,
            self.shape_inner_radius_spin,
            self.shape_corner_radius_spin,
            self.shape_rotation_spin,
            self.shape_start_angle_spin,
            self.shape_sweep_angle_spin,
            self.clip_content_check,
            self.scroll_overflow_combo,
            self.scroll_position_combo,
            self.use_as_mask_check,
            self.mask_invert_check,
            self.mask_outline_check,
            self.text_edit,
            self.text_range_start_spin,
            self.text_range_end_spin,
            self.text_range_weight_spin,
            self.text_range_color_edit,
            self.text_range_apply_button,
            self.text_range_remove_button,
            self.boolean_operation_combo,
            self.boolean_operand_ids_edit,
            self.remote_component_key_edit,
            self.font_size_spin,
            self.font_weight_combo,
            self.text_resize_combo,
            *self.font_axis_checks.values(),
            *self.font_axis_controls.values(),
            self.text_align_combo,
            self.line_height_spin,
            self.image_source_edit,
            self.image_browse_button,
            self.image_fit_combo,
            self.image_tile_scale_spin,
            self.nine_slice_check,
            *self.nine_slice_controls.values(),
            self.accessibility_role_combo,
            self.accessibility_label_edit,
            self.focus_order_spin,
            self.auto_layout_mode_combo,
            self.auto_layout_gap_spin,
            self.auto_layout_cross_gap_spin,
            self.auto_layout_main_combo,
            self.auto_layout_cross_combo,
            self.auto_layout_positioning_combo,
            self.auto_layout_width_sizing_combo,
            self.auto_layout_height_sizing_combo,
            self.auto_layout_wrap_check,
            self.stress_preview_combo,
            self.stress_preview_clear_button,
            *self.auto_layout_padding_controls.values(),
            self.pivot_x_spin,
            self.pivot_y_spin,
            self.horizontal_constraint_combo,
            self.vertical_constraint_combo,
            self.aspect_lock_check,
            self.responsive_edit_check,
            self.responsive_clear_button,
            self.component_create_button,
            self.component_instance_button,
            self.component_combine_button,
            self.component_playground_button,
            self.component_state_combo,
            self.component_variant_combo,
            self.component_variant_new_button,
            self.component_detach_button,
            self.component_localize_button,
            self.component_override_combo,
            self.component_override_reset_button,
            self.component_override_reset_all_button,
            *self.size_limit_controls.values(),
            self.visible_check,
            self.locked_check,
            *self.geometry_controls.values(),
        ):
            widget.setEnabled(enabled)
        if row is None:
            self.name_edit.clear()
            self.kind_label.setText("-")
            self.fill_edit.clear()
            self.stroke_edit.clear()
            self._appearance_style = {}
            self.appearance_button.setText("Solid")
            self.clip_content_check.setChecked(False)
            self.scroll_overflow_combo.setCurrentIndex(0)
            self.scroll_position_combo.setCurrentIndex(0)
            self.use_as_mask_check.setChecked(False)
            self.mask_invert_check.setChecked(False)
            self.mask_outline_check.setChecked(False)
            self.text_edit.clear()
            self.boolean_operand_ids_edit.clear()
            self.remote_component_key_edit.clear()
            self.image_source_edit.clear()
            self.accessibility_label_edit.clear()
            self.focus_order_spin.setValue(0)
            self.component_status_label.setText("Not a component")
            self.auto_layout_status_label.setText("Select an object")
            self.auto_layout_status_label.setToolTip("")
            self.auto_layout_umg_panel_control.set_context(
                self._document,
                None,
                editable=False,
            )
            self.component_state_combo.setCurrentIndex(0)
            self.component_variant_combo.clear()
            self._rebuild_component_variant_property_controls(None, None)
            self._rebuild_component_definition_property_controls(None, None)
            self._rebuild_component_instance_property_controls(None, None)
            self.component_override_combo.clear()
            self.component_override_reset_button.setEnabled(False)
            self.component_override_reset_all_button.setEnabled(False)
            for target, label in self.delivery_status_labels.items():
                label.setText(f"{self._delivery_title(target)}: -")
                label.setToolTip("")
            return
        from app.painter_ui_responsive import responsive_override_for_context

        override = responsive_override_for_context(
            base_row,
            breakpoint=breakpoint,
            orientation=orientation,
        )
        self.responsive_status_label.setText(
            (
                f"{breakpoint} / {orientation}: "
                + ("Override active" if override else "No override")
            )
        )
        self.responsive_clear_button.setEnabled(override is not None)
        component_role = str(base_row.get("component_role") or "none")
        component_id = str(base_row.get("component_id") or "")
        self.component_create_button.setEnabled(component_role == "none")
        self.component_instance_button.setEnabled(bool(component_id))
        selected_ids = set(
            self._document.get("selection", {}).get("object_ids", [])
        )
        selected_components = [
            item
            for item in self._document.get("components", [])
            if item.get("root_object_id") in selected_ids
            and not item.get("base_component_id")
            and not item.get("variant_ids")
        ]
        self.component_combine_button.setEnabled(
            len(selected_components) == len(selected_ids) and len(selected_ids) >= 2
        )
        self.component_playground_button.setEnabled(bool(component_id))
        self.component_create_button.setVisible(component_role == "none")
        self.component_instance_button.setVisible(bool(component_id))
        self.component_combine_button.setVisible(
            len(selected_components) == len(selected_ids)
            and len(selected_ids) >= 2
        )
        self.component_playground_button.setVisible(bool(component_id))
        instance_root = self._component_instance_root(base_row)
        self.component_state_combo.setEnabled(instance_root is not None)
        component_state = str(
            (instance_root or {}).get("component_properties", {}).get(
                "state", "normal"
            )
        )
        state_index = self.component_state_combo.findData(component_state)
        self.component_state_combo.setCurrentIndex(max(0, state_index))
        components = {
            item["id"]: item for item in self._document["components"]
        }
        component = components.get(component_id)
        family_id = (
            str(component.get("base_component_id") or component["id"])
            if component is not None
            else ""
        )
        family = components.get(family_id)
        family_ids = (
            [family_id, *family["variant_ids"]]
            if family is not None
            else []
        )
        self.component_variant_combo.clear()
        for family_component_id in family_ids:
            family_component = components.get(family_component_id)
            if family_component is not None:
                self.component_variant_combo.addItem(
                    str(family_component["name"]),
                    family_component_id,
                )
        variant_index = self.component_variant_combo.findData(component_id)
        self.component_variant_combo.setCurrentIndex(max(0, variant_index))
        self.component_variant_combo.setEnabled(
            instance_root is not None and len(family_ids) > 1
        )
        self.component_variant_new_button.setEnabled(bool(component_id))
        variant_inspection = None
        if component is not None:
            from app.painter_ui_components import inspect_ui_component_set

            variant_inspection = inspect_ui_component_set(
                self._document,
                component_id=component_id,
            )
        self._rebuild_component_variant_property_controls(
            variant_inspection,
            instance_root,
            component_id=component_id,
        )
        self._rebuild_component_definition_property_controls(
            component,
            instance_root,
        )
        self._rebuild_component_instance_property_controls(
            component,
            instance_root,
            variant_property_names=(
                variant_inspection.get("property_names", [])
                if variant_inspection is not None
                else []
            ),
        )
        self.component_detach_button.setEnabled(instance_root is not None)
        self.component_localize_button.setEnabled(instance_root is not None)
        self.component_override_combo.clear()
        override_report = {"count": 0, "overrides": []}
        if instance_root is not None:
            from app.painter_ui_components import (
                inspect_ui_component_instance_overrides,
            )

            override_report = inspect_ui_component_instance_overrides(
                self._document,
                instance_root_id=str(instance_root["id"]),
            )
            for override in override_report["overrides"]:
                object_name = str(override["object_name"])
                property_name = str(override["label"])
                label = (
                    property_name
                    if override["kind"] == "component_property"
                    else f"{object_name} · {property_name}"
                )
                self.component_override_combo.addItem(label, override)
        has_overrides = bool(override_report["count"])
        self.component_override_combo.setEnabled(has_overrides)
        self.component_override_reset_button.setEnabled(has_overrides)
        self.component_override_reset_all_button.setEnabled(has_overrides)
        if component_role == "definition":
            component_text = "Definition"
        elif component_role == "instance":
            override_count = int(override_report["count"])
            component_text = (
                f"Instance / {component_state.title()} / "
                f"{override_count} override"
                + ("" if override_count == 1 else "s")
            )
        else:
            component_text = "Not a component"
        self.component_status_label.setText(component_text)
        self.name_edit.setText(str(row["name"]))
        self.kind_label.setText(str(row["kind"]).title())
        for key, spin in self.geometry_controls.items():
            spin.setValue(float(row[key]))
        self.opacity_spin.setValue(int(round(float(row["opacity"]) * 100.0)))
        self.fill_edit.setText(str(row["style"].get("fill") or ""))
        style = row["style"]
        self.stroke_edit.setText(str(style.get("stroke") or ""))
        self.stroke_width_spin.setValue(float(style.get("stroke_width") or 0.0))
        self.radius_spin.setValue(float(style.get("radius") or 0.0))
        self._appearance_style = dict(style)
        from app.painter_ui_appearance_editor import appearance_summary

        self.appearance_button.setText(appearance_summary(style))
        from app.painter_ui_parametric_shapes import (
            normalize_parametric_shape_content,
        )

        shape_content = normalize_parametric_shape_content(
            str(row["kind"]),
            row.get("content"),
        )
        self.shape_point_count_spin.setValue(
            int(shape_content.get("point_count", 5))
        )
        self.shape_inner_radius_spin.setValue(
            int(round(float(shape_content.get("inner_radius", 0.45)) * 100.0))
        )
        self.shape_corner_radius_spin.setValue(
            float(shape_content.get("corner_radius", 0.0))
        )
        self.shape_rotation_spin.setValue(
            float(shape_content.get("rotation_offset", -90.0))
        )
        self.shape_start_angle_spin.setValue(
            float(shape_content.get("start_angle", -90.0))
        )
        self.shape_sweep_angle_spin.setValue(
            float(shape_content.get("sweep_angle", 270.0))
        )
        is_frame = row["kind"] == "frame"
        self.clip_content_check.setEnabled(is_frame)
        self.clip_content_check.setChecked(
            is_frame and bool(row.get("clip_content", False))
        )
        from app.painter_ui_scroll import normalize_ui_scroll

        scroll = normalize_ui_scroll(base_row.get("scroll"))
        self.scroll_overflow_combo.setCurrentIndex(
            max(0, self.scroll_overflow_combo.findData(scroll["overflow"]))
        )
        self.scroll_position_combo.setCurrentIndex(
            max(0, self.scroll_position_combo.findData(scroll["position"]))
        )
        self.scroll_overflow_combo.setEnabled(is_frame)
        parent = next(
            (
                candidate
                for candidate in self._document.get("objects", [])
                if str(candidate.get("id") or "")
                == str(base_row.get("parent_id") or "")
            ),
            None,
        )
        parent_scroll = normalize_ui_scroll(
            parent.get("scroll") if parent is not None else None
        )
        self.scroll_position_combo.setEnabled(
            parent is not None and parent_scroll["overflow"] != "none"
        )
        mask = dict(base_row.get("mask") or {})
        self.use_as_mask_check.setChecked(bool(mask.get("enabled", False)))
        self.mask_invert_check.setChecked(bool(mask.get("inverted", False)))
        self.mask_outline_check.setChecked(bool(mask.get("outline", False)))
        is_text = row["kind"] in {"text", "button"}
        for widget in (
            self.text_edit,
            self.font_size_spin,
            self.font_weight_combo,
            self.text_resize_combo,
            *self.font_axis_checks.values(),
            *self.font_axis_controls.values(),
            self.text_align_combo,
            self.line_height_spin,
        ):
            widget.setEnabled(is_text)
        self.text_edit.setText(str(row["content"].get("text") or ""))
        from app.painter_ui_text_layout import normalize_text_resize_mode

        resize_index = self.text_resize_combo.findData(
            normalize_text_resize_mode(row["content"].get("text_resize"))
        )
        self.text_resize_combo.setCurrentIndex(max(0, resize_index))
        text_length = len(self.text_edit.text())
        self.text_range_start_spin.setRange(0, text_length)
        self.text_range_end_spin.setRange(0, text_length)
        self.text_range_start_spin.setValue(0)
        self.text_range_end_spin.setValue(text_length)
        for widget in (
            self.text_range_start_spin,
            self.text_range_end_spin,
            self.text_range_weight_spin,
            self.text_range_color_edit,
            self.text_range_apply_button,
            self.text_range_remove_button,
        ):
            widget.setEnabled(is_text)
        boolean = dict(row["content"].get("boolean") or {})
        boolean_index = self.boolean_operation_combo.findData(
            str(boolean.get("operation") or "union")
        )
        self.boolean_operation_combo.setCurrentIndex(max(0, boolean_index))
        self.boolean_operand_ids_edit.setText(
            ", ".join(str(item) for item in boolean.get("operand_ids", []))
        )
        remote = dict(row["content"].get("remote_component") or {})
        self.remote_component_key_edit.setText(
            str(
                remote.get("replacement_component_id")
                or remote.get("component_key")
                or ""
            )
        )
        self.font_size_spin.setValue(float(style.get("font_size") or 14.0))
        weight = int(style.get("font_weight") or 400)
        weight_index = self.font_weight_combo.findData(weight)
        self.font_weight_combo.setCurrentIndex(max(0, weight_index))
        from app.painter_ui_typography import (
            UI_VARIABLE_FONT_AXIS_DEFAULTS,
            normalize_ui_font_axes,
        )

        font_axes = normalize_ui_font_axes(style.get("font_axes"))
        for tag, check in self.font_axis_checks.items():
            enabled = tag in font_axes
            check.setChecked(enabled)
            self.font_axis_controls[tag].setEnabled(is_text and enabled)
            self.font_axis_controls[tag].setValue(
                font_axes.get(tag, UI_VARIABLE_FONT_AXIS_DEFAULTS[tag])
            )
        align_index = self.text_align_combo.findData(
            str(style.get("text_align") or "left")
        )
        self.text_align_combo.setCurrentIndex(max(0, align_index))
        try:
            line_height = float(style.get("line_height") or 1.2)
        except (TypeError, ValueError):
            line_height = 1.2
        line_height_unit = str(
            style.get("line_height_unit") or ""
        ).strip().casefold()
        pixel_line_height = (
            line_height_unit in {"px", "pixel", "pixels"}
            or line_height > 4.0
        )
        self.line_height_spin.setSingleStep(0.5 if pixel_line_height else 0.05)
        self.line_height_spin.setSuffix(" px" if pixel_line_height else "×")
        self.line_height_spin.setResetValue(
            float(style.get("font_size") or 14.0) * 1.2
            if pixel_line_height
            else 1.2
        )
        self.line_height_spin.setValue(line_height)
        from app.painter_ui_image_renderer import normalize_ui_image_content

        image_content = normalize_ui_image_content(row.get("content"))
        from app.painter_ui_image_assets import IMAGE_FILL_KINDS

        is_image = row["kind"] in IMAGE_FILL_KINDS
        for widget in (
            self.image_source_edit,
            self.image_browse_button,
            self.image_fit_combo,
            self.image_tile_scale_spin,
            self.image_focal_x_spin,
            self.image_focal_y_spin,
            self.image_original_size_button,
            self.nine_slice_check,
            *self.nine_slice_controls.values(),
        ):
            widget.setEnabled(is_image)
        self.image_source_edit.setText(image_content["source_path"])
        image_fit_index = self.image_fit_combo.findData(
            image_content["image_fit"]
        )
        self.image_fit_combo.setCurrentIndex(max(0, image_fit_index))
        self.image_tile_scale_spin.setValue(image_content["tile_scale"])
        self.image_focal_x_spin.setValue(image_content["focal_x"])
        self.image_focal_y_spin.setValue(image_content["focal_y"])
        self.image_original_size_button.setEnabled(
            is_image
            and image_content["original_width"] > 0
            and image_content["original_height"] > 0
        )
        self.nine_slice_check.setChecked(
            image_content["nine_slice_enabled"]
        )
        for edge, spin in self.nine_slice_controls.items():
            spin.setValue(float(image_content["nine_slice"][edge]))
        self._sync_image_control_states()
        layout = normalize_ui_auto_layout(row.get("layout"))
        mode_index = self.auto_layout_mode_combo.findData(layout["mode"])
        self.auto_layout_mode_combo.setCurrentIndex(max(0, mode_index))
        self.auto_layout_umg_panel_control.set_context(
            self._document,
            base_row,
            editable=not bool(base_row.get("locked", False)),
        )
        self.auto_layout_grid_columns_spin.setValue(int(layout["grid_columns"]))
        self.auto_layout_grid_column_span_spin.setValue(
            int(layout["grid_column_span"])
        )
        self.auto_layout_grid_row_span_spin.setValue(
            int(layout["grid_row_span"])
        )
        for edge, spin in self.auto_layout_padding_controls.items():
            spin.setValue(float(layout["padding"][edge]))
        self.auto_layout_gap_spin.setValue(float(layout["gap"]))
        self.auto_layout_cross_gap_spin.setValue(float(layout["cross_gap"]))
        main_index = self.auto_layout_main_combo.findData(
            layout["main_alignment"]
        )
        self.auto_layout_main_combo.setCurrentIndex(max(0, main_index))
        cross_index = self.auto_layout_cross_combo.findData(
            layout["cross_alignment"]
        )
        self.auto_layout_cross_combo.setCurrentIndex(max(0, cross_index))
        positioning_index = self.auto_layout_positioning_combo.findData(
            layout["positioning"]
        )
        self.auto_layout_positioning_combo.setCurrentIndex(
            max(0, positioning_index)
        )
        width_sizing_index = self.auto_layout_width_sizing_combo.findData(
            layout["width_sizing"]
        )
        self.auto_layout_width_sizing_combo.setCurrentIndex(
            max(0, width_sizing_index)
        )
        height_sizing_index = self.auto_layout_height_sizing_combo.findData(
            layout["height_sizing"]
        )
        self.auto_layout_height_sizing_combo.setCurrentIndex(
            max(0, height_sizing_index)
        )
        spacing_option = (
            "padding"
            if layout["umg_spacing_strategy"] == "padding"
            else "spacer_fill"
            if layout["umg_spacer_size_rule"] == "fill"
            else "spacer_auto"
        )
        spacing_index = self.auto_layout_umg_spacing_combo.findData(
            spacing_option
        )
        self.auto_layout_umg_spacing_combo.setCurrentIndex(
            max(0, spacing_index)
        )
        self.auto_layout_umg_spacer_fill_spin.setValue(
            float(layout["umg_spacer_fill_coefficient"])
        )
        self.auto_layout_wrap_check.setChecked(bool(layout["wrap"]))
        self._sync_auto_layout_control_states()
        self._sync_object_layout_status(base_row)
        accessibility = row["accessibility"]
        role_index = self.accessibility_role_combo.findData(
            accessibility["role"]
        )
        self.accessibility_role_combo.setCurrentIndex(max(0, role_index))
        self.accessibility_label_edit.setText(accessibility["label"])
        self.focus_order_spin.setValue(accessibility["focus_order"])
        from app.painter_ui_delivery import ui_object_delivery_statuses

        statuses = ui_object_delivery_statuses(self._document, row["id"])
        for status in statuses["targets"]:
            target = status["target"]
            label = self.delivery_status_labels[target]
            label.setText(
                f"{self._delivery_title(target)}: "
                f"{status['display_disposition']}"
            )
            label.setToolTip(status["reason"])
        constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=float(row["width"]),
            height=float(row["height"]),
        )
        self.pivot_x_spin.setValue(float(constraints["pivot_x"]))
        self.pivot_y_spin.setValue(float(constraints["pivot_y"]))
        horizontal_index = self.horizontal_constraint_combo.findData(
            constraints["horizontal"]
        )
        self.horizontal_constraint_combo.setCurrentIndex(
            max(0, horizontal_index)
        )
        vertical_index = self.vertical_constraint_combo.findData(
            constraints["vertical"]
        )
        self.vertical_constraint_combo.setCurrentIndex(max(0, vertical_index))
        for key, spin in self.size_limit_controls.items():
            spin.setValue(float(constraints[key]))
        self.aspect_lock_check.setChecked(bool(constraints["lock_aspect"]))
        self.visible_check.setChecked(bool(row["visible"]))
        self.locked_check.setChecked(bool(row["locked"]))
        self._sync_multi_properties()

    def _sync_design_context_visibility(
        self,
        row: Mapping[str, Any] | None,
    ) -> None:
        selected_ids = [
            str(value)
            for value in self._document.get("selection", {}).get(
                "object_ids",
                [],
            )
            if str(value)
        ]
        count = len(selected_ids)
        if count == 0 or row is None:
            context = "artboard"
            title = "Artboard"
            hint = "Select an object to edit its properties."
            visible_groups: set[str] = set()
        elif count > 1:
            context = "multi"
            title = f"{count} objects selected"
            hint = "Edit common properties, align, or distribute."
            visible_groups = {"multi_properties", "arrange", "auto_layout"}
        else:
            kind = str(row.get("kind") or "object").casefold()
            component_role = str(
                row.get("component_role") or "none"
            ).casefold()
            content = dict(row.get("content") or {})
            context = kind
            title = {
                "frame": "Frame",
                "group": "Group",
                "text": "Text",
                "button": "Button",
                "image": "Image",
                "ellipse": "Ellipse",
                "line": "Line",
                "polygon": "Polygon",
                "star": "Star",
                "arc": "Arc",
                "progress": "Progress",
            }.get(kind, kind.replace("_", " ").title() or "Object")
            hint = {
                "frame": "Layout, clipping, appearance, and constraints",
                "group": "Layout, appearance, and constraints",
                "text": "Typography, appearance, and accessibility",
                "button": "Component state, typography, and interaction",
                "image": "Source, crop behavior, and export",
            }.get(kind, "Geometry, appearance, and delivery")
            visible_groups = {
                "identity",
                "geometry",
                "appearance",
                "state",
                "arrange",
            }
            if (
                int(
                    self.token_suggestion_panel.report().get(
                        "suggestion_count",
                        0,
                    )
                    or 0
                )
                > 0
            ):
                visible_groups.add("token_suggestions")
            if kind in {"frame", "group", "button"}:
                visible_groups.add("auto_layout")
            if kind in {"polygon", "star", "arc"}:
                visible_groups.add("shape")
            visible_groups.add("content_stress")
            if kind == "frame":
                visible_groups.add("frame")
                visible_groups.add("scroll_overflow")
            parent_id = str(row.get("parent_id") or "")
            if parent_id:
                visible_groups.add("scroll_position")
            if kind in {"text", "button"}:
                visible_groups.add("text")
            from app.painter_ui_image_assets import IMAGE_FILL_KINDS

            if (
                kind in IMAGE_FILL_KINDS
                and (
                    kind == "image"
                    or bool(content.get("source_path"))
                )
            ):
                visible_groups.add("image")
            if component_role != "none":
                visible_groups.add("component")
            if (
                self.advanced_properties_toggle.isChecked()
                and (
                component_role != "none"
                or bool(content.get("remote_component"))
                )
            ):
                visible_groups.add("remote")
            if self.advanced_properties_toggle.isChecked():
                visible_groups.update(
                    {"constraints", "accessibility", "delivery"}
                )
                if kind in {"text", "button"}:
                    visible_groups.add("text_advanced")
                if kind == "image":
                    visible_groups.add("image_advanced")
        self._design_context = context
        empty_selection = count == 0
        if bool(self.property("emptySelection")) != empty_selection:
            self.setProperty("emptySelection", empty_selection)
            self.style().unpolish(self)
            self.style().polish(self)
        self.title_bar.setVisible(not empty_selection)
        self.artboard_bar.setVisible(count == 0)
        localized_title = painter_text(title)
        self.title_label.setText(
            painter_text("UI DESIGN")
            if count == 0
            else f"UI · {localized_title}"
        )
        self._sync_context_tabs(count)
        self._selection_count = count
        self._selected_context_kind = (
            str(row.get("kind") or "").casefold()
            if count == 1 and row is not None
            else ""
        )
        self._selected_context_component_role = (
            str(row.get("component_role") or "none").casefold()
            if count == 1 and row is not None
            else "none"
        )
        frame_selected = bool(
            count == 1
            and row is not None
            and str(row.get("kind") or "") == "frame"
        )
        if frame_selected:
            self.frame_selection_panel.set_frame(row, self._document)
        shape_selected = bool(
            count == 1
            and row is not None
            and str(row.get("kind") or "")
            in {"rectangle", "ellipse", "line", "polygon", "star", "arc"}
        )
        if shape_selected:
            self.shape_selection_panel.set_shape(row, self._document)
        self.selection_context.setVisible(count > 0 and not frame_selected)
        self._sync_tool_context_visibility()
        if count == 0:
            self.artboard_bar.hide()
            self.artboard_settings_toggle.hide()
            self.artboard_layout_frame.hide()
        self.motion_binding_panel.setVisible(count > 0)
        self.motion_delivery_panel.setVisible(count > 0)
        self.selection_context_title.setText(localized_title)
        self.selection_context_hint.setText(painter_text(hint))
        self.advanced_properties_toggle.setVisible(count == 1)
        self.artboard_settings_toggle.hide()
        self.artboard_layout_frame.hide()
        visible_rows = {
            widget
            for group in visible_groups
            for widget in self._design_context_rows.get(group, ())
        }
        for widget in self._design_all_rows:
            visible = widget in visible_rows
            if hasattr(self._design_form, "setRowVisible"):
                self._design_form.setRowVisible(widget, visible)
            else:
                label = self._design_form.labelForField(widget)
                if label is not None:
                    label.setVisible(visible)
                widget.setVisible(visible)
        self._sync_parametric_shape_controls(
            str(row.get("kind") or "") if row is not None and count == 1 else ""
        )

    def set_active_tool_context(self, tool: str) -> None:
        self._active_tool_context = str(tool or "select").casefold()
        self._sync_tool_context_visibility()

    def _sync_tool_context_visibility(self) -> None:
        mode = str(getattr(self, "_active_tool_context", "select"))
        selection_count = int(getattr(self, "_selection_count", 0))
        selected_kind = str(getattr(self, "_selected_context_kind", ""))
        component_selected = (
            str(
                getattr(
                    self,
                    "_selected_context_component_role",
                    "none",
                )
            )
            != "none"
        )
        region_tool = selection_count == 0 and mode in {
            "frame",
            "section",
            "slice",
        }
        panel = getattr(self, "frame_presets_panel", None)
        if panel is not None:
            panel.set_mode(mode)
        stack = getattr(self, "selection_content_stack", None)
        if stack is None:
            return
        if mode == "comment":
            target = self.comments_panel
        elif region_tool:
            target = self.frame_presets_panel
        elif selection_count == 0:
            target = self.page_properties_panel
        elif component_selected:
            target = self.object_properties_scroll
        elif selection_count == 1 and selected_kind == "frame":
            target = self.frame_selection_scroll
        elif selection_count == 1 and selected_kind in {
            "rectangle",
            "ellipse",
            "line",
            "polygon",
            "star",
            "arc",
        }:
            target = self.shape_selection_scroll
        else:
            target = self.object_properties_scroll
        stack.setCurrentWidget(target)
        self.object_properties_host.setVisible(
            target is self.object_properties_scroll
        )

    def select_comment(self, comment_id: str) -> None:
        self.set_active_tool_context("comment")
        self.comments_panel.select_comment(comment_id)

    def _emit_frame_panel_geometry(self, changes: object) -> None:
        object_id = self._selected_id()
        if object_id and isinstance(changes, Mapping):
            self.geometry_changed.emit(object_id, dict(changes))

    def _emit_frame_panel_properties(self, changes: object) -> None:
        object_id = self._selected_id()
        if object_id and isinstance(changes, Mapping):
            self.properties_changed.emit(object_id, dict(changes))

    def _emit_frame_panel_align(self, command: str) -> None:
        object_id = self._selected_id()
        if object_id:
            self.arrange_requested.emit(object_id, str(command))

    def _show_page_style_menu(self) -> None:
        point = self.page_style_button.mapToGlobal(
            self.page_style_button.rect().bottomRight()
        )
        point.setX(point.x() - self.page_style_menu.sizeHint().width())
        self.page_style_menu.popup(point)

    def _open_text_style_dialog(self) -> None:
        from app.painter_ui_text_style_dialog import PainterUITextStyleDialog

        dialog = PainterUITextStyleDialog(self)
        dialog.style_created.connect(self.style_add_requested)
        dialog.finished.connect(dialog.deleteLater)
        self._text_style_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _sync_parametric_shape_controls(self, kind: str) -> None:
        visible_by_kind = {
            "polygon": {"points", "corner_radius", "rotation"},
            "star": {
                "points", "inner_radius", "corner_radius", "rotation",
            },
            "arc": {"inner_radius", "angles"},
        }.get(str(kind).casefold(), set())
        for key, row in self.shape_parameter_rows.items():
            row.setVisible(key in visible_by_kind)

    def design_context(self) -> str:
        return str(getattr(self, "_design_context", "artboard"))

    def design_group_visible(self, group: str) -> bool:
        widgets = self._design_context_rows.get(str(group), ())
        if not widgets:
            return False
        if hasattr(self._design_form, "isRowVisible"):
            return any(
                self._design_form.isRowVisible(widget)
                for widget in widgets
            )
        return any(not widget.isHidden() for widget in widgets)

    def _on_advanced_properties_toggled(self, checked: bool) -> None:
        self.advanced_properties_toggle.setIcon(
            app_icon(
                "chevron-down" if checked else "chevron-right",
                size=11,
                color="#AEBACA",
            )
        )
        if not self._syncing:
            self._sync_design_context_visibility(self._selected_row())

    def _responsive_context(self) -> tuple[str, str]:
        from app.painter_ui_responsive import responsive_context

        return responsive_context(self._active_artboard())

    def _on_responsive_edit_toggled(self, _checked: bool) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self._sync_selected_fields()
        finally:
            self._syncing = False

    def _emit_responsive_override_remove(self) -> None:
        if self._syncing or not self._selected_id():
            return
        breakpoint, orientation = self._responsive_context()
        self.responsive_override_remove_requested.emit(
            self._selected_id(),
            breakpoint,
            orientation,
        )

    def _emit_component_create(self) -> None:
        row = self._selected_row()
        if self._syncing or row is None:
            return
        self.component_create_requested.emit(
            str(row["id"]),
            str(row["name"]),
        )

    def _emit_component_instantiate(self) -> None:
        row = self._selected_row()
        if self._syncing or row is None or not row.get("component_id"):
            return
        self.component_instantiate_requested.emit(
            str(row["component_id"]),
            str(row["artboard_id"]),
            float(row["x"]) + 32.0,
            float(row["y"]) + 32.0,
        )

    def _emit_component_variants_combine(self) -> None:
        if self._syncing:
            return
        selected_ids = set(
            self._document.get("selection", {}).get("object_ids", [])
        )
        component_ids = [
            str(item["id"])
            for item in self._document.get("components", [])
            if item.get("root_object_id") in selected_ids
            and not item.get("base_component_id")
            and not item.get("variant_ids")
        ]
        if len(component_ids) >= 2:
            self.component_variants_combine_requested.emit(component_ids)

    def _emit_component_playground(self) -> None:
        row = self._selected_row()
        if self._syncing or row is None or not row.get("component_id"):
            return
        self.component_playground_requested.emit(str(row["component_id"]))

    def _emit_component_state(self) -> None:
        row = self._selected_row()
        instance_root = self._component_instance_root(row)
        if self._syncing or instance_root is None:
            return
        properties = dict(instance_root.get("component_properties") or {})
        properties["state"] = str(
            self.component_state_combo.currentData() or "normal"
        )
        self.properties_changed.emit(
            str(instance_root["id"]),
            {"component_properties": properties},
        )

    def _emit_component_variant_create(self) -> None:
        row = self._selected_row()
        if self._syncing or row is None or not row.get("component_id"):
            return
        component = next(
            (
                item
                for item in self._document["components"]
                if item["id"] == row["component_id"]
            ),
            None,
        )
        if component is None:
            return
        self.component_variant_create_requested.emit(
            str(component["id"]),
            f"{component['name']} Variant",
        )

    def _emit_component_variant_switch(self) -> None:
        row = self._selected_row()
        instance_root = self._component_instance_root(row)
        target_component_id = str(
            self.component_variant_combo.currentData() or ""
        )
        if (
            self._syncing
            or instance_root is None
            or not target_component_id
            or target_component_id == instance_root.get("component_id")
        ):
            return
        self.component_variant_switch_requested.emit(
            str(instance_root["id"]),
            target_component_id,
        )

    def _rebuild_component_variant_property_controls(
        self,
        inspection: Mapping[str, Any] | None,
        instance_root: Mapping[str, Any] | None,
        *,
        component_id: str = "",
    ) -> None:
        layout = self.component_variant_properties_layout
        while layout.rowCount():
            layout.removeRow(0)
        self.component_variant_property_combos.clear()
        report = dict(inspection or {})
        property_names = [str(name) for name in report.get("property_names", [])]
        members = {
            str(member.get("component_id") or ""): member
            for member in report.get("members", [])
            if isinstance(member, Mapping)
        }
        selected_component_id = str(
            (instance_root or {}).get("component_id") or component_id or ""
        )
        selected_properties = dict(
            (members.get(selected_component_id) or {}).get("properties") or {}
        )
        definitions = dict(report.get("property_definitions") or {})
        for property_name in property_names:
            definition = definitions.get(property_name)
            if not isinstance(definition, Mapping):
                continue
            values = [str(value) for value in definition.get("values", [])]
            if not values:
                continue
            combo = QComboBox()
            combo.setToolTip(
                painter_text(
                    "Choose the Variant value for this component property"
                )
            )
            for value in values:
                combo.addItem(value, value)
            current_value = str(
                selected_properties.get(property_name)
                or definition.get("default")
                or values[0]
            )
            combo.setCurrentIndex(max(0, combo.findData(current_value)))
            combo.currentIndexChanged.connect(
                lambda _index, name=property_name: (
                    self._emit_component_variant_property_change(name)
                )
            )
            layout.addRow(property_name, combo)
            self.component_variant_property_combos[property_name] = combo
        self.component_variant_properties_frame.setVisible(
            bool(self.component_variant_property_combos)
        )

    def _emit_component_variant_property_change(self, _name: str) -> None:
        if self._syncing:
            return
        row = self._selected_row()
        if row is None:
            return
        properties = {
            name: str(combo.currentData() or combo.currentText())
            for name, combo in self.component_variant_property_combos.items()
        }
        instance_root = self._component_instance_root(row)
        if instance_root is not None:
            self.component_instance_variant_values_set_requested.emit(
                str(instance_root["id"]),
                properties,
            )
            return
        component_id = str(row.get("component_id") or "")
        if component_id:
            self.component_variant_values_set_requested.emit(
                component_id,
                properties,
            )

    def _rebuild_component_definition_property_controls(
        self,
        component: Mapping[str, Any] | None,
        instance_root: Mapping[str, Any] | None,
    ) -> None:
        """Show main-component property management, separate from instance values."""

        layout = self.component_definition_properties_layout
        while layout.rowCount():
            layout.removeRow(0)
        self.component_definition_property_controls.clear()
        if component is None or instance_root is not None:
            self.component_definition_properties_frame.setVisible(False)
            return
        from app.painter_ui_components import (
            normalize_ui_component_property_definitions,
        )

        definitions = normalize_ui_component_property_definitions(
            component.get("property_definitions")
        )
        component_id = str(component["id"])
        for property_name, definition in definitions.items():
            if str(definition.get("type") or "") != "instance_swap":
                continue
            preferred_count = len(definition.get("preferred_values") or [])
            control = QPushButton(
                f"Preferred instances ({preferred_count})…"
            )
            control.setToolTip(
                "Curate the components shown first when this nested instance is swapped"
            )
            control.clicked.connect(
                lambda _checked=False, cid=component_id, name=property_name: (
                    self.component_instance_swap_preferred_edit_requested.emit(
                        cid,
                        name,
                    )
                )
            )
            layout.addRow(property_name, control)
            self.component_definition_property_controls[property_name] = control
        self.component_definition_properties_frame.setVisible(
            bool(self.component_definition_property_controls)
        )

    def _rebuild_component_instance_property_controls(
        self,
        component: Mapping[str, Any] | None,
        instance_root: Mapping[str, Any] | None,
        *,
        variant_property_names: object = (),
    ) -> None:
        layout = self.component_instance_properties_layout
        while layout.rowCount():
            layout.removeRow(0)
        self.component_instance_property_controls.clear()
        if component is None or instance_root is None:
            self.component_instance_properties_frame.setVisible(False)
            return
        from app.painter_ui_components import (
            component_property_defaults,
            normalize_ui_component_properties,
            normalize_ui_component_property_definitions,
        )

        definitions = normalize_ui_component_property_definitions(
            component.get("property_definitions")
        )
        values = component_property_defaults(component)
        values.update(
            normalize_ui_component_properties(
                instance_root.get("component_properties")
            )
        )
        variant_names = {str(name) for name in (variant_property_names or [])}
        components = {
            str(row["id"]): str(row["name"])
            for row in self._document.get("components", [])
        }
        for property_name, definition in definitions.items():
            if property_name in variant_names or property_name == "state":
                continue
            property_type = str(definition.get("type") or "text")
            value = values.get(property_name)
            if property_type == "slot":
                from app.painter_ui_components import (
                    inspect_ui_component_instance_slot,
                )

                report = inspect_ui_component_instance_slot(
                    self._document,
                    instance_root_id=str(instance_root["id"]),
                    property_name=property_name,
                )
                control = QWidget()
                row_layout = QHBoxLayout(control)
                row_layout.setContentsMargins(0, 0, 0, 0)
                count = int(report.get("child_count") or 0)
                violations = list(report.get("limit_violations") or [])
                summary = QLabel(
                    f"{count} layer" + ("s" if count != 1 else "")
                    + (f" · {', '.join(violations)}" if violations else "")
                )
                summary.setObjectName("painterUISlotSummary")
                reset = QPushButton("Reset")
                reset.setToolTip("Reset Slot to the main component contents")
                reset.clicked.connect(
                    lambda _checked=False, name=property_name, root_id=str(
                        instance_root["id"]
                    ): self.component_slot_reset_requested.emit(root_id, name)
                )
                row_layout.addWidget(summary, 1)
                row_layout.addWidget(reset)
            elif property_type == "boolean":
                control = QCheckBox()
                control.setChecked(bool(value))
                control.toggled.connect(
                    lambda checked, name=property_name: (
                        self._emit_component_instance_property(name, checked)
                    )
                )
            elif property_type in {"enum", "instance_swap"}:
                control = QComboBox()
                choices = (
                    list(definition.get("values") or [])
                    if property_type == "enum"
                    else [
                        *[
                            item
                            for item in definition.get("preferred_values", [])
                            if item in components
                        ],
                        *[
                            item
                            for item in components
                            if item not in definition.get("preferred_values", [])
                        ],
                    ]
                )
                for choice in choices:
                    control.addItem(
                        components.get(str(choice), str(choice)),
                        choice,
                    )
                control.setCurrentIndex(max(0, control.findData(value)))
                control.currentIndexChanged.connect(
                    lambda _index, name=property_name, widget=control: (
                        self._emit_component_instance_property(
                            name,
                            widget.currentData(),
                        )
                    )
                )
            elif property_type == "number":
                control = QDoubleSpinBox()
                control.setRange(-100000.0, 100000.0)
                control.setDecimals(2)
                control.setValue(float(value or 0.0))
                control.editingFinished.connect(
                    lambda name=property_name, widget=control: (
                        self._emit_component_instance_property(
                            name,
                            widget.value(),
                        )
                    )
                )
            else:
                control = QLineEdit(str(value or ""))
                control.editingFinished.connect(
                    lambda name=property_name, widget=control: (
                        self._emit_component_instance_property(
                            name,
                            widget.text(),
                        )
                    )
                )
            description = str(definition.get("description") or "")
            if description:
                control.setToolTip(description)
            layout.addRow(property_name, control)
            self.component_instance_property_controls[property_name] = control
        self.component_instance_properties_frame.setVisible(
            bool(self.component_instance_property_controls)
        )

    def _emit_component_instance_property(
        self,
        property_name: str,
        value: Any,
    ) -> None:
        if self._syncing:
            return
        instance_root = self._component_instance_root(self._selected_row())
        if instance_root is None:
            return
        self.component_instance_property_set_requested.emit(
            str(instance_root["id"]),
            str(property_name),
            value,
        )

    def _emit_component_detach(self, create_local_component: bool) -> None:
        row = self._selected_row()
        instance_root = self._component_instance_root(row)
        if self._syncing or instance_root is None:
            return
        self.component_detach_requested.emit(
            str(instance_root["id"]),
            bool(create_local_component),
            (
                f"{instance_root['name']} Local"
                if create_local_component
                else ""
            ),
        )

    def _emit_component_override_reset(self) -> None:
        row = self._selected_row()
        instance_root = self._component_instance_root(row)
        override = self.component_override_combo.currentData()
        if (
            self._syncing
            or instance_root is None
            or not isinstance(override, Mapping)
        ):
            return
        self.component_override_reset_requested.emit(
            str(instance_root["id"]),
            str(override.get("object_id") or instance_root["id"]),
            str(override.get("property_path") or ""),
        )

    def _emit_component_override_reset_all(self) -> None:
        row = self._selected_row()
        instance_root = self._component_instance_root(row)
        if self._syncing or instance_root is None:
            return
        self.component_override_reset_all_requested.emit(
            str(instance_root["id"])
        )

    def _on_selection_changed(self) -> None:
        if self._syncing:
            return
        selected_ids = [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in self.layer_list.selectedItems()
            if str(item.data(Qt.ItemDataRole.UserRole) or "")
        ]
        current = self.layer_list.currentItem()
        primary = (
            str(current.data(Qt.ItemDataRole.UserRole) or "")
            if current is not None
            else selected_ids[-1] if selected_ids else ""
        )
        self.selection_changed.emit(selected_ids, primary)

    def _on_artboard_changed(self) -> None:
        if self._syncing:
            return
        artboard_id = str(self.artboard_combo.currentData() or "")
        if artboard_id:
            self.artboard_selected.emit(artboard_id)

    def _active_artboard(self) -> dict[str, Any]:
        active = self._document["active_artboard_id"]
        return next(
            row for row in self._document["artboards"] if row["id"] == active
        )

    def _sync_artboard_layout_fields(self) -> None:
        from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

        artboard = self._active_artboard()
        breakpoint = str(artboard.get("breakpoint") or "custom")
        breakpoint_index = self.artboard_breakpoint_combo.findData(breakpoint)
        if breakpoint_index >= 0:
            self.artboard_breakpoint_combo.setCurrentIndex(breakpoint_index)
        else:
            self.artboard_breakpoint_combo.setEditText(breakpoint)
        orientation_index = self.artboard_orientation_combo.findData(
            str(artboard.get("orientation") or "portrait")
        )
        self.artboard_orientation_combo.setCurrentIndex(
            max(0, orientation_index)
        )
        theme_index = self.artboard_theme_combo.findData(
            str(artboard.get("theme") or "light")
        )
        self.artboard_theme_combo.setCurrentIndex(max(0, theme_index))
        selected_style_id = str(artboard.get("layout_grid_style_id") or "")
        self.artboard_grid_style_combo.clear()
        self.artboard_grid_style_combo.addItem("Local", "")
        for style in self._document.get("layout_grid_styles", []):
            self.artboard_grid_style_combo.addItem(
                str(style["name"]),
                str(style["id"]),
            )
        style_index = self.artboard_grid_style_combo.findData(selected_style_id)
        self.artboard_grid_style_combo.setCurrentIndex(max(0, style_index))
        has_style = bool(selected_style_id)
        self.artboard_grid_style_update_button.setEnabled(has_style)
        self.artboard_grid_style_remove_button.setEnabled(has_style)
        layout = normalize_ui_artboard_layout(
            artboard,
            width=float(artboard["width"]),
            height=float(artboard["height"]),
        )
        grid = layout["layout_grid"]
        mode_index = self.artboard_grid_mode_combo.findData(grid["mode"])
        self.artboard_grid_mode_combo.setCurrentIndex(max(0, mode_index))
        self.artboard_grid_count_spin.setValue(int(grid["count"]))
        self.artboard_grid_size_spin.setValue(float(grid["size"]))
        self.artboard_grid_gutter_spin.setValue(float(grid["gutter"]))
        self.artboard_grid_margin_spin.setValue(float(grid["margin"]))
        alignment_index = self.artboard_grid_alignment_combo.findData(
            str(grid.get("alignment") or "stretch")
        )
        self.artboard_grid_alignment_combo.setCurrentIndex(max(0, alignment_index))
        self.artboard_safe_visible_check.setChecked(layout["safe_area_visible"])
        for edge, spin in self.artboard_safe_controls.items():
            spin.setValue(int(layout["safe_area"][edge]))
        guides = layout["guides"]
        self.artboard_guides_visible_check.setChecked(bool(guides["visible"]))
        self.artboard_vertical_guides_edit.setText(
            ", ".join(f"{value:g}" for value in guides["vertical"])
        )
        self.artboard_horizontal_guides_edit.setText(
            ", ".join(f"{value:g}" for value in guides["horizontal"])
        )
        columns = grid["mode"] in {"columns", "rows"}
        uniform = grid["mode"] == "grid"
        centered = columns and grid.get("alignment") == "center"
        self.artboard_grid_count_spin.setEnabled(columns)
        self.artboard_grid_gutter_spin.setEnabled(columns)
        self.artboard_grid_margin_spin.setEnabled(columns and not centered)
        self.artboard_grid_size_spin.setEnabled(uniform or centered)
        from app.painter_ui_layout_diagnostics import diagnose_ui_layout

        report = diagnose_ui_layout(self._document, normalize=False)
        diagnostics = [
            row
            for row in report["diagnostics"]
            if row["owner_id"] == str(artboard["id"])
            or any(
                item["id"] == row["owner_id"]
                and item["artboard_id"] == artboard["id"]
                for item in self._document["objects"]
            )
        ]
        errors = sum(row["severity"] == "error" for row in diagnostics)
        warnings = sum(row["severity"] == "warning" for row in diagnostics)
        if errors:
            text = f"Layout: {errors} error"
        elif warnings:
            text = f"Layout: {warnings} warning"
        else:
            text = "Layout: Ready"
        self.artboard_layout_status_label.setText(text)
        self.artboard_layout_status_label.setToolTip(
            "\n".join(row["message"] for row in diagnostics)
        )

    @staticmethod
    def _guide_values(value: str) -> list[float]:
        result: list[float] = []
        for token in str(value or "").replace(";", ",").split(","):
            try:
                result.append(float(token.strip()))
            except ValueError:
                continue
        return result

    def _emit_artboard_layout(self) -> None:
        if self._syncing:
            return
        artboard = self._active_artboard()
        mode = str(self.artboard_grid_mode_combo.currentData() or "none")
        changes = {
            "layout_grid": {
                "mode": mode,
                "visible": mode != "none",
                "size": float(self.artboard_grid_size_spin.value()),
                "count": int(self.artboard_grid_count_spin.value()),
                "gutter": float(self.artboard_grid_gutter_spin.value()),
                "margin": float(self.artboard_grid_margin_spin.value()),
                "alignment": str(
                    self.artboard_grid_alignment_combo.currentData()
                    or "stretch"
                ),
                "color": str(
                    artboard.get("layout_grid", {}).get("color")
                    or "#4C9AFF32"
                ),
            },
            "safe_area": {
                edge: int(spin.value())
                for edge, spin in self.artboard_safe_controls.items()
            },
            "safe_area_visible": self.artboard_safe_visible_check.isChecked(),
            "guides": {
                "visible": self.artboard_guides_visible_check.isChecked(),
                "vertical": self._guide_values(
                    self.artboard_vertical_guides_edit.text()
                ),
                "horizontal": self._guide_values(
                    self.artboard_horizontal_guides_edit.text()
                ),
            },
        }
        self.artboard_layout_changed.emit(str(artboard["id"]), changes)
        columns = mode in {"columns", "rows"}
        uniform = mode == "grid"
        centered = (
            columns
            and self.artboard_grid_alignment_combo.currentData() == "center"
        )
        self.artboard_grid_count_spin.setEnabled(columns)
        self.artboard_grid_gutter_spin.setEnabled(columns)
        self.artboard_grid_margin_spin.setEnabled(columns and not centered)
        self.artboard_grid_size_spin.setEnabled(uniform or centered)

    def _emit_layout_grid_style_add(self) -> None:
        if self._syncing:
            return
        self.layout_grid_style_add_requested.emit(
            str(self._active_artboard()["id"])
        )

    def _emit_layout_grid_style_update(self) -> None:
        if self._syncing:
            return
        style_id = str(self.artboard_grid_style_combo.currentData() or "")
        if style_id:
            self.layout_grid_style_update_requested.emit(
                style_id,
                str(self._active_artboard()["id"]),
            )

    def _emit_layout_grid_style_apply(self) -> None:
        if self._syncing:
            return
        style_id = str(self.artboard_grid_style_combo.currentData() or "")
        self.artboard_grid_style_update_button.setEnabled(bool(style_id))
        self.artboard_grid_style_remove_button.setEnabled(bool(style_id))
        if style_id:
            self.layout_grid_style_apply_requested.emit(
                str(self._active_artboard()["id"]),
                style_id,
            )
        else:
            self.artboard_layout_changed.emit(
                str(self._active_artboard()["id"]),
                {"layout_grid_style_id": ""},
            )

    def _emit_layout_grid_style_remove(self) -> None:
        if self._syncing:
            return
        style_id = str(self.artboard_grid_style_combo.currentData() or "")
        if style_id:
            self.layout_grid_style_remove_requested.emit(style_id)

    def _emit_artboard_context(self) -> None:
        if self._syncing:
            return
        artboard = self._active_artboard()
        breakpoint = str(
            self.artboard_breakpoint_combo.currentText() or "custom"
        ).strip().casefold()
        orientation = str(
            self.artboard_orientation_combo.currentData() or "portrait"
        )
        theme = str(self.artboard_theme_combo.currentData() or "light")
        width = int(artboard["width"])
        height = int(artboard["height"])
        if (orientation == "landscape") != (width >= height):
            width, height = height, width
        self.artboard_layout_changed.emit(
            str(artboard["id"]),
            {
                "breakpoint": breakpoint,
                "orientation": orientation,
                "theme": theme,
                "width": width,
                "height": height,
            },
        )

    def _emit_add_artboard(self) -> None:
        preset = self.artboard_preset_combo.currentData()
        if not isinstance(preset, tuple) or len(preset) != 4:
            return
        name, width, height, breakpoint = preset
        self.artboard_add_requested.emit(
            str(name),
            int(width),
            int(height),
            str(breakpoint),
        )

    def _emit_add_artboard_preset(self, index: int) -> None:
        if not 0 <= int(index) < self.artboard_preset_combo.count():
            return
        self.artboard_preset_combo.setCurrentIndex(int(index))
        self._emit_add_artboard()

    def _emit_delete_artboard(self) -> None:
        if len(self._document.get("artboards", [])) <= 1:
            return
        artboard_id = str(self.artboard_combo.currentData() or "")
        if artboard_id:
            self.artboard_delete_requested.emit(artboard_id)

    def _sync_section_fields(self, index: int) -> None:
        if index < 0 or index >= len(self._document.get("sections", [])):
            self.section_name_edit.clear()
            self.section_object_ids_edit.clear()
            return
        section = self._document["sections"][index]
        self.section_name_edit.setText(str(section["name"]))
        self.section_object_ids_edit.setText(
            ", ".join(str(item) for item in section["object_ids"])
        )

    def _emit_section(self, operation: str) -> None:
        if self._syncing:
            return
        item = self.section_list.currentItem()
        section_id = (
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            if item is not None
            else ""
        )
        if operation in {"update", "remove"} and not section_id:
            return
        object_ids = [
            item.strip()
            for item in self.section_object_ids_edit.text().split(",")
            if item.strip()
        ]
        selected_rows = [
            row
            for row in self._document["objects"]
            if row["id"] in object_ids
        ]
        if selected_rows:
            x = min(float(row["x"]) for row in selected_rows)
            y = min(float(row["y"]) for row in selected_rows)
            right = max(
                float(row["x"]) + float(row["width"])
                for row in selected_rows
            )
            bottom = max(
                float(row["y"]) + float(row["height"])
                for row in selected_rows
            )
        else:
            x, y, right, bottom = 0.0, 0.0, 640.0, 480.0
        self.section_requested.emit(
            str(operation),
            section_id,
            {
                "name": self.section_name_edit.text().strip() or "Section",
                "object_ids": object_ids,
                "x": x,
                "y": y,
                "width": max(1.0, right - x),
                "height": max(1.0, bottom - y),
            },
        )

    def _emit_geometry(self) -> None:
        if self._syncing or not self._selected_id():
            return
        row = self._selected_row()
        if row is None:
            return
        constraints = row.get("constraints")
        width, height = constrain_ui_size(
            self.geometry_controls["width"].value(),
            self.geometry_controls["height"].value(),
            constraints,
            fallback_ratio=(
                float(row.get("width") or 1.0)
                / max(0.0001, float(row.get("height") or 1.0))
            ),
        )
        changes = {
            **{
                key: float(spin.value())
                for key, spin in self.geometry_controls.items()
            },
            "width": width,
            "height": height,
        }
        if self.responsive_edit_check.isChecked():
            breakpoint, orientation = self._responsive_context()
            self.responsive_override_changed.emit(
                self._selected_id(),
                breakpoint,
                orientation,
                changes,
            )
        else:
            self.geometry_changed.emit(self._selected_id(), changes)

    def _edit_appearance(self) -> None:
        if self._syncing or not self._selected_id():
            return
        from PySide6.QtWidgets import QDialog

        from app.painter_ui_appearance_editor import (
            PainterUIAppearanceDialog,
            appearance_summary,
        )

        dialog = PainterUIAppearanceDialog(
            self._appearance_style,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._appearance_style = dialog.appearance_style()
        self.appearance_button.setText(
            appearance_summary(self._appearance_style)
        )
        self._emit_properties()

    def _open_common_paint_editor(self, *, stroke: bool) -> None:
        """Open the same fill component used by frame and shape inspectors."""
        if self._syncing or not self._selected_id():
            return
        from PySide6.QtWidgets import QDialog

        from app.painter_ui_advanced_appearance import normalize_ui_paint
        from app.painter_ui_paint_editor import PainterUIPaintDialog

        key = "strokes" if stroke else "fills"
        rows = list(self._appearance_style.get(key) or [])
        legacy = self.stroke_edit.text() if stroke else self.fill_edit.text()
        source = rows[0] if rows else {
            "type": "solid",
            "color": legacy or ("#000000FF" if stroke else "#FFFFFFFF"),
            "width": float(self.stroke_width_spin.value()),
            "align": str(self._appearance_style.get("stroke_align") or "center"),
        }
        dialog = PainterUIPaintDialog(source, stroke=stroke, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        paint = normalize_ui_paint(dialog.paint(), stroke=stroke)
        if rows:
            rows[0] = paint
        else:
            rows = [paint]
        self._appearance_style[key] = rows
        if stroke:
            self.stroke_edit.setText(str(paint.get("color") or ""))
            self.stroke_width_spin.setValue(float(paint.get("width", 1.0)))
            self._appearance_style["stroke_align"] = str(paint.get("align") or "center")
        else:
            self.fill_edit.setText(str(paint.get("color") or ""))
        self._emit_properties()

    def _emit_clip_content(self, checked: bool) -> None:
        row = self._selected_row()
        if self._syncing or row is None or row["kind"] != "frame":
            return
        self.clip_changed.emit(str(row["id"]), bool(checked))

    def _emit_scroll_overflow(self) -> None:
        row = self._selected_row()
        if self._syncing or row is None or row["kind"] != "frame":
            return
        if (
            str(self.scroll_overflow_combo.currentData() or "none") != "none"
            and not self.clip_content_check.isChecked()
        ):
            self.clip_content_check.setChecked(True)
        self._emit_properties()

    def _selected_rows(self) -> list[dict[str, Any]]:
        selected_ids = {
            str(value)
            for value in self._document.get("selection", {}).get(
                "object_ids",
                [],
            )
            if str(value)
        }
        return [
            row
            for row in self._document.get("objects", [])
            if str(row.get("id") or "") in selected_ids
        ]

    @staticmethod
    def _common_value(values: list[Any]) -> tuple[bool, Any]:
        if not values:
            return False, None
        first = values[0]
        return all(value == first for value in values[1:]), first

    def _set_multi_spin_value(
        self,
        spin: QSpinBox | QDoubleSpinBox,
        values: list[float],
    ) -> None:
        common, value = self._common_value(values)
        spin.setMinimum(0)
        spin.setSpecialValueText("")
        if common:
            spin.setValue(value)
            spin.setProperty("mixedValue", False)
            return
        spin.setMinimum(-1)
        spin.setSpecialValueText("—")
        spin.setValue(-1)
        spin.setProperty("mixedValue", True)

    def _set_multi_text_value(
        self,
        edit: QLineEdit,
        values: list[str],
    ) -> None:
        common, value = self._common_value(values)
        edit.setProperty("mixedValue", not common)
        if common:
            edit.setPlaceholderText("#RRGGBB")
            edit.setText(str(value or ""))
        else:
            edit.clear()
            edit.setPlaceholderText("—")

    def _set_multi_check_value(
        self,
        check: QCheckBox,
        values: list[bool],
    ) -> None:
        common, value = self._common_value(values)
        check.setTristate(not common)
        check.setCheckState(
            (
                Qt.CheckState.Checked
                if bool(value)
                else Qt.CheckState.Unchecked
            )
            if common
            else Qt.CheckState.PartiallyChecked
        )
        check.setProperty("mixedValue", not common)

    def _sync_multi_properties(self) -> None:
        rows = self._selected_rows()
        if len(rows) < 2:
            self._multi_mixed_keys.clear()
            self._multi_dirty_keys.clear()
            return
        style_rows = [dict(row.get("style") or {}) for row in rows]
        value_sets: dict[str, list[Any]] = {
            "opacity": [round(float(row.get("opacity", 1.0)) * 100) for row in rows],
            "fill": [str(style.get("fill") or "") for style in style_rows],
            "stroke": [str(style.get("stroke") or "") for style in style_rows],
            "stroke_width": [
                float(style.get("stroke_width") or 0.0)
                for style in style_rows
            ],
            "radius": [
                float(style.get("radius") or 0.0)
                for style in style_rows
            ],
            "visible": [bool(row.get("visible", True)) for row in rows],
            "locked": [bool(row.get("locked", False)) for row in rows],
        }
        self._multi_mixed_keys = {
            key
            for key, values in value_sets.items()
            if not self._common_value(values)[0]
        }
        self._multi_dirty_keys.clear()
        self._set_multi_spin_value(
            self.multi_opacity_spin,
            value_sets["opacity"],
        )
        self._set_multi_text_value(self.multi_fill_edit, value_sets["fill"])
        self._set_multi_text_value(
            self.multi_stroke_edit,
            value_sets["stroke"],
        )
        self._set_multi_spin_value(
            self.multi_stroke_width_spin,
            value_sets["stroke_width"],
        )
        self._set_multi_spin_value(
            self.multi_radius_spin,
            value_sets["radius"],
        )
        self._set_multi_check_value(
            self.multi_visible_check,
            value_sets["visible"],
        )
        self._set_multi_check_value(
            self.multi_locked_check,
            value_sets["locked"],
        )
        self._sync_multi_spacing()

    def _sync_multi_spacing(self, _index: int = -1) -> None:
        from app.painter_ui_smart_selection import (
            inspect_ui_selection_spacing,
        )

        report = inspect_ui_selection_spacing(
            self._document,
            axis=str(self.multi_tidy_axis_combo.currentData() or "auto"),
        )
        eligible = bool(report["eligible"])
        self.multi_tidy_axis_combo.setEnabled(eligible)
        self.multi_gap_spin.setEnabled(eligible)
        self.multi_gap_y_spin.setEnabled(eligible)
        self.multi_tidy_button.setEnabled(eligible)
        self.multi_tidy_button.setToolTip(
            (
                "Make the selected object spacing uniform"
                if eligible
                else str(report["reason"])
            )
        )
        self.multi_gap_spin.setMinimum(-1.0)
        self.multi_gap_spin.setSpecialValueText("—")
        is_grid = eligible and report["axis"] == "grid"
        self.multi_gap_y_spin.setVisible(is_grid)
        self.multi_gap_spin.setPrefix("H " if is_grid else "")
        self.multi_gap_y_spin.setPrefix("V ")
        if is_grid:
            self.multi_gap_spin.setValue(float(report["horizontal_gap"]))
            self.multi_gap_y_spin.setValue(float(report["vertical_gap"]))
        elif eligible and report["uniform"]:
            self.multi_gap_spin.setValue(float(report["gap"] or 0.0))
        else:
            self.multi_gap_spin.setValue(-1.0)

    def _emit_tidy_selection(self) -> None:
        if self._syncing or self._design_context != "multi":
            return
        raw_gap = float(self.multi_gap_spin.value())
        axis = str(self.multi_tidy_axis_combo.currentData() or "auto")
        from app.painter_ui_smart_selection import inspect_ui_selection_spacing

        report = inspect_ui_selection_spacing(self._document, axis=axis)
        gap: object = None if raw_gap < 0.0 else raw_gap
        if report["eligible"] and report["axis"] == "grid":
            gap = {
                "horizontal": float(self.multi_gap_spin.value()),
                "vertical": float(self.multi_gap_y_spin.value()),
            }
        self.selection_tidy_requested.emit(
            axis,
            gap,
        )

    def _mark_multi_dirty(self, key: str) -> None:
        if not self._syncing:
            self._multi_dirty_keys.add(str(key))

    def _emit_multi_property(self, key: str, *, force: bool = False) -> None:
        if self._syncing or getattr(self, "_design_context", "") != "multi":
            return
        rows = self._selected_rows()
        if len(rows) < 2:
            return
        key = str(key)
        if key in {"visible", "locked"}:
            check = (
                self.multi_visible_check
                if key == "visible"
                else self.multi_locked_check
            )
            state = check.checkState()
            if state == Qt.CheckState.PartiallyChecked:
                return
            value: Any = state == Qt.CheckState.Checked
        elif key == "opacity":
            value = int(self.multi_opacity_spin.value())
            if value < 0:
                return
            value = value / 100.0
        elif key in {"stroke_width", "radius"}:
            spin = (
                self.multi_stroke_width_spin
                if key == "stroke_width"
                else self.multi_radius_spin
            )
            value = float(spin.value())
            if value < 0.0:
                return
        elif key in {"fill", "stroke"}:
            edit = (
                self.multi_fill_edit
                if key == "fill"
                else self.multi_stroke_edit
            )
            value = edit.text().strip()
            if (
                key in self._multi_mixed_keys
                and key not in self._multi_dirty_keys
                and not value
            ):
                return
        else:
            return
        changes_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            object_id = str(row["id"])
            if key in {"opacity", "visible", "locked"}:
                changes_by_id[object_id] = {key: value}
                continue
            style = copy.deepcopy(dict(row.get("style") or {}))
            if key in {"fill", "stroke"} and not value:
                style.pop(key, None)
            else:
                style[key] = value
            changes_by_id[object_id] = {"style": style}
        self._multi_dirty_keys.discard(key)
        self.batch_properties_changed.emit(changes_by_id)

    def _apply_shared_palette_color(self, color: str) -> None:
        target = str(self.palette_target_combo.currentData() or "fill")
        if getattr(self, "_design_context", "") == "multi":
            edit = (
                self.multi_stroke_edit
                if target == "stroke"
                else self.multi_fill_edit
            )
            edit.setText(str(color))
            self._mark_multi_dirty(target)
            self._emit_multi_property(target)
            return
        edit = self.stroke_edit if target == "stroke" else self.fill_edit
        edit.setText(str(color))
        edit.editingFinished.emit()

    def _emit_properties(self) -> None:
        if self._syncing or not self._selected_id():
            return
        row = self._selected_row()
        if row is None:
            return
        style = dict(row.get("style") or {})
        fill = self.fill_edit.text().strip()
        if fill:
            style["fill"] = fill
        else:
            style.pop("fill", None)
        stroke = self.stroke_edit.text().strip()
        if stroke:
            style["stroke"] = stroke
        else:
            style.pop("stroke", None)
        style["stroke_width"] = float(self.stroke_width_spin.value())
        style["radius"] = float(self.radius_spin.value())
        for key in (
            "fill_gradient",
            "effects",
            "shadow",
            "fills",
            "strokes",
            "blend_mode",
            "corner_radii",
            "stroke_align",
        ):
            if key in self._appearance_style:
                style[key] = copy.deepcopy(self._appearance_style[key])
            else:
                style.pop(key, None)
        content = dict(row.get("content") or {})
        shape_kind = str(row.get("kind") or "").casefold()
        if shape_kind in {"polygon", "star", "arc"}:
            from app.painter_ui_parametric_shapes import (
                normalize_parametric_shape_content,
            )

            content.update(
                normalize_parametric_shape_content(
                    shape_kind,
                    {
                        **content,
                        "point_count": self.shape_point_count_spin.value(),
                        "inner_radius": (
                            self.shape_inner_radius_spin.value() / 100.0
                        ),
                        "corner_radius": self.shape_corner_radius_spin.value(),
                        "rotation_offset": self.shape_rotation_spin.value(),
                        "start_angle": self.shape_start_angle_spin.value(),
                        "sweep_angle": self.shape_sweep_angle_spin.value(),
                    },
                )
            )
        if row.get("kind") in {"text", "button"}:
            content["text"] = self.text_edit.text()
            if row.get("kind") == "text":
                content["text_resize"] = str(
                    self.text_resize_combo.currentData() or "auto_width"
                )
            style["font_size"] = float(self.font_size_spin.value())
            style["font_weight"] = int(
                self.font_weight_combo.currentData() or 400
            )
            from app.painter_ui_typography import normalize_ui_font_axes

            font_axes = normalize_ui_font_axes(
                {
                    tag: self.font_axis_controls[tag].value()
                    for tag, check in self.font_axis_checks.items()
                    if check.isChecked()
                }
            )
            if font_axes:
                style["font_axes"] = font_axes
            else:
                style.pop("font_axes", None)
            style["text_align"] = str(
                self.text_align_combo.currentData() or "left"
            )
            style["line_height"] = float(self.line_height_spin.value())
        from app.painter_ui_image_assets import IMAGE_FILL_KINDS

        if row.get("kind") in IMAGE_FILL_KINDS:
            content.update(
                {
                    "source_path": self.image_source_edit.text().strip(),
                    "image_fit": str(
                        self.image_fit_combo.currentData() or "fit"
                    ),
                    "tile_scale": float(self.image_tile_scale_spin.value()),
                    "focal_x": float(self.image_focal_x_spin.value()),
                    "focal_y": float(self.image_focal_y_spin.value()),
                    "nine_slice_enabled": (
                        self.nine_slice_check.isChecked()
                    ),
                    "nine_slice": {
                        edge: float(spin.value())
                        for edge, spin in self.nine_slice_controls.items()
                    },
                }
            )
        constraints = capture_ui_constraints(
            row,
            constraint_parent_geometry(self._document, row),
            {
                "horizontal": self.horizontal_constraint_combo.currentData()
                or "left",
                "vertical": self.vertical_constraint_combo.currentData() or "top",
                "pivot_x": self.pivot_x_spin.value(),
                "pivot_y": self.pivot_y_spin.value(),
                "lock_aspect": self.aspect_lock_check.isChecked(),
                **{
                    key: spin.value()
                    for key, spin in self.size_limit_controls.items()
                },
            },
        )
        layout = normalize_ui_auto_layout(
            {
                **dict(row.get("layout") or {}),
                "mode": self.auto_layout_mode_combo.currentData() or "none",
                "padding": {
                    edge: float(spin.value())
                    for edge, spin in self.auto_layout_padding_controls.items()
                },
                "gap": float(self.auto_layout_gap_spin.value()),
                "cross_gap": float(self.auto_layout_cross_gap_spin.value()),
                "main_alignment": (
                    self.auto_layout_main_combo.currentData() or "start"
                ),
                "cross_alignment": (
                    self.auto_layout_cross_combo.currentData() or "start"
                ),
                "positioning": (
                    self.auto_layout_positioning_combo.currentData() or "auto"
                ),
                "width_sizing": (
                    self.auto_layout_width_sizing_combo.currentData() or "fixed"
                ),
                "height_sizing": (
                    self.auto_layout_height_sizing_combo.currentData() or "fixed"
                ),
                "umg_panel_mode": (
                    self.auto_layout_umg_panel_control.mode_combo.currentData()
                    or "auto"
                ),
                "umg_spacing_strategy": (
                    "padding"
                    if self.auto_layout_umg_spacing_combo.currentData()
                    == "padding"
                    else "spacer"
                ),
                "umg_spacer_size_rule": (
                    "fill"
                    if self.auto_layout_umg_spacing_combo.currentData()
                    == "spacer_fill"
                    else "auto"
                ),
                "umg_spacer_fill_coefficient": float(
                    self.auto_layout_umg_spacer_fill_spin.value()
                ),
                "grid_columns": int(self.auto_layout_grid_columns_spin.value()),
                "grid_column_span": int(
                    self.auto_layout_grid_column_span_spin.value()
                ),
                "grid_row_span": int(
                    self.auto_layout_grid_row_span_spin.value()
                ),
                "wrap": self.auto_layout_wrap_check.isChecked(),
            }
        )
        changes = {
            "name": self.name_edit.text().strip()
            or str((row or {}).get("name") or "UI Object"),
            "opacity": self.opacity_spin.value() / 100.0,
            "visible": self.visible_check.isChecked(),
            "locked": self.locked_check.isChecked(),
            "clip_content": (
                self.clip_content_check.isChecked()
                if str((row or {}).get("kind") or "") == "frame"
                else bool((row or {}).get("clip_content", False))
            ),
            "style": style,
            "content": content,
            "constraints": constraints,
            "layout": layout,
            "scroll": {
                **dict(row.get("scroll") or {}),
                "overflow": str(
                    self.scroll_overflow_combo.currentData() or "none"
                ),
                "position": str(
                    self.scroll_position_combo.currentData() or "scroll"
                ),
            },
            "mask": {
                **dict(row.get("mask") or {}),
                "enabled": self.use_as_mask_check.isChecked(),
                "inverted": self.mask_invert_check.isChecked(),
                "outline": self.mask_outline_check.isChecked(),
            },
            "accessibility": {
                "role": str(
                    self.accessibility_role_combo.currentData() or "auto"
                ),
                "label": self.accessibility_label_edit.text().strip(),
                "focus_order": int(self.focus_order_spin.value()),
            },
        }
        if self.responsive_edit_check.isChecked():
            breakpoint, orientation = self._responsive_context()
            self.responsive_override_changed.emit(
                self._selected_id(),
                breakpoint,
                orientation,
                changes,
            )
        else:
            self.properties_changed.emit(self._selected_id(), changes)

    def _emit_text_range(self, remove: bool) -> None:
        row = self._selected_row()
        if self._syncing or row is None or row["kind"] not in {"text", "button"}:
            return
        self.text_range_requested.emit(
            str(row["id"]),
            int(self.text_range_start_spin.value()),
            int(self.text_range_end_spin.value()),
            {
                "font_weight": int(self.text_range_weight_spin.value()),
                "color": self.text_range_color_edit.text().strip()
                or "#FFFFFFFF",
            },
            bool(remove),
        )

    def _emit_boolean(self, operation: str) -> None:
        row = self._selected_row()
        if self._syncing or row is None:
            return
        operand_ids = [
            item.strip()
            for item in self.boolean_operand_ids_edit.text().split(",")
            if item.strip()
        ]
        self.boolean_requested.emit(
            str(row["id"]),
            str(operation),
            {
                "operation": str(
                    self.boolean_operation_combo.currentData() or "union"
                ),
                "operand_ids": operand_ids,
            },
        )

    def _emit_remote(self, operation: str) -> None:
        row = self._selected_row()
        if self._syncing or row is None:
            return
        key = self.remote_component_key_edit.text().strip()
        payload: dict[str, Any]
        if operation == "replace":
            payload = {"component_id": key}
        elif operation == "localize":
            payload = {"name": str(row["name"])}
        else:
            payload = {"component_key": key}
        self.remote_component_requested.emit(
            str(row["id"]),
            str(operation),
            payload,
        )

    @staticmethod
    def _delivery_title(target: str) -> str:
        return {
            "asset_export": "Asset",
            "design_handoff": "Handoff",
            "review_prototype": "Prototype",
            "unreal_umg": "Unreal UMG",
        }.get(str(target), str(target))

    def _choose_image_source(self) -> None:
        if self._syncing or self._selected_row() is None:
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose UI Image",
            self.image_source_edit.text().strip(),
            "Images (*.png *.webp *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if not path:
            return
        self.image_source_edit.setText(path)
        self._emit_properties()

    def _sync_image_control_states(self) -> None:
        row = self._selected_row()
        from app.painter_ui_image_assets import IMAGE_FILL_KINDS

        is_image = (
            row is not None and row.get("kind") in IMAGE_FILL_KINDS
        )
        tiled = self.image_fit_combo.currentData() == "tile"
        sliced = self.nine_slice_check.isChecked()
        self.image_tile_scale_spin.setEnabled(is_image and tiled and not sliced)
        self.image_fit_combo.setEnabled(is_image and not sliced)
        focal_enabled = (
            is_image
            and self.image_fit_combo.currentData() == "fill"
            and not sliced
        )
        self.image_focal_x_spin.setEnabled(focal_enabled)
        self.image_focal_y_spin.setEnabled(focal_enabled)
        for spin in self.nine_slice_controls.values():
            spin.setEnabled(is_image and sliced)

    def _restore_image_original_size(self) -> None:
        if self._syncing:
            return
        row = self._selected_row()
        if row is None:
            return
        from app.painter_ui_image_renderer import normalize_ui_image_content

        content = normalize_ui_image_content(row.get("content"))
        width = int(content["original_width"])
        height = int(content["original_height"])
        if width <= 0 or height <= 0:
            return
        self.properties_changed.emit(
            str(row["id"]),
            {"width": float(width), "height": float(height)},
        )

    def _set_auto_layout_gap_auto(self, checked: bool) -> None:
        self.auto_layout_main_combo.blockSignals(True)
        try:
            target = "space_between" if checked else "start"
            if not checked and self.auto_layout_main_combo.currentData() != "space_between":
                target = str(self.auto_layout_main_combo.currentData() or "start")
            index = self.auto_layout_main_combo.findData(target)
            self.auto_layout_main_combo.setCurrentIndex(max(0, index))
        finally:
            self.auto_layout_main_combo.blockSignals(False)
        self._sync_auto_layout_control_states()
        self._emit_properties()

    def _set_auto_layout_alignment(
        self,
        row_index: int,
        column_index: int,
    ) -> None:
        positions = ("start", "center", "end")
        mode = str(self.auto_layout_mode_combo.currentData() or "horizontal")
        if mode == "vertical":
            main_alignment = positions[max(0, min(2, row_index))]
            cross_alignment = positions[max(0, min(2, column_index))]
        else:
            main_alignment = positions[max(0, min(2, column_index))]
            cross_alignment = positions[max(0, min(2, row_index))]
        self.auto_layout_main_combo.blockSignals(True)
        self.auto_layout_cross_combo.blockSignals(True)
        try:
            self.auto_layout_main_combo.setCurrentIndex(
                self.auto_layout_main_combo.findData(main_alignment)
            )
            self.auto_layout_cross_combo.setCurrentIndex(
                self.auto_layout_cross_combo.findData(cross_alignment)
            )
        finally:
            self.auto_layout_main_combo.blockSignals(False)
            self.auto_layout_cross_combo.blockSignals(False)
        self._sync_auto_layout_control_states()
        self._emit_properties()

    def _set_auto_layout_baseline(self, checked: bool) -> None:
        if not checked:
            return
        index = self.auto_layout_cross_combo.findData("baseline")
        if index < 0:
            return
        self.auto_layout_cross_combo.blockSignals(True)
        try:
            self.auto_layout_cross_combo.setCurrentIndex(index)
        finally:
            self.auto_layout_cross_combo.blockSignals(False)
        self._sync_auto_layout_control_states()
        self._emit_properties()

    def _sync_auto_layout_control_states(self) -> None:
        row = self._selected_row()
        selected_count = len(
            self._document.get("selection", {}).get("object_ids", [])
        )
        is_container = (
            row is not None
            and row.get("kind") in {"frame", "group", "button"}
        )
        active = (
            is_container
            and self.auto_layout_mode_combo.currentData()
            in {"horizontal", "vertical", "grid", "overlay"}
        )
        self.auto_layout_add_button.setEnabled(selected_count > 0 and not active)
        self.auto_layout_add_button.setVisible(not active)
        self.auto_layout_remove_button.setEnabled(active)
        self.auto_layout_remove_button.setVisible(active)
        self.auto_layout_mode_combo.setEnabled(is_container)
        mode = str(self.auto_layout_mode_combo.currentData() or "none")
        self.auto_layout_horizontal_button.setChecked(mode == "horizontal")
        self.auto_layout_vertical_button.setChecked(mode == "vertical")
        self.auto_layout_grid_button.setChecked(mode == "grid")
        self.auto_layout_overlay_button.setChecked(mode == "overlay")
        self.auto_layout_flow_control.setEnabled(is_container)
        is_linear_panel = bool(
            is_container and mode in {"horizontal", "vertical"}
        )
        is_overlay_panel = bool(is_container and mode == "overlay")
        if not is_linear_panel and (
            self.auto_layout_umg_spacing_combo.currentData() != "padding"
        ):
            self.auto_layout_umg_spacing_combo.blockSignals(True)
            try:
                self.auto_layout_umg_spacing_combo.setCurrentIndex(
                    self.auto_layout_umg_spacing_combo.findData("padding")
                )
            finally:
                self.auto_layout_umg_spacing_combo.blockSignals(False)
        self.auto_layout_umg_spacing_control.setVisible(
            is_linear_panel or is_overlay_panel
        )
        self.auto_layout_umg_spacing_combo.setEnabled(is_linear_panel)
        spacer_fill_selected = (
            self.auto_layout_umg_spacing_combo.currentData()
            == "spacer_fill"
        )
        self.auto_layout_umg_spacer_fill_spin.setVisible(
            is_linear_panel and spacer_fill_selected
        )
        self.auto_layout_umg_spacer_fill_spin.setEnabled(
            is_linear_panel and spacer_fill_selected
        )
        self.auto_layout_umg_spacing_hint.setText(
            "Overlay는 UOverlaySlot Padding으로 고정됩니다. "
            "상위 크기에 반응하는 비례 배치는 Canvas 앵커나 "
            "ScaleBox를 사용하세요."
            if is_overlay_panel
            else "상위 크기가 바뀌면 남은 공간을 Weight 비율로 "
            "나누는 native USpacer입니다."
            if spacer_fill_selected
            else "고정 폭/높이의 독립 native USpacer를 생성합니다."
            if self.auto_layout_umg_spacing_combo.currentData()
            == "spacer_auto"
            else "UMG 슬롯의 고정 Padding입니다. 상위 크기의 남는 "
            "공간을 비례 분배하지 않습니다."
        )
        parent = None
        if row is not None and row.get("parent_id"):
            parent = next(
                (
                    candidate
                    for candidate in self._document.get("objects", [])
                    if str(candidate.get("id") or "")
                    == str(row.get("parent_id") or "")
                ),
                None,
            )
        parent_layout = normalize_ui_auto_layout(
            parent.get("layout") if parent is not None else None
        )
        is_flow_layout = active and mode in {
            "horizontal",
            "vertical",
            "grid",
        }
        is_grid = active and mode == "grid"
        is_grid_child = (
            row is not None
            and parent is not None
            and parent_layout["mode"] == "grid"
            and normalize_ui_auto_layout(row.get("layout"))["positioning"]
            != "absolute"
        )
        is_horizontal = active and mode == "horizontal"
        if active and not is_horizontal and self.auto_layout_wrap_check.isChecked():
            self.auto_layout_wrap_check.blockSignals(True)
            self.auto_layout_wrap_check.setChecked(False)
            self.auto_layout_wrap_check.blockSignals(False)
        is_wrapped = is_horizontal and self.auto_layout_wrap_check.isChecked()
        self.auto_layout_wrap_check.setEnabled(is_horizontal)
        self.auto_layout_wrap_check.setVisible(is_horizontal)
        self.auto_layout_cross_gap_spin.setEnabled(is_wrapped or is_grid)
        self.auto_layout_cross_gap_spin.setVisible(is_wrapped or is_grid)
        self.auto_layout_grid_controls.setVisible(is_grid or is_grid_child)
        self.auto_layout_grid_columns_spin.setVisible(is_grid)
        self.auto_layout_grid_columns_spin.setEnabled(is_grid)
        self.auto_layout_grid_column_span_spin.setVisible(is_grid_child)
        self.auto_layout_grid_column_span_spin.setEnabled(is_grid_child)
        self.auto_layout_grid_row_span_spin.setVisible(is_grid_child)
        self.auto_layout_grid_row_span_spin.setEnabled(is_grid_child)
        gap_auto = self.auto_layout_main_combo.currentData() == "space_between"
        self.auto_layout_gap_auto_button.setChecked(gap_auto)
        self.auto_layout_gap_auto_button.setEnabled(
            is_flow_layout and not is_wrapped and not is_grid
        )
        self.auto_layout_gap_spin.setEnabled(is_flow_layout and not gap_auto)
        positions = {"start": 0, "center": 1, "end": 2}
        main = str(self.auto_layout_main_combo.currentData() or "start")
        cross = str(self.auto_layout_cross_combo.currentData() or "start")
        if cross == "baseline":
            selected_alignment = (-1, -1)
        elif mode == "vertical":
            selected_alignment = (positions.get(main, 0), positions.get(cross, 0))
        else:
            selected_alignment = (positions.get(cross, 0), positions.get(main, 0))
        for position, button in self.auto_layout_alignment_buttons.items():
            button.setChecked(position == selected_alignment)
            button.setEnabled(is_flow_layout)
        baseline_available = active and mode == "horizontal"
        self.auto_layout_baseline_button.setVisible(mode == "horizontal")
        self.auto_layout_baseline_button.setEnabled(baseline_available)
        self.auto_layout_baseline_button.setChecked(
            baseline_available and cross == "baseline"
        )
        self.auto_layout_width_sizing_combo.setEnabled(row is not None)
        self.auto_layout_height_sizing_combo.setEnabled(row is not None)
        self.auto_layout_width_sizing_control.setEnabled(row is not None)
        self.auto_layout_height_sizing_control.setEnabled(row is not None)
        can_hug = is_flow_layout
        can_fill = (
            parent is not None
            and parent_layout["mode"] in {"horizontal", "vertical", "grid"}
            and normalize_ui_auto_layout(row.get("layout"))["positioning"]
            != "absolute"
        )
        for sizing_control in (
            self.auto_layout_width_sizing_control,
            self.auto_layout_height_sizing_control,
        ):
            sizing_control.set_option_enabled("fixed", row is not None)
            sizing_control.set_option_enabled("hug", can_hug)
            sizing_control.set_option_enabled("fill", can_fill)
        for widget in (
            self.auto_layout_main_combo,
            self.auto_layout_cross_combo,
            *self.auto_layout_padding_controls.values(),
        ):
            widget.setEnabled(is_flow_layout)
        self.auto_layout_positioning_combo.setEnabled(
            row is not None and bool(row.get("parent_id"))
        )

    def _set_auto_layout_sizing(
        self,
        combo: QComboBox,
        value: str,
    ) -> None:
        index = combo.findData(str(value))
        if index >= 0 and combo.currentIndex() != index:
            combo.setCurrentIndex(index)

    def _sync_object_layout_status(
        self,
        row: Mapping[str, Any] | None,
    ) -> None:
        if row is None:
            self.auto_layout_status_label.setText("Select an object")
            self.auto_layout_status_label.setToolTip("")
            return
        from app.painter_ui_layout_diagnostics import diagnose_ui_layout

        object_id = str(row["id"])
        diagnostics = [
            item
            for item in diagnose_ui_layout(
                self._document,
                normalize=False,
            )["diagnostics"]
            if item["owner_id"] == object_id
            or item["related_id"] == object_id
        ]
        errors = sum(item["severity"] == "error" for item in diagnostics)
        warnings = sum(item["severity"] == "warning" for item in diagnostics)
        if errors:
            text = f"{errors} layout error"
            color = "#F0A0A0"
        elif warnings:
            text = f"{warnings} layout warning"
            color = "#E8C47A"
        else:
            text = "Layout ready"
            color = "#8ECAA9"
        recovery = {
            "layout_hug_fill_cycle": (
                "Use Fixed on the parent axis, or Hug/Fixed on the Fill child."
            ),
            "constraint_min_exceeds_max": (
                "Raise Max or lower Min so the range is valid."
            ),
            "wrap_ignored_on_hug_axis": (
                "Use Fixed sizing on the wrapped main axis."
            ),
            "auto_layout_no_content_space": (
                "Reduce padding or increase the container size."
            ),
            "auto_layout_fixed_overflow": (
                "Enable Wrap, reduce Gap, or use Fill/Hug sizing."
            ),
        }
        tooltip_rows = []
        for item in diagnostics:
            fix = recovery.get(item["code"], "")
            suffix = f" Recovery: {fix}" if fix else ""
            tooltip_rows.append(
                f"{item['owner_id']}: {item['message']}{suffix}"
            )
        self.auto_layout_status_label.setText(text)
        self.auto_layout_status_label.setToolTip("\n".join(tooltip_rows))
        self.auto_layout_status_label.setStyleSheet(f"color: {color};")

    def _sync_stress_preview_controls(self) -> None:
        report = dict(getattr(self, "_stress_preview_report", {}) or {})
        active = bool(report.get("active", False))
        preset = str(report.get("preset") or "none")
        was_syncing = bool(self._syncing)
        self._syncing = True
        try:
            index = self.stress_preview_combo.findData(
                preset if active else "none"
            )
            self.stress_preview_combo.setCurrentIndex(max(0, index))
        finally:
            self._syncing = was_syncing
        self.stress_preview_clear_button.setEnabled(active)
        if active:
            target = str(report.get("target_name") or "Selection")
            count = int(report.get("affected_count") or 0)
            self.stress_preview_status_label.setText(
                painter_text(
                    "Preview only - document is unchanged"
                )
                + f" · {target} · {count}"
            )
            self.stress_preview_status_label.setToolTip(
                str(report.get("message") or "")
            )
        else:
            self.stress_preview_status_label.setText(
                painter_text("Preview only - document is unchanged")
            )
            self.stress_preview_status_label.setToolTip("")

    def _emit_stress_preview(self, _index: int = -1) -> None:
        if self._syncing:
            return
        object_id = self._selected_id()
        if not object_id:
            return
        preset = str(self.stress_preview_combo.currentData() or "none")
        self.stress_preview_requested.emit(object_id, preset)

    def _clear_stress_preview(self) -> None:
        index = self.stress_preview_combo.findData("none")
        if index >= 0:
            self.stress_preview_combo.setCurrentIndex(index)

    def _emit_duplicate(self) -> None:
        if self._selected_id():
            self.duplicate_requested.emit(self._selected_id())

    def _emit_delete(self) -> None:
        if self._selected_id():
            self.delete_requested.emit(self._selected_id())

    def _emit_arrange(self, command: str) -> None:
        if self._selected_id():
            self.arrange_requested.emit(self._selected_id(), str(command))

    def _selected_ids(self) -> list[str]:
        return [
            str(item.data(Qt.ItemDataRole.UserRole) or "")
            for item in self.layer_list.selectedItems()
            if str(item.data(Qt.ItemDataRole.UserRole) or "")
        ]

    def _emit_group(self) -> None:
        selected_ids = self._selected_ids()
        if len(selected_ids) >= 2:
            self.group_requested.emit(selected_ids)

    def _emit_ungroup(self) -> None:
        if self._selected_id():
            self.ungroup_requested.emit(self._selected_id())

    def _emit_reorder(self, command: str) -> None:
        selected_ids = self._selected_ids()
        if selected_ids:
            self.reorder_requested.emit(selected_ids, str(command))


__all__ = ["PainterUIInspector"]
