from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFontComboBox,
    QFormLayout, QFrame, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
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
        self.reverse = QCheckBox("Reverse order", self)
        form.addRow("IN", self.in_animation)
        form.addRow("IN Duration (ms)", self.in_duration)
        form.addRow("HOLD", self.hold_animation)
        form.addRow("OUT", self.out_animation)
        form.addRow("OUT Duration (ms)", self.out_duration)
        form.addRow("Selector", self.unit)
        form.addRow("Stagger (ms)", self.stagger)
        form.addRow("Range Start", self.selector_start)
        form.addRow("Range End", self.selector_end)
        form.addRow(self.reverse)

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
        ):
            control.currentTextChanged.connect(lambda _value: self._emit_animation())
        for control in (
            self.in_duration, self.out_duration, self.stagger,
            self.selector_start, self.selector_end,
        ):
            control.valueChanged.connect(lambda _value: self._emit_animation())
        self.reverse.toggled.connect(lambda _value: self._emit_animation())
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
        self.in_animation.setCurrentText(str(config.get("in") or "none"))
        self.hold_animation.setCurrentText(str(config.get("hold") or "none"))
        self.out_animation.setCurrentText(str(config.get("out") or "none"))
        self.in_duration.setValue(int(config.get("in_duration_ms", 700) or 0))
        self.out_duration.setValue(int(config.get("out_duration_ms", 500) or 0))
        self.unit.setCurrentText(str(config.get("unit") or "character"))
        self.stagger.setValue(int(config.get("stagger_ms", 35) or 0))
        self.selector_start.setValue(float(config.get("selector_start", 0.0) or 0.0))
        self.selector_end.setValue(float(config.get("selector_end", 1.0) if config.get("selector_end", 1.0) is not None else 1.0))
        self.reverse.setChecked(bool(config.get("reverse", False)))
        has_path = isinstance(_default(self._params.get("text_path"), None), Mapping)
        self.follow_path.setChecked(has_path)
        self.path_offset.setValue(float(_default(self._params.get("text_path_offset"), .5) or 0.0))
        self.path_offset.setEnabled(has_path)
        self.reset_path.setEnabled(has_path)
        self._loading = False

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
            "intensity": 1.0,
        }

    def _emit_animation(self) -> None:
        if not self._loading:
            self.source_changed.emit({"text_animation": self._animation_value()})

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
