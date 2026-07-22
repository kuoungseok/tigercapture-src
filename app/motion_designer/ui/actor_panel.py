from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from app.motion_designer.actor_source import ACTOR_SOURCE_KINDS, LIVE2D_SOURCE_KIND
from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty, MotionLayer


def _default(value: Any, fallback: Any, value_type: str = "scalar") -> Any:
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        return evaluate_property(AnimatedProperty.from_dict(value, value_type=value_type), 0.0)
    return fallback if value is None else value


class ActorPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionActorPanel")
        self._loading = False
        self._kind = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionActorScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionActorContent")
        self.form = QFormLayout(content)
        self.form.setContentsMargins(8, 6, 8, 8)
        self.form.setSpacing(5)
        self.asset = QLabel("", content)
        self.asset.setWordWrap(True)
        self.form.addRow("Asset", self.asset)
        self.motion = QComboBox(content)
        self.motion.setEditable(True)
        self.form.addRow("Motion", self.motion)
        self.motion_index = QSpinBox(content)
        self.motion_index.setRange(0, 9999)
        self.form.addRow("Motion Index", self.motion_index)
        self.expression = QComboBox(content)
        self.expression.setEditable(True)
        self.form.addRow("Expression", self.expression)
        self.animation = QComboBox(content)
        self.animation.setEditable(True)
        self.form.addRow("Animation", self.animation)
        self.skin = QComboBox(content)
        self.skin.setEditable(True)
        self.form.addRow("Skin", self.skin)
        self.loop = QCheckBox("Loop animation", content)
        self.form.addRow("Playback", self.loop)
        self.rate = self._spin(content, 0.05, 8.0, 0.05, 2)
        self.form.addRow("Rate", self.rate)
        self.pos_x = self._spin(content, 0.0, 1.0, 0.01, 3)
        self.pos_y = self._spin(content, 0.0, 1.0, 0.01, 3)
        self.scale = self._spin(content, 0.05, 20.0, 0.05, 3)
        self.opacity = self._spin(content, 0.0, 1.0, 0.01, 3)
        self.form.addRow("Actor X", self.pos_x)
        self.form.addRow("Actor Y", self.pos_y)
        self.form.addRow("Actor Scale", self.scale)
        self.form.addRow("Actor Opacity", self.opacity)
        self.status = QLabel("", content)
        self.status.setObjectName("MotionActorStatus")
        self.status.setWordWrap(True)
        self.form.addRow("Runtime", self.status)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        for control in (
            self.motion, self.motion_index, self.expression, self.animation, self.skin,
            self.loop, self.rate, self.pos_x, self.pos_y, self.scale, self.opacity,
        ):
            signal = getattr(control, "currentTextChanged", None)
            if signal is None:
                signal = getattr(control, "valueChanged", None)
            if signal is None:
                signal = getattr(control, "toggled")
            signal.connect(lambda _value: self._emit_values())
        self.set_layer(None)

    @staticmethod
    def _spin(parent, minimum: float, maximum: float, step: float, decimals: int) -> QDoubleSpinBox:
        control = QDoubleSpinBox(parent)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(decimals)
        return control

    def _set_combo(self, combo: QComboBox, values: list[str], current: str) -> None:
        combo.clear()
        combo.addItems([str(value) for value in values])
        if current and combo.findText(current) < 0:
            combo.addItem(current)
        combo.setCurrentText(current)

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        self._kind = layer.layer_type if layer is not None else ""
        supported = self._kind in ACTOR_SOURCE_KINDS
        self.setEnabled(supported)
        if layer is None or not supported:
            self._loading = False
            return
        params = layer.source.params
        playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
        actor = params.get("actor") if isinstance(params.get("actor"), Mapping) else {}
        catalog = params.get("catalog") if isinstance(params.get("catalog"), Mapping) else {}
        self.asset.setText(layer.source.uri)
        motions = list(catalog.get("motions") or [])
        groups = list(dict.fromkeys(str(row.get("group") or "") for row in motions if isinstance(row, Mapping)))
        self._set_combo(self.motion, groups, str(_default(playback.get("motion_group"), "", "string")))
        self.motion_index.setValue(int(_default(playback.get("motion_index"), 0)))
        self._set_combo(
            self.expression,
            [""] + [str(value) for value in catalog.get("expressions", [])],
            str(_default(playback.get("expression"), "", "string")),
        )
        self._set_combo(
            self.animation,
            [str(value) for value in catalog.get("animations", [])],
            str(_default(playback.get("animation"), "", "string")),
        )
        self._set_combo(
            self.skin,
            [str(value) for value in catalog.get("skins", [])],
            str(_default(playback.get("skin"), "default", "string")),
        )
        self.loop.setChecked(bool(_default(playback.get("loop"), True, "bool")))
        self.rate.setValue(float(_default(playback.get("rate"), 1.0)))
        position = list(_default(actor.get("position"), [0.5, 0.5], "vector2"))
        self.pos_x.setValue(float(position[0]))
        self.pos_y.setValue(float(position[1]))
        self.scale.setValue(float(_default(actor.get("scale"), 1.0)))
        self.opacity.setValue(float(_default(actor.get("opacity"), 1.0)))
        live2d = self._kind == LIVE2D_SOURCE_KIND
        for control in (self.motion, self.motion_index, self.expression):
            control.setVisible(live2d)
            label = self.form.labelForField(control)
            if label is not None:
                label.setVisible(live2d)
        for control in (self.animation, self.skin):
            control.setVisible(not live2d)
            label = self.form.labelForField(control)
            if label is not None:
                label.setVisible(not live2d)
        self.status.setText(
            "Cubism GPU / fixed-FPS seek" if live2d else "Shared Spine renderer / preview-export parity"
        )
        self._loading = False

    def _emit_values(self) -> None:
        if self._loading or self._kind not in ACTOR_SOURCE_KINDS:
            return
        playback: dict[str, Any] = {"loop": self.loop.isChecked(), "rate": self.rate.value()}
        if self._kind == LIVE2D_SOURCE_KIND:
            playback.update({
                "motion_group": self.motion.currentText(),
                "motion_index": self.motion_index.value(),
                "expression": self.expression.currentText(),
            })
        else:
            playback.update({"animation": self.animation.currentText(), "skin": self.skin.currentText()})
        self.source_changed.emit({
            "playback": playback,
            "actor": {
                "position": [self.pos_x.value(), self.pos_y.value()],
                "scale": self.scale.value(),
                "opacity": self.opacity.value(),
            },
        })


__all__ = ["ActorPanel"]
