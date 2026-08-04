"""Figma-style text resizing modes and geometry helpers."""
from __future__ import annotations

import math
from typing import Any, Mapping

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetricsF


TEXT_RESIZE_MODES = ("auto_width", "auto_height", "fixed_size")


def normalize_text_resize_mode(value: Any) -> str:
    mode = str(value or "auto_width").strip().casefold().replace("-", "_")
    return mode if mode in TEXT_RESIZE_MODES else "auto_width"


def text_line_height_px(
    metrics: QFontMetricsF,
    style: Mapping[str, Any] | None,
) -> float:
    """Resolve legacy line-height ratios and imported Figma pixel values."""
    style = style if isinstance(style, Mapping) else {}
    try:
        value = float(style.get("line_height") or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    unit = str(style.get("line_height_unit") or "").strip().casefold()
    if unit in {"px", "pixel", "pixels"} or value > 4.0:
        return max(1.0, value or metrics.height())
    ratio = max(0.5, min(4.0, value or 1.2))
    return max(1.0, metrics.height() * ratio)


def text_content_geometry(
    text: str,
    style: Mapping[str, Any] | None,
    *,
    mode: str,
    width: float,
    height: float,
) -> tuple[float, float]:
    """Return document-space text bounds for a Figma resizing mode."""
    style = dict(style or {})
    font = QFont(str(style.get("font_family") or "Inter"))
    font.setPixelSize(max(1, round(float(style.get("font_size") or 16.0))))
    font.setWeight(
        QFont.Weight(max(100, min(900, int(style.get("font_weight") or 400))))
    )
    metrics = QFontMetricsF(font)
    value = str(text or "") or " "
    line_height = text_line_height_px(metrics, style)
    resize_mode = normalize_text_resize_mode(mode)
    if resize_mode == "fixed_size":
        return max(1.0, float(width)), max(1.0, float(height))
    if resize_mode == "auto_width":
        lines = value.splitlines() or [" "]
        measured_width = max(metrics.horizontalAdvance(line or " ") for line in lines)
        return max(4.0, math.ceil(measured_width + 4.0)), max(
            line_height,
            math.ceil(line_height * len(lines)),
        )
    wrap_width = max(4.0, float(width))
    bounds = metrics.boundingRect(
        QRectF(0.0, 0.0, wrap_width, 100000.0),
        int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft),
        value,
    )
    return wrap_width, max(line_height, math.ceil(bounds.height() + 2.0))


__all__ = [
    "TEXT_RESIZE_MODES",
    "normalize_text_resize_mode",
    "text_content_geometry",
    "text_line_height_px",
]
