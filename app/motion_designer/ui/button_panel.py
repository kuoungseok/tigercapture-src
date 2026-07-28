from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.interactive_button import (
    BUTTON_EASINGS,
    BUTTON_STATES,
    button_component,
)
from app.motion_designer.schema import MotionLayer


class ButtonComponentPanel(QWidget):
    create_requested = Signal()
    remove_requested = Signal()
    state_changed = Signal(str)
    settings_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ButtonComponentPanel")
        self._loading = False

        self.summary = QLabel(
            "Convert a layer or group into an interactive button with reusable states.",
            self,
        )
        self.summary.setWordWrap(True)

        self.create_button = QPushButton("Create Button Component", self)
        self.create_button.clicked.connect(self.create_requested)
        self.remove_button = QPushButton("Remove", self)
        self.remove_button.clicked.connect(self.remove_requested)
        commands = QHBoxLayout()
        commands.addWidget(self.create_button, 1)
        commands.addWidget(self.remove_button)

        self.state = QComboBox(self)
        for value in BUTTON_STATES:
            self.state.addItem(value.title(), value)
        self.state.currentIndexChanged.connect(self._emit_state)

        self.scale = QDoubleSpinBox(self)
        self.scale.setRange(0.05, 8.0)
        self.scale.setSingleStep(0.01)
        self.scale.setDecimals(3)
        self.scale.valueChanged.connect(self._emit_style)

        self.offset_x = self._offset_spin()
        self.offset_y = self._offset_spin()
        self.rotation = QDoubleSpinBox(self)
        self.rotation.setRange(-360.0, 360.0)
        self.rotation.setSingleStep(0.5)
        self.rotation.setSuffix(" deg")
        self.rotation.valueChanged.connect(self._emit_style)
        self.opacity = QDoubleSpinBox(self)
        self.opacity.setRange(0.0, 1.0)
        self.opacity.setSingleStep(0.05)
        self.opacity.setDecimals(2)
        self.opacity.valueChanged.connect(self._emit_style)

        self.duration = QSpinBox(self)
        self.duration.setRange(0, 5000)
        self.duration.setSingleStep(10)
        self.duration.setSuffix(" ms")
        self.duration.valueChanged.connect(self._emit_component_settings)
        self.easing = QComboBox(self)
        for value in BUTTON_EASINGS:
            self.easing.addItem(value.replace("_", " ").title(), value)
        self.easing.currentIndexChanged.connect(self._emit_component_settings)
        self.hit_padding = QDoubleSpinBox(self)
        self.hit_padding.setRange(0.0, 500.0)
        self.hit_padding.setSingleStep(1.0)
        self.hit_padding.setSuffix(" px")
        self.hit_padding.valueChanged.connect(self._emit_component_settings)

        form = QFormLayout()
        form.addRow("Preview State", self.state)
        form.addRow("Scale", self.scale)
        form.addRow("Offset X", self.offset_x)
        form.addRow("Offset Y", self.offset_y)
        form.addRow("Rotation", self.rotation)
        form.addRow("Opacity", self.opacity)
        form.addRow("Transition", self.duration)
        form.addRow("Easing", self.easing)
        form.addRow("Hit Padding", self.hit_padding)

        hint = QLabel(
            "Pointer enter/down/up/leave and focus triggers are stored with the component. "
            "The selected state is used by preview and export.",
            self,
        )
        hint.setWordWrap(True)
        hint.setObjectName("MotionHint")

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addLayout(commands)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.set_layer(None)

    def _offset_spin(self) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(-10000.0, 10000.0)
        control.setSingleStep(1.0)
        control.setSuffix(" px")
        control.valueChanged.connect(self._emit_style)
        return control

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        component = button_component(layer) if layer is not None else None
        has_layer = layer is not None
        has_component = component is not None
        self.create_button.setEnabled(has_layer and not has_component)
        self.remove_button.setEnabled(has_component)
        for control in (
            self.state,
            self.scale,
            self.offset_x,
            self.offset_y,
            self.rotation,
            self.opacity,
            self.duration,
            self.easing,
            self.hit_padding,
        ):
            control.setEnabled(has_component)
        if component is not None:
            self.state.setCurrentIndex(self.state.findData(component.active_state))
            style = component.states[component.active_state]
            self.scale.setValue(float(style.scale_multiplier[0]))
            self.offset_x.setValue(float(style.position_offset[0]))
            self.offset_y.setValue(float(style.position_offset[1]))
            self.rotation.setValue(float(style.rotation_offset))
            self.opacity.setValue(float(style.opacity_multiplier))
            self.duration.setValue(int(component.transition_duration_ms))
            self.easing.setCurrentIndex(self.easing.findData(component.easing))
            self.hit_padding.setValue(float(component.hit_padding))
            self.summary.setText(
                f"{layer.name} is an interactive button. Edit each preview state independently."
            )
        elif layer is not None:
            self.summary.setText(
                f"Convert {layer.name} into a button with Normal, Hover, Pressed, Disabled, and Focused states."
            )
        else:
            self.summary.setText("Select a layer or group to create a button component.")
        self._loading = False

    def _emit_state(self) -> None:
        if self._loading:
            return
        self.state_changed.emit(str(self.state.currentData() or "normal"))

    def _emit_style(self) -> None:
        if self._loading:
            return
        self.settings_changed.emit({
            "state": str(self.state.currentData() or "normal"),
            "state_style": {
                "position_offset": [self.offset_x.value(), self.offset_y.value()],
                "scale_multiplier": [self.scale.value(), self.scale.value()],
                "rotation_offset": self.rotation.value(),
                "opacity_multiplier": self.opacity.value(),
            },
        })

    def _emit_component_settings(self) -> None:
        if self._loading:
            return
        self.settings_changed.emit({
            "transition_duration_ms": self.duration.value(),
            "easing": str(self.easing.currentData() or "ease_out"),
            "hit_padding": self.hit_padding.value(),
        })


__all__ = ["ButtonComponentPanel"]
