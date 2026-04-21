from __future__ import annotations

import ctypes
from ctypes import wintypes

from PIL import Image, ImageDraw
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", _POINT),
    ]


def cursor_position_logical() -> tuple[int, int] | None:
    """Return cursor position in Qt logical (virtual-desktop) coordinates.

    Uses ``QGuiApplication.screens()`` + ``QCursor.pos()`` which already
    reports in logical coords consistent with our RegionSelectorOverlay.

    Returns None when the cursor is hidden (e.g., fullscreen apps).
    """
    try:
        ci = _CURSORINFO()
        ci.cbSize = ctypes.sizeof(_CURSORINFO)
        if not ctypes.windll.user32.GetCursorInfo(ctypes.byref(ci)):
            return None
        CURSOR_SHOWING = 0x00000001
        if not (ci.flags & CURSOR_SHOWING):
            return None
    except Exception:
        pass

    from PySide6.QtGui import QCursor

    pos = QCursor.pos()
    return (pos.x(), pos.y())


def composite_cursor(
    image: Image.Image,
    rect_logical: QRect,
) -> Image.Image:
    """Draw a simple arrow cursor onto ``image`` at the current cursor
    position, if the cursor is inside ``rect_logical``.

    ``image`` is assumed to be in physical pixels (as returned by
    ``QScreen.grabWindow``). ``rect_logical`` is the region being captured
    in Qt logical coords.
    """
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
    """Draw a simple Windows-like arrow cursor at (x, y) in ``img``."""
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
