"""Transient zoom controls for the Painter UI Design canvas."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size


class PainterUIZoomPopover(QFrame):
    zoom_requested = Signal(float)
    fit_requested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIZoomPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(7, 7, 7, 7)
        root.setSpacing(5)

        self.percent_spin = QSpinBox()
        self.percent_spin.setObjectName("PainterUIZoomPercent")
        self.percent_spin.setRange(3, 800)
        self.percent_spin.setSuffix("%")
        self.percent_spin.setKeyboardTracking(False)
        self.percent_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.percent_spin.editingFinished.connect(self._emit_zoom)
        root.addWidget(self.percent_spin)

        fit_row = QHBoxLayout()
        fit_row.setContentsMargins(0, 0, 0, 0)
        fit_row.setSpacing(3)
        self.fit_buttons: dict[str, QPushButton] = {}
        for label, mode, icon_name in (
            ("Fit all artboards", "all", "zoom-fit"),
            ("Fit active artboard", "artboard", "fit"),
            ("Fit selection", "selection", "ui-frame"),
        ):
            button = QPushButton("")
            button.setObjectName("PainterUIZoomFitButton")
            button.setFixedSize(34, 28)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIcon(app_icon(icon_name, size=14, color="#E4E8EE"))
            button.setIconSize(icon_size(14))
            button.clicked.connect(
                lambda _checked=False, value=mode: self.fit_requested.emit(
                    value
                )
            )
            fit_row.addWidget(button)
            self.fit_buttons[mode] = button
        root.addLayout(fit_row)
        self.adjustSize()
        self.hide()

    def set_zoom_percent(self, percent: float) -> None:
        value = max(3, min(800, int(round(float(percent)))))
        self.percent_spin.blockSignals(True)
        self.percent_spin.setValue(value)
        self.percent_spin.blockSignals(False)

    def open_above(self, anchor: QWidget) -> None:
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        anchor_top_left = anchor.mapTo(parent, anchor.rect().topLeft())
        x = anchor_top_left.x() + (anchor.width() - self.width()) // 2
        x = max(8, min(x, parent.width() - self.width() - 8))
        y = max(8, anchor_top_left.y() - self.height() - 7)
        self.move(x, y)
        self.show()
        self.raise_()
        self.percent_spin.setFocus(Qt.FocusReason.PopupFocusReason)
        self.percent_spin.selectAll()

    def _emit_zoom(self) -> None:
        self.zoom_requested.emit(float(self.percent_spin.value()))


__all__ = ["PainterUIZoomPopover"]
