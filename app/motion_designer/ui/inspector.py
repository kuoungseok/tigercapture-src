from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from app.motion_designer.schema import MotionLayer


class InspectorPanel(QWidget):
    property_changed = Signal(str, object)
    keyframe_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("InspectorPanel")
        layout = QFormLayout(self)
        self._controls: dict[str, QDoubleSpinBox] = {}
        specs = (("x", -100000, 100000, 1), ("y", -100000, 100000, 1),
                 ("scale_x", -100, 100, .01), ("scale_y", -100, 100, .01),
                 ("rotation", -36000, 36000, .5), ("opacity", 0, 1, .01),
                 ("anchor_x", -10, 10, .01), ("anchor_y", -10, 10, .01))
        for name, minimum, maximum, step in specs:
            spin = QDoubleSpinBox(self)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setDecimals(3)
            spin.valueChanged.connect(lambda value, key=name: self.property_changed.emit(key, value))
            key_button = QPushButton("K", self)
            key_button.setFixedWidth(26)
            key_button.setToolTip("Set keyframe")
            key_button.clicked.connect(lambda _checked=False, key=name: self.keyframe_requested.emit(key))
            row = QHBoxLayout()
            row.addWidget(spin, 1)
            row.addWidget(key_button)
            layout.addRow(QLabel(name.replace("_", " ").title()), row)
            self._controls[name] = spin
        self._loading = False

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        self.setEnabled(layer is not None)
        if layer is not None:
            values = {
                "x": layer.transform.position.default[0], "y": layer.transform.position.default[1],
                "scale_x": layer.transform.scale.default[0], "scale_y": layer.transform.scale.default[1],
                "rotation": layer.transform.rotation.default, "opacity": layer.transform.opacity.default,
                "anchor_x": layer.transform.anchor.default[0], "anchor_y": layer.transform.anchor.default[1],
            }
            for key, value in values.items():
                self._controls[key].setValue(float(value))
        self._loading = False

    def values(self) -> dict[str, float]:
        return {key: control.value() for key, control in self._controls.items()}

    def is_loading(self) -> bool:
        return self._loading
