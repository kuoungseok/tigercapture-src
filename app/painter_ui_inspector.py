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

from app.painter_ui_document import normalize_ui_document


class PainterUIInspector(QWidget):
    artboard_selected = Signal(str)
    object_selected = Signal(str)
    selection_changed = Signal(object, str)
    geometry_changed = Signal(str, object)
    properties_changed = Signal(str, object)
    duplicate_requested = Signal(str)
    delete_requested = Signal(str)
    arrange_requested = Signal(str, str)

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

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self._tabs = tabs
        root.addWidget(tabs, 1)

        layers_page = QWidget()
        layers_layout = QVBoxLayout(layers_page)
        layers_layout.setContentsMargins(4, 4, 4, 4)
        self.layer_list = QListWidget()
        self.layer_list.setObjectName("PaintLayerList")
        self.layer_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.layer_list.itemSelectionChanged.connect(self._on_selection_changed)
        layers_layout.addWidget(self.layer_list, 1)
        actions = QHBoxLayout()
        duplicate = QPushButton("Duplicate")
        delete = QPushButton("Delete")
        duplicate.clicked.connect(self._emit_duplicate)
        delete.clicked.connect(self._emit_delete)
        actions.addWidget(duplicate)
        actions.addWidget(delete)
        layers_layout.addLayout(actions)
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
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.editingFinished.connect(self._emit_properties)
        form.addRow("Opacity", self.opacity_spin)
        self.fill_edit = QLineEdit()
        self.fill_edit.setPlaceholderText("#RRGGBB")
        self.fill_edit.editingFinished.connect(self._emit_properties)
        form.addRow("Fill", self.fill_edit)
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
        rows = sorted(
            (
                row
                for row in self._document["objects"]
                if row["artboard_id"] == active
            ),
            key=lambda row: row["z_index"],
            reverse=True,
        )
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
            for row in rows:
                prefix = "  " if row["parent_id"] else ""
                state = "" if row["visible"] else "  [hidden]"
                item = QListWidgetItem(f"{prefix}{row['name']}  [{row['kind']}]{state}")
                item.setData(Qt.ItemDataRole.UserRole, row["id"])
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
            self.visible_check,
            self.locked_check,
            *self.geometry_controls.values(),
        ):
            widget.setEnabled(enabled)
        if row is None:
            self.name_edit.clear()
            self.kind_label.setText("-")
            return
        self.name_edit.setText(str(row["name"]))
        self.kind_label.setText(str(row["kind"]).title())
        for key, spin in self.geometry_controls.items():
            spin.setValue(float(row[key]))
        self.opacity_spin.setValue(int(round(float(row["opacity"]) * 100.0)))
        self.fill_edit.setText(str(row["style"].get("fill") or ""))
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

    def _emit_geometry(self) -> None:
        if self._syncing or not self._selected_id():
            return
        self.geometry_changed.emit(
            self._selected_id(),
            {
                key: float(spin.value())
                for key, spin in self.geometry_controls.items()
            },
        )

    def _emit_properties(self) -> None:
        if self._syncing or not self._selected_id():
            return
        row = self._selected_row()
        style = dict((row or {}).get("style") or {})
        fill = self.fill_edit.text().strip()
        if fill:
            style["fill"] = fill
        self.properties_changed.emit(
            self._selected_id(),
            {
                "name": self.name_edit.text().strip() or str((row or {}).get("name") or "UI Object"),
                "opacity": self.opacity_spin.value() / 100.0,
                "visible": self.visible_check.isChecked(),
                "locked": self.locked_check.isChecked(),
                "style": style,
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


__all__ = ["PainterUIInspector"]
