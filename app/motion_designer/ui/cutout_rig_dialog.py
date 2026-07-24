"""Human-facing setup dialog for editable 2D cutout arm rigs."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from app.motion_designer.commands import find_layer
from app.motion_designer.cutout_rig import ArmJointLayout, apply_arm_wave_rig
from app.motion_designer.schema import MotionComposition


class CutoutArmRigDialog(QDialog):
    def __init__(self, composition: MotionComposition, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cutout Arm Wave")
        self.setModal(True)
        self._composition = MotionComposition.from_dict(composition.to_dict())
        form = QFormLayout(self)
        self.layer_boxes: dict[str, QComboBox] = {}
        for role, title in (
            ("torso", "Torso"),
            ("upper_arm", "Upper Arm"),
            ("forearm", "Forearm"),
            ("hand", "Hand"),
        ):
            box = QComboBox(self)
            for layer in self._composition.layers:
                box.addItem(layer.name, layer.id)
            box.setCurrentIndex(min(len(self.layer_boxes), max(0, box.count() - 1)))
            self.layer_boxes[role] = box
            form.addRow(title, box)

        width, height = self._composition.width, self._composition.height
        self.joints = {
            "shoulder": self._point_editor(width * 0.60, height * 0.38),
            "elbow": self._point_editor(width * 0.69, height * 0.52),
            "wrist": self._point_editor(width * 0.75, height * 0.66),
        }
        form.addRow("Shoulder (px)", self.joints["shoulder"][0])
        form.addRow("Elbow (px)", self.joints["elbow"][0])
        form.addRow("Wrist (px)", self.joints["wrist"][0])
        self.start_ms = QSpinBox(self)
        self.start_ms.setRange(0, max(0, self._composition.duration_ms - 1))
        self.start_ms.setValue(min(400, self.start_ms.maximum()))
        self.end_ms = QSpinBox(self)
        self.end_ms.setRange(1, self._composition.duration_ms)
        self.end_ms.setValue(min(self._composition.duration_ms, 3000))
        self.side = QComboBox(self)
        self.side.addItems(("right", "left"))
        self.cycles = QSpinBox(self)
        self.cycles.setRange(1, 8)
        self.cycles.setValue(3)
        form.addRow("Start (ms)", self.start_ms)
        form.addRow("End (ms)", self.end_ms)
        form.addRow("Arm Side", self.side)
        form.addRow("Wave Cycles", self.cycles)
        self.status = QLabel(
            "Use full-canvas aligned transparent parts. Coordinates are composition pixels.",
            self,
        )
        self.status.setWordWrap(True)
        form.addRow(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_rig)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _point_editor(self, x: float, y: float) -> tuple[QWidget, QDoubleSpinBox, QDoubleSpinBox]:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        fields: list[QDoubleSpinBox] = []
        for value, maximum in (
            (x, self._composition.width),
            (y, self._composition.height),
        ):
            field = QDoubleSpinBox(row)
            field.setRange(0.0, float(maximum))
            field.setDecimals(1)
            field.setValue(float(value))
            layout.addWidget(field)
            fields.append(field)
        return row, fields[0], fields[1]

    def _point(self, name: str) -> tuple[float, float]:
        _, x, y = self.joints[name]
        return x.value(), y.value()

    def _accept_rig(self) -> None:
        ids = {
            role: str(box.currentData() or "")
            for role, box in self.layer_boxes.items()
        }
        if len(set(ids.values())) != 4:
            self.status.setText("Choose four different layers.")
            return
        if self.end_ms.value() <= self.start_ms.value():
            self.status.setText("End must be later than Start.")
            return
        layers = {role: find_layer(self._composition, layer_id) for role, layer_id in ids.items()}
        apply_arm_wave_rig(
            self._composition,
            torso=layers["torso"],
            upper_arm=layers["upper_arm"],
            forearm=layers["forearm"],
            hand=layers["hand"],
            joints=ArmJointLayout(
                shoulder=self._point("shoulder"),
                elbow=self._point("elbow"),
                wrist=self._point("wrist"),
            ),
            start_ms=self.start_ms.value(),
            end_ms=self.end_ms.value(),
            side=self.side.currentText(),
            cycles=self.cycles.value(),
        )
        self._composition.revision += 1
        self.accept()

    def result_composition(self) -> MotionComposition:
        return MotionComposition.from_dict(self._composition.to_dict())


__all__ = ["CutoutArmRigDialog"]
