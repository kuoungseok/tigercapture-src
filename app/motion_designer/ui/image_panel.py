from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from app.motion_designer.schema import MotionLayer
from app.motion_designer.vector_shapes import evaluate_source_param


class ImagePanel(QWidget):
    source_changed = Signal(object)
    keyframe_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        form = QFormLayout(self)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(7)
        self.tilt_x = self._spin(-70.0, 70.0, 0.5)
        self.tilt_y = self._spin(-70.0, 70.0, 0.5)
        self.perspective = self._spin(1.2, 8.0, 0.1)
        self._controls = {
            "tilt_x": self.tilt_x,
            "tilt_y": self.tilt_y,
            "perspective": self.perspective,
        }
        for name, label in (
            ("tilt_x", "Tilt X"),
            ("tilt_y", "Tilt Y"),
            ("perspective", "Perspective"),
        ):
            row = QHBoxLayout()
            row.addWidget(self._controls[name], 1)
            key_button = QPushButton("K", self)
            key_button.setFixedWidth(26)
            key_button.setToolTip(f"Set {label} keyframe")
            key_button.clicked.connect(
                lambda _checked=False, key=name: self.keyframe_requested.emit(key)
            )
            row.addWidget(key_button)
            form.addRow(label, row)
        for control in self._controls.values():
            control.valueChanged.connect(self._emit_values)
        self.setEnabled(False)

    @staticmethod
    def _spin(minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(2)
        return control

    def set_layer(self, layer: MotionLayer | None, time_ms: int = 0) -> None:
        active = bool(layer and layer.layer_type == "image")
        self.setEnabled(active)
        if not active or layer is None:
            return
        self._loading = True
        params = layer.source.params
        self.tilt_x.setValue(float(evaluate_source_param(params, "tilt_x", time_ms, 0.0)))
        self.tilt_y.setValue(float(evaluate_source_param(params, "tilt_y", time_ms, 0.0)))
        self.perspective.setValue(float(evaluate_source_param(params, "perspective", time_ms, 2.6)))
        self._loading = False

    def value(self, name: str) -> float:
        control = self._controls.get(str(name))
        if control is None:
            raise ValueError(f"unknown image parameter: {name}")
        return float(control.value())

    def _emit_values(self) -> None:
        if self._loading:
            return
        self.source_changed.emit({
            "tilt_x": self.tilt_x.value(),
            "tilt_y": self.tilt_y.value(),
            "perspective": self.perspective.value(),
        })


__all__ = ["ImagePanel"]
