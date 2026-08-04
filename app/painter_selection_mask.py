"""Pixel-accurate selection masks and deterministic selection operations."""
from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from PySide6.QtGui import QImage


def _qimage_rgba(image: QImage) -> Image.Image:
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    raw = bytes(converted.constBits())
    return Image.frombuffer(
        "RGBA",
        (converted.width(), converted.height()),
        raw,
        "raw",
        "RGBA",
        converted.bytesPerLine(),
        1,
    ).copy()


def _pil_mask_to_qimage(mask: Image.Image) -> QImage:
    prepared = mask.convert("L")
    raw = prepared.tobytes()
    return QImage(
        raw,
        prepared.width,
        prepared.height,
        prepared.width,
        QImage.Format.Format_Alpha8,
    ).copy()


def _qimage_mask_to_pil(mask: QImage, width: int = 0, height: int = 0) -> Image.Image:
    if mask.format() in {QImage.Format.Format_Alpha8, QImage.Format.Format_Grayscale8}:
        converted = mask
        raw = bytes(converted.constBits())
        image = Image.frombuffer(
            "L", (converted.width(), converted.height()), raw, "raw", "L",
            converted.bytesPerLine(), 1,
        ).copy()
    else:
        rgba = _qimage_rgba(mask)
        alpha = rgba.getchannel("A")
        image = alpha if alpha.getextrema()[0] < 255 else rgba.convert("L")
    if width > 0 and height > 0 and image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.NEAREST)
    return image


def selection_mask_alpha8(mask: QImage, width: int = 0, height: int = 0) -> QImage:
    return _pil_mask_to_qimage(_qimage_mask_to_pil(mask, width, height))


def polygon_selection_mask(
    width: int,
    height: int,
    points: Sequence[tuple[float, float]],
    *,
    ellipse: bool = False,
) -> QImage:
    width, height = max(1, int(width)), max(1, int(height))
    mask = Image.new("L", (width, height), 0)
    rows = [(float(x) * width, float(y) * height) for x, y in points]
    if len(rows) >= 3:
        draw = ImageDraw.Draw(mask)
        if ellipse:
            xs, ys = [p[0] for p in rows], [p[1] for p in rows]
            draw.ellipse((min(xs), min(ys), max(xs), max(ys)), fill=255)
        else:
            draw.polygon(rows, fill=255)
    return _pil_mask_to_qimage(mask)


def color_selection_mask(
    image: QImage,
    x: int,
    y: int,
    *,
    tolerance: int = 32,
    contiguous: bool = True,
) -> QImage:
    source = _qimage_rgba(image)
    width, height = source.size
    x, y = max(0, min(width - 1, int(x))), max(0, min(height - 1, int(y)))
    tolerance = max(0, min(255, int(tolerance)))
    target = source.getpixel((x, y))

    def matches(pixel) -> bool:
        return max(abs(int(pixel[i]) - int(target[i])) for i in range(4)) <= tolerance

    selected = Image.new("L", source.size, 0)
    out = selected.load()
    pixels = source.load()
    if not contiguous:
        for py in range(height):
            for px in range(width):
                if matches(pixels[px, py]):
                    out[px, py] = 255
        return _pil_mask_to_qimage(selected)
    queue = deque([(x, y)])
    out[x, y] = 255
    while queue:
        px, py = queue.popleft()
        for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
            if 0 <= nx < width and 0 <= ny < height and out[nx, ny] == 0:
                if matches(pixels[nx, ny]):
                    out[nx, ny] = 255
                    queue.append((nx, ny))
    return _pil_mask_to_qimage(selected)


def combine_selection_masks(
    current: QImage | None,
    incoming: QImage,
    mode: str = "new",
) -> QImage:
    right = _qimage_mask_to_pil(incoming)
    if current is None or current.isNull() or mode == "new":
        return _pil_mask_to_qimage(right)
    left = _qimage_mask_to_pil(current, *right.size)
    normalized = str(mode or "new").casefold()
    if normalized == "add":
        result = ImageChops.lighter(left, right)
    elif normalized == "subtract":
        result = ImageChops.subtract(left, right)
    elif normalized == "intersect":
        result = ImageChops.darker(left, right)
    else:
        result = right
    return _pil_mask_to_qimage(result)


def modify_selection_mask(mask: QImage, operation: str, radius_px: float) -> QImage:
    source = _qimage_mask_to_pil(mask)
    radius = max(0, int(round(float(radius_px))))
    operation = str(operation or "feather").casefold()
    if operation == "feather":
        result = source.filter(ImageFilter.GaussianBlur(max(0.0, float(radius_px))))
    else:
        # Pillow limits one Min/MaxFilter kernel to 99px. Repeating square
        # morphology composes radii exactly, while the former silent size=99
        # clamp made every requested radius above 49px incorrect.
        effective = min(radius, max(source.size))
        expanded = _square_morphology(source, effective, maximum=True)
        contracted = _square_morphology(source, effective, maximum=False)
        if operation == "expand":
            result = expanded
        elif operation == "contract":
            result = contracted
        elif operation == "border":
            result = ImageChops.subtract(expanded, contracted)
        else:
            raise ValueError(f"Unsupported selection operation: {operation}")
    return _pil_mask_to_qimage(result)


def _square_morphology(mask: Image.Image, radius: int, *, maximum: bool) -> Image.Image:
    remaining = max(0, int(radius))
    result = mask
    filter_type = ImageFilter.MaxFilter if maximum else ImageFilter.MinFilter
    while remaining:
        step = min(49, remaining)
        result = result.filter(filter_type(step * 2 + 1))
        remaining -= step
    return result.copy() if result is mask else result


def invert_selection_mask(mask: QImage) -> QImage:
    return _pil_mask_to_qimage(ImageChops.invert(_qimage_mask_to_pil(mask)))


def selection_mask_bounds(mask: QImage) -> tuple[int, int, int, int] | None:
    bbox = _qimage_mask_to_pil(mask).getbbox()
    return tuple(int(value) for value in bbox) if bbox else None


__all__ = [
    "color_selection_mask",
    "combine_selection_masks",
    "modify_selection_mask",
    "invert_selection_mask",
    "polygon_selection_mask",
    "selection_mask_bounds",
    "selection_mask_alpha8",
]
