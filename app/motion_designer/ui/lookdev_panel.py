"""Focused painterly/toon/ink look controls for Motion Designer."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QColorDialog,
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
    texture_requested = Signal(str, str, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        self._line_color = "#17202a"
        self._paper_color = "#f1ead9"
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
        self.line_color = QPushButton(self)
        self.line_color.clicked.connect(
            lambda: self._choose_color("line"),
        )
        form.addRow("Line Color", self.line_color)
        self.paper_color = QPushButton(self)
        self.paper_color.clicked.connect(
            lambda: self._choose_color("paper"),
        )
        form.addRow("Paper Color", self.paper_color)
        self.texture_blend = QComboBox(self)
        for label, value in (
            ("Multiply", "multiply"),
            ("Overlay", "overlay"),
            ("Screen", "screen"),
        ):
            self.texture_blend.addItem(label, value)
        form.addRow("Texture Blend", self.texture_blend)
        self.texture_opacity = QDoubleSpinBox(self)
        self.texture_opacity.setRange(0.0, 1.0)
        self.texture_opacity.setSingleStep(0.05)
        self.texture_opacity.setDecimals(2)
        self.texture_opacity.setValue(0.25)
        form.addRow("Texture Opacity", self.texture_opacity)
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
        self._line_color = str(values.get("line_color") or "#17202a")
        self._paper_color = str(values.get("paper_color") or "#f1ead9")
        self._refresh_color_buttons()
        self._loading = False

    def _refresh_color_buttons(self) -> None:
        for button, color in (
            (self.line_color, self._line_color),
            (self.paper_color, self._paper_color),
        ):
            parsed = QColor(color)
            luminance = (
                0.2126 * parsed.redF()
                + 0.7152 * parsed.greenF()
                + 0.0722 * parsed.blueF()
            )
            text_color = "#111111" if luminance > 0.55 else "#ffffff"
            button.setText(color.upper())
            button.setStyleSheet(
                f"background:{color}; color:{text_color};"
            )

    def _choose_color(self, target: str) -> None:
        current = self._line_color if target == "line" else self._paper_color
        chosen = QColorDialog.getColor(QColor(current), self)
        if not chosen.isValid():
            return
        if target == "line":
            self._line_color = chosen.name()
        else:
            self._paper_color = chosen.name()
        self._refresh_color_buttons()

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
            self.texture_requested.emit(
                uri,
                str(self.texture_blend.currentData()),
                self.texture_opacity.value(),
            )

    def _emit_apply(self) -> None:
        values = {key: control.value() for key, control in self.controls.items()}
        values["line_color"] = self._line_color
        values["paper_color"] = self._paper_color
        self.apply_requested.emit(
            str(self.preset.currentData()),
            values,
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
        values["line_color"] = effect.metadata.get("line_color")
        values["paper_color"] = effect.metadata.get("paper_color")
        texture = effect.metadata.get("projected_texture")
        if isinstance(texture, dict):
            blend_index = self.texture_blend.findData(
                str(texture.get("blend_mode") or "multiply"),
            )
            if blend_index >= 0:
                self.texture_blend.setCurrentIndex(blend_index)
            self.texture_opacity.setValue(float(texture.get("opacity", 0.25)))
        self._set_values(normalize_painterly_look(values, preset=preset))


__all__ = ["PainterlyLookPanel"]
