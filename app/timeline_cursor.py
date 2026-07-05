from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap

from app.icons import app_icon, icon_size


_TIMELINE_CURSOR_CACHE: dict[tuple[str, int], QCursor] = {}


def _timeline_tool_cursor(mode: str, phase: int = 0):
    """Return a visible, tool-specific cursor for timeline/editor tools."""
    m = str(mode or "select").strip().lower()
    if m in {"ripple", "roll", "slip", "slide", "trim", "trim_tool"}:
        return Qt.CursorShape.SizeHorCursor
    if m in {"grab", "move", "pan"}:
        return Qt.CursorShape.OpenHandCursor
    icon_name = "cursor"
    color = "#FFFFFF"
    hotspot = (5, 4)
    if m in {"blade", "blade_tool", "split", "scissors"}:
        icon_name = "scissors"
        color = "#FFD36B"
        hotspot = (7, 7)
    elif m in {"zoom", "zoom_tool"}:
        icon_name = "zoom"
        color = "#63D7FF"
        hotspot = (10, 10)
    elif m in {"color", "color_picker", "eyedropper"}:
        icon_name = "color"
        color = "#78F2C0"
        hotspot = (10, 10)
    elif m in {"ai", "magic_ai", "assistant"}:
        icon_name = "ai"
        color = "#D4A8FF"
        hotspot = (10, 10)
    key = (icon_name, int(phase) % (2 if icon_name == "scissors" else 1))
    cached = _TIMELINE_CURSOR_CACHE.get(key)
    if cached is not None:
        return cached
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 110))
    painter.drawEllipse(4, 5, 23, 23)
    pix = app_icon(icon_name, size=22, color=color).pixmap(icon_size(22))
    painter.save()
    painter.translate(16, 16)
    if icon_name == "scissors" and key[1]:
        painter.rotate(-18)
    elif icon_name == "scissors":
        painter.rotate(8)
    painter.drawPixmap(QRect(-11, -11, 22, 22), pix)
    painter.restore()
    if icon_name == "scissors":
        painter.setPen(QPen(QColor("#FF7B5C"), 2.0))
        y = 23 if key[1] else 25
        painter.drawLine(QPointF(22, y), QPointF(29, y - 4))
    painter.end()
    cursor = QCursor(pm, hotspot[0], hotspot[1])
    _TIMELINE_CURSOR_CACHE[key] = cursor
    return cursor
