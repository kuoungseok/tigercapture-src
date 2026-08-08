"""Striped timeline host widget shared by editor timeline surfaces."""
from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.timeline_lane_paint import (
    TIMELINE_BG,
    TIMELINE_BG_80,
    TIMELINE_BG_80_AUDIO,
    TIMELINE_STRIPE,
    TIMELINE_STRIPE_80,
    TIMELINE_STRIPE_80_AUDIO,
    draw_timeline_stripes,
)


DEFAULT_TRACK_HEIGHT = 44
DEFAULT_TRACK_V_PADDING = 0
DEFAULT_TRACK_LABEL_H = 0


class StripedHost(QWidget):
    """Scrollable timeline host with a flat, subtly raised studio surface."""

    BG = TIMELINE_BG
    STRIPE = TIMELINE_STRIPE
    STRIPE_WIDTH = 1
    STRIPE_STEP = 24

    BG_80 = TIMELINE_BG_80
    STRIPE_80 = TIMELINE_STRIPE_80
    BG_80_AUDIO = TIMELINE_BG_80_AUDIO
    STRIPE_80_AUDIO = TIMELINE_STRIPE_80_AUDIO

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        self._draw_stripes(painter, self.rect(), self.BG, self.STRIPE)
        painter.save()
        margin = 170
        lane_h = max(
            28,
            DEFAULT_TRACK_LABEL_H + DEFAULT_TRACK_HEIGHT + DEFAULT_TRACK_V_PADDING,
        )
        painter.fillRect(QRect(0, 0, margin, self.height()), QColor(17, 17, 17, 142))
        painter.setPen(QPen(QColor(255, 255, 255, 10), 1))
        painter.drawLine(margin - 1, 0, margin - 1, self.height())
        x = margin + 52
        major_every = 5
        tick = 1
        while x < self.width():
            alpha = 12 if tick % major_every == 0 else 5
            painter.setPen(QPen(QColor(255, 255, 255, alpha), 1))
            painter.drawLine(x, 0, x, self.height())
            x += 52
            tick += 1
        y = 36
        while y < self.height():
            painter.setPen(QPen(QColor(255, 255, 255, 8), 1))
            painter.drawLine(margin, y, self.width(), y)
            painter.setPen(QPen(QColor(0, 0, 0, 12), 1))
            painter.drawLine(0, y + 1, self.width(), y + 1)
            y += lane_h
        painter.restore()

    @staticmethod
    def _draw_stripes(
        painter: QPainter,
        rect: QRect,
        bg: QColor,
        stripe: QColor,
        step: int = 28,
        width: int = 5,
    ) -> None:
        draw_timeline_stripes(painter, rect, bg, stripe, step=step, width=width)
