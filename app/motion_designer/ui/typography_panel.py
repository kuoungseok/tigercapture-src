from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFontComboBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from app.motion_designer.schema import MotionLayer
from app.motion_designer.vector_shapes import default_pen_path


def _default(value, fallback):
    if isinstance(value, Mapping) and ("default" in value or "keyframes" in value):
        return value.get("default", fallback)
    return fallback if value is None else value


class TypographyPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionTypographyPanel")
        self._loading = False
        self._params: dict = {}
        self._animators: list[dict] = []
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

        self.text = QPlainTextEdit(self)
        self.text.setMaximumHeight(78)
        self.font = QFontComboBox(self)
        self.size = QSpinBox(self)
        self.size.setRange(1, 1000)
        self.weight = QSpinBox(self)
        self.weight.setRange(100, 900)
        self.weight.setSingleStep(100)
        self.fill = QPushButton(self)
        self.alignment = QComboBox(self)
        self.alignment.addItems(["left", "center", "right"])
        self.letter_spacing = self._spin(0, 1000, .5)
        self.line_height = self._spin(.5, 4, .05)
        form.addRow("Text", self.text)
        form.addRow("Font", self.font)
        form.addRow("Size", self.size)
        form.addRow("Weight", self.weight)
        form.addRow("Fill", self.fill)
        form.addRow("Alignment", self.alignment)
        form.addRow("Tracking", self.letter_spacing)
        form.addRow("Line Height", self.line_height)

        axes = QLabel("Variable Font", self)
        axes.setObjectName("MotionInspectorSection")
        form.addRow(axes)
        self.axis_weight = self._spin(1, 1000, 1)
        self.axis_width = self._spin(25, 200, 1)
        form.addRow("wght", self.axis_weight)
        form.addRow("wdth", self.axis_width)

        animation = QLabel("Text Animation", self)
        animation.setObjectName("MotionInspectorSection")
        form.addRow(animation)
        animator_row = QWidget(self)
        animator_layout = QHBoxLayout(animator_row)
        animator_layout.setContentsMargins(0, 0, 0, 0)
        animator_layout.setSpacing(4)
        self.animator_list = QComboBox(animator_row)
        self.animator_add = QPushButton("+", animator_row)
        self.animator_add.setToolTip("Add Text Animator")
        self.animator_remove = QPushButton("-", animator_row)
        self.animator_remove.setToolTip("Remove selected Text Animator")
        for button in (self.animator_add, self.animator_remove):
            button.setFixedWidth(28)
        animator_layout.addWidget(self.animator_list, 1)
        animator_layout.addWidget(self.animator_add)
        animator_layout.addWidget(self.animator_remove)
        form.addRow("Animators", animator_row)
        self.in_animation = self._combo([
            "none", "fade-in", "slide-up-in", "pop-in", "typewriter-in",
            "bounce-in", "fold-paper-in", "wave-in", "cascade-in",
        ])
        self.hold_animation = self._combo([
            "none", "hold-wave", "hold-bob", "hold-pulse", "hold-sway", "hold-glitch",
        ])
        self.out_animation = self._combo([
            "none", "fade-out", "slide-up-out", "pop-out", "burst-out", "dissolve-out",
        ])
        self.in_duration = QSpinBox(self)
        self.in_duration.setRange(0, 60000)
        self.out_duration = QSpinBox(self)
        self.out_duration.setRange(0, 60000)
        self.unit = self._combo(["character", "word", "line"])
        self.stagger = QSpinBox(self)
        self.stagger.setRange(0, 10000)
        self.selector_start = self._spin(0, 1, .01)
        self.selector_end = self._spin(0, 1, .01)
        self.selector_offset = self._spin(-1, 1, .01)
        self.selector_smoothness = self._spin(0, 1, .05)
        self.selector_shape = self._combo([
            "square", "ramp_up", "ramp_down", "triangle", "round",
        ])
        self.selector_amount = self._spin(0, 1, .05)
        self.reverse = QCheckBox("Reverse order", self)
        self.randomize = QCheckBox("Random order", self)
        self.ping_pong = QCheckBox("Ping-pong order", self)
        form.addRow("IN", self.in_animation)
        form.addRow("IN Duration (ms)", self.in_duration)
        form.addRow("HOLD", self.hold_animation)
        form.addRow("OUT", self.out_animation)
        form.addRow("OUT Duration (ms)", self.out_duration)
        form.addRow("Selector", self.unit)
        form.addRow("Stagger (ms)", self.stagger)
        form.addRow("Range Start", self.selector_start)
        form.addRow("Range End", self.selector_end)
        form.addRow("Range Offset", self.selector_offset)
        form.addRow("Smoothness", self.selector_smoothness)
        form.addRow("Shape", self.selector_shape)
        form.addRow("Amount", self.selector_amount)
        form.addRow(self.reverse)
        form.addRow(self.randomize)
        form.addRow(self.ping_pong)

        properties = QLabel("Per-glyph Properties", self)
        properties.setObjectName("MotionInspectorSection")
        form.addRow(properties)
        self.glyph_x = self._spin(-2000, 2000, 1)
        self.glyph_y = self._spin(-2000, 2000, 1)
        self.glyph_scale_x = self._spin(0, 10, .05)
        self.glyph_scale_y = self._spin(0, 10, .05)
        self.glyph_rotation = self._spin(-3600, 3600, 1)
        self.glyph_opacity = self._spin(0, 1, .05)
        self.glyph_tracking = self._spin(-1000, 1000, .5)
        self.glyph_blur = self._spin(0, 32, .5)
        self.glyph_fill = QLineEdit(self)
        form.addRow("Position X", self.glyph_x)
        form.addRow("Position Y", self.glyph_y)
        form.addRow("Scale X", self.glyph_scale_x)
        form.addRow("Scale Y", self.glyph_scale_y)
        form.addRow("Rotation", self.glyph_rotation)
        form.addRow("Opacity", self.glyph_opacity)
        form.addRow("Tracking", self.glyph_tracking)
        form.addRow("Blur", self.glyph_blur)
        form.addRow("Fill override", self.glyph_fill)

        path_section = QLabel("Text Path", self)
        path_section.setObjectName("MotionInspectorSection")
        form.addRow(path_section)
        self.follow_path = QCheckBox("Follow path", self)
        self.path_offset = self._spin(0, 1, .01)
        self.reset_path = QPushButton("Reset curve", self)
        form.addRow(self.follow_path)
        form.addRow("Offset", self.path_offset)
        form.addRow(self.reset_path)

        self.text.textChanged.connect(self._emit_style)
        self.font.currentFontChanged.connect(self._emit_style)
        for control in (
            self.size, self.weight, self.alignment, self.letter_spacing, self.line_height,
        ):
            signal = control.currentTextChanged if isinstance(control, QComboBox) else control.valueChanged
            signal.connect(lambda _value: self._emit_style())
        self.fill.clicked.connect(self._choose_fill)
        self.axis_weight.valueChanged.connect(lambda _value: self._emit_axes())
        self.axis_width.valueChanged.connect(lambda _value: self._emit_axes())
        for control in (
            self.in_animation, self.hold_animation, self.out_animation, self.unit,
            self.selector_shape,
        ):
            control.currentTextChanged.connect(lambda _value: self._emit_animation())
        for control in (
            self.in_duration, self.out_duration, self.stagger,
            self.selector_start, self.selector_end, self.selector_offset,
            self.selector_smoothness, self.selector_amount,
            self.glyph_x, self.glyph_y,
            self.glyph_scale_x, self.glyph_scale_y, self.glyph_rotation,
            self.glyph_opacity, self.glyph_tracking, self.glyph_blur,
        ):
            control.valueChanged.connect(lambda _value: self._emit_animation())
        self.reverse.toggled.connect(lambda _value: self._emit_animation())
        self.randomize.toggled.connect(lambda _value: self._emit_animation())
        self.ping_pong.toggled.connect(lambda _value: self._emit_animation())
        self.glyph_fill.editingFinished.connect(self._emit_animation)
        self.animator_list.currentIndexChanged.connect(self._select_animator)
        self.animator_add.clicked.connect(self._add_animator)
        self.animator_remove.clicked.connect(self._remove_animator)
        self.follow_path.toggled.connect(self._toggle_path)
        self.path_offset.valueChanged.connect(self._emit_path_offset)
        self.reset_path.clicked.connect(self._reset_path)

    def _spin(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        return control

    def _combo(self, values: list[str]) -> QComboBox:
        control = QComboBox(self)
        control.addItems(values)
        return control

    def set_layer(self, layer: MotionLayer | None) -> None:
        enabled = layer is not None and layer.layer_type == "text"
        self.setEnabled(enabled)
        self._loading = True
        self._params = dict(layer.source.params) if enabled else {}
        self.text.setPlainText(str(_default(self._params.get("text"), "")))
        family = str(_default(self._params.get("font_family"), "Noto Sans KR"))
        self.font.setCurrentFont(QFont(family))
        self.size.setValue(int(_default(self._params.get("font_size"), 72)))
        self.weight.setValue(int(_default(self._params.get("font_weight"), 700)))
        self.alignment.setCurrentText(str(_default(self._params.get("alignment"), "center")))
        self.letter_spacing.setValue(float(_default(self._params.get("letter_spacing"), 0.0)))
        self.line_height.setValue(float(_default(self._params.get("line_height"), 1.2)))
        self._set_color(str(_default(self._params.get("fill"), "#ffffff")))
        font_axes = _default(self._params.get("font_axes"), {})
        font_axes = font_axes if isinstance(font_axes, Mapping) else {}
        self.axis_weight.setValue(float(font_axes.get("wght", self.weight.value())))
        self.axis_width.setValue(float(font_axes.get("wdth", 100.0)))
        config = _default(self._params.get("text_animation"), {})
        config = config if isinstance(config, Mapping) else {}
        stored_animators = _default(self._params.get("text_animators"), [])
        self._animators = [
            dict(value) for value in stored_animators
            if isinstance(value, Mapping)
        ] if isinstance(stored_animators, list) else []
        self.animator_list.clear()
        self.animator_list.addItem("Legacy Animator")
        for index, animator in enumerate(self._animators):
            self.animator_list.addItem(
                str(animator.get("name") or f"Animator {index + 1}"),
            )
        if self._animators:
            self.animator_list.setCurrentIndex(1)
            config = self._animators[0]
        self._load_animation_config(config)
        self.animator_remove.setEnabled(bool(self._animators))
        has_path = isinstance(_default(self._params.get("text_path"), None), Mapping)
        self.follow_path.setChecked(has_path)
        self.path_offset.setValue(float(_default(self._params.get("text_path_offset"), .5) or 0.0))
        self.path_offset.setEnabled(has_path)
        self.reset_path.setEnabled(has_path)
        self._loading = False

    def _load_animation_config(self, config: Mapping[str, object]) -> None:
        self.in_animation.setCurrentText(str(config.get("in") or "none"))
        self.hold_animation.setCurrentText(str(config.get("hold") or "none"))
        self.out_animation.setCurrentText(str(config.get("out") or "none"))
        self.in_duration.setValue(int(config.get("in_duration_ms", 700) or 0))
        self.out_duration.setValue(int(config.get("out_duration_ms", 500) or 0))
        self.unit.setCurrentText(str(config.get("unit") or "character"))
        self.stagger.setValue(int(config.get("stagger_ms", 35) or 0))
        self.selector_start.setValue(float(config.get("selector_start", 0.0) or 0.0))
        self.selector_end.setValue(float(config.get("selector_end", 1.0) if config.get("selector_end", 1.0) is not None else 1.0))
        self.selector_offset.setValue(float(config.get("selector_offset", 0.0) or 0.0))
        self.selector_smoothness.setValue(float(config.get("smoothness", 0.0) or 0.0))
        self.selector_shape.setCurrentText(str(config.get("selector_shape") or "square"))
        self.selector_amount.setValue(float(config.get("selector_amount", 1.0) or 0.0))
        self.reverse.setChecked(bool(config.get("reverse", False)))
        self.randomize.setChecked(bool(config.get("randomize_order", False)))
        self.ping_pong.setChecked(bool(config.get("ping_pong", False)))
        properties = config.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        position = list(properties.get("position") or [0.0, 0.0])
        scale = list(properties.get("scale") or [1.0, 1.0])
        self.glyph_x.setValue(float(position[0] if position else 0.0))
        self.glyph_y.setValue(float(position[1] if len(position) > 1 else 0.0))
        self.glyph_scale_x.setValue(float(scale[0] if scale else 1.0))
        self.glyph_scale_y.setValue(float(scale[1] if len(scale) > 1 else 1.0))
        self.glyph_rotation.setValue(float(properties.get("rotation", 0.0) or 0.0))
        self.glyph_opacity.setValue(float(properties.get("opacity", 1.0) or 0.0))
        self.glyph_tracking.setValue(float(properties.get("tracking", 0.0) or 0.0))
        self.glyph_blur.setValue(float(properties.get("blur", 0.0) or 0.0))
        self.glyph_fill.setText(str(properties.get("fill") or ""))

    def _emit_style(self) -> None:
        if self._loading:
            return
        self.source_changed.emit({
            "text": self.text.toPlainText(), "font_family": self.font.currentFont().family(),
            "font_size": self.size.value(), "font_weight": self.weight.value(),
            "alignment": self.alignment.currentText(),
            "letter_spacing": self.letter_spacing.value(), "line_height": self.line_height.value(),
        })

    def _emit_axes(self) -> None:
        if not self._loading:
            self.source_changed.emit({"font_axes": {
                "wght": self.axis_weight.value(), "wdth": self.axis_width.value(),
            }})

    def _animation_value(self) -> dict:
        return {
            "in": self.in_animation.currentText(), "hold": self.hold_animation.currentText(),
            "out": self.out_animation.currentText(), "in_duration_ms": self.in_duration.value(),
            "out_duration_ms": self.out_duration.value(), "unit": self.unit.currentText(),
            "stagger_ms": self.stagger.value(), "selector_start": self.selector_start.value(),
            "selector_end": self.selector_end.value(), "reverse": self.reverse.isChecked(),
            "selector_offset": self.selector_offset.value(),
            "smoothness": self.selector_smoothness.value(),
            "selector_shape": self.selector_shape.currentText(),
            "selector_amount": self.selector_amount.value(),
            "randomize_order": self.randomize.isChecked(),
            "ping_pong": self.ping_pong.isChecked(),
            "properties": {
                "position": [self.glyph_x.value(), self.glyph_y.value()],
                "scale": [self.glyph_scale_x.value(), self.glyph_scale_y.value()],
                "rotation": self.glyph_rotation.value(),
                "opacity": self.glyph_opacity.value(),
                "tracking": self.glyph_tracking.value(),
                "blur": self.glyph_blur.value(),
                "fill": self.glyph_fill.text().strip() or None,
            },
            "intensity": 1.0,
        }

    def _emit_animation(self) -> None:
        if self._loading:
            return
        index = self.animator_list.currentIndex() - 1
        if 0 <= index < len(self._animators):
            current = self._animators[index]
            self._animators[index] = {
                **current,
                **self._animation_value(),
            }
            self.source_changed.emit({"text_animators": list(self._animators)})
        else:
            self.source_changed.emit({"text_animation": self._animation_value()})

    def _select_animator(self, combo_index: int) -> None:
        if self._loading:
            return
        index = int(combo_index) - 1
        config = (
            self._animators[index]
            if 0 <= index < len(self._animators)
            else _default(self._params.get("text_animation"), {})
        )
        self._loading = True
        self._load_animation_config(config if isinstance(config, Mapping) else {})
        self._loading = False
        self.animator_remove.setEnabled(0 <= index < len(self._animators))

    def _add_animator(self) -> None:
        if self._loading:
            return
        from uuid import uuid4

        animator = {
            "id": f"animator_{uuid4().hex[:10]}",
            "name": f"Animator {len(self._animators) + 1}",
            "enabled": True,
            **self._animation_value(),
        }
        self._animators.append(animator)
        self.animator_list.addItem(animator["name"])
        self.animator_list.setCurrentIndex(len(self._animators))
        self.source_changed.emit({"text_animators": list(self._animators)})

    def _remove_animator(self) -> None:
        index = self.animator_list.currentIndex() - 1
        if not 0 <= index < len(self._animators):
            return
        self._animators.pop(index)
        self.animator_list.removeItem(index + 1)
        self.animator_list.setCurrentIndex(min(index + 1, len(self._animators)))
        self.source_changed.emit({"text_animators": list(self._animators)})

    def _path_payload(self) -> tuple[float, float, dict]:
        width = max(160.0, float(_default(self._params.get("width"), 640.0) or 640.0))
        height = max(100.0, float(_default(self._params.get("height"), 240.0) or 240.0))
        return width, height, default_pen_path(width, height).to_dict()

    def _toggle_path(self, enabled: bool) -> None:
        self.path_offset.setEnabled(enabled)
        self.reset_path.setEnabled(enabled)
        if self._loading:
            return
        if enabled:
            existing = _default(self._params.get("text_path"), None)
            if isinstance(existing, Mapping) and existing.get("points"):
                self.source_changed.emit({
                    "text_path": dict(existing),
                    "text_path_offset": self.path_offset.value(),
                })
                return
            width, height, path = self._path_payload()
            self._params.update({"width": width, "height": height, "text_path": path})
            self.source_changed.emit({
                "width": width,
                "height": height,
                "text_path": path,
                "text_path_offset": self.path_offset.value(),
            })
        else:
            self._params["text_path"] = None
            self.source_changed.emit({"text_path": None})

    def _emit_path_offset(self, value: float) -> None:
        if not self._loading and self.follow_path.isChecked():
            self._params["text_path_offset"] = float(value)
            self.source_changed.emit({"text_path_offset": float(value)})

    def _reset_path(self) -> None:
        if self._loading or not self.follow_path.isChecked():
            return
        width, height, path = self._path_payload()
        self._params.update({"width": width, "height": height, "text_path": path})
        self.source_changed.emit({
            "width": width,
            "height": height,
            "text_path": path,
            "text_path_offset": self.path_offset.value(),
        })

    def _choose_fill(self) -> None:
        current = QColor(str(self._params.get("fill") or "#ffffff"))
        color = QColorDialog.getColor(current, self, "Choose text color", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            value = color.name(QColor.HexArgb)
            self._params["fill"] = value
            self._set_color(value)
            self.source_changed.emit({"fill": value})

    def _set_color(self, value: str) -> None:
        color = QColor(value)
        self.fill.setText(value)
        if color.isValid():
            foreground = "#111111" if color.lightnessF() > .55 else "#f5f5f5"
            self.fill.setStyleSheet(
                f"background:{color.name(QColor.HexArgb)};color:{foreground};border:1px solid #4a515b;"
            )
