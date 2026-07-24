from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QWidget

from app.motion_designer.schema import MotionLayer
from app.motion_designer.vector_shapes import evaluate_source_param


class ImagePanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(7)
        self.tilt_x = self._spin(-70.0, 70.0, 0.5)
        self.tilt_y = self._spin(-70.0, 70.0, 0.5)
        self.perspective = self._spin(1.2, 8.0, 0.1)
        form.addRow("Tilt X", self.tilt_x)
        form.addRow("Tilt Y", self.tilt_y)
        form.addRow("Perspective", self.perspective)
        for control in (self.tilt_x, self.tilt_y, self.perspective):
            control.valueChanged.connect(self._emit_values)
        self.setEnabled(False)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(2)
        return control

    def set_layer(self, layer: MotionLayer | None) -> None:
        active = bool(layer and layer.layer_type == "image")
        self.setEnabled(active)
        if not active or layer is None:
            return
        self._loading = True
        params = layer.source.params
        self.tilt_x.setValue(float(evaluate_source_param(params, "tilt_x", 0.0, 0.0)))
        self.tilt_y.setValue(float(evaluate_source_param(params, "tilt_y", 0.0, 0.0)))
        self.perspective.setValue(float(evaluate_source_param(params, "perspective", 0.0, 2.6)))
        self._loading = False

    def _emit_values(self) -> None:
        if self._loading:
            return
        self.source_changed.emit({
            "tilt_x": self.tilt_x.value(),
            "tilt_y": self.tilt_y.value(),
            "perspective": self.perspective.value(),
        })


__all__ = ["ImagePanel"]
