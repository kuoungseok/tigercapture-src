from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QLabel,
    QFrame, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.boolean_layers import would_create_boolean_cycle


def _default(value, fallback):
    if isinstance(value, Mapping) and ("default" in value or "keyframes" in value):
        return value.get("default", fallback)
    return fallback if value is None else value


class VectorPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionVectorPanel")
        self._loading = False
        self._params: dict = {}
        self._layer_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionInspectorScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.viewport().setObjectName("MotionInspectorViewport")
        content = QWidget(self.scroll)
        content.setObjectName("MotionInspectorContent")
        for surface in (self, self.scroll.viewport(), content):
            palette = surface.palette()
            palette.setColor(QPalette.Window, QColor("#121419"))
            palette.setColor(QPalette.Base, QColor("#121419"))
            surface.setPalette(palette)
            surface.setAutoFillBackground(True)
        form = QFormLayout(content)
        form.setContentsMargins(7, 7, 7, 7)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll)

        self.shape = QComboBox(self)
        self.shape.addItems(["rectangle", "ellipse", "polygon", "star", "path"])
        self.sides = QSpinBox(self)
        self.sides.setRange(3, 128)
        self.inner_ratio = self._spin(.01, .99, .01)
        self.radius = self._spin(0, 10000, 1)
        self.stroke_width = self._spin(0, 1000, .5)
        self.fill = QPushButton(self)
        self.fill.setToolTip("Fill color")
        self.stroke = QPushButton(self)
        self.stroke.setToolTip("Stroke color")
        form.addRow("Primitive", self.shape)
        form.addRow("Sides", self.sides)
        form.addRow("Inner Ratio", self.inner_ratio)
        form.addRow("Corner Radius", self.radius)
        form.addRow("Fill", self.fill)
        form.addRow("Stroke", self.stroke)
        form.addRow("Stroke Width", self.stroke_width)

        trim_label = QLabel("Trim Path", self)
        trim_label.setObjectName("MotionInspectorSection")
        form.addRow(trim_label)
        self.trim_start = self._spin(0, 1, .01)
        self.trim_end = self._spin(0, 1, .01)
        self.trim_offset = self._spin(-10, 10, .01)
        form.addRow("Start", self.trim_start)
        form.addRow("End", self.trim_end)
        form.addRow("Offset", self.trim_offset)

        repeater_label = QLabel("Repeater", self)
        repeater_label.setObjectName("MotionInspectorSection")
        form.addRow(repeater_label)
        self.repeat_count = QSpinBox(self)
        self.repeat_count.setRange(1, 512)
        self.repeat_x = self._spin(-100000, 100000, 1)
        self.repeat_y = self._spin(-100000, 100000, 1)
        self.repeat_rotation = self._spin(-36000, 36000, .5)
        self.repeat_scale_x = self._spin(-10, 10, .01)
        self.repeat_scale_y = self._spin(-10, 10, .01)
        self.repeat_opacity = self._spin(0, 1, .01)
        form.addRow("Copies", self.repeat_count)
        form.addRow("Offset X", self.repeat_x)
        form.addRow("Offset Y", self.repeat_y)
        form.addRow("Rotation", self.repeat_rotation)
        form.addRow("Scale X", self.repeat_scale_x)
        form.addRow("Scale Y", self.repeat_scale_y)
        form.addRow("End Opacity", self.repeat_opacity)

        boolean_label = QLabel("Boolean", self)
        boolean_label.setObjectName("MotionInspectorSection")
        form.addRow(boolean_label)
        self.boolean_operation = QComboBox(self)
        self.boolean_operation.addItems(["none", "union", "subtract", "intersect", "exclude"])
        self.boolean_operands = QListWidget(self)
        self.boolean_operands.setMinimumHeight(72)
        self.boolean_operands.setMaximumHeight(116)
        self.boolean_operands.setToolTip("Linked shape operands")
        self.boolean_hide_operands = QCheckBox(self)
        self.boolean_hide_operands.setChecked(True)
        form.addRow("Operation", self.boolean_operation)
        form.addRow("Operands", self.boolean_operands)
        form.addRow("Hide Operands", self.boolean_hide_operands)

        self.shape.currentTextChanged.connect(lambda value: self._emit_simple("shape", value))
        self.sides.valueChanged.connect(lambda value: self._emit_simple("sides", int(value)))
        self.inner_ratio.valueChanged.connect(lambda value: self._emit_simple("inner_ratio", value))
        self.radius.valueChanged.connect(lambda value: self._emit_simple("radius", value))
        self.stroke_width.valueChanged.connect(lambda value: self._emit_simple("stroke_width", value))
        self.fill.clicked.connect(lambda: self._choose_color("fill", self.fill))
        self.stroke.clicked.connect(lambda: self._choose_color("stroke", self.stroke))
        for control in (self.trim_start, self.trim_end, self.trim_offset):
            control.valueChanged.connect(lambda _value: self._emit_trim())
        for control in (
            self.repeat_count, self.repeat_x, self.repeat_y, self.repeat_rotation,
            self.repeat_scale_x, self.repeat_scale_y, self.repeat_opacity,
        ):
            control.valueChanged.connect(lambda _value: self._emit_repeater())
        self.boolean_operation.currentTextChanged.connect(lambda _value: self._emit_boolean())
        self.boolean_operands.itemChanged.connect(lambda _item: self._emit_boolean())
        self.boolean_hide_operands.toggled.connect(lambda _checked: self._emit_boolean())

    def _spin(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        return control

    def set_layer(self, layer: MotionLayer | None, composition: MotionComposition | None = None) -> None:
        enabled = layer is not None and layer.layer_type == "shape"
        self.setEnabled(enabled)
        self._loading = True
        self._layer_id = layer.id if enabled else ""
        self._params = dict(layer.source.params) if enabled else {}
        shape = str(_default(self._params.get("shape"), "rectangle"))
        self.shape.setCurrentText(shape if self.shape.findText(shape) >= 0 else "rectangle")
        self.sides.setValue(int(_default(self._params.get("sides"), 5)))
        self.inner_ratio.setValue(float(_default(self._params.get("inner_ratio"), .45)))
        self.radius.setValue(float(_default(self._params.get("radius"), 0.0)))
        self.stroke_width.setValue(float(_default(self._params.get("stroke_width"), 2.0)))
        self._set_color_button(self.fill, str(_default(self._params.get("fill"), "#3f8fba")))
        self._set_color_button(self.stroke, str(_default(self._params.get("stroke"), "#20242b")))
        trim = _default(self._params.get("trim"), {})
        trim = trim if isinstance(trim, Mapping) else {}
        self.trim_start.setValue(float(trim.get("start", 0.0) or 0.0))
        self.trim_end.setValue(float(trim.get("end", 1.0) if trim.get("end", 1.0) is not None else 1.0))
        self.trim_offset.setValue(float(trim.get("offset", 0.0) or 0.0))
        repeater = _default(self._params.get("repeater"), {})
        repeater = repeater if isinstance(repeater, Mapping) else {}
        offset = list(repeater.get("offset") or [0.0, 0.0])
        scale = list(repeater.get("scale") or [1.0, 1.0])
        self.repeat_count.setValue(int(repeater.get("count", 1) or 1))
        self.repeat_x.setValue(float(offset[0]))
        self.repeat_y.setValue(float(offset[1]))
        self.repeat_rotation.setValue(float(repeater.get("rotation", 0.0) or 0.0))
        self.repeat_scale_x.setValue(float(scale[0]))
        self.repeat_scale_y.setValue(float(scale[1]))
        self.repeat_opacity.setValue(float(repeater.get("opacity_end", 1.0) or 0.0))
        boolean = _default(self._params.get("boolean"), {})
        boolean = boolean if isinstance(boolean, Mapping) else {}
        operand_ids = {str(value) for value in boolean.get("operand_layer_ids", [])}
        has_boolean = bool(boolean) and str(boolean.get("operation") or "none") != "none"
        operation = str(boolean.get("operation") or "union") if has_boolean else "none"
        self.boolean_operation.setCurrentText(
            operation if self.boolean_operation.findText(operation) >= 0 else "union"
        )
        self.boolean_hide_operands.setChecked(bool(boolean.get("hide_operands", True)))
        self.boolean_operands.clear()
        if composition is not None:
            for candidate in reversed(composition.layers):
                if (
                    candidate.layer_type != "shape"
                    or would_create_boolean_cycle(composition, self._layer_id, candidate.id)
                ):
                    continue
                row = QListWidgetItem(candidate.name)
                row.setData(Qt.UserRole, candidate.id)
                row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
                row.setCheckState(Qt.Checked if candidate.id in operand_ids else Qt.Unchecked)
                self.boolean_operands.addItem(row)
        self._loading = False
        self._update_visibility()

    def _emit_simple(self, key: str, value) -> None:
        if self._loading:
            return
        self._params[key] = value
        self._update_visibility()
        self.source_changed.emit({key: value})

    def _emit_trim(self) -> None:
        if not self._loading:
            value = {"start": self.trim_start.value(), "end": self.trim_end.value(),
                     "offset": self.trim_offset.value()}
            self._params["trim"] = value
            self.source_changed.emit({"trim": value})

    def _emit_repeater(self) -> None:
        if not self._loading:
            value = {
                "count": self.repeat_count.value(),
                "offset": [self.repeat_x.value(), self.repeat_y.value()],
                "rotation": self.repeat_rotation.value(),
                "scale": [self.repeat_scale_x.value(), self.repeat_scale_y.value()],
                "opacity_start": 1.0, "opacity_end": self.repeat_opacity.value(),
            }
            self._params["repeater"] = value
            self.source_changed.emit({"repeater": value})

    def _emit_boolean(self) -> None:
        if self._loading:
            return
        operation = self.boolean_operation.currentText()
        if operation == "none":
            self._params["boolean"] = {}
            self.source_changed.emit({"boolean": {}})
            self._update_visibility()
            return
        existing = _default(self._params.get("boolean"), {})
        value = dict(existing) if isinstance(existing, Mapping) else {}
        operand_ids = []
        for index in range(self.boolean_operands.count()):
            item = self.boolean_operands.item(index)
            if item.checkState() == Qt.Checked:
                operand_ids.append(str(item.data(Qt.UserRole) or ""))
        value.update({
            "operation": operation,
            "operand_layer_ids": [layer_id for layer_id in operand_ids if layer_id],
            "hide_operands": self.boolean_hide_operands.isChecked(),
        })
        self._params["boolean"] = value
        self.source_changed.emit({"boolean": value})
        self._update_visibility()

    def _choose_color(self, key: str, button: QPushButton) -> None:
        current = QColor(str(self._params.get(key) or "#ffffff"))
        color = QColorDialog.getColor(current, self, f"Choose {key}", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            value = color.name(QColor.HexArgb)
            self._params[key] = value
            self._set_color_button(button, value)
            self.source_changed.emit({key: value})

    @staticmethod
    def _set_color_button(button: QPushButton, value: str) -> None:
        color = QColor(value)
        button.setText(value)
        if color.isValid():
            foreground = "#111111" if color.lightnessF() > .55 else "#f5f5f5"
            button.setStyleSheet(
                f"background:{color.name(QColor.HexArgb)};color:{foreground};border:1px solid #4a515b;"
            )

    def _update_visibility(self) -> None:
        shape = self.shape.currentText()
        self.sides.setEnabled(shape in {"polygon", "star"})
        self.inner_ratio.setEnabled(shape == "star")
        self.radius.setEnabled(shape == "rectangle")
        boolean_enabled = self.boolean_operation.currentText() != "none"
        self.boolean_operands.setEnabled(boolean_enabled)
        self.boolean_hide_operands.setEnabled(boolean_enabled)
