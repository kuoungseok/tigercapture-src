from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from app.painter_dimensions import nonnegative_real, positive_integer, positive_real


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
    PrintPreset("Manga B5 182×257 mm · 600 PPI", 182.0, 257.0, 600, 3.0, "line_art"),
    PrintPreset("Tiger Postcard · 300 PPI", 100.0, 148.0),
    PrintPreset("A3 Poster · 300 PPI", 297.0, 420.0),
    PrintPreset("A2 Large Poster · 150 PPI", 420.0, 594.0, 150, 5.0, "large_format"),
    PrintPreset("Square 200 mm · 300 PPI", 200.0, 200.0),
)

PRINT_PRESET_MODEL_CONTRACT = {
    "schema": "tigerstudio.painter.print_preset_model.v1",
    "iso_216_trim_sizes": ("A2", "A3", "A4", "A5"),
    "manga_b5_source": "clip_studio_official_182x257mm_600dpi_guidance",
    "postcard_and_square_source": "tiger_authored_starting_presets",
    "bleed_and_safe_margin_source": "tiger_authored_starting_values_confirm_with_printer",
    "large_format_ppi_source": "tiger_authored_starting_value_confirm_with_printer",
    "universal_print_quality_claim": False,
    "universal_bleed_claim": False,
}

OUTPUT_KIND_TARGET_PPI = {
    "color": 300,
    "line_art": 600,
    "large_format": 150,
}

OUTPUT_KIND_TARGET_CONTRACT = {
    "color": {
        "source": "adobe_photoshop_general_high_quality_print_guidance",
        "url": "https://helpx.adobe.com/ca/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resolution-specs-for-printing-images.html",
        "printer_confirmation_required": True,
    },
    "line_art": {
        "source": "clip_studio_official_monochrome_manga_guidance",
        "url": "https://tips.clip-studio.com/en-us/articles/1747",
        "printer_confirmation_required": True,
    },
    "large_format": {
        "source": "tiger_authored_starting_point_not_a_print_quality_threshold",
        "url": "",
        "printer_confirmation_required": True,
    },
}

PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT = 16384
PAINTER_NEW_CANVAS_MIN_DIMENSION_PX = 64
PAINTER_CANVAS_LIMIT_CONTRACT = {
    "source": "tiger_authored_current_runtime_capacity_not_a_qt_or_file_format_limit",
    "limit_px_per_axis": PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT,
    "largest_native_runtime_evidence_px": [8192, 8192],
    "universal_capacity_claim": False,
}
PAINTER_NEW_CANVAS_DIMENSION_CONTRACT = {
    "source": "tiger_authored_new_canvas_control_domain_not_format_limit",
    "minimum_px_per_axis": PAINTER_NEW_CANVAS_MIN_DIMENSION_PX,
    "maximum_px_per_axis": PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT,
    "artwork_quality_threshold_claim": False,
}


def _number(value: Any, fallback: float) -> float:
    if isinstance(value, bool):
        return float(fallback)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return number if math.isfinite(number) else float(fallback)


def _boolean(value: Any, fallback: bool) -> bool:
    return value if isinstance(value, bool) else bool(fallback)


def to_millimetres(value: float, unit: str) -> float:
    normalized_unit = str(unit).strip().casefold()
    if normalized_unit not in {"mm", "in", "inch", "inches"}:
        raise ValueError(f"Unsupported Painter print unit: {unit}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Painter print dimension must be finite")
    return number * MM_PER_INCH if normalized_unit in {"in", "inch", "inches"} else number


def from_millimetres(value_mm: float, unit: str) -> float:
    normalized_unit = str(unit).strip().casefold()
    if normalized_unit not in {"mm", "in", "inch", "inches"}:
        raise ValueError(f"Unsupported Painter print unit: {unit}")
    number = float(value_mm)
    if not math.isfinite(number):
        raise ValueError("Painter print dimension must be finite")
    return number / MM_PER_INCH if normalized_unit in {"in", "inch", "inches"} else number


def pixels_for_print(
    width: float,
    height: float,
    *,
    unit: str = "mm",
    ppi: int = 300,
    bleed_mm: float = 0.0,
    include_bleed: bool = True,
) -> tuple[int, int]:
    width_mm = positive_real(to_millimetres(width, unit), field="print width")
    height_mm = positive_real(to_millimetres(height, unit), field="print height")
    resolved_ppi = positive_integer(ppi, field="print ppi")
    bleed = nonnegative_real(bleed_mm, field="print bleed_mm") if include_bleed else 0.0
    return (
        max(1, int(round((width_mm + bleed * 2.0) / MM_PER_INCH * resolved_ppi))),
        max(1, int(round((height_mm + bleed * 2.0) / MM_PER_INCH * resolved_ppi))),
    )


def print_size_from_pixels(
    pixel_width: int,
    pixel_height: int,
    *,
    ppi: int,
    unit: str = "mm",
    bleed_mm: float = 0.0,
) -> tuple[float, float]:
    safe_ppi = positive_integer(ppi, field="print ppi")
    resolved_width = positive_integer(pixel_width, field="pixel width")
    resolved_height = positive_integer(pixel_height, field="pixel height")
    bleed = nonnegative_real(bleed_mm, field="print bleed_mm")
    full_width_mm = resolved_width / safe_ppi * MM_PER_INCH
    full_height_mm = resolved_height / safe_ppi * MM_PER_INCH
    trim_width_mm = full_width_mm - bleed * 2.0
    trim_height_mm = full_height_mm - bleed * 2.0
    if trim_width_mm <= 0.0 or trim_height_mm <= 0.0:
        raise ValueError("Painter print bleed must leave a positive trim size")
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
    resolved_pixel_width = positive_integer(pixel_width, field="pixel width")
    resolved_pixel_height = positive_integer(pixel_height, field="pixel height")
    source = payload if isinstance(payload, dict) else {}
    mode = str(source.get("mode") or "screen").strip().casefold()
    if mode not in {"screen", "print"}:
        mode = "screen"
    output_kind = str(source.get("output_kind") or "color").strip().casefold()
    if output_kind not in OUTPUT_KIND_TARGET_PPI:
        output_kind = "color"
    include_bleed = _boolean(source.get("include_bleed"), mode == "print")
    ppi = max(36, min(1200, int(round(_number(source.get("ppi"), 300 if mode == "print" else 96)))))
    bleed_mm = max(0.0, min(50.0, _number(source.get("bleed_mm"), 3.0 if mode == "print" else 0.0)))
    width_mm = _number(source.get("width_mm"), 0.0)
    height_mm = _number(source.get("height_mm"), 0.0)
    if width_mm <= 0.0 or height_mm <= 0.0:
        width_mm, height_mm = print_size_from_pixels(
            resolved_pixel_width,
            resolved_pixel_height,
            ppi=ppi,
            unit="mm",
            bleed_mm=bleed_mm if mode == "print" and include_bleed else 0.0,
        )
    return {
        "schema": PAINTER_OUTPUT_SCHEMA,
        "mode": mode,
        "unit": "mm",
        "width_mm": round(max(0.1, width_mm), 4),
        "height_mm": round(max(0.1, height_mm), 4),
        "ppi": ppi,
        "bleed_mm": round(bleed_mm, 4),
        "include_bleed": include_bleed,
        "safe_margin_mm": round(max(0.0, min(100.0, _number(source.get("safe_margin_mm"), 5.0 if mode == "print" else 0.0))), 4),
        "output_kind": output_kind,
        "color_space": "srgb",
        "resample": _boolean(source.get("resample"), True),
        "pixel_width": resolved_pixel_width,
        "pixel_height": resolved_pixel_height,
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
        normalized["pixel_width"] / full_width_in,
        normalized["pixel_height"] / full_height_in,
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
    if (
        pixel_width > PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
        or pixel_height > PAINTER_CURRENT_CANVAS_DIMENSION_LIMIT
    ):
        errors.append(
            "Pixel dimensions exceed Tiger Painter's current authored runtime limit; "
            "this is not a Qt, PNG, TIFF, or PSD format limit."
        )
    if normalized["mode"] == "screen":
        return {
            "schema": "tigerstudio.painter.output-preflight.v1",
            "ok": not errors,
            "mode": "screen",
            "settings": normalized,
            "effective_ppi": None,
            "target_ppi": None,
            "target_contract": None,
            "print_quality_threshold_claim": False,
            "canvas_limit_contract": dict(PAINTER_CANVAS_LIMIT_CONTRACT),
            "warnings": [],
            "errors": errors,
            "summary": f"{pixel_width} × {pixel_height} px · screen",
        }
    x_ppi, y_ppi = effective_ppi(normalized, pixel_width, pixel_height)
    effective_bleed_mm = (
        float(normalized["bleed_mm"])
        if bool(normalized["include_bleed"])
        else 0.0
    )
    effective = min(x_ppi, y_ppi)
    target = OUTPUT_KIND_TARGET_PPI[normalized["output_kind"]]
    target_contract = OUTPUT_KIND_TARGET_CONTRACT[normalized["output_kind"]]
    if effective < target:
        warnings.append(
            f"Effective resolution {effective:.0f} PPI is below the {target} PPI guidance value."
        )
    warnings.append(
        "Resolution guidance is not a print-quality pass/fail threshold; confirm the required PPI with the printer or print service."
    )
    if not effective_bleed_mm:
        warnings.append("No bleed is configured; confirm this with the printer.")
    if normalized["color_space"] == "srgb":
        warnings.append("Document colors are sRGB; confirm the printer's requested profile.")
    return {
        "schema": "tigerstudio.painter.output-preflight.v1",
        "ok": not errors,
        "mode": "print",
        "settings": normalized,
        "effective_ppi": round(effective, 2),
        "effective_ppi_x": round(x_ppi, 2),
        "effective_ppi_y": round(y_ppi, 2),
        "target_ppi": target,
        "target_contract": dict(target_contract),
        "print_quality_threshold_claim": False,
        "canvas_limit_contract": dict(PAINTER_CANVAS_LIMIT_CONTRACT),
        "warnings": warnings,
        "errors": errors,
        "summary": (
            f"{normalized['width_mm']:g} × {normalized['height_mm']:g} mm · "
            f"{effective:.0f} PPI · {pixel_width} × {pixel_height} px · "
            f"{effective_bleed_mm:g} mm bleed"
        ),
    }
