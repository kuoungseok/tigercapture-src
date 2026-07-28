"""Inspector controls for image-layer Puppet Mesh deformation."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.puppet_mesh import layer_puppet_mesh
from app.motion_designer.schema import MotionLayer


class PuppetPanel(QWidget):
    mesh_create_requested = Signal(str, int, int, bool)
    mesh_settings_changed = Signal(str, object)
    pin_add_requested = Signal(str, str)
    pin_changed = Signal(str, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layer: MotionLayer | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.status = QLabel("Select an image layer", self)
        layout.addWidget(self.status)
        grid_form = QFormLayout()
        self.columns = QSpinBox(self)
        self.columns.setRange(2, 128)
        self.columns.setValue(8)
        self.rows = QSpinBox(self)
        self.rows.setRange(2, 128)
        self.rows.setValue(8)
        grid_form.addRow("Columns", self.columns)
        grid_form.addRow("Rows", self.rows)
        self.follow_alpha = QCheckBox("Follow source alpha", self)
        self.follow_alpha.setChecked(True)
        grid_form.addRow("Boundary", self.follow_alpha)
        self.tear_repair = QCheckBox("Repair local tears", self)
        self.tear_repair.setChecked(True)
        grid_form.addRow("Safety", self.tear_repair)
        self.max_edge_stretch = QDoubleSpinBox(self)
        self.max_edge_stretch.setRange(1.01, 100.0)
        self.max_edge_stretch.setValue(6.0)
        self.max_edge_stretch.setSingleStep(0.25)
        self.max_edge_stretch.setDecimals(2)
        grid_form.addRow("Max Edge Stretch", self.max_edge_stretch)
        layout.addLayout(grid_form)
        self.create_mesh = QPushButton("Create Mesh", self)
        layout.addWidget(self.create_mesh)
        pin_row = QHBoxLayout()
        self.pin_kind = QComboBox(self)
        self.pin_kind.addItems(["position", "bend", "starch", "overlap"])
        self.add_pin = QPushButton("Add Pin", self)
        pin_row.addWidget(self.pin_kind, 1)
        pin_row.addWidget(self.add_pin)
        layout.addLayout(pin_row)
        self.pins = QListWidget(self)
        layout.addWidget(self.pins, 1)
        pin_form = QFormLayout()
        self.radius = QDoubleSpinBox(self)
        self.radius.setRange(0.001, 2.0)
        self.radius.setSingleStep(0.05)
        self.radius.setDecimals(3)
        self.strength = QDoubleSpinBox(self)
        self.strength.setRange(0.0, 2.0)
        self.strength.setSingleStep(0.1)
        self.rotation = QDoubleSpinBox(self)
        self.rotation.setRange(-720.0, 720.0)
        self.rotation.setSuffix(" deg")
        pin_form.addRow("Radius", self.radius)
        pin_form.addRow("Strength", self.strength)
        pin_form.addRow("Bend", self.rotation)
        layout.addLayout(pin_form)
        self.create_mesh.clicked.connect(self._create)
        self.add_pin.clicked.connect(self._add)
        self.pins.currentItemChanged.connect(self._select_pin)
        self.tear_repair.toggled.connect(self._emit_mesh_settings)
        self.max_edge_stretch.editingFinished.connect(self._emit_mesh_settings)
        for control in (self.radius, self.strength, self.rotation):
            control.editingFinished.connect(self._emit_pin)
        self._set_enabled(False)

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._layer = layer if layer is not None and layer.layer_type == "image" else None
        self._loading = True
        self.pins.clear()
        mesh = layer_puppet_mesh(self._layer) if self._layer is not None else None
        if self._layer is None:
            self.status.setText("Select an image layer")
            self._set_enabled(False)
        else:
            self._set_enabled(True)
            if mesh is None:
                self.status.setText("No Puppet Mesh")
            else:
                repair = mesh.metadata.get("tear_repair")
                repair = repair if isinstance(repair, dict) else {}
                self.tear_repair.setChecked(bool(repair.get("enabled", True)))
                self.max_edge_stretch.setValue(
                    float(repair.get("max_edge_stretch", 6.0) or 6.0)
                )
                self.status.setText(
                    f"{len(mesh.vertices)} vertices / {len(mesh.triangles)} triangles",
                )
                for pin in mesh.pins:
                    item = QListWidgetItem(f"{pin.name} / {pin.kind}", self.pins)
                    item.setData(32, pin.id)
                if self.pins.count():
                    self.pins.setCurrentRow(0)
        self._loading = False
        self._select_pin(self.pins.currentItem(), None)

    def select_pin(self, layer_id: str, pin_id: str) -> None:
        if self._layer is None or self._layer.id != str(layer_id):
            return
        for index in range(self.pins.count()):
            item = self.pins.item(index)
            if str(item.data(32) or "") == str(pin_id):
                self.pins.setCurrentItem(item)
                break

    def _set_enabled(self, enabled: bool) -> None:
        for control in (
            self.columns,
            self.rows,
            self.follow_alpha,
            self.tear_repair,
            self.max_edge_stretch,
            self.create_mesh,
            self.pin_kind,
            self.add_pin,
        ):
            control.setEnabled(bool(enabled))

    def _create(self) -> None:
        if self._layer is not None:
            self.mesh_create_requested.emit(
                self._layer.id,
                self.columns.value(),
                self.rows.value(),
                self.follow_alpha.isChecked(),
            )

    def _add(self) -> None:
        if self._layer is not None:
            self.pin_add_requested.emit(
                self._layer.id,
                self.pin_kind.currentText(),
            )

    def _emit_mesh_settings(self, *_args) -> None:
        if self._loading or self._layer is None:
            return
        self.mesh_settings_changed.emit(
            self._layer.id,
            {
                "enabled": self.tear_repair.isChecked(),
                "max_edge_stretch": self.max_edge_stretch.value(),
            },
        )

    def _select_pin(self, current, _previous) -> None:
        mesh = layer_puppet_mesh(self._layer) if self._layer is not None else None
        pin_id = str(current.data(32) or "") if current is not None else ""
        pin = next(
            (row for row in mesh.pins if row.id == pin_id),
            None,
        ) if mesh is not None else None
        self._loading = True
        for control in (self.radius, self.strength, self.rotation):
            control.setEnabled(pin is not None)
        if pin is not None:
            self.radius.setValue(pin.radius)
            self.strength.setValue(pin.strength)
            self.rotation.setValue(float(pin.rotation.default or 0.0))
        self._loading = False

    def _emit_pin(self) -> None:
        current = self.pins.currentItem()
        if self._loading or self._layer is None or current is None:
            return
        self.pin_changed.emit(
            self._layer.id,
            str(current.data(32) or ""),
            {
                "radius": self.radius.value(),
                "strength": self.strength.value(),
                "rotation": self.rotation.value(),
            },
        )


__all__ = ["PuppetPanel"]
