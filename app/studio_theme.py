"""Screen-recording inspired timeline painting helpers.

The editor has dense timeline logic, so this module keeps the visual language
centralized: neutral layered media clips, restrained action blocks, warm edit
markers, and a red playhead. It is intentionally QPainter-native so it works in the
current PySide preview without extra assets.
"""
from __future__ import annotations

from math import sin

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygon,
)


STUDIO_TIMELINE_BG = QColor("#111111")
STUDIO_RULER_BG = QColor("#181818")
STUDIO_TRACK_EMPTY = QColor("#1F1F1F")
STUDIO_CLIP = QColor(48, 50, 52, 142)
STUDIO_CLIP_HI = QColor(58, 60, 62, 152)
STUDIO_CLIP_EDGE = QColor(106, 110, 114, 118)
STUDIO_ACTION = QColor(58, 58, 60, 138)
STUDIO_ACTION_HI = QColor(68, 68, 70, 148)
STUDIO_ACTION_EDGE = QColor(118, 118, 122, 112)
STUDIO_PLAYHEAD = QColor("#FF6A5E")
STUDIO_CUT = QColor("#D8C89E")
STUDIO_TEXT = QColor("#F7F2E9")
STUDIO_MUTED = QColor("#AAB1C1")


def _rounded_path(rect: QRect, radius: float = 7.0) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(0, 0, -1, -1), radius, radius)
    return path


def _with_alpha(color: QColor, alpha: int) -> QColor:
    out = QColor(color)
    out.setAlpha(max(0, min(255, int(alpha))))
    return out


def _coerce_color(value, fallback: QColor) -> QColor:
    if isinstance(value, QColor):
        return QColor(value)
    if value:
        candidate = QColor(str(value))
        if candidate.isValid():
            return candidate
    return QColor(fallback)


def paint_studio_clip_block(
    painter: QPainter,
    rect: QRect,
    *,
    selected: bool = False,
    active: bool = False,
    fill=None,
    highlight=None,
    edge=None,
) -> None:
    """Paint a media clip body with restrained catalog-style layer colors."""
    if rect.width() <= 0 or rect.height() <= 0:
        return
    base = _coerce_color(fill, STUDIO_CLIP)
    hi = _coerce_color(highlight, STUDIO_CLIP_HI)
    edge_color = _coerce_color(edge, STUDIO_CLIP_EDGE)
    painter.save()
    painter.setClipRect(rect)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    inset_y = 5 if rect.height() >= 32 else max(1, rect.height() // 8)
    r = rect.adjusted(1, inset_y, -1, -inset_y)

    shadow = QRect(r)
    shadow.translate(0, 1)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 16 if active else 9))
    painter.drawRoundedRect(shadow, 2, 2)

    grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
    grad.setColorAt(0.0, _with_alpha(hi.lighter(104), 116 if active else 98))
    grad.setColorAt(0.48, _with_alpha(base, 132 if active else 110))
    grad.setColorAt(1.0, _with_alpha(base.darker(106), 142 if active else 118))
    painter.setBrush(grad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(r, 2, 2)

    surface_light = QLinearGradient(r.left(), r.top(), r.left(), r.bottom())
    surface_light.setColorAt(0.0, QColor(255, 255, 255, 8 if active else 5))
    surface_light.setColorAt(0.34, QColor(255, 255, 255, 3 if active else 2))
    surface_light.setColorAt(1.0, QColor(255, 245, 210, 0))
    painter.setBrush(surface_light)
    painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 2, 2)

    if selected:
        painter.setBrush(_with_alpha(edge_color, 24))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 2, 2)
    else:
        outline = _with_alpha(edge_color, 18)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(outline, 1))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 2, 2)

    painter.setPen(QPen(QColor(0, 0, 0, 12), 1))
    painter.drawLine(r.left() + 5, r.bottom() - 1, r.right() - 5, r.bottom() - 1)
    painter.restore()


def paint_studio_clip_label(painter: QPainter, rect: QRect, text: str) -> None:
    """Draw the small Screen-Studio-like clip label if space allows."""
    if rect.width() < 74 or rect.height() < 24:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    label_rect = QRect(rect.left() + 10, rect.top() + 12, min(rect.width() - 20, 168), 16)
    font = QFont(painter.font())
    font.setPixelSize(9)
    font.setBold(False)
    painter.setFont(font)
    painter.setPen(QColor(230, 230, 230, 202))
    painter.drawText(
        label_rect,
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        text,
    )
    painter.restore()


def paint_studio_zoom_block(
    painter: QPainter,
    rect: QRect,
    *,
    configured: bool = True,
) -> None:
    """Paint a violet action actor block."""
    if rect.width() <= 0 or rect.height() <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    r = rect.adjusted(1, 1, -1, -1)
    grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
    grad.setColorAt(0.0, _with_alpha(STUDIO_ACTION_HI, 232))
    grad.setColorAt(1.0, _with_alpha(STUDIO_ACTION, 220))
    painter.setBrush(grad)
    pen = QPen(STUDIO_ACTION_EDGE, 2)
    if not configured:
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawRoundedRect(r, 6, 6)
    painter.restore()


def paint_studio_playhead(
    painter: QPainter,
    x: int,
    top: int,
    bottom: int,
    *,
    handle_top: int | None = None,
    show_handle: bool = True,
) -> None:
    """Paint a red playhead line with a small triangular handle."""
    painter.save()
    glow = QPen(_with_alpha(STUDIO_PLAYHEAD, 18), 1.6)
    glow.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(glow)
    painter.drawLine(x, top, x, bottom)
    pen = QPen(STUDIO_PLAYHEAD, 1.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(x, top, x, bottom)
    if show_handle:
        y = top if handle_top is None else handle_top
        painter.setBrush(STUDIO_PLAYHEAD)
        painter.setPen(QPen(QColor("#FF9B92"), 0.8))
        d = 4
        painter.drawPolygon(QPolygon([
            QPoint(x - d, y),
            QPoint(x + d, y),
            QPoint(x, y + d + 2),
        ]))
    painter.restore()


def paint_scissors_marker(
    painter: QPainter,
    x: int,
    rect: QRect,
    *,
    progress: float = 1.0,
) -> None:
    """Paint a restrained blade boundary inside a clip strip."""
    alpha = int(54 + 58 * max(0.0, min(1.0, progress)))
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    top = rect.top() + 3
    bottom = rect.bottom() - 3
    shadow = QPen(QColor(0, 0, 0, min(95, alpha)), 2)
    shadow.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(shadow)
    painter.drawLine(x, top, x, bottom)
    line = QPen(_with_alpha(STUDIO_CUT, alpha), 1)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(line)
    painter.drawLine(x, top, x, bottom)
    cap = _with_alpha(STUDIO_CUT, min(132, alpha + 12))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(cap)
    painter.drawRoundedRect(QRect(x - 4, top - 1, 8, 2), 1, 1)
    painter.drawRoundedRect(QRect(x - 4, bottom - 1, 8, 2), 1, 1)

    notch_alpha = min(150, alpha + 18)
    painter.setBrush(_with_alpha(STUDIO_CUT, notch_alpha))
    painter.setPen(QPen(QColor(20, 20, 20, min(115, notch_alpha)), 0.8))
    notch = 5
    painter.drawPolygon(QPolygon([
        QPoint(x - notch, top + 4),
        QPoint(x + notch, top + 4),
        QPoint(x, top + 10),
    ]))
    painter.drawPolygon(QPolygon([
        QPoint(x - notch, bottom - 4),
        QPoint(x + notch, bottom - 4),
        QPoint(x, bottom - 10),
    ]))
    handle_rect = QRect(x - 6, rect.center().y() - 5, 12, 10)
    painter.setBrush(QColor(18, 18, 18, min(150, alpha + 18)))
    painter.setPen(QPen(_with_alpha(STUDIO_CUT, min(135, alpha + 20)), 1))
    painter.drawRoundedRect(handle_rect, 3, 3)
    painter.setPen(QPen(_with_alpha(STUDIO_CUT, min(160, alpha + 30)), 1))
    painter.drawLine(x - 3, handle_rect.center().y(), x + 3, handle_rect.center().y())
    painter.restore()


def paint_timeline_burst(
    painter: QPainter,
    kind: str,
    x: int,
    y: int,
    progress: float,
) -> None:
    """Transient click/drop feedback for edit actions."""
    p = max(0.0, min(1.0, progress))
    scale = 1.0 + 0.45 * sin(p * 3.14159)
    alpha = int(210 * (1.0 - p))
    if alpha <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = STUDIO_CUT if kind == "cut" else STUDIO_ACTION_EDGE
    pen = QPen(_with_alpha(color, alpha), max(2, int(3 * scale)))
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    radius = int(10 + 18 * p)
    painter.drawEllipse(QPoint(x, y), radius, radius)
    if kind == "cut":
        painter.setPen(QPen(_with_alpha(STUDIO_CUT, alpha), 2))
        painter.drawLine(x - int(8 * scale), y - int(6 * scale), x + int(9 * scale), y + int(7 * scale))
        painter.drawLine(x - int(8 * scale), y + int(7 * scale), x + int(9 * scale), y - int(6 * scale))
    else:
        painter.setPen(QPen(_with_alpha(STUDIO_ACTION_EDGE, alpha), 2))
        painter.drawLine(x - 7, y, x + 7, y)
        painter.drawLine(x, y - 7, x, y + 7)
    painter.restore()
