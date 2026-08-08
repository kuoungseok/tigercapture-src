from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.generators import GENERATOR_KINDS, GENERATOR_SOURCE_KIND
from app.motion_designer.schema import MotionLayer


class GeneratorPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionGeneratorPanel")
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionGeneratorScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionGeneratorContent")
        form = QFormLayout(content)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        self.kind = QComboBox(content)
        self.kind.addItems(GENERATOR_KINDS)
        self.width = self._int(1, 16384)
        self.height = self._int(1, 16384)
        self.color_a = QLineEdit(content)
        self.color_b = QLineEdit(content)
        self.scale = self._double(2, 4096, 2)
        self.angle = self._double(-3600, 3600, 1)
        self.offset_x = self._double(-16384, 16384, 1)
        self.offset_y = self._double(-16384, 16384, 1)
        self.seed = self._int(-2147483647, 2147483647)
        self.detail = self._int(1, 8)
        self.contrast = self._double(0, 4, .05)
        for label, control in (
            ("Generator", self.kind),
            ("Width", self.width),
            ("Height", self.height),
            ("Color A", self.color_a),
            ("Color B", self.color_b),
            ("Scale", self.scale),
            ("Angle", self.angle),
            ("Offset X", self.offset_x),
            ("Offset Y", self.offset_y),
            ("Seed", self.seed),
            ("Detail", self.detail),
            ("Contrast", self.contrast),
        ):
            form.addRow(label, control)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

        self.kind.currentTextChanged.connect(self._emit)
        for control in (
            self.width,
            self.height,
            self.scale,
            self.angle,
            self.offset_x,
            self.offset_y,
            self.seed,
            self.detail,
            self.contrast,
        ):
            control.valueChanged.connect(self._emit)
        self.color_a.editingFinished.connect(self._emit)
        self.color_b.editingFinished.connect(self._emit)
        self.setEnabled(False)

    def _int(self, minimum: int, maximum: int) -> QSpinBox:
        control = QSpinBox(self)
        control.setRange(minimum, maximum)
        return control

    def _double(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        return control

    def set_layer(self, layer: MotionLayer | None) -> None:
        active = bool(layer and layer.layer_type == GENERATOR_SOURCE_KIND)
        self.setEnabled(active)
        if not active or layer is None:
            return
        self._loading = True
        params = layer.source.params
        offset = list(params.get("offset") or [0.0, 0.0])
        self.kind.setCurrentText(str(params.get("kind") or "gradient"))
        self.width.setValue(int(params.get("width", 1920) or 1920))
        self.height.setValue(int(params.get("height", 1080) or 1080))
        self.color_a.setText(str(params.get("color_a") or "#24677f"))
        self.color_b.setText(str(params.get("color_b") or "#111820"))
        self.scale.setValue(float(params.get("scale", 96.0) or 96.0))
        self.angle.setValue(float(params.get("angle", 35.0) or 0.0))
        self.offset_x.setValue(float(offset[0] if offset else 0.0))
        self.offset_y.setValue(float(offset[1] if len(offset) > 1 else 0.0))
        self.seed.setValue(int(params.get("seed", 17) or 0))
        self.detail.setValue(int(params.get("detail", 4) or 4))
        self.contrast.setValue(float(params.get("contrast", 1.0) or 0.0))
        self._loading = False

    def _emit(self, *_args) -> None:
        if self._loading or not self.isEnabled():
            return
        self.source_changed.emit({
            "kind": self.kind.currentText(),
            "width": self.width.value(),
            "height": self.height.value(),
            "color_a": self.color_a.text().strip(),
            "color_b": self.color_b.text().strip(),
            "scale": self.scale.value(),
            "angle": self.angle.value(),
            "offset": [self.offset_x.value(), self.offset_y.value()],
            "seed": self.seed.value(),
            "detail": self.detail.value(),
            "contrast": self.contrast.value(),
        })


__all__ = ["GeneratorPanel"]
