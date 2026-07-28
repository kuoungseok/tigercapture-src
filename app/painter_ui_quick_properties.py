"""Canvas-overlay host for a temporarily expanded UI inspector."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


class PainterUIQuickPropertiesPopover(QFrame):
    """Hosts the canonical inspector without creating another mutation UI."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIQuickPropertiesPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PainterUIQuickPropertiesScroll")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        layout.addWidget(self.scroll_area, 1)
        self._widget: QWidget | None = None
        parent.installEventFilter(self)
        self.hide()

    def attach(self, widget: QWidget) -> None:
        if self._widget is widget:
            self.place()
            self.show()
            self.raise_()
            return
        if self._widget is not None:
            self.take()
        self._widget = widget
        widget.setMinimumWidth(0)
        widget.setMinimumHeight(max(360, widget.sizeHint().height()))
        self.scroll_area.setWidget(widget)
        self.place()
        self.show()
        self.raise_()
        widget.show()

    def take(self) -> QWidget | None:
        widget = self._widget
        if widget is not None:
            self.scroll_area.takeWidget()
            widget.setMinimumHeight(0)
            widget.setMaximumWidth(16777215)
            widget.setParent(None)
        self._widget = None
        self.hide()
        return widget

    def contains(self, widget: QWidget) -> bool:
        return self._widget is widget

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(320, max(260, parent.width() - 24))
        # Keep the canvas-local floating toolbar and status edge unobstructed.
        height = min(620, max(240, parent.height() - 140))
        self.setGeometry(
            max(8, parent.width() - width - 12),
            12,
            width,
            height,
        )
        if self._widget is not None:
            viewport_width = max(0, self.scroll_area.viewport().width())
            if viewport_width:
                self._widget.setMaximumWidth(viewport_width)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.parentWidget() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self.place()
        return super().eventFilter(watched, event)


__all__ = ["PainterUIQuickPropertiesPopover"]
