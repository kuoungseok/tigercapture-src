"""Human-facing setup dialog for a standard full-body cutout rig."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.motion_designer.rigging import create_humanoid_rig
from app.motion_designer.schema import MotionComposition


SLOTS = (
    ("torso", "Torso / body", ("torso", "body", "chest")),
    ("head", "Head", ("head", "face")),
    ("left_upper_arm", "Left upper arm", ("left upper arm", "l upper arm", "left arm")),
    ("left_forearm", "Left forearm", ("left forearm", "l forearm")),
    ("left_hand", "Left hand", ("left hand", "l hand")),
    ("right_upper_arm", "Right upper arm", ("right upper arm", "r upper arm", "right arm")),
    ("right_forearm", "Right forearm", ("right forearm", "r forearm")),
    ("right_hand", "Right hand", ("right hand", "r hand")),
    ("left_thigh", "Left thigh", ("left thigh", "l thigh", "left leg")),
    ("left_shin", "Left shin", ("left shin", "l shin", "left calf")),
    ("left_foot", "Left foot", ("left foot", "l foot")),
    ("right_thigh", "Right thigh", ("right thigh", "r thigh", "right leg")),
    ("right_shin", "Right shin", ("right shin", "r shin", "right calf")),
    ("right_foot", "Right foot", ("right foot", "r foot")),
)


class FullBodyRigDialog(QDialog):
    def __init__(
        self,
        composition: MotionComposition,
        *,
        selected_layer_id: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create Full Body Rig")
        self._composition = composition
        self._controls: dict[str, QComboBox] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Map cutout layers to the standard 17-bone skeleton. "
            "Unassigned bones remain editable for later binding.",
            self,
        ))
        form = QFormLayout()
        self.name = QLineEdit("Humanoid Cutout Rig", self)
        form.addRow("Name", self.name)
        for slot, title, tokens in SLOTS:
            combo = QComboBox(self)
            combo.addItem("Unassigned", "")
            for layer in reversed(composition.layers):
                combo.addItem(layer.name, layer.id)
            preferred = self._match_layer(tokens)
            if slot == "torso" and selected_layer_id:
                preferred = selected_layer_id
            if preferred:
                index = combo.findData(preferred)
                if index >= 0:
                    combo.setCurrentIndex(index)
            self._controls[slot] = combo
            form.addRow(title, combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _match_layer(self, tokens: tuple[str, ...]) -> str:
        for layer in reversed(self._composition.layers):
            name = str(layer.name or "").strip().lower().replace("_", " ")
            if any(token in name for token in tokens):
                return layer.id
        return ""

    def create(self, composition: MotionComposition):
        return create_humanoid_rig(
            composition,
            name=self.name.text().strip() or "Humanoid Cutout Rig",
            layer_slots={
                slot: str(control.currentData() or "")
                for slot, control in self._controls.items()
                if control.currentData()
            },
        )


__all__ = ["FullBodyRigDialog"]
