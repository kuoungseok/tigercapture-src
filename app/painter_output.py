from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MM_PER_INCH = 25.4
PAINTER_OUTPUT_SCHEMA = "tigerstudio.painter.output.v1"


@dataclass(frozen=True)
class PrintPreset:
    name: str
    width_mm: float
    height_mm: float
    ppi: int = 300
    bleed_mm: float = 3.0
    output_kind: str = "color"


PRINT_PRESETS: tuple[PrintPreset, ...] = (
    PrintPreset("A4 Print · 300 PPI", 210.0, 297.0),
    PrintPreset("A5 Print · 300 PPI", 148.0, 210.0),
    PrintPreset("B5 Manga · 600 PPI", 182.0, 257.0, 600, 3.0, "line_art"),
    PrintPreset("Postcard · 300 PPI", 100.0, 148.0),
    PrintPreset("A3 Poster · 300 PPI", 297.0, 420.0),
    PrintPreset("A2 Large Poster · 150 PPI", 420.0, 594.0, 150, 5.0, "large_format"),
    PrintPreset("Square 200 mm · 300 PPI", 200.0, 200.0),
)

OUTPUT_KIND_TARGET_PPI = {
    "color": 300,
    "line_art": 600,
    "large_format": 150,
}


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def to_millimetres(value: float, unit: str) -> float:
    return float(value) * MM_PER_INCH if str(unit).casefold() in {"in", "inch", "inches"} else float(value)


def from_millimetres(value_mm: float, unit: str) -> float:
    return float(value_mm) / MM_PER_INCH if str(unit).casefold() in {"in", "inch", "inches"} else float(value_mm)


def pixels_for_print(
    width: float,
    height: float,
    *,
    unit: str = "mm",
    ppi: int = 300,
    bleed_mm: float = 0.0,
    include_bleed: bool = True,
) -> tuple[int, int]:
    width_mm = max(0.1, to_millimetres(width, unit))
    height_mm = max(0.1, to_millimetres(height, unit))
    bleed = max(0.0, float(bleed_mm)) if include_bleed else 0.0
    return (
        max(1, int(round((width_mm + bleed * 2.0) / MM_PER_INCH * max(1, int(ppi))))),
        max(1, int(round((height_mm + bleed * 2.0) / MM_PER_INCH * max(1, int(ppi))))),
    )


def print_size_from_pixels(
    pixel_width: int,
    pixel_height: int,
    *,
    ppi: int,
    unit: str = "mm",
    bleed_mm: float = 0.0,
) -> tuple[float, float]:
    safe_ppi = max(1, int(ppi))
    full_width_mm = max(0.1, int(pixel_width)) / safe_ppi * MM_PER_INCH
    full_height_mm = max(0.1, int(pixel_height)) / safe_ppi * MM_PER_INCH
    trim_width_mm = max(0.1, full_width_mm - max(0.0, bleed_mm) * 2.0)
    trim_height_mm = max(0.1, full_height_mm - max(0.0, bleed_mm) * 2.0)
    return (
        from_millimetres(trim_width_mm, unit),
        from_millimetres(trim_height_mm, unit),
    )


def normalize_output_settings(
    payload: dict | None,
    *,
    pixel_width: int,
    pixel_height: int,
) -> dict:
    source = payload if isinstance(payload, dict) else {}
    mode = str(source.get("mode") or "screen").strip().casefold()
    if mode not in {"screen", "print"}:
        mode = "screen"
    output_kind = str(source.get("output_kind") or "color").strip().casefold()
    if output_kind not in OUTPUT_KIND_TARGET_PPI:
        output_kind = "color"
    ppi = max(36, min(1200, int(round(_number(source.get("ppi"), 300 if mode == "print" else 96)))))
    bleed_mm = max(0.0, min(50.0, _number(source.get("bleed_mm"), 3.0 if mode == "print" else 0.0)))
    width_mm = _number(source.get("width_mm"), 0.0)
    height_mm = _number(source.get("height_mm"), 0.0)
    if width_mm <= 0.0 or height_mm <= 0.0:
        width_mm, height_mm = print_size_from_pixels(
            pixel_width,
            pixel_height,
            ppi=ppi,
            unit="mm",
            bleed_mm=bleed_mm if mode == "print" else 0.0,
        )
    return {
        "schema": PAINTER_OUTPUT_SCHEMA,
        "mode": mode,
        "unit": "mm",
        "width_mm": round(max(0.1, width_mm), 4),
        "height_mm": round(max(0.1, height_mm), 4),
        "ppi": ppi,
        "bleed_mm": round(bleed_mm, 4),
        "include_bleed": bool(source.get("include_bleed", mode == "print")),
        "safe_margin_mm": round(max(0.0, min(100.0, _number(source.get("safe_margin_mm"), 5.0 if mode == "print" else 0.0))), 4),
        "output_kind": output_kind,
        "color_space": str(source.get("color_space") or "srgb"),
        "resample": bool(source.get("resample", True)),
        "pixel_width": max(1, int(pixel_width)),
        "pixel_height": max(1, int(pixel_height)),
    }


def effective_ppi(settings: dict, pixel_width: int, pixel_height: int) -> tuple[float, float]:
    normalized = normalize_output_settings(
        settings,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )
    bleed = normalized["bleed_mm"] if normalized["include_bleed"] else 0.0
    full_width_in = (normalized["width_mm"] + bleed * 2.0) / MM_PER_INCH
    full_height_in = (normalized["height_mm"] + bleed * 2.0) / MM_PER_INCH
    return (
        max(1, int(pixel_width)) / max(0.001, full_width_in),
        max(1, int(pixel_height)) / max(0.001, full_height_in),
    )


def output_preflight(
    settings: dict | None,
    *,
    pixel_width: int,
    pixel_height: int,
) -> dict:
    normalized = normalize_output_settings(
        settings,
        pixel_width=pixel_width,
        pixel_height=pixel_height,
    )
    warnings: list[str] = []
    errors: list[str] = []
    if normalized["mode"] == "screen":
        return {
            "schema": "tigerstudio.painter.output-preflight.v1",
            "ok": True,
            "mode": "screen",
            "settings": normalized,
            "effective_ppi": None,
            "target_ppi": None,
            "warnings": [],
            "errors": [],
            "summary": f"{pixel_width} × {pixel_height} px · screen",
        }
    x_ppi, y_ppi = effective_ppi(normalized, pixel_width, pixel_height)
    effective = min(x_ppi, y_ppi)
    target = OUTPUT_KIND_TARGET_PPI[normalized["output_kind"]]
    if effective < target * 0.5:
        errors.append(
            f"Effective resolution {effective:.0f} PPI is far below the {target} PPI target."
        )
    elif effective < target * 0.9:
        warnings.append(
            f"Effective resolution {effective:.0f} PPI is below the {target} PPI target."
        )
    if normalized["bleed_mm"] <= 0.0:
        warnings.append("No bleed is configured; confirm this with the printer.")
    if normalized["color_space"] == "srgb":
        warnings.append("Document colors are sRGB; confirm the printer's requested profile.")
    if pixel_width > 16384 or pixel_height > 16384:
        errors.append("Pixel dimensions exceed Painter's 16384 px canvas limit.")
    return {
        "schema": "tigerstudio.painter.output-preflight.v1",
        "ok": not errors,
        "mode": "print",
        "settings": normalized,
        "effective_ppi": round(effective, 2),
        "effective_ppi_x": round(x_ppi, 2),
        "effective_ppi_y": round(y_ppi, 2),
        "target_ppi": target,
        "warnings": warnings,
        "errors": errors,
        "summary": (
            f"{normalized['width_mm']:g} × {normalized['height_mm']:g} mm · "
            f"{effective:.0f} PPI · {pixel_width} × {pixel_height} px · "
            f"{normalized['bleed_mm']:g} mm bleed"
        ),
    }
