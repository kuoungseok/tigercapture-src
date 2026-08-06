"""Pixel-accurate alpha and luminance compositing for Painter UI masks."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtGui import QImage, QPainter


# One cropped 4K mask group should remain comfortably interactive and below a
# large full-frame triple-buffer allocation on supported desktop hardware.
PIXEL_MASK_SINGLE_GROUP_TIME_BUDGET_MS = 1500.0
PIXEL_MASK_CROPPED_TEMP_BUDGET_BYTES = 64 * 1024 * 1024


def ui_mask_render_mode(source: Mapping[str, Any]) -> str:
    """Return the authored mask mode without inventing provider semantics."""

    content = source.get("content")
    content = content if isinstance(content, Mapping) else {}
    figma_mask = content.get("figma_mask")
    figma_mask = figma_mask if isinstance(figma_mask, Mapping) else {}
    mode = str(figma_mask.get("type") or "").strip().casefold()
    return mode if mode in {"alpha", "luminance", "vector"} else "vector"


def ui_mask_uses_pixel_compositing(source: Mapping[str, Any]) -> bool:
    return ui_mask_render_mode(source) in {"alpha", "luminance"}


def _alpha8_from_mask(source: QImage, mode: str) -> QImage:
    if source.isNull():
        return QImage()
    if str(mode).casefold() != "luminance":
        return source.convertToFormat(QImage.Format.Format_Alpha8)

    # Figma luminance masks multiply Rec.709 luminance by the source alpha.
    # NumPy is already a required TigerCapture runtime dependency and avoids a
    # Python pixel loop on full-resolution UI artboards.
    import numpy as np

    rgba = source.convertToFormat(QImage.Format.Format_RGBA8888)
    width = rgba.width()
    height = rgba.height()
    rgba_bytes = np.frombuffer(
        rgba.bits(),
        dtype=np.uint8,
        count=rgba.sizeInBytes(),
    ).reshape(height, rgba.bytesPerLine())
    pixels = rgba_bytes[:, : width * 4].reshape(height, width, 4)
    luminance = (
        pixels[..., 0].astype(np.float32) * 0.2126
        + pixels[..., 1].astype(np.float32) * 0.7152
        + pixels[..., 2].astype(np.float32) * 0.0722
    )
    alpha = pixels[..., 3].astype(np.float32) / 255.0
    values = np.rint(luminance * alpha).clip(0.0, 255.0).astype(np.uint8)

    result = QImage(width, height, QImage.Format.Format_Alpha8)
    result.fill(0)
    result_bytes = np.frombuffer(
        result.bits(),
        dtype=np.uint8,
        count=result.sizeInBytes(),
    ).reshape(height, result.bytesPerLine())
    result_bytes[:, :width] = values
    return result


def apply_ui_pixel_mask(
    target: QImage,
    mask_source: QImage,
    *,
    mode: str,
    inverted: bool = False,
) -> QImage:
    """Apply one rendered mask to an already-composited target group."""

    if target.isNull() or mask_source.isNull():
        return target.copy()
    if target.size() != mask_source.size():
        raise ValueError("UI mask and target surfaces must have identical sizes")
    alpha = _alpha8_from_mask(mask_source, mode)
    output = target.copy()
    painter = QPainter(output)
    try:
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationOut
            if inverted
            else QPainter.CompositionMode.CompositionMode_DestinationIn
        )
        painter.drawImage(0, 0, alpha)
    finally:
        painter.end()
    return output


__all__ = [
    "PIXEL_MASK_CROPPED_TEMP_BUDGET_BYTES",
    "PIXEL_MASK_SINGLE_GROUP_TIME_BUDGET_MS",
    "apply_ui_pixel_mask",
    "ui_mask_render_mode",
    "ui_mask_uses_pixel_compositing",
]
