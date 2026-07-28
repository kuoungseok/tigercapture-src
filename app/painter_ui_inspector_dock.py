"""Resizable and detachable chrome for Painter's UI inspector."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PainterUIInspectorResizeHandle(QFrame):
    """Thin left-edge handle that emits the requested right-panel width."""

    width_requested = Signal(int)

    def __init__(self, panel: QWidget) -> None:
        super().__init__(panel)
        self._panel = panel
        self._press_global_x = 0.0
        self._press_width = 0
        self.setObjectName("PainterUIInspectorResizeHandle")
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setFixedWidth(5)
        panel.installEventFilter(self)
        self._place()

    def _place(self) -> None:
        self.setGeometry(0, 0, self.width(), max(0, self._panel.height()))
        self.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._panel and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._place()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._press_global_x = float(event.globalPosition().x())
        self._press_width = self._panel.width()
        self.setProperty("dragging", True)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            event.ignore()
            return
        delta = float(event.globalPosition().x()) - self._press_global_x
        self.width_requested.emit(round(self._press_width - delta))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()


class PainterUIInspectorDockWindow(QDialog):
    """Floating owner for the canonical inspector widget.

    Closing requests re-docking; it never destroys the inspector.
    """

    dock_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setObjectName("PainterUIInspectorDockWindow")
        self.setWindowTitle("UI Inspector")
        self.setMinimumSize(340, 420)
        self.resize(380, 720)
        self._content_layout = QVBoxLayout(self)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PainterUIInspectorDockScroll")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self._content_layout.addWidget(self.scroll_area, 1)
        self._widget: QWidget | None = None

    def attach(self, widget: QWidget) -> None:
        if self._widget is widget:
            return
        if self._widget is not None:
            self.scroll_area.takeWidget()
        self._widget = widget
        widget.setMinimumWidth(0)
        widget.setMinimumHeight(max(720, widget.sizeHint().height()))
        self.scroll_area.setWidget(widget)
        self._fit_widget_width()
        widget.show()

    def take(self) -> QWidget | None:
        widget = self._widget
        if widget is not None:
            self.scroll_area.takeWidget()
            widget.setMaximumWidth(16777215)
            widget.setMinimumHeight(0)
            widget.setParent(None)
        self._widget = None
        return widget

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_widget_width()

    def _fit_widget_width(self) -> None:
        if self._widget is None:
            return
        width = max(0, self.scroll_area.viewport().width())
        if width > 0:
            self._widget.setMaximumWidth(width)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.dock_requested.emit()


__all__ = [
    "PainterUIInspectorDockWindow",
    "PainterUIInspectorResizeHandle",
]
