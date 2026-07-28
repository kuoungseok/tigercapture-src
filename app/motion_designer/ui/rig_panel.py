"""Inspector for the selected Motion Designer cutout rig bone."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.rigging import MotionRig, rig_for_layer
from app.motion_designer.schema import MotionComposition, MotionLayer


class RigPanel(QWidget):
    bone_changed = Signal(str, str, object)
    bone_selected = Signal(str, str)
    mirror_requested = Signal(str, str)
    ik_lock_requested = Signal(str, str)
    constraint_enabled = Signal(str, str, bool)
    constraint_bake_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rig: MotionRig | None = None
        self._bone_id = ""
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.title = QLabel("No rig on selected layer", self)
        layout.addWidget(self.title)
        self.bones = QListWidget(self)
        self.bones.setToolTip("Select a bone to edit its rest pose and limits")
        layout.addWidget(self.bones, 1)
        form = QFormLayout()
        self.x = self._number(-100000.0, 100000.0, 1.0)
        self.y = self._number(-100000.0, 100000.0, 1.0)
        self.rotation_min = self._number(-360.0, 360.0, 1.0)
        self.rotation_max = self._number(-360.0, 360.0, 1.0)
        self.translation_locked = QCheckBox("Lock translation", self)
        self.rotation_locked = QCheckBox("Lock rotation", self)
        self.scale_locked = QCheckBox("Lock scale", self)
        form.addRow("Rest X", self.x)
        form.addRow("Rest Y", self.y)
        form.addRow("Rotation min", self.rotation_min)
        form.addRow("Rotation max", self.rotation_max)
        form.addRow("", self.translation_locked)
        form.addRow("", self.rotation_locked)
        form.addRow("", self.scale_locked)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.mirror_button = QPushButton("Mirror Bone", self)
        self.mirror_button.setToolTip(
            "Copy the selected left/right bone pose and limits across the rig center",
        )
        actions.addWidget(self.mirror_button)
        layout.addLayout(actions)
        layout.addWidget(QLabel("IK Constraints", self))
        self.constraints = QListWidget(self)
        self.constraints.setMaximumHeight(96)
        layout.addWidget(self.constraints)
        ik_actions = QHBoxLayout()
        self.ik_lock_button = QPushButton("Lock End", self)
        self.fk_ik_button = QPushButton("FK / IK", self)
        self.bake_button = QPushButton("Bake IK", self)
        self.ik_lock_button.setToolTip(
            "Create a persistent IK target from the selected hand or foot chain",
        )
        self.fk_ik_button.setToolTip(
            "Enable or disable the selected IK constraint without deleting it",
        )
        self.bake_button.setToolTip(
            "Bake the selected IK constraint into ordinary FK rotation keys",
        )
        for button in (self.ik_lock_button, self.fk_ik_button, self.bake_button):
            ik_actions.addWidget(button)
        layout.addLayout(ik_actions)
        self.bones.currentItemChanged.connect(self._select_item)
        self.mirror_button.clicked.connect(self._request_mirror)
        self.ik_lock_button.clicked.connect(self._request_ik_lock)
        self.fk_ik_button.clicked.connect(self._toggle_constraint)
        self.bake_button.clicked.connect(self._request_constraint_bake)
        for control in (self.x, self.y, self.rotation_min, self.rotation_max):
            control.editingFinished.connect(self._emit_changes)
        for control in (
            self.translation_locked,
            self.rotation_locked,
            self.scale_locked,
        ):
            control.toggled.connect(self._emit_changes)
        self._set_controls_enabled(False)

    def _number(
        self,
        minimum: float,
        maximum: float,
        step: float,
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(2)
        return control

    def set_layer(
        self,
        layer: MotionLayer | None,
        composition: MotionComposition,
    ) -> None:
        rig = rig_for_layer(composition, layer.id) if layer is not None else None
        selected = self._bone_id if self._rig is not None and rig is not None and self._rig.id == rig.id else ""
        self._rig = rig
        self._loading = True
        self.bones.clear()
        self.constraints.clear()
        if rig is None:
            self.title.setText("No rig on selected layer")
            self._bone_id = ""
            self._set_controls_enabled(False)
            self._loading = False
            return
        self.title.setText(f"{rig.name} / {len(rig.bones)} bones")
        for bone in rig.bones:
            item = QListWidgetItem(bone.name or bone.role or bone.id, self.bones)
            item.setData(32, bone.id)
            if bone.id == selected:
                self.bones.setCurrentItem(item)
        for constraint in rig.constraints:
            item = QListWidgetItem(
                (
                    "IK"
                    if bool(constraint.get("enabled", True))
                    else "FK"
                )
                + " / "
                + str(constraint.get("end_bone_id") or "chain"),
                self.constraints,
            )
            item.setData(32, str(constraint.get("id") or ""))
            item.setData(33, bool(constraint.get("enabled", True)))
        if self.constraints.count():
            self.constraints.setCurrentRow(0)
        if self.bones.currentItem() is None and self.bones.count():
            self.bones.setCurrentRow(0)
        self._loading = False
        self._load_selected_bone()

    def select_bone(self, rig_id: str, bone_id: str) -> None:
        if self._rig is None or self._rig.id != str(rig_id):
            return
        for index in range(self.bones.count()):
            item = self.bones.item(index)
            if str(item.data(32) or "") == str(bone_id):
                self.bones.setCurrentItem(item)
                return

    def _select_item(self, current, _previous) -> None:
        self._bone_id = str(current.data(32) or "") if current is not None else ""
        if not self._loading:
            self._load_selected_bone()
            if self._rig is not None and self._bone_id:
                self.bone_selected.emit(self._rig.id, self._bone_id)

    def _load_selected_bone(self) -> None:
        rig = self._rig
        bone = next(
            (row for row in rig.bones if row.id == self._bone_id),
            None,
        ) if rig is not None else None
        self._loading = True
        self._set_controls_enabled(bone is not None)
        if bone is not None:
            self.x.setValue(float(bone.rest_position[0]))
            self.y.setValue(float(bone.rest_position[1]))
            self.rotation_min.setValue(float(bone.rotation_min))
            self.rotation_max.setValue(float(bone.rotation_max))
            self.translation_locked.setChecked(bool(bone.translation_locked))
            self.rotation_locked.setChecked(bool(bone.rotation_locked))
            self.scale_locked.setChecked(bool(bone.scale_locked))
        self._loading = False

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.x,
            self.y,
            self.rotation_min,
            self.rotation_max,
            self.translation_locked,
            self.rotation_locked,
            self.scale_locked,
            self.mirror_button,
            self.ik_lock_button,
        ):
            control.setEnabled(bool(enabled))
        has_constraint = bool(self._rig is not None and self._rig.constraints)
        self.fk_ik_button.setEnabled(has_constraint)
        self.bake_button.setEnabled(has_constraint)

    def _emit_changes(self, *_args) -> None:
        if self._loading or self._rig is None or not self._bone_id:
            return
        self.bone_changed.emit(
            self._rig.id,
            self._bone_id,
            {
                "rest_position": [self.x.value(), self.y.value()],
                "rotation_min": self.rotation_min.value(),
                "rotation_max": self.rotation_max.value(),
                "translation_locked": self.translation_locked.isChecked(),
                "rotation_locked": self.rotation_locked.isChecked(),
                "scale_locked": self.scale_locked.isChecked(),
            },
        )

    def _request_mirror(self) -> None:
        if self._rig is not None and self._bone_id:
            self.mirror_requested.emit(self._rig.id, self._bone_id)

    def _request_ik_lock(self) -> None:
        if self._rig is not None and self._bone_id:
            self.ik_lock_requested.emit(self._rig.id, self._bone_id)

    def _selected_constraint(self):
        return self.constraints.currentItem()

    def _toggle_constraint(self) -> None:
        item = self._selected_constraint()
        if self._rig is None or item is None:
            return
        self.constraint_enabled.emit(
            self._rig.id,
            str(item.data(32) or ""),
            not bool(item.data(33)),
        )

    def _request_constraint_bake(self) -> None:
        item = self._selected_constraint()
        if self._rig is not None and item is not None:
            self.constraint_bake_requested.emit(
                self._rig.id,
                str(item.data(32) or ""),
            )


__all__ = ["RigPanel"]
