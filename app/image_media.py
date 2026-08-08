"""Static image media helpers shared by editor import, preview, and export."""
from __future__ import annotations

from pathlib import Path
from typing import Any

IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp"})
DEFAULT_IMAGE_DURATION_MS = 5_000


def is_image_path(path: Path | str | None) -> bool:
    if path is None:
        return False
    try:
        return Path(path).suffix.casefold() in IMAGE_EXTS
    except Exception:
        return False


def _canvas_size(width: int | None, height: int | None) -> tuple[int, int]:
    try:
        w = int(width or 0)
    except Exception:
        w = 0
    try:
        h = int(height or 0)
    except Exception:
        h = 0
    return max(1, w), max(1, h)


def load_image_rgb(
    path: Path | str,
    width: int,
    height: int,
    *,
    fit: str = "contain",
    background: tuple[int, int, int] = (0, 0, 0),
) -> Any | None:
    """Load a still image into an RGB numpy array sized for the render canvas."""
    try:
        from PIL import Image
        import numpy as np
    except Exception:
        return None

    canvas_w, canvas_h = _canvas_size(width, height)
    try:
        image = Image.open(Path(path)).convert("RGBA")
    except Exception:
        return None
    src_w, src_h = image.size
    if src_w <= 0 or src_h <= 0:
        return None

    if str(fit or "contain").casefold() == "cover":
        scale = max(canvas_w / src_w, canvas_h / src_h)
    else:
        scale = min(canvas_w / src_w, canvas_h / src_h)
    dst_w = max(1, int(round(src_w * scale)))
    dst_h = max(1, int(round(src_h * scale)))
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS
    image = image.resize((dst_w, dst_h), resample)

    bg = Image.new("RGBA", (canvas_w, canvas_h), (*background, 255))
    if str(fit or "contain").casefold() == "cover":
        left = max(0, (dst_w - canvas_w) // 2)
        top = max(0, (dst_h - canvas_h) // 2)
        image = image.crop((left, top, left + canvas_w, top + canvas_h))
        bg.alpha_composite(image, (0, 0))
    else:
        bg.alpha_composite(image, ((canvas_w - dst_w) // 2, (canvas_h - dst_h) // 2))
    return np.ascontiguousarray(np.asarray(bg.convert("RGB"), dtype=np.uint8))


def image_pixmap(
    path: Path | str,
    width: int,
    height: int,
    *,
    fit: str = "contain",
    background: tuple[int, int, int] = (17, 18, 20),
):
    """Return a QPixmap thumbnail for a still image, or None on failure."""
    rgb = load_image_rgb(path, width, height, fit=fit, background=background)
    if rgb is None:
        return None
    try:
        from PySide6.QtGui import QImage, QPixmap
    except Exception:
        return None
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def image_timeline_thumbnails(path: Path | str, thumb_height: int) -> list[Any]:
    """Build a compact still-image thumbnail list for timeline tiling."""
    try:
        thumb_h = max(16, int(thumb_height))
    except Exception:
        thumb_h = 48
    pm = image_pixmap(path, max(1, int(round(thumb_h * 16 / 9))), thumb_h, fit="cover")
    return [pm] if pm is not None and not pm.isNull() else []


def preview_canvas_size(settings: dict | None, fallback: tuple[int, int] = (1280, 720)) -> tuple[int, int]:
    """Resolve a render canvas size from project settings with conservative defaults."""
    if not isinstance(settings, dict):
        return fallback
    candidates = (
        ("width", "height"),
        ("canvas_width", "canvas_height"),
        ("output_width", "output_height"),
        ("video_width", "video_height"),
    )
    for w_key, h_key in candidates:
        try:
            w = int(settings.get(w_key) or 0)
            h = int(settings.get(h_key) or 0)
        except Exception:
            continue
        if w > 0 and h > 0:
            return w, h
    video = settings.get("video") if isinstance(settings.get("video"), dict) else None
    if isinstance(video, dict):
        try:
            w = int(video.get("width") or video.get("canvas_width") or 0)
            h = int(video.get("height") or video.get("canvas_height") or 0)
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
    return fallback


__all__ = [
    "DEFAULT_IMAGE_DURATION_MS",
    "IMAGE_EXTS",
    "image_pixmap",
    "image_timeline_thumbnails",
    "is_image_path",
    "load_image_rgb",
    "preview_canvas_size",
]
