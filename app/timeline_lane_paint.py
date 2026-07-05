"""Shared timeline-lane painting helpers."""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen


TIMELINE_BG = QColor("#141414")
TIMELINE_STRIPE = QColor("#161616")
TIMELINE_BG_80 = QColor(25, 25, 25, 126)
TIMELINE_STRIPE_80 = QColor(30, 30, 30, 72)
TIMELINE_BG_80_AUDIO = QColor(24, 26, 24, 118)
TIMELINE_STRIPE_80_AUDIO = QColor(30, 34, 30, 68)


def draw_timeline_stripes(
    painter: QPainter,
    rect: QRect,
    bg: QColor,
    stripe: QColor,
    step: int = 28,
    width: int = 5,
) -> None:
    if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    grad.setColorAt(0.0, QColor(bg).lighter(106))
    grad.setColorAt(0.45, QColor(bg).lighter(101))
    grad.setColorAt(1.0, QColor(bg).darker(106))
    painter.fillRect(rect, grad)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor(255, 255, 255, 5), 1))
    painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
    painter.setPen(QPen(QColor(0, 0, 0, 32), 1))
    painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
    if rect.height() >= 16:
        painter.setPen(QPen(QColor(255, 255, 255, 2), 1))
        painter.drawLine(rect.left(), rect.top() + 1, rect.right(), rect.top() + 1)
        painter.setPen(QPen(QColor(0, 0, 0, 20), 1))
        painter.drawLine(rect.left(), rect.bottom() - 1, rect.right(), rect.bottom() - 1)
    painter.restore()
