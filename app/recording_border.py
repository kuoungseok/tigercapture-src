from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QScreen
from PySide6.QtWidgets import QWidget


BORDER_COLOR = QColor(255, 40, 40)
BORDER_WIDTH = 4
BORDER_OFFSET = 3  # paint outside the capture rect so it doesn't end up in frames


class _BorderWindow(QWidget):
    def __init__(self, screen: QScreen, global_rect: QRect) -> None:
        super().__init__()
        self._screen = screen
        self._global_rect = global_rect

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
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def paintEvent(self, _event) -> None:
        screen_rect = self._screen.geometry()
        clipped = self._global_rect.intersected(screen_rect)
        if clipped.isEmpty():
            return

        origin = screen_rect.topLeft()
        local = QRect(
            clipped.x() - origin.x(),
            clipped.y() - origin.y(),
            clipped.width(),
            clipped.height(),
        )
        outer = local.adjusted(-BORDER_OFFSET, -BORDER_OFFSET,
                               BORDER_OFFSET - 1, BORDER_OFFSET - 1)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        pen = QPen(BORDER_COLOR)
        pen.setWidth(BORDER_WIDTH)
        pen.setStyle(Qt.PenStyle.SolidLine)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(outer)


class RecordingBorderOverlay:
    """Shows a red dashed border around a global rect across all monitors it
    intersects. The border is drawn *outside* the rect so it does not appear
    in mss captures of the rect itself."""

    def __init__(self, global_rect: QRect) -> None:
        self._windows: list[_BorderWindow] = []
        for screen in QGuiApplication.screens():
            if screen.geometry().intersects(global_rect):
                win = _BorderWindow(screen, global_rect)
                win.show()
                self._windows.append(win)

    def close(self) -> None:
        for w in self._windows:
            w.close()
        self._windows.clear()
