"""Layers and Inspect panel for Painter's UI Design workspace."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
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
from app.painter_ui_document import normalize_ui_document


class PainterUILayerList(QListWidget):
    hierarchy_drop_requested = Signal(object, str, str)

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
        target = self.itemAt(point)
        if target is None:
            self.hierarchy_drop_requested.emit(selected_ids, "", "root")
            event.acceptProposedAction()
            return
        target_id = str(target.data(Qt.ItemDataRole.UserRole) or "")
        if not target_id or target_id in selected_ids:
            event.ignore()
            return
        rect = self.visualItemRect(target)
        relative_y = point.y() - rect.top()
        if relative_y < rect.height() * 0.25:
            placement = "before"
        elif relative_y > rect.height() * 0.75:
            placement = "after"
        elif str(target.data(int(Qt.ItemDataRole.UserRole) + 1) or "") == "group":
            placement = "inside"
        else:
            placement = "after"
        self.hierarchy_drop_requested.emit(selected_ids, target_id, placement)
        event.acceptProposedAction()


class PainterUIInspector(QWidget):
    artboard_selected = Signal(str)
    artboard_add_requested = Signal(str, int, int, str)
    object_selected = Signal(str)
    selection_changed = Signal(object, str)
    geometry_changed = Signal(str, object)
    properties_changed = Signal(str, object)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    arrange_requested = Signal(str, str)
    group_requested = Signal(object)
    ungroup_requested = Signal(str)
    reorder_requested = Signal(object, str)
    hierarchy_drop_requested = Signal(object, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(None)
        self._syncing = False
        self.setObjectName("PainterUIInspector")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        title = QLabel("UI DESIGN")
        title.setObjectName("PaintSectionTitle")
        root.addWidget(title)
        self.artboard_combo = QComboBox()
        self.artboard_combo.setToolTip("Active UI artboard")
        self.artboard_combo.currentIndexChanged.connect(self._on_artboard_changed)
        root.addWidget(self.artboard_combo)
        artboard_add_row = QHBoxLayout()
        self.artboard_preset_combo = QComboBox()
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
        add_artboard = QPushButton("+")
        add_artboard.setFixedWidth(30)
        add_artboard.setToolTip("Add artboard from preset")
        add_artboard.setAccessibleName("Add artboard")
        add_artboard.clicked.connect(self._emit_add_artboard)
        artboard_add_row.addWidget(self.artboard_preset_combo, 1)
        artboard_add_row.addWidget(add_artboard)
        root.addLayout(artboard_add_row)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self._tabs = tabs
        root.addWidget(tabs, 1)

        layers_page = QWidget()
        layers_layout = QVBoxLayout(layers_page)
        layers_layout.setContentsMargins(4, 4, 4, 4)
        self.layer_list = PainterUILayerList()
        self.layer_list.setObjectName("PaintLayerList")
        self.layer_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.layer_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.layer_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.layer_list.setDragEnabled(True)
        self.layer_list.setAcceptDrops(True)
        self.layer_list.setDropIndicatorShown(True)
        self.layer_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.layer_list.hierarchy_drop_requested.connect(
            self.hierarchy_drop_requested
        )
        layers_layout.addWidget(self.layer_list, 1)
        actions = QHBoxLayout()
        duplicate = QPushButton("Duplicate")
        delete = QPushButton("Delete")
        duplicate.clicked.connect(self._emit_duplicate)
        delete.clicked.connect(self._emit_delete)
        actions.addWidget(duplicate)
        actions.addWidget(delete)
        layers_layout.addLayout(actions)
        hierarchy_actions = QHBoxLayout()
        group = QPushButton("Group")
        ungroup = QPushButton("Ungroup")
        backward = QPushButton("Down")
        forward = QPushButton("Up")
        group.clicked.connect(self._emit_group)
        ungroup.clicked.connect(self._emit_ungroup)
        backward.clicked.connect(lambda: self._emit_reorder("backward"))
        forward.clicked.connect(lambda: self._emit_reorder("forward"))
        hierarchy_actions.addWidget(group)
        hierarchy_actions.addWidget(ungroup)
        hierarchy_actions.addWidget(backward)
        hierarchy_actions.addWidget(forward)
        layers_layout.addLayout(hierarchy_actions)
        tabs.addTab(layers_page, "Layers")

        inspect_page = QWidget()
        inspect_layout = QVBoxLayout(inspect_page)
        inspect_layout.setContentsMargins(6, 6, 6, 6)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Name", self.name_edit)
        self.kind_label = QLabel("-")
        form.addRow("Type", self.kind_label)
        self.geometry_controls: dict[str, QDoubleSpinBox] = {}
        for key in ("x", "y", "width", "height", "rotation"):
            spin = QDoubleSpinBox()
            spin.setRange(
                -180.0 if key == "rotation" else 0.0,
                180.0 if key == "rotation" else 100000.0,
            )
            spin.setDecimals(1)
            spin.editingFinished.connect(self._emit_geometry)
            self.geometry_controls[key] = spin
            form.addRow(key.upper(), spin)
        pivot_row = QFrame()
        pivot_layout = QHBoxLayout(pivot_row)
        pivot_layout.setContentsMargins(0, 0, 0, 0)
        pivot_layout.setSpacing(3)
        self.pivot_x_spin = QDoubleSpinBox()
        self.pivot_y_spin = QDoubleSpinBox()
        for label, spin in (("X ", self.pivot_x_spin), ("Y ", self.pivot_y_spin)):
            spin.setRange(0.0, 1.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.setPrefix(label)
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
                spin = QDoubleSpinBox()
                spin.setRange(0.0, 100000.0)
                spin.setDecimals(1)
                spin.setPrefix(prefix)
                spin.setSuffix(" px")
                spin.editingFinished.connect(self._emit_properties)
                self.size_limit_controls[key] = spin
                row_layout.addWidget(spin)
            form.addRow(label, row_widget)
        self.aspect_lock_check = QCheckBox("Lock aspect ratio")
        self.aspect_lock_check.toggled.connect(self._emit_properties)
        form.addRow("Ratio", self.aspect_lock_check)
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Opacity", self.opacity_spin)
        self.fill_edit = QLineEdit()
        self.fill_edit.setPlaceholderText("#RRGGBB")
        self.fill_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Fill", self.fill_edit)
        self.stroke_edit = QLineEdit()
        self.stroke_edit.setPlaceholderText("#RRGGBB")
        self.stroke_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Stroke", self.stroke_edit)
        self.stroke_width_spin = QDoubleSpinBox()
        self.stroke_width_spin.setRange(0.0, 64.0)
        self.stroke_width_spin.setDecimals(1)
        self.stroke_width_spin.setSuffix(" px")
        self.stroke_width_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Stroke Width", self.stroke_width_spin)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.0, 4096.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setSuffix(" px")
        self.radius_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Radius", self.radius_spin)
        self.shadow_color_edit = QLineEdit()
        self.shadow_color_edit.setPlaceholderText("#00000066")
        self.shadow_color_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Shadow", self.shadow_color_edit)
        shadow_metrics = QFrame()
        shadow_metrics_layout = QHBoxLayout(shadow_metrics)
        shadow_metrics_layout.setContentsMargins(0, 0, 0, 0)
        shadow_metrics_layout.setSpacing(3)
        self.shadow_y_spin = QDoubleSpinBox()
        self.shadow_y_spin.setRange(-512.0, 512.0)
        self.shadow_y_spin.setPrefix("Y ")
        self.shadow_y_spin.editingFinished.connect(self._emit_properties)
        self.shadow_blur_spin = QDoubleSpinBox()
        self.shadow_blur_spin.setRange(0.0, 512.0)
        self.shadow_blur_spin.setPrefix("Blur ")
        self.shadow_blur_spin.editingFinished.connect(self._emit_properties)
        shadow_metrics_layout.addWidget(self.shadow_y_spin)
        shadow_metrics_layout.addWidget(self.shadow_blur_spin)
        form.addRow("", shadow_metrics)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("Text")
        self.text_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Text", self.text_edit)
        text_metrics = QFrame()
        text_metrics_layout = QHBoxLayout(text_metrics)
        text_metrics_layout.setContentsMargins(0, 0, 0, 0)
        text_metrics_layout.setSpacing(3)
        self.font_size_spin = QDoubleSpinBox()
        self.font_size_spin.setRange(1.0, 512.0)
        self.font_size_spin.setSuffix(" px")
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
        self.line_height_spin = QDoubleSpinBox()
        self.line_height_spin.setRange(0.5, 4.0)
        self.line_height_spin.setDecimals(2)
        self.line_height_spin.setSingleStep(0.05)
        self.line_height_spin.setPrefix("Line ")
        self.line_height_spin.editingFinished.connect(self._emit_properties)
        text_layout_row.addWidget(self.text_align_combo)
        text_layout_row.addWidget(self.line_height_spin)
        form.addRow("Text Layout", text_layout)
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
        inspect_layout.addLayout(form)
        inspect_layout.addStretch(1)
        tabs.addTab(inspect_page, "Inspect")

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        self._document = normalize_ui_document(value)
        selected = self._document["selection"]["object_id"]
        selected_ids = set(self._document["selection"]["object_ids"])
        active = self._document["active_artboard_id"]
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
        self._syncing = True
        try:
            self.artboard_combo.clear()
            for artboard in self._document["artboards"]:
                self.artboard_combo.addItem(
                    f"{artboard['name']}  {artboard['width']} x {artboard['height']}",
                    artboard["id"],
                )
                if artboard["id"] == active:
                    self.artboard_combo.setCurrentIndex(
                        self.artboard_combo.count() - 1
                    )
            self.layer_list.clear()
            row_by_id = {row["id"]: row for row in rows}
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
                prefix = "  " * depth
                state = "" if row["visible"] else "  [hidden]"
                item = QListWidgetItem(f"{prefix}{row['name']}  [{row['kind']}]{state}")
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
                item.setData(int(Qt.ItemDataRole.UserRole) + 1, row["kind"])
                self.layer_list.addItem(item)
                if row["id"] in selected_ids:
                    item.setSelected(True)
                if row["id"] == selected:
                    self.layer_list.setCurrentItem(item)
            self._sync_selected_fields()
        finally:
            self._syncing = False

    def _selected_id(self) -> str:
        return str(self._document["selection"]["object_id"] or "")

    def _selected_row(self) -> dict[str, Any] | None:
        selected = self._selected_id()
        return next(
            (row for row in self._document["objects"] if row["id"] == selected),
            None,
        )

    def _sync_selected_fields(self) -> None:
        row = self._selected_row()
        enabled = row is not None
        for widget in (
            self.name_edit,
            self.opacity_spin,
            self.fill_edit,
            self.stroke_edit,
            self.stroke_width_spin,
            self.radius_spin,
            self.shadow_color_edit,
            self.shadow_y_spin,
            self.shadow_blur_spin,
            self.text_edit,
            self.font_size_spin,
            self.font_weight_combo,
            self.text_align_combo,
            self.line_height_spin,
            self.pivot_x_spin,
            self.pivot_y_spin,
            self.horizontal_constraint_combo,
            self.vertical_constraint_combo,
            self.aspect_lock_check,
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
            self.shadow_color_edit.clear()
            self.text_edit.clear()
            return
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
        shadow = style.get("shadow")
        shadow = shadow if isinstance(shadow, Mapping) else {}
        self.shadow_color_edit.setText(str(shadow.get("color") or ""))
        self.shadow_y_spin.setValue(float(shadow.get("y") or 0.0))
        self.shadow_blur_spin.setValue(float(shadow.get("blur") or 0.0))
        is_text = row["kind"] in {"text", "button"}
        for widget in (
            self.text_edit,
            self.font_size_spin,
            self.font_weight_combo,
            self.text_align_combo,
            self.line_height_spin,
        ):
            widget.setEnabled(is_text)
        self.text_edit.setText(str(row["content"].get("text") or ""))
        self.font_size_spin.setValue(float(style.get("font_size") or 14.0))
        weight = int(style.get("font_weight") or 400)
        weight_index = self.font_weight_combo.findData(weight)
        self.font_weight_combo.setCurrentIndex(max(0, weight_index))
        align_index = self.text_align_combo.findData(
            str(style.get("text_align") or "left")
        )
        self.text_align_combo.setCurrentIndex(max(0, align_index))
        self.line_height_spin.setValue(float(style.get("line_height") or 1.2))
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
        self.geometry_changed.emit(
            self._selected_id(),
            {
                **{
                    key: float(spin.value())
                    for key, spin in self.geometry_controls.items()
                },
                "width": width,
                "height": height,
            },
        )

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
        shadow_color = self.shadow_color_edit.text().strip()
        shadow_blur = float(self.shadow_blur_spin.value())
        if shadow_color or shadow_blur > 0.0:
            style["shadow"] = {
                "x": 0.0,
                "y": float(self.shadow_y_spin.value()),
                "blur": shadow_blur,
                "spread": 0.0,
                "color": shadow_color or "#00000066",
            }
        else:
            style.pop("shadow", None)
        content = dict(row.get("content") or {})
        if row.get("kind") in {"text", "button"}:
            content["text"] = self.text_edit.text()
            style["font_size"] = float(self.font_size_spin.value())
            style["font_weight"] = int(
                self.font_weight_combo.currentData() or 400
            )
            style["text_align"] = str(
                self.text_align_combo.currentData() or "left"
            )
            style["line_height"] = float(self.line_height_spin.value())
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
        self.properties_changed.emit(
            self._selected_id(),
            {
                "name": self.name_edit.text().strip() or str((row or {}).get("name") or "UI Object"),
                "opacity": self.opacity_spin.value() / 100.0,
                "visible": self.visible_check.isChecked(),
                "locked": self.locked_check.isChecked(),
                "style": style,
                "content": content,
                "constraints": constraints,
            },
        )

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
