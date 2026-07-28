"""Focused painterly/toon/ink look controls for Motion Designer."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.painterly_look import (
    PAINTERLY_LOOK_PRESETS,
    is_painterly_look_effect,
    normalize_painterly_look,
)
from app.motion_designer.schema import MotionLayer


class PainterlyLookPanel(QWidget):
    apply_requested = Signal(str, object)
    clear_requested = Signal()
    texture_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QLabel("Painterly / Toon / Ink", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        root.addWidget(QLabel(
            "Stylize video, images, and existing AR/PBR output consistently.",
            self,
        ))
        form = QFormLayout()
        self.preset = QComboBox(self)
        for preset_id in PAINTERLY_LOOK_PRESETS:
            self.preset.addItem(preset_id.title(), preset_id)
        form.addRow("Preset", self.preset)
        specs = (
            ("amount", "Amount", 0.0, 1.0, 0.01, 2),
            ("color_levels", "Color Bands", 2.0, 32.0, 1.0, 0),
            ("toon_amount", "Toon", 0.0, 1.0, 0.01, 2),
            ("smoothing", "Paint Smoothing", 0.0, 1.0, 0.01, 2),
            ("edge_strength", "Ink Lines", 0.0, 2.0, 0.01, 2),
            ("edge_threshold", "Line Threshold", 0.0, 1.0, 0.01, 2),
            ("brush_amount", "Brush Texture", 0.0, 1.0, 0.01, 2),
            ("granulation", "Granulation", 0.0, 1.0, 0.01, 2),
            ("paper_amount", "Paper", 0.0, 1.0, 0.01, 2),
            ("hatch_amount", "Hatching", 0.0, 1.0, 0.01, 2),
        )
        self.controls: dict[str, QDoubleSpinBox] = {}
        for key, label, minimum, maximum, step, decimals in specs:
            control = QDoubleSpinBox(self)
            control.setRange(minimum, maximum)
            control.setSingleStep(step)
            control.setDecimals(decimals)
            form.addRow(label, control)
            self.controls[key] = control
        root.addLayout(form)
        buttons = QHBoxLayout()
        texture = QPushButton("Texture...", self)
        clear = QPushButton("Clear", self)
        apply = QPushButton("Apply", self)
        buttons.addWidget(texture)
        buttons.addStretch(1)
        buttons.addWidget(clear)
        buttons.addWidget(apply)
        root.addLayout(buttons)
        root.addStretch(1)
        self.preset.currentIndexChanged.connect(self._load_preset)
        texture.clicked.connect(self._choose_texture)
        clear.clicked.connect(self.clear_requested)
        apply.clicked.connect(self._emit_apply)
        self.set_layer(None)

    def _set_values(self, values: dict) -> None:
        self._loading = True
        for key, control in self.controls.items():
            control.setValue(float(values[key]))
        self._loading = False

    def _load_preset(self) -> None:
        if not self._loading:
            self._set_values(normalize_painterly_look(
                preset=str(self.preset.currentData()),
            ))

    def _choose_texture(self) -> None:
        uri, _selected = QFileDialog.getOpenFileName(
            self,
            "Project Painterly Texture",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )
        if uri:
            self.texture_requested.emit(uri)

    def _emit_apply(self) -> None:
        self.apply_requested.emit(
            str(self.preset.currentData()),
            {key: control.value() for key, control in self.controls.items()},
        )

    def set_layer(self, layer: MotionLayer | None) -> None:
        self.setEnabled(layer is not None)
        if layer is None:
            self._set_values(normalize_painterly_look())
            return
        effect = next(
            (row for row in layer.effects if is_painterly_look_effect(row)),
            None,
        )
        if effect is None:
            self._set_values(normalize_painterly_look())
            return
        preset = str(effect.metadata.get("preset") or "realistic")
        index = self.preset.findData(preset)
        self._loading = True
        if index >= 0:
            self.preset.setCurrentIndex(index)
        self._loading = False
        values = {key: prop.default for key, prop in effect.params.items()}
        self._set_values(normalize_painterly_look(values, preset=preset))


__all__ = ["PainterlyLookPanel"]
