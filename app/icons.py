"""Small vector icon helpers for editor chrome.

The first pass keeps icons code-native so packaging stays simple. Call sites use
``app_icon(name)`` and can later be switched to SVG-backed lucide assets without
changing button setup code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)


def _color(value: str | QColor) -> QColor:
    return QColor(value) if not isinstance(value, QColor) else QColor(value)


def _key_light_logo(pixmap: QPixmap, color: str | QColor) -> QPixmap:
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    base = _color(color)
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            luminance = int(pixel.red() * .299 + pixel.green() * .587 + pixel.blue() * .114)
            if luminance < 52:
                pixel.setAlpha(0)
                image.setPixelColor(x, y, pixel)
                continue
            alpha = max(0, min(255, int((luminance - 52) / 203.0 * 255)))
            image.setPixelColor(x, y, QColor(base.red(), base.green(), base.blue(), alpha))
    return QPixmap.fromImage(image)


_BLOCK_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
}


def _paint_block_text(painter: QPainter, text: str, rect: QRectF, color: str | QColor) -> None:
    glyphs = []
    columns = 0
    for char in text.upper():
        if char == " ":
            glyphs.append((" ", None))
            columns += 3
            continue
        glyph = _BLOCK_GLYPHS.get(char)
        if glyph is None:
            continue
        glyphs.append((char, glyph))
        columns += 5
    if not glyphs or columns <= 0:
        return
    columns += max(0, len(glyphs) - 1)
    cell = min(float(rect.width()) / columns, float(rect.height()) / 7.0)
    if cell <= 0:
        return
    pixel = max(0.8, cell * .82)
    x = float(rect.left()) + (float(rect.width()) - columns * cell) * .5
    y0 = float(rect.top()) + (float(rect.height()) - 7.0 * cell) * .5
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(_color(color))
    radius = max(.25, cell * .16)
    for _char, glyph in glyphs:
        if glyph is None:
            x += 4 * cell
            continue
        for row, line in enumerate(glyph):
            for col, value in enumerate(line):
                if value != "1":
                    continue
                painter.drawRoundedRect(
                    QRectF(x + col * cell, y0 + row * cell, pixel, pixel),
                    radius,
                    radius,
                )
        x += 6 * cell


def _paint_sound_lab_logo(painter: QPainter, rect: QRectF, color: str | QColor) -> None:
    base = _color(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(base)

    w = max(1.0, float(rect.width()))
    h = max(1.0, float(rect.height()))
    left = float(rect.left())
    top = float(rect.top())
    bars = [.18, .32, .46, .62, .48, .38, .30, .44, .62, .82, .96, .68, .50, .36, .28, .38, .30, .22]
    usable_w = max(h * .90, min(w * .72, h * 4.0))
    bar_w = max(1.0, usable_w / (len(bars) + (len(bars) - 1) * .45))
    gap = max(.7, bar_w * .45)
    total_w = len(bars) * bar_w + (len(bars) - 1) * gap
    x0 = left + (w - total_w) * .5
    center_y = top + h * .34
    center_gap = max(1.0, h * .035)
    radius = max(.35, h * .012)
    for i, height in enumerate(bars):
        x = x0 + i * (bar_w + gap)
        half_h = h * height * .28
        top_h = max(.8, half_h - center_gap * .5)
        bottom_h = max(.8, half_h - center_gap * .5)
        painter.drawRoundedRect(
            QRectF(x, center_y - center_gap * .5 - top_h, bar_w, top_h),
            radius,
            radius,
        )
        painter.drawRoundedRect(
            QRectF(x, center_y + center_gap * .5, bar_w, bottom_h),
            radius,
            radius,
        )

    _paint_block_text(
        painter,
        "SOUND LAB",
        QRectF(left + w * .10, top + h * .66, w * .80, h * .29),
        base,
    )


def _paint_composer_logo(painter: QPainter, rect: QRectF, color: str | QColor) -> None:
    base = _color(color)

    w = max(1.0, float(rect.width()))
    h = max(1.0, float(rect.height()))
    left = float(rect.left())
    top = float(rect.top())
    badge_w = min(w * .94, h * 2.50)
    badge_h = min(h * .98, badge_w / 2.50)
    bx = left + (w - badge_w) * .5
    by = top + (h - badge_h) * .5
    bw = badge_w
    bh = badge_h

    def pt(x: float, y: float) -> QPointF:
        return QPointF(bx + bw * x, by + bh * y)

    def box(x: float, y: float, ww: float, hh: float) -> QRectF:
        return QRectF(bx + bw * x, by + bh * y, bw * ww, bh * hh)

    heavy = max(1.0, bh * .030)
    mid = max(1.0, bh * .021)
    fine = max(1.0, bh * .015)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(base, heavy, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))

    # Voice-Lab-style angular outer ornament.
    left_frame = QPolygonF([
        pt(.050, .185), pt(.085, .135), pt(.470, .135),
        pt(.470, .150), pt(.075, .150), pt(.030, .205),
        pt(.030, .640), pt(.072, .740), pt(.128, .740),
        pt(.155, .675), pt(.252, .675),
    ])
    right_frame = QPolygonF([
        pt(.530, .135), pt(.915, .135), pt(.950, .185),
        pt(.970, .205), pt(.970, .640), pt(.928, .740),
        pt(.872, .740), pt(.845, .675), pt(.748, .675),
    ])
    painter.drawPolyline(left_frame)
    painter.drawPolyline(right_frame)

    painter.setBrush(base)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(QPolygonF([
        pt(.050, .205), pt(.112, .165), pt(.138, .165),
        pt(.096, .250), pt(.050, .300),
    ]))
    painter.drawPolygon(QPolygonF([
        pt(.950, .205), pt(.888, .165), pt(.862, .165),
        pt(.904, .250), pt(.950, .300),
    ]))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(base, mid, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    painter.drawPolygon(QPolygonF([pt(.050, .205), pt(.140, .165), pt(.102, .265), pt(.050, .300)]))
    painter.drawPolygon(QPolygonF([pt(.950, .205), pt(.860, .165), pt(.898, .265), pt(.950, .300)]))

    for x0, side in ((.045, 1), (.955, -1)):
        x1 = x0 + side * .032
        for y in (.405, .445, .485, .525, .565):
            painter.drawLine(pt(x0, y), pt(x1, y))

    # Bottom title plate, including the notched shoulders and diagonal ticks.
    plate = QPolygonF([
        pt(.235, .625), pt(.765, .625), pt(.792, .690),
        pt(.852, .690), pt(.918, .820), pt(.878, .885),
        pt(.122, .885), pt(.082, .820), pt(.148, .690),
        pt(.208, .690), pt(.235, .625),
    ])
    painter.setPen(QPen(base, heavy, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    painter.drawPolyline(plate)
    painter.setPen(QPen(base, mid, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    painter.drawLine(pt(.095, .785), pt(.135, .865))
    painter.drawLine(pt(.120, .770), pt(.160, .850))
    painter.drawLine(pt(.905, .785), pt(.865, .865))
    painter.drawLine(pt(.880, .770), pt(.840, .850))

    plus = bh * .030
    for cx in (.190, .810):
        cy = .770
        painter.drawLine(QPointF(pt(cx, cy).x() - plus, pt(cx, cy).y()), QPointF(pt(cx, cy).x() + plus, pt(cx, cy).y()))
        painter.drawLine(QPointF(pt(cx, cy).x(), pt(cx, cy).y() - plus), QPointF(pt(cx, cy).x(), pt(cx, cy).y() + plus))

    # The center illustration follows Voice Lab's placement, but uses sheet music.
    painter.setPen(QPen(base, fine, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    staff_left = bx + bw * .265
    staff_right = bx + bw * .735
    staff_top = by + bh * .278
    staff_gap = max(1.0, bh * .026)
    for row in range(5):
        y = staff_top + row * staff_gap
        painter.drawLine(QPointF(staff_left, y), QPointF(staff_right, y))

    def draw_half_note(center: QPointF, scale: float, stem_up: bool = True) -> None:
        note_w = bh * .023 * scale
        note_h = bh * .015 * scale
        note_pen = QPen(base, max(1.0, bh * .024), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.save()
        painter.translate(center)
        painter.rotate(-18)
        painter.setPen(note_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), note_w, note_h)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawEllipse(QPointF(0, 0), note_w * .52, note_h * .44)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(note_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(0, 0), note_w, note_h)
        painter.restore()
        stem_x = center.x() + bh * .020 * scale
        stem_top = center.y() - bh * .125 * scale
        stem_bottom = center.y() + bh * .006 * scale
        if stem_up:
            painter.drawLine(QPointF(stem_x, stem_bottom), QPointF(stem_x, stem_top))
        else:
            painter.drawLine(
                QPointF(center.x() - bh * .020 * scale, center.y() - bh * .006 * scale),
                QPointF(center.x() - bh * .020 * scale, center.y() + bh * .125 * scale),
            )

    staff_w = staff_right - staff_left
    draw_half_note(QPointF(staff_left + staff_w * .33, staff_top + staff_gap * 3.0), 1.55)
    draw_half_note(QPointF(staff_left + staff_w * .51, staff_top + staff_gap * 2.0), 1.40)
    draw_half_note(QPointF(staff_left + staff_w * .68, staff_top + staff_gap * 2.8), 1.28)
    painter.setPen(QPen(base, mid, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(pt(.255, .360), pt(.210, .330))
    painter.drawLine(pt(.210, .330), pt(.190, .375))
    painter.drawLine(pt(.745, .360), pt(.790, .330))
    painter.drawLine(pt(.790, .330), pt(.810, .375))

    _paint_block_text(
        painter,
        "COMPOSER",
        box(.215, .675, .570, .185),
        base,
    )


def _paint_voice_lab_logo(painter: QPainter, rect: QRectF, color: str | QColor) -> None:
    base = _color(color)
    w = max(1.0, float(rect.width()))
    h = max(1.0, float(rect.height()))
    left = float(rect.left())
    top = float(rect.top())
    stroke = max(1.0, h * .075)
    painter.setPen(QPen(base, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    # Rounded microphone capsule.
    mic = QRectF(left + w * .34, top + h * .16, w * .26, h * .44)
    painter.drawRoundedRect(mic, w * .13, w * .13)
    painter.drawLine(QPointF(left + w * .47, top + h * .62), QPointF(left + w * .47, top + h * .78))
    painter.drawLine(QPointF(left + w * .33, top + h * .80), QPointF(left + w * .61, top + h * .80))
    painter.drawArc(QRectF(left + w * .22, top + h * .34, w * .50, h * .34), 200 * 16, 140 * 16)

    # Voice waveform bubbles to keep it distinct from a plain audio icon.
    wave_pen = QPen(base, max(1.0, h * .052), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(wave_pen)
    path = QPainterPath()
    path.moveTo(left + w * .12, top + h * .51)
    path.cubicTo(left + w * .18, top + h * .34, left + w * .23, top + h * .68, left + w * .29, top + h * .50)
    painter.drawPath(path)
    path = QPainterPath()
    path.moveTo(left + w * .66, top + h * .49)
    path.cubicTo(left + w * .72, top + h * .28, left + w * .79, top + h * .72, left + w * .86, top + h * .46)
    painter.drawPath(path)

    # Small creator/AI sparkle.
    painter.setPen(QPen(base, max(1.0, h * .045), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    cx = left + w * .76
    cy = top + h * .22
    r = h * .085
    painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))


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

    if n in {"tiger-painter-logo", "tiger_painter_logo"}:
        # Original Tiger Painter mark: a brush-nib T with two tiger stripes.
        base = _color(color)
        painter.setPen(
            QPen(
                base,
                max(1.4, s * .075),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        mark = QPainterPath()
        mark.moveTo(s * .18, s * .24)
        mark.cubicTo(s * .34, s * .14, s * .66, s * .14, s * .82, s * .24)
        mark.moveTo(s * .50, s * .20)
        mark.lineTo(s * .50, s * .69)
        painter.drawPath(mark)
        nib = QPainterPath()
        nib.moveTo(s * .36, s * .64)
        nib.lineTo(s * .50, s * .87)
        nib.lineTo(s * .64, s * .64)
        nib.closeSubpath()
        painter.setBrush(base)
        painter.drawPath(nib)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(s * .22, s * .39), QPointF(s * .38, s * .34))
        painter.drawLine(QPointF(s * .62, s * .34), QPointF(s * .78, s * .39))
        painter.drawLine(QPointF(s * .25, s * .53), QPointF(s * .39, s * .48))
        painter.drawLine(QPointF(s * .61, s * .48), QPointF(s * .75, s * .53))
    elif n in {"figma-full-mode", "figma_full_mode", "panel-layout"}:
        painter.drawRoundedRect(
            QRectF(s * .14, s * .22, s * .72, s * .56),
            s * .06,
            s * .06,
        )
        painter.drawLine(
            QPointF(s * .43, s * .22),
            QPointF(s * .43, s * .78),
        )
    elif n in {"focus-canvas", "focus_canvas", "fullscreen"}:
        # Four open corners read clearly at toolbar sizes and work for both
        # entering and leaving the distraction-free canvas mode.
        painter.drawLine(QPointF(s * .18, s * .38), QPointF(s * .18, s * .18))
        painter.drawLine(QPointF(s * .18, s * .18), QPointF(s * .38, s * .18))
        painter.drawLine(QPointF(s * .62, s * .18), QPointF(s * .82, s * .18))
        painter.drawLine(QPointF(s * .82, s * .18), QPointF(s * .82, s * .38))
        painter.drawLine(QPointF(s * .18, s * .62), QPointF(s * .18, s * .82))
        painter.drawLine(QPointF(s * .18, s * .82), QPointF(s * .38, s * .82))
        painter.drawLine(QPointF(s * .62, s * .82), QPointF(s * .82, s * .82))
        painter.drawLine(QPointF(s * .82, s * .82), QPointF(s * .82, s * .62))
    elif n in {"project", "folder"}:
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
    elif n in {"motion", "motion-designer", "motion_designer", "keyframes"}:
        painter.setPen(
            QPen(
                _color(color),
                max(1.4, s * .070),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        curve = QPainterPath()
        curve.moveTo(s * .16, s * .58)
        curve.cubicTo(s * .30, s * .24, s * .43, s * .80, s * .58, s * .45)
        curve.cubicTo(s * .67, s * .25, s * .76, s * .28, s * .86, s * .36)
        painter.drawPath(curve)
        painter.setBrush(_color(color))
        painter.setPen(Qt.PenStyle.NoPen)
        for x, y in ((.16, .58), (.43, .68), (.58, .45), (.86, .36)):
            diamond = QPolygonF([
                QPointF(s * x, s * (y - .085)),
                QPointF(s * (x + .085), s * y),
                QPointF(s * x, s * (y + .085)),
                QPointF(s * (x - .085), s * y),
            ])
            painter.drawPolygon(diamond)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                _color(color),
                max(1.0, s * .052),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        for x in (.22, .42, .62, .82):
            painter.drawLine(QPointF(s * x, s * .78), QPointF(s * x, s * .88))
        painter.drawLine(QPointF(s * .14, s * .83), QPointF(s * .90, s * .83))
    elif n in {"more", "ellipsis"}:
        painter.setBrush(_color(color))
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (.28, .50, .72):
            painter.drawEllipse(QPointF(s * x, s * .50), s * .055, s * .055)
    elif n in {"favorite", "star"}:
        import math

        points = []
        for index in range(10):
            angle = math.radians(-90 + index * 36)
            radius = s * (.34 if index % 2 == 0 else .15)
            points.append(
                QPointF(
                    s * .50 + math.cos(angle) * radius,
                    s * .50 + math.sin(angle) * radius,
                )
            )
        painter.setBrush(_color(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF(points))
    elif n in {
        "boolean-union",
        "boolean_union",
        "boolean-subtract",
        "boolean_subtract",
        "boolean-intersect",
        "boolean_intersect",
        "boolean-exclude",
        "boolean_exclude",
    }:
        left_shape = QPainterPath()
        right_shape = QPainterPath()
        left_shape.addEllipse(QRectF(s * .16, s * .26, s * .46, s * .48))
        right_shape.addEllipse(QRectF(s * .38, s * .26, s * .46, s * .48))
        if "subtract" in n:
            result = left_shape.subtracted(right_shape)
        elif "intersect" in n:
            result = left_shape.intersected(right_shape)
        elif "exclude" in n:
            result = left_shape.united(right_shape).subtracted(
                left_shape.intersected(right_shape)
            )
        else:
            result = left_shape.united(right_shape)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawPath(result)
    elif n in {"filter", "funnel"}:
        funnel = QPainterPath()
        funnel.moveTo(s * .16, s * .22)
        funnel.lineTo(s * .84, s * .22)
        funnel.lineTo(s * .59, s * .51)
        funnel.lineTo(s * .59, s * .76)
        funnel.lineTo(s * .42, s * .84)
        funnel.lineTo(s * .42, s * .51)
        funnel.closeSubpath()
        painter.drawPath(funnel)
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
    elif n in {"copy", "duplicate"}:
        painter.drawRoundedRect(QRectF(s * .28, s * .18, s * .46, s * .56), 2, 2)
        painter.drawRoundedRect(QRectF(s * .18, s * .30, s * .46, s * .56), 2, 2)
        painter.drawLine(QPointF(s * .28, s * .44), QPointF(s * .54, s * .44))
        painter.drawLine(QPointF(s * .28, s * .58), QPointF(s * .54, s * .58))
    elif n in {"paste", "clipboard"}:
        painter.drawRoundedRect(QRectF(s * .22, s * .26, s * .56, s * .58), 2, 2)
        painter.drawRoundedRect(QRectF(s * .36, s * .16, s * .28, s * .18), 2, 2)
        painter.drawLine(QPointF(s * .34, s * .48), QPointF(s * .66, s * .48))
        painter.drawLine(QPointF(s * .34, s * .62), QPointF(s * .62, s * .62))
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
    elif n in {"lock", "locked"}:
        painter.drawRoundedRect(QRectF(s * .24, s * .44, s * .52, s * .36), 3, 3)
        painter.drawArc(QRectF(s * .32, s * .20, s * .36, s * .36), 0, 180 * 16)
        painter.drawLine(QPointF(s * .32, s * .38), QPointF(s * .32, s * .45))
        painter.drawLine(QPointF(s * .68, s * .38), QPointF(s * .68, s * .45))
    elif n in {"eye", "visible"}:
        eye = QPainterPath()
        eye.moveTo(s * .14, s * .50)
        eye.cubicTo(s * .28, s * .26, s * .72, s * .26, s * .86, s * .50)
        eye.cubicTo(s * .72, s * .74, s * .28, s * .74, s * .14, s * .50)
        painter.drawPath(eye)
        painter.setBrush(_color(color))
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .085, s * .085)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"eye-off", "hidden", "invisible"}:
        eye = QPainterPath()
        eye.moveTo(s * .16, s * .50)
        eye.cubicTo(s * .30, s * .30, s * .70, s * .30, s * .84, s * .50)
        eye.cubicTo(s * .70, s * .70, s * .30, s * .70, s * .16, s * .50)
        painter.drawPath(eye)
        painter.drawLine(QPointF(s * .22, s * .78), QPointF(s * .78, s * .22))
    elif n in {"grid"}:
        for y in (.22, .54):
            for x in (.22, .54):
                painter.drawRoundedRect(QRectF(s * x, s * y, s * .22, s * .22), 2, 2)
    elif n in {"ruler", "guides"}:
        painter.drawLine(QPointF(s * .18, s * .72), QPointF(s * .82, s * .72))
        painter.drawLine(QPointF(s * .18, s * .72), QPointF(s * .18, s * .28))
        for x, height in ((.32, .12), (.46, .20), (.60, .12), (.74, .20)):
            painter.drawLine(
                QPointF(s * x, s * .72),
                QPointF(s * x, s * (.72 - height)),
            )
        for y, width in ((.58, .12), (.44, .20), (.30, .12)):
            painter.drawLine(
                QPointF(s * .18, s * y),
                QPointF(s * (.18 + width), s * y),
            )
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
    elif n in {"image", "picture", "photo", "sticker"}:
        painter.drawRoundedRect(QRectF(s * .16, s * .22, s * .68, s * .56), 3, 3)
        painter.drawEllipse(QPointF(s * .34, s * .38), s * .065, s * .065)
        painter.drawPolyline(QPolygonF([
            QPointF(s * .22, s * .70),
            QPointF(s * .42, s * .50),
            QPointF(s * .54, s * .62),
            QPointF(s * .66, s * .46),
            QPointF(s * .80, s * .70),
        ]))
    elif n in {"ui-frame", "ui_frame", "frame-tool"}:
        painter.drawRect(QRectF(s * .18, s * .20, s * .64, s * .60))
        tick = s * .12
        for point, dx, dy in (
            (QPointF(s * .18, s * .20), tick, tick),
            (QPointF(s * .82, s * .20), -tick, tick),
            (QPointF(s * .18, s * .80), tick, -tick),
            (QPointF(s * .82, s * .80), -tick, -tick),
        ):
            painter.drawLine(point, QPointF(point.x() + dx, point.y()))
            painter.drawLine(point, QPointF(point.x(), point.y() + dy))
    elif n in {"rectangle", "rect-tool", "rect_tool"}:
        painter.drawRoundedRect(QRectF(s * .17, s * .24, s * .66, s * .52), 2, 2)
    elif n in {"ellipse", "oval", "ellipse-tool", "ellipse_tool"}:
        painter.drawEllipse(QRectF(s * .17, s * .24, s * .66, s * .52))
    elif n in {"line", "line-tool", "line_tool"}:
        painter.drawLine(QPointF(s * .18, s * .76), QPointF(s * .82, s * .24))
        painter.setBrush(_color(color))
        painter.drawEllipse(QPointF(s * .18, s * .76), s * .045, s * .045)
        painter.drawEllipse(QPointF(s * .82, s * .24), s * .045, s * .045)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"polygon", "polygon-tool", "polygon_tool"}:
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(s * .50, s * .16),
                    QPointF(s * .82, s * .35),
                    QPointF(s * .72, s * .76),
                    QPointF(s * .28, s * .76),
                    QPointF(s * .18, s * .35),
                ]
            )
        )
    elif n in {"arc", "arc-tool", "arc_tool"}:
        painter.drawArc(
            QRectF(s * .18, s * .18, s * .64, s * .64),
            25 * 16,
            280 * 16,
        )
        painter.drawLine(
            QPointF(s * .50, s * .50),
            QPointF(s * .79, s * .38),
        )
        painter.drawLine(
            QPointF(s * .50, s * .50),
            QPointF(s * .32, s * .75),
        )
    elif n in {"button", "ui-button", "ui_button"}:
        painter.drawRoundedRect(QRectF(s * .14, s * .28, s * .72, s * .44), s * .09, s * .09)
        painter.drawLine(QPointF(s * .34, s * .50), QPointF(s * .66, s * .50))
    elif n in {"progress", "progress-bar", "progress_bar"}:
        painter.drawRoundedRect(QRectF(s * .14, s * .38, s * .72, s * .24), s * .07, s * .07)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawRoundedRect(QRectF(s * .18, s * .42, s * .38, s * .16), s * .045, s * .045)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"marquee-rect", "rect-select", "rect_select", "selection-rect"}:
        dash_pen = QPen(_color(color), max(1.2, s * .070))
        dash_pen.setDashPattern([3.0, 3.0])
        dash_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(dash_pen)
        painter.drawRect(QRectF(s * .19, s * .24, s * .62, s * .52))
    elif n in {"marquee-ellipse", "ellipse-select", "ellipse_select", "selection-ellipse"}:
        dash_pen = QPen(_color(color), max(1.2, s * .070))
        dash_pen.setDashPattern([3.0, 3.0])
        dash_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(dash_pen)
        painter.drawEllipse(QRectF(s * .19, s * .24, s * .62, s * .52))
    elif n in {"crop", "crop-tool", "crop_tool"}:
        painter.drawLine(QPointF(s * .28, s * .12), QPointF(s * .28, s * .72))
        painter.drawLine(QPointF(s * .18, s * .28), QPointF(s * .78, s * .28))
        painter.drawLine(QPointF(s * .72, s * .28), QPointF(s * .72, s * .88))
        painter.drawLine(QPointF(s * .28, s * .72), QPointF(s * .88, s * .72))
        painter.drawLine(QPointF(s * .17, s * .17), QPointF(s * .28, s * .17))
        painter.drawLine(QPointF(s * .17, s * .17), QPointF(s * .17, s * .28))
        painter.drawLine(QPointF(s * .83, s * .83), QPointF(s * .72, s * .83))
        painter.drawLine(QPointF(s * .83, s * .83), QPointF(s * .83, s * .72))
    elif n in {"mirror-x", "mirror_x", "flip-horizontal", "flip_horizontal"}:
        painter.drawLine(QPointF(s * .50, s * .16), QPointF(s * .50, s * .84))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .16, s * .50),
            QPointF(s * .38, s * .28),
            QPointF(s * .38, s * .72),
        ]))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .84, s * .50),
            QPointF(s * .62, s * .28),
            QPointF(s * .62, s * .72),
        ]))
    elif n in {"mirror-y", "mirror_y", "flip-vertical", "flip_vertical"}:
        painter.drawLine(QPointF(s * .16, s * .50), QPointF(s * .84, s * .50))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .50, s * .16),
            QPointF(s * .28, s * .38),
            QPointF(s * .72, s * .38),
        ]))
        painter.drawPolygon(QPolygonF([
            QPointF(s * .50, s * .84),
            QPointF(s * .28, s * .62),
            QPointF(s * .72, s * .62),
        ]))
    elif n in {"eraser", "erase"}:
        painter.save()
        painter.translate(s * .50, s * .50)
        painter.rotate(-28)
        painter.translate(-s * .50, -s * .50)
        body = QRectF(s * .22, s * .38, s * .56, s * .28)
        painter.setBrush(QColor(255, 255, 255, 24))
        painter.drawRoundedRect(body, s * .07, s * .07)
        painter.drawLine(QPointF(s * .42, s * .39), QPointF(s * .42, s * .65))
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(s * .25, s * .78), QPointF(s * .74, s * .78))
    elif n in {"path", "path-tool", "path_tool", "bezier"}:
        curve = QPainterPath()
        curve.moveTo(s * .18, s * .68)
        curve.cubicTo(s * .28, s * .22, s * .58, s * .28, s * .80, s * .36)
        painter.drawPath(curve)
        painter.setBrush(_color(color))
        for x, y in ((.18, .68), (.46, .34), (.80, .36)):
            painter.drawEllipse(QPointF(s * x, s * y), s * .055, s * .055)
        painter.setBrush(Qt.BrushStyle.NoBrush)
    elif n in {"paint", "painter", "paint-brush", "paint_brush", "brush"}:
        painter.save()
        painter.setPen(QPen(_color(color), max(1.5, s * .075), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(QPointF(s * .66, s * .20), QPointF(s * .35, s * .62))
        painter.setPen(QPen(_color(color), max(1.0, s * .050), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(QRectF(s * .30, s * .56, s * .17, s * .12), s * .035, s * .035)
        bristle = QPainterPath()
        bristle.moveTo(s * .28, s * .66)
        bristle.cubicTo(s * .15, s * .69, s * .14, s * .80, s * .17, s * .88)
        bristle.cubicTo(s * .25, s * .83, s * .34, s * .82, s * .43, s * .70)
        bristle.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color(color))
        painter.drawPath(bristle)
        painter.restore()
    elif n in {"music-note", "music_note", "note", "musical-note", "musical_note"}:
        base = _color(color)
        painter.save()
        painter.setPen(QPen(base, max(1.6, s * .085), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(base)
        painter.translate(s * .50, s * .50)
        painter.rotate(-9)
        painter.translate(-s * .50, -s * .50)
        painter.drawEllipse(QRectF(s * .18, s * .58, s * .25, s * .16))
        painter.drawEllipse(QRectF(s * .58, s * .53, s * .25, s * .16))
        painter.drawLine(QPointF(s * .38, s * .61), QPointF(s * .38, s * .22))
        painter.drawLine(QPointF(s * .78, s * .56), QPointF(s * .78, s * .17))
        beam = QPainterPath()
        beam.moveTo(s * .38, s * .22)
        beam.lineTo(s * .78, s * .17)
        beam.lineTo(s * .78, s * .28)
        beam.lineTo(s * .38, s * .33)
        beam.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(beam)
        painter.restore()
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
    elif n in {"sound-lab", "sound_lab", "audio-lab", "audio_lab"}:
        _paint_sound_lab_logo(painter, QRectF(0, 0, s, s), color)
    elif n in {"composer", "music-composer", "music_composer", "music-lab", "music_lab"}:
        _paint_composer_logo(painter, QRectF(0, 0, s, s), color)
    elif n in {"voice", "voice-lab", "voice_lab", "tts", "tts-lab", "tts_lab"}:
        _paint_voice_lab_logo(painter, QRectF(0, 0, s, s), color)
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
    elif n in {"move-tool", "move_tool", "four-way-arrow"}:
        center = QPointF(s * .50, s * .50)
        painter.drawLine(QPointF(s * .50, s * .14), QPointF(s * .50, s * .86))
        painter.drawLine(QPointF(s * .14, s * .50), QPointF(s * .86, s * .50))
        for points in (
            ((.50, .10), (.40, .24), (.60, .24)),
            ((.50, .90), (.40, .76), (.60, .76)),
            ((.10, .50), (.24, .40), (.24, .60)),
            ((.90, .50), (.76, .40), (.76, .60)),
        ):
            painter.setBrush(_color(color))
            painter.drawPolygon(QPolygonF([QPointF(s * x, s * y) for x, y in points]))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, s * .035, s * .035)
    elif n in {"magic-wand", "magic_wand", "wand"}:
        painter.setPen(
            QPen(
                _color(color),
                max(1.8, s * .105),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        painter.drawLine(QPointF(s * .23, s * .78), QPointF(s * .65, s * .36))
        painter.setPen(QPen(_color(color), max(1.2, s * .065)))
        for cx, cy, radius in ((.72, .23, .13), (.81, .48, .08), (.48, .18, .065)):
            painter.drawLine(
                QPointF(s * cx, s * (cy - radius)),
                QPointF(s * cx, s * (cy + radius)),
            )
            painter.drawLine(
                QPointF(s * (cx - radius), s * cy),
                QPointF(s * (cx + radius), s * cy),
            )
    elif n in {"paint-bucket", "paint_bucket", "bucket-fill", "bucket_fill"}:
        painter.save()
        painter.translate(s * .50, s * .50)
        painter.rotate(-35)
        bucket = QPolygonF(
            [
                QPointF(-s * .23, -s * .20),
                QPointF(s * .20, -s * .20),
                QPointF(s * .25, s * .18),
                QPointF(-s * .25, s * .18),
            ]
        )
        painter.drawPolygon(bucket)
        painter.drawArc(QRectF(-s * .19, -s * .35, s * .38, s * .30), 0, 180 * 16)
        painter.restore()
        drop = QPainterPath()
        drop.moveTo(s * .78, s * .55)
        drop.cubicTo(s * .68, s * .68, s * .69, s * .82, s * .78, s * .84)
        drop.cubicTo(s * .88, s * .82, s * .89, s * .68, s * .78, s * .55)
        painter.drawPath(drop)
    elif n in {"quick-mask", "quick_mask"}:
        dash_pen = QPen(_color(color), max(1.2, s * .060))
        dash_pen.setDashPattern([2.4, 2.4])
        painter.setPen(dash_pen)
        painter.drawRect(QRectF(s * .14, s * .19, s * .72, s * .62))
        painter.setPen(QPen(_color(color), max(1.5, s * .080)))
        painter.drawEllipse(QPointF(s * .50, s * .50), s * .20, s * .20)
    elif n in {"zoom-fit", "zoom_fit", "fit-view", "fit_view"}:
        corner = s * .18
        for x, y, dx, dy in (
            (.14, .14, 1, 1),
            (.86, .14, -1, 1),
            (.14, .86, 1, -1),
            (.86, .86, -1, -1),
        ):
            painter.drawLine(
                QPointF(s * x, s * y),
                QPointF(s * x + corner * dx, s * y),
            )
            painter.drawLine(
                QPointF(s * x, s * y),
                QPointF(s * x, s * y + corner * dy),
            )
        painter.drawEllipse(QPointF(s * .50, s * .48), s * .15, s * .15)
        painter.drawLine(QPointF(s * .61, s * .59), QPointF(s * .72, s * .70))
    elif n in {"pen-nib", "pen_nib", "bezier-pen", "bezier_pen"}:
        nib = QPolygonF(
            [
                QPointF(s * .50, s * .12),
                QPointF(s * .76, s * .39),
                QPointF(s * .62, s * .78),
                QPointF(s * .38, s * .78),
                QPointF(s * .24, s * .39),
            ]
        )
        painter.drawPolygon(nib)
        painter.drawEllipse(QPointF(s * .50, s * .47), s * .075, s * .075)
        painter.drawLine(QPointF(s * .50, s * .55), QPointF(s * .50, s * .78))
    elif n in {"pencil", "freehand"}:
        painter.save()
        painter.translate(s * .50, s * .50)
        painter.rotate(-42.0)
        painter.drawRoundedRect(QRectF(-s * .10, -s * .36, s * .20, s * .58), s * .04, s * .04)
        tip = QPolygonF([
            QPointF(-s * .10, s * .22),
            QPointF(s * .10, s * .22),
            QPointF(0.0, s * .39),
        ])
        painter.drawPolygon(tip)
        painter.drawLine(QPointF(-s * .10, -s * .23), QPointF(s * .10, -s * .23))
        painter.restore()
    elif n in {"zoom", "search", "zoom-in", "zoom_in", "zoom-out", "zoom_out"}:
        painter.drawEllipse(QPointF(s * .43, s * .42), s * .23, s * .23)
        painter.drawLine(QPointF(s * .60, s * .60), QPointF(s * .82, s * .82))
        if n in {"zoom-in", "zoom_in", "zoom-out", "zoom_out"}:
            painter.drawLine(
                QPointF(s * .31, s * .42),
                QPointF(s * .55, s * .42),
            )
            if n in {"zoom-in", "zoom_in"}:
                painter.drawLine(
                    QPointF(s * .43, s * .30),
                    QPointF(s * .43, s * .54),
                )
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
    elif n in {"hand", "pan"}:
        painter.drawLine(QPointF(s * .36, s * .48), QPointF(s * .36, s * .24))
        painter.drawLine(QPointF(s * .48, s * .48), QPointF(s * .48, s * .18))
        painter.drawLine(QPointF(s * .60, s * .50), QPointF(s * .60, s * .24))
        painter.drawLine(QPointF(s * .72, s * .56), QPointF(s * .72, s * .34))
        palm = QPainterPath()
        palm.moveTo(s * .26, s * .46)
        palm.cubicTo(s * .18, s * .52, s * .22, s * .64, s * .34, s * .74)
        palm.cubicTo(s * .46, s * .86, s * .72, s * .84, s * .78, s * .64)
        palm.lineTo(s * .78, s * .50)
        painter.drawPath(palm)
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


@lru_cache(maxsize=64)
def sound_lab_wide_icon(width: int = 220, height: int = 40, *, color: str = "#FFFFFF") -> QIcon:
    safe_width = max(48, int(width or 220))
    safe_height = max(24, int(height or 40))
    pix = QPixmap(safe_width, safe_height)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _paint_sound_lab_logo(painter, QRectF(0, 0, float(safe_width), float(safe_height)), color)
    painter.end()
    return QIcon(pix)


@lru_cache(maxsize=64)
def composer_wide_icon(width: int = 260, height: int = 42, *, color: str = "#FFFFFF") -> QIcon:
    safe_width = max(72, int(width or 260))
    safe_height = max(26, int(height or 42))
    pix = QPixmap(safe_width, safe_height)
    pix.fill(Qt.GlobalColor.transparent)
    logo_path = Path(__file__).resolve().parents[1] / "resources" / "branding" / "composer_logo.png"
    if logo_path.exists():
        logo = QPixmap(str(logo_path))
        if not logo.isNull():
            scaled = logo.scaled(
                QSize(safe_width, safe_height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter = QPainter(pix)
            painter.drawPixmap(
                int((safe_width - scaled.width()) / 2),
                int((safe_height - scaled.height()) / 2),
                scaled,
            )
            painter.end()
            return QIcon(pix)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _paint_composer_logo(painter, QRectF(0, 0, float(safe_width), float(safe_height)), color)
    painter.end()
    return QIcon(pix)


@lru_cache(maxsize=64)
def voice_lab_wide_icon(width: int = 260, height: int = 42, *, color: str = "#FFFFFF") -> QIcon:
    safe_width = max(72, int(width or 260))
    safe_height = max(26, int(height or 42))
    pix = QPixmap(safe_width, safe_height)
    pix.fill(Qt.GlobalColor.transparent)
    logo_path = Path(__file__).resolve().parents[1] / "resources" / "branding" / "voice_lab_logo.png"
    if logo_path.exists():
        logo = QPixmap(str(logo_path))
        if not logo.isNull():
            scaled = logo.scaled(
                QSize(safe_width, safe_height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled = _key_light_logo(scaled, color)
            painter = QPainter(pix)
            painter.drawPixmap(
                int((safe_width - scaled.width()) / 2),
                int((safe_height - scaled.height()) / 2),
                scaled,
            )
            painter.end()
            return QIcon(pix)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _paint_voice_lab_logo(painter, QRectF(0, 0, float(safe_width), float(safe_height)), color)
    painter.end()
    return QIcon(pix)


@lru_cache(maxsize=64)
def unreal_engine_icon(size: int = 18, *, color: str = "#FFFFFF") -> QIcon:
    safe_size = max(12, int(size or 18))
    logo_path = Path(__file__).resolve().parents[1] / "resources" / "branding" / "unreal_engine_logo.svg"
    source = QIcon(str(logo_path)).pixmap(safe_size, safe_size)
    pix = QPixmap(safe_size, safe_size)
    pix.fill(Qt.GlobalColor.transparent)
    if source.isNull():
        return app_icon("link", size=safe_size, color=color)

    image = source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    base = _color(color)
    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            alpha = pixel.alpha()
            if alpha <= 0:
                continue
            image.setPixelColor(x, y, QColor(base.red(), base.green(), base.blue(), alpha))
    return QIcon(QPixmap.fromImage(image))


def icon_size(px: int = 16) -> QSize:
    return QSize(px, px)
