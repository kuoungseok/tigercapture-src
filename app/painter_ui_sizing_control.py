"""Compact Figma-style Fixed/Hug/Fill selector for Painter UI."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton


class PainterUISizingControl(QFrame):
    value_changed = Signal(str)

    def __init__(self, axis: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUISizingControl")
        self.setStyleSheet(
            """
            QFrame#PainterUISizingControl {
                background: transparent;
            }
            QLabel#PainterUISizingAxis {
                color: #8F9BAA;
                font-size: 10px;
                font-weight: 700;
            }
            QPushButton#PainterUISizingOption {
                min-width: 38px;
                padding: 2px 5px;
                border: 1px solid #313A47;
                border-radius: 3px;
                background: #161C24;
                color: #AEB9C8;
                font-size: 10px;
            }
            QPushButton#PainterUISizingOption:hover {
                border-color: #506079;
                color: #EEF4FC;
            }
            QPushButton#PainterUISizingOption:checked {
                border-color: #6B9BE5;
                background: #254C7D;
                color: #F4F8FF;
            }
            QPushButton#PainterUISizingOption:disabled {
                border-color: #252B34;
                background: #13171D;
                color: #596371;
            }
            """
        )
        self._value = "fixed"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        axis_label = QLabel(str(axis).upper())
        axis_label.setObjectName("PainterUISizingAxis")
        axis_label.setMinimumWidth(14)
        layout.addWidget(axis_label)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for label, value, tooltip in (
            ("Fixed", "fixed", "Keep the explicit object size"),
            ("Hug", "hug", "Resize to fit Auto Layout content"),
            ("Fill", "fill", "Fill available space in the parent"),
        ):
            button = QPushButton(label)
            button.setObjectName("PainterUISizingOption")
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setMinimumHeight(24)
            button.clicked.connect(
                lambda checked=False, selected=value: self._choose(
                    selected,
                    checked,
                )
            )
            self._group.addButton(button)
            self._buttons[value] = button
            layout.addWidget(button, 1)
        self.set_value("fixed")

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        normalized = str(value or "fixed").strip().casefold()
        if normalized not in self._buttons:
            normalized = "fixed"
        self._value = normalized
        self._buttons[normalized].setChecked(True)

    def set_option_enabled(self, value: str, enabled: bool) -> None:
        button = self._buttons.get(str(value))
        if button is not None:
            button.setEnabled(bool(enabled))

    def option_enabled(self, value: str) -> bool:
        button = self._buttons.get(str(value))
        return bool(button is not None and button.isEnabled())

    def _choose(self, value: str, checked: bool) -> None:
        if not checked:
            self._buttons[self._value].setChecked(True)
            return
        if self._value == value:
            return
        self._value = value
        self.value_changed.emit(value)


__all__ = ["PainterUISizingControl"]
