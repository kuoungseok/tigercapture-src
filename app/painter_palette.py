from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Iterable


PAINTER_PALETTE_SCHEMA = "tigerstudio.painter.palette-library.v1"
PAINTER_BRUSH_BUNDLE_SCHEMA = "tigerstudio.painter.brush-bundle.v1"
MAX_RECENT_COLORS = 32
MAX_DOCUMENT_COLORS = 32
MAX_RECENT_BRUSHES = 16
HARMONY_MODES = {
    "full",
    "monochrome",
    "analogous",
    "complementary",
    "split_complementary",
    "triadic",
}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def normalize_rgb(value) -> tuple[int, int, int] | None:
    if isinstance(value, str):
        text = value.strip().lstrip("#")
        if len(text) == 6:
            try:
                return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
            except ValueError:
                return None
        return None
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return tuple(max(0, min(255, int(round(float(channel))))) for channel in value[:3])
    except (TypeError, ValueError):
        return None


def rgb_hex(rgb: tuple[int, int, int]) -> str:
    normalized = normalize_rgb(rgb) or (0, 0, 0)
    return f"#{normalized[0]:02X}{normalized[1]:02X}{normalized[2]:02X}"


def unique_colors(values: Iterable, *, limit: int = MAX_RECENT_COLORS) -> list[list[int]]:
    result: list[list[int]] = []
    seen: set[tuple[int, int, int]] = set()
    for value in values:
        rgb = normalize_rgb(value)
        if rgb is None or rgb in seen:
            continue
        seen.add(rgb)
        result.append([rgb[0], rgb[1], rgb[2]])
        if len(result) >= max(0, int(limit)):
            break
    return result


def default_palette_library() -> dict:
    return {
        "schema": PAINTER_PALETTE_SCHEMA,
        "favorites": [],
        "recent_brushes": [],
        "recent_colors": [],
        "pinned_colors": [],
        "custom_brushes": [],
        "touch_targets": True,
        "harmony_mode": "full",
    }


def palette_library_path() -> Path | None:
    override = str(os.environ.get("TIGERSTUDIO_PAINTER_PALETTE_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    # Unit tests must not mutate the user's real global Painter library.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    return Path.home() / "TigerStudio" / "Painter" / "palette_library.json"


def normalize_brush_preset(payload: dict, *, fallback_name: str = "Custom Brush") -> dict:
    row = dict(payload or {})
    name = str(row.get("name") or fallback_name).strip() or fallback_name
    category = str(row.get("category") or "My Brushes").strip() or "My Brushes"
    tags = row.get("tags")
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    elif isinstance(tags, (list, tuple, set)):
        tags = [str(part).strip() for part in tags if str(part).strip()]
    else:
        tags = []
    return {
        "name": name,
        "category": category,
        "style": str(row.get("style") or "round"),
        "width": max(1, min(2048, int(round(float(row.get("width") or 6))))),
        "opacity": max(1, min(100, int(round(float(row.get("opacity") or 100))))),
        "hardness": max(1, min(100, int(round(float(row.get("hardness") or 100))))),
        "spacing": max(1, min(200, int(round(float(row.get("spacing") or 25))))),
        "angle": max(-180, min(180, int(round(float(row.get("angle") or 0))))),
        "roundness": max(10, min(100, int(round(float(row.get("roundness") or 100))))),
        "pressure_response": max(
            25,
            min(250, int(round(float(row.get("pressure_response") or 100)))),
        ),
        "flip_x": bool(row.get("flip_x", False)),
        "flip_y": bool(row.get("flip_y", False)),
        "tags": list(dict.fromkeys(tags)),
        "custom": True,
    }


def normalize_palette_library(payload: dict | None) -> dict:
    source = payload if isinstance(payload, dict) else {}
    result = default_palette_library()
    result["favorites"] = list(
        dict.fromkeys(str(value) for value in source.get("favorites", []) if str(value))
    )
    result["recent_brushes"] = list(
        dict.fromkeys(str(value) for value in source.get("recent_brushes", []) if str(value))
    )[:MAX_RECENT_BRUSHES]
    result["recent_colors"] = unique_colors(source.get("recent_colors", []))
    result["pinned_colors"] = unique_colors(source.get("pinned_colors", []))
    result["custom_brushes"] = [
        normalize_brush_preset(row)
        for row in source.get("custom_brushes", [])
        if isinstance(row, dict)
    ]
    result["touch_targets"] = bool(source.get("touch_targets", True))
    harmony_mode = str(source.get("harmony_mode") or "full").strip().casefold()
    result["harmony_mode"] = (
        harmony_mode if harmony_mode in HARMONY_MODES else "full"
    )
    return result


def load_palette_library(path: Path | None = None) -> dict:
    resolved = palette_library_path() if path is None else Path(path)
    if resolved is None or not resolved.exists():
        return default_palette_library()
    try:
        return normalize_palette_library(
            json.loads(resolved.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, TypeError):
        return default_palette_library()


def save_palette_library(payload: dict, path: Path | None = None) -> Path | None:
    resolved = palette_library_path() if path is None else Path(path)
    if resolved is None:
        return None
    normalized = normalize_palette_library(payload)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_suffix(resolved.suffix + ".tmp")
    temporary.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(resolved)
    return resolved


def export_brush_bundle(presets: Iterable[dict], path: Path) -> Path:
    payload = {
        "schema": PAINTER_BRUSH_BUNDLE_SCHEMA,
        "brushes": [normalize_brush_preset(row) for row in presets],
    }
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolved


def import_brush_bundle(path: Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != PAINTER_BRUSH_BUNDLE_SCHEMA:
        raise ValueError("Unsupported Painter brush bundle")
    return [
        normalize_brush_preset(row)
        for row in payload.get("brushes", [])
        if isinstance(row, dict)
    ]


def _srgb_to_linear(value: float) -> float:
    value = _clamp(value)
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(value: float) -> float:
    value = _clamp(value)
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1.0 / 2.4) - 0.055


def rgb_to_oklch(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    normalized = normalize_rgb(rgb) or (0, 0, 0)
    red, green, blue = (_srgb_to_linear(channel / 255.0) for channel in normalized)
    l_value = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    m_value = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    s_value = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_root = max(0.0, l_value) ** (1.0 / 3.0)
    m_root = max(0.0, m_value) ** (1.0 / 3.0)
    s_root = max(0.0, s_value) ** (1.0 / 3.0)
    lightness = 0.2104542553 * l_root + 0.7936177850 * m_root - 0.0040720468 * s_root
    a_value = 1.9779984951 * l_root - 2.4285922050 * m_root + 0.4505937099 * s_root
    b_value = 0.0259040371 * l_root + 0.7827717662 * m_root - 0.8086757660 * s_root
    chroma = math.hypot(a_value, b_value)
    hue = (math.degrees(math.atan2(b_value, a_value)) + 360.0) % 360.0
    return lightness, chroma, hue


def _oklch_linear_rgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    radians = math.radians(hue)
    a_value = chroma * math.cos(radians)
    b_value = chroma * math.sin(radians)
    l_root = lightness + 0.3963377774 * a_value + 0.2158037573 * b_value
    m_root = lightness - 0.1055613458 * a_value - 0.0638541728 * b_value
    s_root = lightness - 0.0894841775 * a_value - 1.2914855480 * b_value
    l_value, m_value, s_value = l_root**3, m_root**3, s_root**3
    return (
        4.0767416621 * l_value - 3.3077115913 * m_value + 0.2309699292 * s_value,
        -1.2684380046 * l_value + 2.6097574011 * m_value - 0.3413193965 * s_value,
        -0.0041960863 * l_value - 0.7034186147 * m_value + 1.7076147010 * s_value,
    )


def oklch_to_rgb(lightness: float, chroma: float, hue: float) -> tuple[int, int, int]:
    lightness = _clamp(lightness)
    chroma = max(0.0, float(chroma))
    linear = _oklch_linear_rgb(lightness, chroma, hue)
    if any(channel < 0.0 or channel > 1.0 for channel in linear):
        low, high = 0.0, chroma
        for _ in range(14):
            candidate = (low + high) / 2.0
            test = _oklch_linear_rgb(lightness, candidate, hue)
            if all(0.0 <= channel <= 1.0 for channel in test):
                low = candidate
                linear = test
            else:
                high = candidate
    return tuple(
        max(0, min(255, int(round(_linear_to_srgb(channel) * 255.0))))
        for channel in linear
    )


def oklch_harmony_colors(
    rgb: tuple[int, int, int],
    mode: str = "full",
) -> list[tuple[tuple[int, int, int], str]]:
    normalized = normalize_rgb(rgb) or (0, 0, 0)
    lightness, chroma, hue = rgb_to_oklch(normalized)
    chroma = max(0.025, chroma)
    tonal = [
        (oklch_to_rgb(max(0.18, lightness * 0.48), chroma * 0.78, hue), "Deep shade"),
        (oklch_to_rgb(max(0.26, lightness * 0.72), chroma * 0.90, hue), "Shadow"),
        (normalized, "Current color"),
        (oklch_to_rgb(min(0.88, lightness + 0.16), chroma * 0.72, hue), "Tint"),
        (oklch_to_rgb(min(0.96, lightness + 0.29), chroma * 0.38, hue), "Pale highlight"),
    ]
    normalized_mode = str(mode or "full").strip().casefold()
    if normalized_mode == "monochrome":
        return [
            (oklch_to_rgb(level, chroma * scale, hue), label)
            for level, scale, label in (
                (0.20, 0.66, "Deep shade"),
                (0.32, 0.76, "Dark"),
                (0.45, 0.88, "Mid shadow"),
                (lightness, 1.0, "Current color"),
                (0.70, 0.80, "Light"),
                (0.80, 0.62, "Tint"),
                (0.89, 0.42, "Pale"),
                (0.96, 0.18, "Near white"),
            )
        ]
    if normalized_mode == "analogous":
        shifts = (-60.0, -40.0, -20.0, 0.0, 20.0, 40.0, 60.0, 80.0)
        return [
            (
                normalized if shift == 0.0 else oklch_to_rgb(lightness, chroma * 0.92, hue + shift),
                "Current color" if shift == 0.0 else f"Analogous {shift:+.0f}°",
            )
            for shift in shifts
        ]
    if normalized_mode == "complementary":
        return [
            *tonal[:4],
            (oklch_to_rgb(max(0.24, lightness * 0.62), chroma * 0.72, hue + 180.0), "Complement shade"),
            (oklch_to_rgb(lightness, chroma * 0.86, hue + 180.0), "Complement"),
            (oklch_to_rgb(min(0.88, lightness + 0.18), chroma * 0.58, hue + 180.0), "Complement tint"),
            tonal[4],
        ]
    if normalized_mode == "split_complementary":
        shifts = (0.0, -30.0, 30.0, 150.0, 165.0, 195.0, 210.0, 180.0)
        labels = (
            "Current color",
            "Analogous cool",
            "Analogous warm",
            "Split complement A",
            "Split complement A warm",
            "Split complement B cool",
            "Split complement B",
            "Complement",
        )
        return [
            (
                normalized if shift == 0.0 else oklch_to_rgb(lightness, chroma * 0.84, hue + shift),
                labels[index],
            )
            for index, shift in enumerate(shifts)
        ]
    if normalized_mode == "triadic":
        shifts = (0.0, 120.0, 240.0)
        rows: list[tuple[tuple[int, int, int], str]] = []
        for index, shift in enumerate(shifts):
            name = ("Base", "Triad B", "Triad C")[index]
            rows.append(
                (
                    normalized if index == 0 else oklch_to_rgb(lightness, chroma * 0.86, hue + shift),
                    name,
                )
            )
            rows.append(
                (
                    oklch_to_rgb(min(0.88, lightness + 0.16), chroma * 0.55, hue + shift),
                    f"{name} tint",
                )
            )
        rows.extend([tonal[0], tonal[1]])
        return rows[:8]
    return [
        *tonal,
        (oklch_to_rgb(lightness, chroma * 0.94, hue - 30.0), "Analogous cool"),
        (oklch_to_rgb(lightness, chroma * 0.94, hue + 30.0), "Analogous warm"),
        (oklch_to_rgb(lightness, chroma * 0.82, hue + 180.0), "Complement"),
    ]
