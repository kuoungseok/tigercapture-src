from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QGuiApplication, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from app.i18n import tr


BAR_QSS = """
QWidget#RecordingBar {
    background-color: #0a0a0a;
}
QLabel#RecDot { color: #ff3434; font-size: 16px; font-weight: 900; }
QLabel#RecDot[paused="true"] { color: #dddddd; }
QLabel#RecTime { color: #ffffff; font-size: 14px; font-weight: 700; }
QLabel#RecInfo { color: #ffffff; font-size: 11px; }

QPushButton[barBtn="true"] {
    background-color: transparent;
    color: #ffffff;
    border: none;
    padding: 4px 10px;
    font-size: 18px;
    font-weight: 900;
    min-width: 30px;
}
QPushButton[barBtn="true"]:hover {
    background-color: #2a2a2a;
    border-radius: 6px;
}
QPushButton[barBtn="true"]:pressed {
    background-color: #3a3a3a;
}
"""


class RecordingControlBar(QWidget):
    """Small floating control bar shown during recording.

    Positions itself just below the capture region (or above/inside if it
    would not fit), and requests display-affinity exclusion from capture so
    the bar itself is not recorded on Windows 10 2004+."""

    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, region_rect: QRect, fps: int) -> None:
        super().__init__()
        self._region = region_rect
        self._fps = int(fps)
        self._paused = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAutoFillBackground(True)
        self.setObjectName("RecordingBar")
        self.setStyleSheet(BAR_QSS)

        self._build_ui()
        self.adjustSize()
        self._position_near_region()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 10, 6)
        layout.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setObjectName("RecDot")

        self._time_label = QLabel("0:00")
        self._time_label.setObjectName("RecTime")

        self._info_label = QLabel(tr("rec.info", fps=self._fps, count=0))
        self._info_label.setObjectName("RecInfo")

        self._pause_btn = QPushButton("‖")
        self._pause_btn.setProperty("barBtn", True)
        self._pause_btn.setToolTip(tr("rec.tooltip.pause"))
        self._pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pause_btn.clicked.connect(self._on_pause_toggle)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setProperty("barBtn", True)
        self._stop_btn.setToolTip(tr("rec.tooltip.stop"))
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.clicked.connect(self.stop_requested.emit)

        self._cancel_btn = QPushButton("✕")
        self._cancel_btn.setProperty("barBtn", True)
        self._cancel_btn.setToolTip(tr("rec.tooltip.cancel"))
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)

        layout.addWidget(self._dot)
        layout.addWidget(self._time_label)
        layout.addWidget(self._info_label)
        layout.addSpacing(2)
        layout.addWidget(self._pause_btn)
        layout.addWidget(self._stop_btn)
        layout.addWidget(self._cancel_btn)

    def _on_pause_toggle(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.setText("►")
            self._pause_btn.setToolTip(tr("rec.tooltip.resume"))
            self._dot.setProperty("paused", True)
            self.pause_requested.emit()
        else:
            self._pause_btn.setText("‖")
            self._pause_btn.setToolTip(tr("rec.tooltip.pause"))
            self._dot.setProperty("paused", False)
            self.resume_requested.emit()
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)

    def update_progress(self, frame_count: int, elapsed_ms: int) -> None:
        seconds = elapsed_ms // 1000
        self._time_label.setText(f"{seconds // 60}:{seconds % 60:02d}")
        self._info_label.setText(tr("rec.info", fps=self._fps, count=frame_count))

    def _position_near_region(self) -> None:
        size = self.sizeHint()
        bar_w, bar_h = size.width(), size.height()
        region = self._region

        x = region.x() + (region.width() - bar_w) // 2
        y_above = region.y() - bar_h - 10
        y_below = region.y() + region.height() + 10

        screen = QGuiApplication.screenAt(QPoint(x + bar_w // 2, region.y()))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()

        if y_above >= avail.y():
            y = y_above
        elif y_below + bar_h <= avail.y() + avail.height():
            y = y_below
        else:
            y = region.y() + 6
            x = region.x() + (region.width() - bar_w) // 2

        x = max(avail.x() + 4, min(avail.x() + avail.width() - bar_w - 4, x))
        y = max(avail.y() + 4, min(avail.y() + avail.height() - bar_h - 4, y))
        self.move(x, y)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._try_exclude_from_capture()

    def _try_exclude_from_capture(self) -> None:
        try:
            import ctypes

            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            hwnd = int(self.winId())
            if hwnd:
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass
