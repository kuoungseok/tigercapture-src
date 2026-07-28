"""Focused controls for Motion Designer craft/imperfection styling."""
from __future__ import annotations

import secrets

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.craft_style import (
    CRAFT_STYLE_PRESETS,
    is_craft_style_effect,
    normalize_craft_style,
)
from app.motion_designer.schema import MotionLayer


class CraftStylePanel(QWidget):
    apply_requested = Signal(str, object)
    clear_requested = Signal()
    texture_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QLabel("Craft / Imperfection", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        root.addWidget(QLabel(
            "Add controlled texture and movement without changing source media.",
            self,
        ))

        form = QFormLayout()
        self.preset = QComboBox(self)
        for preset_id in CRAFT_STYLE_PRESETS:
            self.preset.addItem(preset_id.replace("_", " ").title(), preset_id)
        form.addRow("Preset", self.preset)

        specs = (
            ("amount", "Amount", 0.0, 1.0, 0.01, 3),
            ("grain_amount", "Film Grain", 0.0, 1.0, 0.01, 3),
            ("grain_size", "Grain Size", 1.0, 12.0, 0.1, 2),
            ("weave_x", "Gate Weave X", 0.0, 100.0, 0.1, 2),
            ("weave_y", "Gate Weave Y", 0.0, 100.0, 0.1, 2),
            ("flicker_amount", "Light Flicker", 0.0, 1.0, 0.001, 3),
            ("flicker_warmth", "Flicker Warmth", -1.0, 1.0, 0.01, 2),
            ("dust_amount", "Dust", 0.0, 1.0, 0.01, 3),
            ("scratch_amount", "Scratches", 0.0, 1.0, 0.01, 3),
            ("misregistration", "Print Offset", 0.0, 20.0, 0.1, 2),
            ("halation_amount", "Halation", 0.0, 1.0, 0.01, 3),
            ("warmth", "Film Warmth", -1.0, 1.0, 0.01, 2),
            ("vhs_amount", "VHS Wobble", 0.0, 1.0, 0.01, 3),
            ("edge_roughness", "Edge Roughness", 0.0, 1.0, 0.01, 3),
            ("loop_period", "Loop Period (s)", 0.1, 3600.0, 0.1, 2),
        )
        self.controls: dict[str, QDoubleSpinBox] = {}
        for key, label, minimum, maximum, step, decimals in specs:
            control = QDoubleSpinBox(self)
            control.setRange(minimum, maximum)
            control.setSingleStep(step)
            control.setDecimals(decimals)
            form.addRow(label, control)
            self.controls[key] = control
        self.seed = QSpinBox(self)
        self.seed.setRange(0, 2_147_483_647)
        form.addRow("Locked Seed", self.seed)
        root.addLayout(form)

        buttons = QHBoxLayout()
        randomize = QPushButton("Randomize", self)
        texture = QPushButton("Texture...", self)
        apply = QPushButton("Apply", self)
        clear = QPushButton("Clear", self)
        buttons.addWidget(randomize)
        buttons.addWidget(texture)
        buttons.addStretch(1)
        buttons.addWidget(clear)
        buttons.addWidget(apply)
        root.addLayout(buttons)
        root.addStretch(1)

        self.preset.currentIndexChanged.connect(self._load_preset)
        randomize.clicked.connect(self._randomize_seed)
        texture.clicked.connect(self._choose_texture)
        apply.clicked.connect(self._emit_apply)
        clear.clicked.connect(self.clear_requested)
        self.set_layer(None)

    def _choose_texture(self) -> None:
        uri, _filter = QFileDialog.getOpenFileName(
            self,
            "Attach Craft Texture",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)",
        )
        if uri:
            self.texture_requested.emit(uri)

    def _load_preset(self) -> None:
        if self._loading:
            return
        values = normalize_craft_style(preset=str(self.preset.currentData()))
        self._set_values(values)

    def _set_values(self, values: dict) -> None:
        self._loading = True
        for key, control in self.controls.items():
            control.setValue(float(values[key]))
        self.seed.setValue(int(values["seed"]))
        self._loading = False

    def _randomize_seed(self) -> None:
        self.seed.setValue(secrets.randbelow(2_147_483_647))

    def _emit_apply(self) -> None:
        values = {key: control.value() for key, control in self.controls.items()}
        values["seed"] = self.seed.value()
        values["seed_locked"] = True
        self.apply_requested.emit(str(self.preset.currentData()), values)

    def set_layer(self, layer: MotionLayer | None) -> None:
        self.setEnabled(layer is not None)
        if layer is None:
            self._set_values(normalize_craft_style())
            return
        effect = next((row for row in layer.effects if is_craft_style_effect(row)), None)
        if effect is None:
            self._set_values(normalize_craft_style())
            return
        preset = str(effect.metadata.get("preset") or "subtle_film")
        index = self.preset.findData(preset)
        self._loading = True
        if index >= 0:
            self.preset.setCurrentIndex(index)
        self._loading = False
        values = {
            key: prop.default
            for key, prop in effect.params.items()
        }
        self._set_values(normalize_craft_style(values, preset=preset))


__all__ = ["CraftStylePanel"]
