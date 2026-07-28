from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.schema import MotionLayer


class ReplicatorPanel(QWidget):
    settings_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionReplicatorPanel")
        self._loading = False
        self._layer_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionReplicatorScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionReplicatorContent")
        form = QFormLayout(content)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(6)

        self.enabled = QCheckBox("Enabled", content)
        self.arrangement = QComboBox(content)
        self.arrangement.addItems(("line", "grid", "radial"))
        self.count = self._int(1, 256)
        self.columns = self._int(1, 256)
        self.offset_x = self._double(-10000, 10000, 1)
        self.offset_y = self._double(-10000, 10000, 1)
        self.rotation = self._double(-3600, 3600, .5)
        self.scale_x = self._double(.01, 10, .01)
        self.scale_y = self._double(.01, 10, .01)
        self.opacity_start = self._double(0, 1, .01)
        self.opacity_end = self._double(0, 1, .01)
        self.jitter_x = self._double(0, 5000, 1)
        self.jitter_y = self._double(0, 5000, 1)
        self.seed = self._int(-2147483647, 2147483647)
        for label, control in (
            ("", self.enabled),
            ("Arrangement", self.arrangement),
            ("Copies", self.count),
            ("Columns", self.columns),
            ("Offset X / Radius", self.offset_x),
            ("Offset Y", self.offset_y),
            ("Rotation", self.rotation),
            ("Scale X / copy", self.scale_x),
            ("Scale Y / copy", self.scale_y),
            ("Start Opacity", self.opacity_start),
            ("End Opacity", self.opacity_end),
            ("Jitter X", self.jitter_x),
            ("Jitter Y", self.jitter_y),
            ("Random Seed", self.seed),
        ):
            form.addRow(label, control)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

        self.enabled.toggled.connect(self._emit)
        self.arrangement.currentTextChanged.connect(self._emit)
        for control in (
            self.count,
            self.columns,
            self.offset_x,
            self.offset_y,
            self.rotation,
            self.scale_x,
            self.scale_y,
            self.opacity_start,
            self.opacity_end,
            self.jitter_x,
            self.jitter_y,
            self.seed,
        ):
            control.valueChanged.connect(self._emit)
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
        active = bool(layer and layer.layer_type not in {
            "group", "null", "camera", "light", "adjustment",
        })
        self.setEnabled(active)
        self._layer_id = layer.id if active and layer is not None else ""
        if not active or layer is None:
            return
        self._loading = True
        config = layer.metadata.get("replicator")
        config = config if isinstance(config, Mapping) else {}
        offset = list(config.get("offset") or [80.0, 0.0])
        scale = list(config.get("scale") or [1.0, 1.0])
        jitter = list(config.get("jitter") or [0.0, 0.0])
        self.enabled.setChecked(bool(config.get("enabled", False)))
        self.arrangement.setCurrentText(str(config.get("arrangement") or "line"))
        self.count.setValue(int(config.get("count", 5) or 5))
        self.columns.setValue(int(config.get("columns", 5) or 5))
        self.offset_x.setValue(float(offset[0] if offset else 80.0))
        self.offset_y.setValue(float(offset[1] if len(offset) > 1 else 0.0))
        self.rotation.setValue(float(config.get("rotation", 0.0) or 0.0))
        self.scale_x.setValue(float(scale[0] if scale else 1.0))
        self.scale_y.setValue(float(scale[1] if len(scale) > 1 else 1.0))
        self.opacity_start.setValue(float(config.get("opacity_start", 1.0) or 0.0))
        self.opacity_end.setValue(float(config.get("opacity_end", 1.0) or 0.0))
        self.jitter_x.setValue(float(jitter[0] if jitter else 0.0))
        self.jitter_y.setValue(float(jitter[1] if len(jitter) > 1 else 0.0))
        self.seed.setValue(int(config.get("seed", 0) or 0))
        self._loading = False
        self._update_visibility()

    def _update_visibility(self) -> None:
        self.columns.setEnabled(self.arrangement.currentText() == "grid")
        self.offset_y.setEnabled(self.arrangement.currentText() != "radial")

    def _emit(self, *_args) -> None:
        self._update_visibility()
        if self._loading or not self._layer_id:
            return
        self.settings_changed.emit({
            "enabled": self.enabled.isChecked(),
            "arrangement": self.arrangement.currentText(),
            "count": self.count.value(),
            "columns": self.columns.value(),
            "offset": [self.offset_x.value(), self.offset_y.value()],
            "rotation": self.rotation.value(),
            "scale": [self.scale_x.value(), self.scale_y.value()],
            "opacity_start": self.opacity_start.value(),
            "opacity_end": self.opacity_end.value(),
            "jitter": [self.jitter_x.value(), self.jitter_y.value()],
            "seed": self.seed.value(),
        })


__all__ = ["ReplicatorPanel"]
