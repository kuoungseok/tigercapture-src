"""Material inspector for backdrop-aware Tiger Glass."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.glass_material import (
    GLASS_PRESETS,
    glass_effect,
    normalize_glass,
)
from app.motion_designer.schema import MotionLayer


class GlassMaterialPanel(QWidget):
    apply_requested = Signal(str, object)
    remove_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QLabel("Tiger Glass", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        root.addWidget(QLabel("Samples the composed layers behind this object.", self))
        form = QFormLayout()
        self.preset = QComboBox(self)
        for preset_id in GLASS_PRESETS:
            self.preset.addItem(preset_id.replace("_", " ").title(), preset_id)
        form.addRow("Preset", self.preset)
        specs = (
            ("blur_radius", "Backdrop Blur", 0.0, 100.0, 0.25),
            ("refraction", "Refraction", 0.0, 64.0, 0.1),
            ("normal_scale", "Normal Scale", 0.1, 20.0, 0.1),
            ("thickness", "Thickness", 0.0, 2.0, 0.01),
            ("absorption", "Absorption", 0.0, 1.0, 0.01),
            ("edge_highlight", "Edge Highlight", 0.0, 2.0, 0.01),
            ("specular", "Specular", 0.0, 4.0, 0.01),
            ("dispersion", "Dispersion", 0.0, 8.0, 0.01),
            ("bloom", "Gloss Bloom", 0.0, 2.0, 0.01),
            ("tint_strength", "Tint Strength", 0.0, 1.0, 0.01),
            ("driver_x", "Driver X", -10.0, 10.0, 0.05),
            ("driver_y", "Driver Y", -10.0, 10.0, 0.05),
        )
        self.controls: dict[str, QDoubleSpinBox] = {}
        for key, label, minimum, maximum, step in specs:
            control = QDoubleSpinBox(self)
            control.setRange(minimum, maximum)
            control.setSingleStep(step)
            control.setDecimals(3)
            form.addRow(label, control)
            self.controls[key] = control
        self.tint = QLineEdit("#dff7ff", self)
        form.addRow("Tint", self.tint)
        self.quality = QComboBox(self)
        self.quality.addItems(["draft", "preview", "final"])
        form.addRow("Quality", self.quality)
        root.addLayout(form)
        buttons = QHBoxLayout()
        remove = QPushButton("Remove", self)
        apply = QPushButton("Apply", self)
        buttons.addStretch(1)
        buttons.addWidget(remove)
        buttons.addWidget(apply)
        root.addLayout(buttons)
        root.addStretch(1)
        self.preset.currentIndexChanged.connect(self._load_preset)
        remove.clicked.connect(self.remove_requested)
        apply.clicked.connect(self._emit_apply)
        self.set_layer(None)

    def _set_values(self, values: dict) -> None:
        self._loading = True
        for key, control in self.controls.items():
            control.setValue(float(values[key]))
        self.tint.setText(str(values["tint"]))
        self.quality.setCurrentText(str(values["quality"]))
        self._loading = False

    def _load_preset(self) -> None:
        if not self._loading:
            self._set_values(normalize_glass(preset=str(self.preset.currentData())))

    def _emit_apply(self) -> None:
        values = {key: control.value() for key, control in self.controls.items()}
        values["tint"] = self.tint.text().strip()
        values["quality"] = self.quality.currentText()
        self.apply_requested.emit(str(self.preset.currentData()), values)

    def set_layer(self, layer: MotionLayer | None) -> None:
        self.setEnabled(layer is not None)
        effect = glass_effect(layer.effects) if layer is not None else None
        if effect is None:
            self._set_values(normalize_glass())
            return
        preset = str(effect.metadata.get("preset") or "clear")
        index = self.preset.findData(preset)
        self._loading = True
        if index >= 0:
            self.preset.setCurrentIndex(index)
        self._loading = False
        values = {key: prop.default for key, prop in effect.params.items()}
        values["tint"] = effect.metadata.get("tint", "#ffffff")
        values["quality"] = effect.metadata.get("quality", "preview")
        self._set_values(normalize_glass(values, preset=preset))


__all__ = ["GlassMaterialPanel"]
