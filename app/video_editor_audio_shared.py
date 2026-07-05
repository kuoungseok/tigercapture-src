from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen


class _AntsOwnerProxy:
    def __eq__(self, other) -> bool:
        module = sys.modules.get("app.video_editor_window")
        owner = getattr(module, "_ANTS_OWNER", "") if module is not None else ""
        return owner == other


_ANTS_OWNER = _AntsOwnerProxy()


def _draw_marching_ants(painter: "QPainter", rect, offset: int) -> None:
    r = rect.adjusted(1, 1, -2, -2)
    if r.width() <= 0 or r.height() <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 104), 2))
    painter.drawRoundedRect(r.adjusted(0, 0, 0, 0), 3, 3)
    painter.setPen(QPen(QColor(226, 230, 236, 118), 1.1))
    painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 2, 2)
    painter.setPen(QPen(QColor(255, 91, 76, 150), 1.2))
    painter.drawLine(r.left() + 5, r.top() + 2, r.right() - 5, r.top() + 2)
    painter.restore()


def _format_ms(ms: int) -> str:
    ms = max(0, int(ms))
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


class _block_signals:
    """Context manager: blocks Qt signals on the given object."""

    def __init__(self, obj):
        self._obj = obj

    def __enter__(self):
        self._prev = self._obj.blockSignals(True)
        return self._obj

    def __exit__(self, *exc):
        self._obj.blockSignals(self._prev)
