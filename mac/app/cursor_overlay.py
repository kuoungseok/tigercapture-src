"""macOS cursor overlay — draws a simple arrow cursor into captured
frames when the cursor is inside the captured region.

We don't try to replicate the actual macOS system cursor; the same
stylized arrow used on Windows is rendered via Pillow so capture output
is visually consistent across platforms. macOS's own cursor is hidden
in SCStream captures unless explicitly requested (see recorder.py).
"""
from __future__ import annotations

from PIL import Image, ImageDraw
from PySide6.QtCore import QRect
from PySide6.QtGui import QCursor, QGuiApplication


def cursor_position_logical() -> tuple[int, int] | None:
    pos = QCursor.pos()
    return (pos.x(), pos.y())


def composite_cursor(
    image: Image.Image,
    rect_logical: QRect,
) -> Image.Image:
    pos = cursor_position_logical()
    if pos is None:
        return image
    cx, cy = pos
    if not rect_logical.contains(cx, cy):
        return image

    screen = (
        QGuiApplication.screenAt(rect_logical.topLeft())
        or QGuiApplication.primaryScreen()
    )
    dpr = float(screen.devicePixelRatio())

    local_x = int((cx - rect_logical.x()) * dpr)
    local_y = int((cy - rect_logical.y()) * dpr)

    if image.mode != "RGB":
        image = image.convert("RGB")
    _draw_arrow_cursor(image, local_x, local_y, dpr)
    return image


def _draw_arrow_cursor(img: Image.Image, x: int, y: int, dpr: float) -> None:
    s = max(1.0, dpr)

    def p(px: float, py: float) -> tuple[int, int]:
        return (int(round(x + px * s)), int(round(y + py * s)))

    outline = [
        p(0, 0),
        p(0, 16),
        p(4, 12),
        p(7, 18),
        p(9.5, 17),
        p(6.5, 11),
        p(11, 11),
    ]

    draw = ImageDraw.Draw(img, "RGBA")
    draw.polygon(outline, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))

    outline_pen = [
        p(0.5, 0.5),
        p(0.5, 14.5),
        p(3.5, 11),
        p(6, 16.5),
        p(7.5, 16),
        p(4.5, 10),
        p(9, 10),
    ]
    draw.polygon(outline_pen, fill=(0, 0, 0, 255))
