"""Deterministic print-guide geometry for the Painter canvas."""
from __future__ import annotations

from typing import Mapping


def output_guide_geometry(
    settings: Mapping[str, object] | None,
    *,
    pixel_width: int,
    pixel_height: int,
) -> dict[str, object] | None:
    from app.painter_output import normalize_output_settings

    normalized = normalize_output_settings(
        dict(settings or {}),
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )
    if normalized["mode"] != "print":
        return None

    width = float(pixel_width)
    height = float(pixel_height)
    trim_width_mm = float(normalized["width_mm"])
    trim_height_mm = float(normalized["height_mm"])
    bleed_mm = (
        float(normalized["bleed_mm"])
        if bool(normalized["include_bleed"])
        else 0.0
    )
    safe_mm = float(normalized["safe_margin_mm"])
    full_width_mm = trim_width_mm + bleed_mm * 2.0
    full_height_mm = trim_height_mm + bleed_mm * 2.0
    bleed_x = width * bleed_mm / full_width_mm
    bleed_y = height * bleed_mm / full_height_mm
    trim = (
        bleed_x,
        bleed_y,
        max(0.0, width - bleed_x * 2.0),
        max(0.0, height - bleed_y * 2.0),
    )
    safe_x = min(trim[2] / 2.0, width * safe_mm / full_width_mm)
    safe_y = min(trim[3] / 2.0, height * safe_mm / full_height_mm)
    safe = (
        trim[0] + safe_x,
        trim[1] + safe_y,
        max(0.0, trim[2] - safe_x * 2.0),
        max(0.0, trim[3] - safe_y * 2.0),
    )
    return {
        "settings": normalized,
        "trim_rect": trim,
        "safe_rect": safe,
        "safe_visible": safe_mm > 0.0,
    }


__all__ = ["output_guide_geometry"]
