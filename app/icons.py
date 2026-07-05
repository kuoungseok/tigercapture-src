"""Small vector icon helpers for editor chrome.

The first pass keeps icons code-native so packaging stays simple. Call sites use
``app_icon(name)`` and can later be switched to SVG-backed lucide assets without
changing button setup code.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def _color(value: str | QColor) -> QColor:
    return QColor(value) if not isinstance(value, QColor) else QColor(value)


@lru_cache(maxsize=256)
def app_icon(name: str, *, size: int = 18, color: str = "#D7DAE7") -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(_color(color), max(1.6, size / 10.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    s = float(size)
    n = (name or "").strip().lower()

    if n in {"project", "folder"}:
        painter.drawRoundedRect(QRectF(s * .14, s * .32, s * .72, s * .46), 2, 2)
        painter.drawPolyline(QPolygonF([
            QPointF(s * .18, s * .34),
            QPointF(s * .34, s * .22),
            QPointF(s * .52, s * .22),
            QPointF(s * .60, s * .32),
        ]))
    elif n in {"actors", "user"}:
        painter.drawEllipse(QPointF(s * .50, s * .35), s * .15, s * .15)
        path = QPainterPath()
        path.moveTo(s * .24, s * .78)
        path.cubicTo(s * .28, s * .55, s * .72, s * .55, s * .76, s * .78)
        painter.drawPath(path)
    elif n in {"target", "crosshair"}:
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .30, s * .30)
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .08, s * .08)
        painter.drawLine(QPointF(s * .50, s * .12), QPointF(s * .50, s * .28))
        painter.drawLine(QPointF(s * .50, s * .72), QPointF(s * .50, s * .88))
        painter.drawLine(QPointF(s * .12, s * .50), QPointF(s * .28, s * .50))
        painter.drawLine(QPointF(s * .72, s * .50), QPointF(s * .88, s * .50))
    elif n in {"person", "body"}:
        painter.drawEllipse(QPointF(s * .50, s * .24), s * .10, s * .10)
        painter.drawLine(QPointF(s * .50, s * .36), QPointF(s * .50, s * .62))
        painter.drawLine(QPointF(s * .32, s * .48), QPointF(s * .68, s * .48))
        painter.drawLine(QPointF(s * .50, s * .62), QPointF(s * .34, s * .84))
        painter.drawLine(QPointF(s * .50, s * .62), QPointF(s * .66, s * .84))
    elif n in {"more", "ellipsis"}:
        painter.setBrush(_color(color))
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (.28, .50, .72):
            painter.drawEllipse(QPointF(s * x, s * .50), s * .055, s * .055)
    elif n in {"export", "upload"}:
        painter.drawLine(QPointF(s * .50, s * .78), QPointF(s * .50, s * .24))
        painter.drawLine(QPointF(s * .30, s * .43), QPointF(s * .50, s * .23))
        painter.drawLine(QPointF(s * .70, s * .43), QPointF(s * .50, s * .23))
        painter.drawRoundedRect(QRectF(s * .22, s * .68, s * .56, s * .16), 2, 2)
    elif n in {"plus", "add", "new"}:
        painter.drawLine(QPointF(s * .50, s * .22), QPointF(s * .50, s * .78))
        painter.drawLine(QPointF(s * .22, s * .50), QPointF(s * .78, s * .50))
    elif n in {"save", "floppy"}:
        painter.drawRoundedRect(QRectF(s * .20, s * .18, s * .60, s * .64), 2, 2)
        painter.drawRect(QRectF(s * .34, s * .18, s * .30, s * .22))
        painter.drawRoundedRect(QRectF(s * .34, s * .58, s * .32, s * .20), 2, 2)
    elif n in {"link", "relink", "chain"}:
        painter.drawArc(QRectF(s * .16, s * .34, s * .38, s * .30), 35 * 16, 290 * 16)
        painter.drawArc(QRectF(s * .46, s * .34, s * .38, s * .30), 215 * 16, 290 * 16)
        painter.drawLine(QPointF(s * .38, s * .50), QPointF(s * .62, s * .50))
    elif n in {"health", "pulse"}:
        path = QPainterPath()
        path.moveTo(s * .14, s * .54)
        path.lineTo(s * .30, s * .54)
        path.lineTo(s * .38, s * .34)
        path.lineTo(s * .50, s * .72)
        path.lineTo(s * .61, s * .44)
        path.lineTo(s * .70, s * .54)
        path.lineTo(s * .86, s * .54)
        painter.drawPath(path)
    elif n in {"popout", "external"}:
        painter.drawRoundedRect(QRectF(s * .18, s * .26, s * .52, s * .56), 2, 2)
        painter.drawLine(QPointF(s * .50, s * .18), QPointF(s * .82, s * .18))
        painter.drawLine(QPointF(s * .82, s * .18), QPointF(s * .82, s * .50))
        painter.drawLine(QPointF(s * .48, s * .52), QPointF(s * .80, s * .20))
        painter.drawLine(QPointF(s * .64, s * .20), QPointF(s * .80, s * .20))
        painter.drawLine(QPointF(s * .80, s * .20), QPointF(s * .80, s * .36))
    elif n in {"trash", "delete"}:
        painter.drawLine(QPointF(s * .26, s * .32), QPointF(s * .74, s * .32))
        painter.drawLine(QPointF(s * .40, s * .22), QPointF(s * .60, s * .22))
        painter.drawRoundedRect(QRectF(s * .32, s * .36, s * .36, s * .46), 2, 2)
        painter.drawLine(QPointF(s * .43, s * .44), QPointF(s * .43, s * .74))
        painter.drawLine(QPointF(s * .57, s * .44), QPointF(s * .57, s * .74))
    elif n in {"grid"}:
        for y in (.22, .54):
            for x in (.22, .54):
                painter.drawRoundedRect(QRectF(s * x, s * y, s * .22, s * .22), 2, 2)
    elif n in {"list"}:
        painter.setBrush(_color(color))
        for y in (.28, .50, .72):
            painter.drawEllipse(QPointF(s * .24, s * y), s * .035, s * .035)
            painter.drawLine(QPointF(s * .36, s * y), QPointF(s * .80, s * y))
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"video", "media"}:
        painter.drawRoundedRect(QRectF(s * .18, s * .28, s * .64, s * .44), 3, 3)
        painter.drawLine(QPointF(s * .32, s * .28), QPointF(s * .32, s * .72))
        painter.drawLine(QPointF(s * .68, s * .28), QPointF(s * .68, s * .72))
        painter.drawLine(QPointF(s * .24, s * .40), QPointF(s * .30, s * .40))
        painter.drawLine(QPointF(s * .70, s * .40), QPointF(s * .76, s * .40))
        painter.drawLine(QPointF(s * .24, s * .60), QPointF(s * .30, s * .60))
        painter.drawLine(QPointF(s * .70, s * .60), QPointF(s * .76, s * .60))
    elif n in {"camera", "screenshot"}:
        painter.drawRoundedRect(QRectF(s * .18, s * .34, s * .64, s * .38), 3, 3)
        painter.drawPolyline(QPolygonF([
            QPointF(s * .34, s * .34),
            QPointF(s * .40, s * .24),
            QPointF(s * .60, s * .24),
            QPointF(s * .66, s * .34),
        ]))
        painter.drawEllipse(QPointF(s * .50, s * .53), s * .12, s * .12)
    elif n in {"settings", "gear"}:
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .16, s * .16)
        for angle in range(0, 360, 45):
            import math
            a = math.radians(angle)
            painter.drawLine(
                QPointF(s * (.50 + math.cos(a) * .26), s * (.50 + math.sin(a) * .26)),
                QPointF(s * (.50 + math.cos(a) * .36), s * (.50 + math.sin(a) * .36)),
            )
    elif n in {"language", "globe"}:
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .34, s * .34)
        painter.drawArc(QRectF(s * .28, s * .16, s * .44, s * .68), 90 * 16, 180 * 16)
        painter.drawArc(QRectF(s * .28, s * .16, s * .44, s * .68), -90 * 16, 180 * 16)
        painter.drawLine(QPointF(s * .18, s * .50), QPointF(s * .82, s * .50))
        painter.drawArc(QRectF(s * .20, s * .30, s * .60, s * .40), 0, 180 * 16)
        painter.drawArc(QRectF(s * .20, s * .30, s * .60, s * .40), 180 * 16, 180 * 16)
    elif n in {"audio", "speaker"}:
        painter.drawPolygon(QPolygonF([
            QPointF(s * .18, s * .42),
            QPointF(s * .34, s * .42),
            QPointF(s * .52, s * .26),
            QPointF(s * .52, s * .74),
            QPointF(s * .34, s * .58),
            QPointF(s * .18, s * .58),
        ]))
        painter.drawArc(QRectF(s * .50, s * .34, s * .22, s * .32), -45 * 16, 90 * 16)
        painter.drawArc(QRectF(s * .48, s * .24, s * .38, s * .52), -45 * 16, 90 * 16)
    elif n in {"sliders", "mixer", "adjust"}:
        for x, y in ((.28, .38), (.50, .62), (.72, .46)):
            painter.drawLine(QPointF(s * x, s * .22), QPointF(s * x, s * .82))
            painter.drawEllipse(QPointF(s * x, s * y), s * .075, s * .075)
    elif n in {"blur", "soften"}:
        painter.drawEllipse(QPointF(s * .38, s * .46), s * .18, s * .18)
        painter.drawEllipse(QPointF(s * .58, s * .54), s * .20, s * .20)
        painter.drawEllipse(QPointF(s * .52, s * .36), s * .10, s * .10)
    elif n in {"spark", "effects"}:
        painter.drawLine(QPointF(s * .50, s * .16), QPointF(s * .50, s * .84))
        painter.drawLine(QPointF(s * .16, s * .50), QPointF(s * .84, s * .50))
        painter.drawLine(QPointF(s * .27, s * .27), QPointF(s * .73, s * .73))
        painter.drawLine(QPointF(s * .73, s * .27), QPointF(s * .27, s * .73))
    elif n in {"ai", "ai-script", "assistant", "bot", "magic-edit"}:
        badge = QRectF(s * .10, s * .20, s * .80, s * .60)
        painter.setPen(QPen(_color(color), max(1.2, s * .065)))
        painter.setBrush(QColor(255, 255, 255, 30))
        painter.drawRoundedRect(badge, s * .18, s * .18)
        font = QFont("Arial")
        font.setBold(True)
        font.setPixelSize(max(8, int(s * .38)))
        painter.setFont(font)
        painter.setPen(_color(color))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "AI")
        painter.setBrush(_color(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(s * .82, s * .22), s * .045, s * .045)
        painter.drawEllipse(QPointF(s * .20, s * .78), s * .032, s * .032)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"caption", "subtitle", "transcript"}:
        painter.drawRoundedRect(QRectF(s * .14, s * .24, s * .72, s * .46), 3, 3)
        painter.drawLine(QPointF(s * .35, s * .70), QPointF(s * .28, s * .84))
        painter.drawLine(QPointF(s * .35, s * .70), QPointF(s * .48, s * .70))
        painter.drawLine(QPointF(s * .28, s * .42), QPointF(s * .72, s * .42))
        painter.drawLine(QPointF(s * .28, s * .56), QPointF(s * .62, s * .56))
    elif n in {"scope", "scopes", "waveform"}:
        path = QPainterPath()
        path.moveTo(s * .14, s * .60)
        path.cubicTo(s * .24, s * .28, s * .34, s * .88, s * .45, s * .55)
        path.cubicTo(s * .54, s * .30, s * .64, s * .74, s * .72, s * .52)
        path.cubicTo(s * .78, s * .38, s * .84, s * .45, s * .88, s * .42)
        painter.drawPath(path)
    elif n in {"fade", "dissolve", "transition"}:
        painter.drawRoundedRect(QRectF(s * .14, s * .28, s * .72, s * .44), 3, 3)
        painter.drawLine(QPointF(s * .50, s * .24), QPointF(s * .50, s * .76))
        left_grad = QLinearGradient(QPointF(s * .17, s * .50), QPointF(s * .48, s * .50))
        left_grad.setColorAt(0.0, QColor(255, 255, 255, 20))
        left_grad.setColorAt(1.0, _color(color))
        right_grad = QLinearGradient(QPointF(s * .52, s * .50), QPointF(s * .83, s * .50))
        right_grad.setColorAt(0.0, _color(color))
        right_grad.setColorAt(1.0, QColor(255, 255, 255, 20))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(left_grad))
        painter.drawRoundedRect(QRectF(s * .18, s * .33, s * .28, s * .34), 2, 2)
        painter.setBrush(QBrush(right_grad))
        painter.drawRoundedRect(QRectF(s * .54, s * .33, s * .28, s * .34), 2, 2)
        painter.setPen(QPen(_color(color), max(1.3, s * .075)))
        painter.drawLine(QPointF(s * .50, s * .30), QPointF(s * .50, s * .70))
    elif n in {"mark-in", "in"}:
        painter.drawLine(QPointF(s * .30, s * .22), QPointF(s * .30, s * .78))
        painter.drawLine(QPointF(s * .30, s * .50), QPointF(s * .74, s * .28))
        painter.drawLine(QPointF(s * .30, s * .50), QPointF(s * .74, s * .72))
    elif n in {"mark-out", "out"}:
        painter.drawLine(QPointF(s * .70, s * .22), QPointF(s * .70, s * .78))
        painter.drawLine(QPointF(s * .70, s * .50), QPointF(s * .26, s * .28))
        painter.drawLine(QPointF(s * .70, s * .50), QPointF(s * .26, s * .72))
    elif n in {"clear", "x"}:
        painter.drawLine(QPointF(s * .28, s * .28), QPointF(s * .72, s * .72))
        painter.drawLine(QPointF(s * .72, s * .28), QPointF(s * .28, s * .72))
    elif n in {"fit"}:
        painter.drawRoundedRect(QRectF(s * .20, s * .24, s * .60, s * .52), 2, 2)
        painter.drawLine(QPointF(s * .32, s * .36), QPointF(s * .20, s * .24))
        painter.drawLine(QPointF(s * .68, s * .36), QPointF(s * .80, s * .24))
        painter.drawLine(QPointF(s * .32, s * .64), QPointF(s * .20, s * .76))
        painter.drawLine(QPointF(s * .68, s * .64), QPointF(s * .80, s * .76))
    elif n in {"color", "palette", "grading", "color-grade", "colorwheel"}:
        wheel_rect = QRectF(s * .17, s * .15, s * .54, s * .54)
        grad = QConicalGradient(wheel_rect.center(), -35)
        for pos, hex_color in (
            (0.00, "#ff5f57"),
            (0.15, "#ffb454"),
            (0.31, "#76e36d"),
            (0.48, "#35d7d7"),
            (0.64, "#5d8cff"),
            (0.82, "#bd6dff"),
            (1.00, "#ff5f57"),
        ):
            grad.setColorAt(pos, QColor(hex_color))
        painter.setPen(QPen(QColor(255, 255, 255, 72), max(1.0, s * .055)))
        painter.setBrush(QBrush(grad))
        painter.drawEllipse(wheel_rect)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(10, 12, 22, 220))
        painter.drawEllipse(QRectF(s * .34, s * .32, s * .20, s * .20))

        painter.setBrush(_color(color))
        painter.drawEllipse(QRectF(s * .48, s * .20, s * .09, s * .09))

        curve = QPainterPath()
        curve.moveTo(s * .30, s * .78)
        curve.cubicTo(s * .42, s * .56, s * .55, s * .88, s * .72, s * .56)
        curve.cubicTo(s * .77, s * .46, s * .81, s * .43, s * .86, s * .40)
        painter.setPen(QPen(_color(color), max(1.6, s / 10.0)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(curve)
        painter.drawLine(QPointF(s * .25, s * .80), QPointF(s * .88, s * .80))
    elif n in {"nest", "compound"}:
        painter.drawRoundedRect(QRectF(s * .20, s * .34, s * .42, s * .34), 2, 2)
        painter.drawRoundedRect(QRectF(s * .38, s * .24, s * .42, s * .34), 2, 2)
    elif n in {"proxy", "layers"}:
        painter.drawPolygon(QPolygonF([
            QPointF(s * .50, s * .20),
            QPointF(s * .78, s * .36),
            QPointF(s * .50, s * .52),
            QPointF(s * .22, s * .36),
        ]))
        painter.drawPolyline(QPolygonF([
            QPointF(s * .22, s * .50),
            QPointF(s * .50, s * .66),
            QPointF(s * .78, s * .50),
        ]))
        painter.drawPolyline(QPolygonF([
            QPointF(s * .22, s * .64),
            QPointF(s * .50, s * .80),
            QPointF(s * .78, s * .64),
        ]))
    elif n in {"workflow", "node-graph", "graph"}:
        nodes = (
            QRectF(s * .15, s * .25, s * .20, s * .18),
            QRectF(s * .43, s * .15, s * .22, s * .18),
            QRectF(s * .67, s * .52, s * .20, s * .18),
            QRectF(s * .34, s * .62, s * .22, s * .18),
        )
        painter.drawLine(QPointF(s * .35, s * .34), QPointF(s * .43, s * .24))
        painter.drawLine(QPointF(s * .65, s * .24), QPointF(s * .67, s * .61))
        painter.drawLine(QPointF(s * .65, s * .61), QPointF(s * .56, s * .71))
        painter.drawLine(QPointF(s * .35, s * .34), QPointF(s * .34, s * .71))
        for rect in nodes:
            painter.drawRoundedRect(rect, 2, 2)
    elif n in {"scissors", "cut", "blade"}:
        painter.drawLine(QPointF(s * .36, s * .50), QPointF(s * .82, s * .20))
        painter.drawLine(QPointF(s * .36, s * .50), QPointF(s * .82, s * .80))
        painter.drawEllipse(QPointF(s * .25, s * .38), s * .11, s * .11)
        painter.drawEllipse(QPointF(s * .25, s * .62), s * .11, s * .11)
    elif n in {"zoom", "search"}:
        painter.drawEllipse(QPointF(s * .43, s * .42), s * .23, s * .23)
        painter.drawLine(QPointF(s * .60, s * .60), QPointF(s * .82, s * .82))
    elif n in {"cursor", "select", "pointer"}:
        path = QPainterPath()
        path.moveTo(s * .25, s * .16)
        path.lineTo(s * .76, s * .55)
        path.lineTo(s * .52, s * .61)
        path.lineTo(s * .63, s * .84)
        path.lineTo(s * .48, s * .90)
        path.lineTo(s * .38, s * .66)
        path.lineTo(s * .22, s * .80)
        path.closeSubpath()
        painter.drawPath(path)
    elif n in {"ripple", "wave"}:
        path = QPainterPath()
        path.moveTo(s * .16, s * .52)
        path.cubicTo(s * .30, s * .22, s * .42, s * .82, s * .56, s * .52)
        path.cubicTo(s * .68, s * .28, s * .78, s * .66, s * .88, s * .44)
        painter.drawPath(path)
    elif n in {"roll"}:
        painter.drawArc(QRectF(s * .22, s * .22, s * .56, s * .56), 30 * 16, 260 * 16)
        painter.drawLine(QPointF(s * .70, s * .22), QPointF(s * .80, s * .36))
    elif n in {"slip"}:
        painter.drawRect(QRectF(s * .18, s * .35, s * .64, s * .30))
        painter.drawLine(QPointF(s * .32, s * .28), QPointF(s * .20, s * .50))
        painter.drawLine(QPointF(s * .68, s * .72), QPointF(s * .80, s * .50))
    elif n in {"slide"}:
        painter.drawLine(QPointF(s * .18, s * .50), QPointF(s * .82, s * .50))
        painter.drawLine(QPointF(s * .30, s * .36), QPointF(s * .18, s * .50))
        painter.drawLine(QPointF(s * .30, s * .64), QPointF(s * .18, s * .50))
        painter.drawLine(QPointF(s * .70, s * .36), QPointF(s * .82, s * .50))
        painter.drawLine(QPointF(s * .70, s * .64), QPointF(s * .82, s * .50))
    elif n in {"marker"}:
        painter.setBrush(_color(color))
        points = [
            QPointF(s * .50, s * .14),
            QPointF(s * .76, s * .40),
            QPointF(s * .50, s * .86),
            QPointF(s * .24, s * .40),
        ]
        painter.drawPolygon(QPolygonF(points))
    elif n in {"play"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .34, s * .22),
            QPointF(s * .34, s * .78),
            QPointF(s * .78, s * .50),
        ]))
    elif n in {"pause"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawRoundedRect(QRectF(s * .30, s * .22, s * .15, s * .56), 2, 2)
        painter.drawRoundedRect(QRectF(s * .56, s * .22, s * .15, s * .56), 2, 2)
    elif n in {"stop"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawRoundedRect(QRectF(s * .28, s * .28, s * .44, s * .44), 2, 2)
    elif n in {"previous", "prev", "step-back"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawRoundedRect(QRectF(s * .20, s * .22, s * .09, s * .56), 2, 2)
        painter.drawPolygon(QPolygonF([
            QPointF(s * .76, s * .22),
            QPointF(s * .76, s * .78),
            QPointF(s * .36, s * .50),
        ]))
    elif n in {"next", "step-forward"}:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawRoundedRect(QRectF(s * .71, s * .22, s * .09, s * .56), 2, 2)
        painter.drawPolygon(QPolygonF([
            QPointF(s * .24, s * .22),
            QPointF(s * .24, s * .78),
            QPointF(s * .64, s * .50),
        ]))
    elif n in {"chevrons", "fast-forward"}:
        for x0 in (.18, .42, .66):
            painter.drawLine(QPointF(s * x0, s * .28), QPointF(s * (x0 + .16), s * .50))
            painter.drawLine(QPointF(s * (x0 + .16), s * .50), QPointF(s * x0, s * .72))
    elif n in {"chevron-right", "disclosure-right"}:
        painter.drawLine(QPointF(s * .38, s * .26), QPointF(s * .62, s * .50))
        painter.drawLine(QPointF(s * .62, s * .50), QPointF(s * .38, s * .74))
    elif n in {"chevron-down", "disclosure-down"}:
        painter.drawLine(QPointF(s * .26, s * .38), QPointF(s * .50, s * .62))
        painter.drawLine(QPointF(s * .50, s * .62), QPointF(s * .74, s * .38))
    elif n in {"reset", "replay"}:
        painter.drawArc(QRectF(s * .22, s * .22, s * .56, s * .56), 35 * 16, 285 * 16)
        painter.drawLine(QPointF(s * .30, s * .26), QPointF(s * .24, s * .46))
        painter.drawLine(QPointF(s * .30, s * .26), QPointF(s * .50, s * .30))
    elif n in {"loop", "repeat"}:
        painter.drawArc(QRectF(s * .18, s * .24, s * .42, s * .34), 40 * 16, 240 * 16)
        painter.drawArc(QRectF(s * .40, s * .42, s * .42, s * .34), 220 * 16, 240 * 16)
        painter.drawLine(QPointF(s * .55, s * .24), QPointF(s * .70, s * .28))
        painter.drawLine(QPointF(s * .55, s * .24), QPointF(s * .60, s * .40))
        painter.drawLine(QPointF(s * .45, s * .76), QPointF(s * .30, s * .72))
        painter.drawLine(QPointF(s * .45, s * .76), QPointF(s * .40, s * .60))
    elif n in {"keyframe", "key"}:
        painter.setBrush(_color(color))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .50, s * .16),
            QPointF(s * .76, s * .50),
            QPointF(s * .50, s * .84),
            QPointF(s * .24, s * .50),
        ]))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .08, s * .08)
    elif n in {"bone", "spine"}:
        painter.drawLine(QPointF(s * .30, s * .70), QPointF(s * .70, s * .30))
        painter.drawEllipse(QPointF(s * .25, s * .75), s * .09, s * .09)
        painter.drawEllipse(QPointF(s * .37, s * .70), s * .08, s * .08)
        painter.drawEllipse(QPointF(s * .63, s * .30), s * .08, s * .08)
        painter.drawEllipse(QPointF(s * .75, s * .25), s * .09, s * .09)
    elif n in {"live2d"}:
        painter.drawRoundedRect(QRectF(s * .18, s * .32, s * .28, s * .34), 3, 3)
        painter.drawRoundedRect(QRectF(s * .54, s * .32, s * .28, s * .34), 3, 3)
        painter.drawLine(QPointF(s * .46, s * .50), QPointF(s * .54, s * .50))
    else:
        painter.drawRoundedRect(QRectF(s * .20, s * .20, s * .60, s * .60), 3, 3)

    painter.end()
    return QIcon(pix)


def icon_size(px: int = 16) -> QSize:
    return QSize(px, px)
