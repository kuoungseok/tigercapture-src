"""Floating window that hosts the NodeGraphWidget.

Same reparent pattern as the editor's other popouts (color, media
pool, effects library, subtitle). The widget instance is the same
object whether it's docked in the workbench or living in this
window — selection, view position, scene state all carry across
pop-out / dock cycles.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.i18n import tr
from app.style import studio_chrome_qss


class NodeGraphPopoutWindow(QWidget):

    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(tr("workbench.node_graph_popout.title"))
        # Match the workbench dock so the panel feels at home in
        # either context.
        self.setStyleSheet(studio_chrome_qss("QWidget { background-color: #0B0D16; }"))
        # Roughly DaVinci Color Page proportions — wide enough for a
        # 6-node serial chain at default zoom.
        self.resize(900, 560)
        self.setMinimumSize(480, 320)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def install(self, host: QWidget) -> None:
        self._layout.addWidget(host)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)
