from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget


class CountdownOverlay(QWidget):
    """Large centered countdown displayed before region selection.

    Shows ``N → N-1 → ... → 1`` (one second each) on the primary screen,
    then emits ``finished`` signal and closes itself.
    """

    finished = Signal()

    def __init__(self, seconds: int) -> None:
        super().__init__()
        self._remaining = max(1, int(seconds))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        primary = QGuiApplication.primaryScreen()
        self.setScreen(primary)
        geom = primary.geometry()
        size = 260
        self.setGeometry(
            geom.x() + (geom.width() - size) // 2,
            geom.y() + (geom.height() - size) // 2,
            size,
            size,
        )

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self.show()
        self._timer.start()

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.finished.emit()
            self.close()
            return
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        painter.drawRoundedRect(rect, 24, 24)

        pen = QPen(QColor(0, 103, 192))
        pen.setWidth(6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 22, 22)

        font = QFont()
        font.setPointSize(120)
        font.setWeight(QFont.Weight.Black)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self._remaining))
