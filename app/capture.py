from __future__ import annotations

from io import BytesIO

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QRect
from PySide6.QtGui import QGuiApplication, QImage


def capture_region(rect: QRect, include_cursor: bool = False) -> Image.Image:
    """Capture a screen region given in global (logical) coordinates.

    Uses ``QScreen.grabWindow`` so Qt handles per-monitor DPI internally;
    we do not manually scale by devicePixelRatio. Returns an RGB PIL Image
    at the native physical resolution of the source screen.

    When ``include_cursor`` is True, a simple arrow cursor is composited at
    the current cursor position if it falls inside the region.
    """
    screen = (
        QGuiApplication.screenAt(rect.topLeft())
        or QGuiApplication.screenAt(rect.center())
        or QGuiApplication.primaryScreen()
    )
    screen_origin = screen.geometry().topLeft()
    local_x = rect.x() - screen_origin.x()
    local_y = rect.y() - screen_origin.y()

    pixmap = screen.grabWindow(0, local_x, local_y, rect.width(), rect.height())
    qimg = pixmap.toImage()
    image = _qimage_to_pil(qimg)
    if include_cursor:
        from app.cursor_overlay import composite_cursor

        image = composite_cursor(image, rect)
    return image


def _qimage_to_pil(qimg: QImage) -> Image.Image:
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    qimg.save(buffer, "PNG")
    buffer.close()
    with BytesIO(bytes(byte_array)) as bio:
        img = Image.open(bio)
        img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def pil_to_qimage(img: Image.Image) -> QImage:
    """Convert a PIL Image to a QImage with independent memory."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return qimg.copy()
