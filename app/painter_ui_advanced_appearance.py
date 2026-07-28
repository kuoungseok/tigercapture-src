"""Advanced Figma-style appearance contracts for Painter UI."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from app.painter_ui_appearance import UI_EFFECT_BLEND_MODES, normalize_ui_gradient
from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


UI_OBJECT_BLEND_MODES = set(UI_EFFECT_BLEND_MODES) | {
    "pass_through",
    "linear_burn",
    "linear_dodge",
}
UI_PAINT_TYPES = {"solid", "linear", "radial"}
UI_STROKE_ALIGNS = {"inside", "center", "outside"}


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def normalize_ui_paint(value: object, *, stroke: bool = False) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    paint_type = str(row.get("type") or "solid").strip().casefold()
    if paint_type not in UI_PAINT_TYPES:
        paint_type = "solid"
    result: dict[str, Any] = {
        "type": paint_type,
        "visible": bool(row.get("visible", True)),
        "opacity": max(0.0, min(1.0, _number(row.get("opacity"), 1.0))),
        "color": str(row.get("color") or "#FFFFFFFF"),
    }
    if paint_type in {"linear", "radial"}:
        result["gradient"] = normalize_ui_gradient(
            {
                **dict(row.get("gradient") or {}),
                "type": paint_type,
            }
        )
    if stroke:
        result["width"] = max(0.0, _number(row.get("width"), 1.0))
        align = str(row.get("align") or "center").strip().casefold()
        result["align"] = align if align in UI_STROKE_ALIGNS else "center"
    return result


def normalize_ui_paints(value: object, *, stroke: bool = False) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        normalize_ui_paint(row, stroke=stroke)
        for row in value
        if isinstance(row, Mapping)
    ]


def normalize_ui_corner_radii(value: object, fallback: float = 0.0) -> dict[str, float]:
    row = value if isinstance(value, Mapping) else {}
    return {
        key: max(0.0, _number(row.get(key), fallback))
        for key in ("top_left", "top_right", "bottom_right", "bottom_left")
    }


def normalize_ui_advanced_style(value: object) -> dict[str, Any]:
    style = copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    from app.painter_ui_typography import normalize_ui_font_axes

    axes = normalize_ui_font_axes(style.get("font_axes"))
    if axes:
        style["font_axes"] = axes
    else:
        style.pop("font_axes", None)
    blend = str(style.get("blend_mode") or "normal").strip().casefold()
    style["blend_mode"] = blend if blend in UI_OBJECT_BLEND_MODES else "normal"
    legacy_fill = str(style.get("fill") or "#00000000")
    fills = normalize_ui_paints(style.get("fills"))
    if not fills:
        fills = [normalize_ui_paint({"color": legacy_fill})]
    style["fills"] = fills
    legacy_stroke = str(style.get("stroke") or "#00000000")
    strokes = normalize_ui_paints(style.get("strokes"), stroke=True)
    if not strokes and not legacy_stroke.endswith("00"):
        strokes = [
            normalize_ui_paint(
                {
                    "color": legacy_stroke,
                    "width": style.get("stroke_width", 1.0),
                    "align": style.get("stroke_align", "center"),
                },
                stroke=True,
            )
        ]
    style["strokes"] = strokes
    fallback = max(0.0, _number(style.get("radius")))
    style["corner_radii"] = normalize_ui_corner_radii(
        style.get("corner_radii"),
        fallback,
    )
    align = str(style.get("stroke_align") or "center").strip().casefold()
    style["stroke_align"] = align if align in UI_STROKE_ALIGNS else "center"
    return style


def _style(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    return document, normalize_ui_advanced_style(row.get("style"))


def inspect_ui_advanced_appearance(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document, style = _style(value, object_id)
    return {
        "object_id": str(object_id),
        "revision": document["revision"],
        "blend_mode": style["blend_mode"],
        "fills": style["fills"],
        "strokes": style["strokes"],
        "corner_radii": style["corner_radii"],
        "stroke_align": style["stroke_align"],
    }


def set_ui_object_blend_mode(
    value: Mapping[str, Any] | None,
    object_id: str,
    blend_mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, style = _style(value, object_id)
    candidate = str(blend_mode or "normal").strip().casefold()
    if candidate not in UI_OBJECT_BLEND_MODES:
        raise PainterUIDocumentError(f"Unsupported UI blend mode: {blend_mode}")
    style["blend_mode"] = candidate
    return update_ui_object(document, str(object_id), {"style": style})


def mutate_ui_paint(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    stack: str,
    operation: str,
    paint: Mapping[str, Any] | None = None,
    index: int = -1,
    target_index: int = -1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, style = _style(value, object_id)
    key = "strokes" if str(stack).casefold() == "stroke" else "fills"
    stroke = key == "strokes"
    rows = normalize_ui_paints(style.get(key), stroke=stroke)
    operation = str(operation).strip().casefold()
    if operation == "add":
        row = normalize_ui_paint(paint, stroke=stroke)
        insert_at = len(rows) if index < 0 else max(0, min(len(rows), int(index)))
        rows.insert(insert_at, row)
    elif operation == "update":
        if not 0 <= index < len(rows):
            raise PainterUIDocumentError(f"UI paint index out of range: {index}")
        row = normalize_ui_paint({**rows[index], **dict(paint or {})}, stroke=stroke)
        rows[index] = row
    elif operation == "remove":
        if not 0 <= index < len(rows):
            raise PainterUIDocumentError(f"UI paint index out of range: {index}")
        row = rows.pop(index)
    elif operation == "reorder":
        if not 0 <= index < len(rows):
            raise PainterUIDocumentError(f"UI paint index out of range: {index}")
        destination = max(0, min(len(rows) - 1, int(target_index)))
        row = rows.pop(index)
        rows.insert(destination, row)
    else:
        raise PainterUIDocumentError(f"Unsupported UI paint operation: {operation}")
    style[key] = rows
    if key == "fills":
        first = next((item for item in rows if item["visible"]), None)
        if first and first["type"] == "solid":
            style["fill"] = first["color"]
    elif key == "strokes":
        first = next((item for item in rows if item["visible"]), None)
        if first:
            style["stroke"] = first["color"]
            style["stroke_width"] = first["width"]
            style["stroke_align"] = first["align"]
    document, _updated = update_ui_object(
        document,
        str(object_id),
        {"style": style},
    )
    return document, copy.deepcopy(row)


def set_ui_corner_geometry(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    corner_radii: Mapping[str, Any] | None = None,
    stroke_align: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, style = _style(value, object_id)
    if corner_radii is not None:
        style["corner_radii"] = normalize_ui_corner_radii(corner_radii)
    if stroke_align is not None:
        align = str(stroke_align).strip().casefold()
        if align not in UI_STROKE_ALIGNS:
            raise PainterUIDocumentError(f"Unsupported stroke alignment: {stroke_align}")
        style["stroke_align"] = align
        for row in style["strokes"]:
            row["align"] = align
    return update_ui_object(document, str(object_id), {"style": style})


__all__ = [
    "UI_OBJECT_BLEND_MODES",
    "UI_STROKE_ALIGNS",
    "inspect_ui_advanced_appearance",
    "mutate_ui_paint",
    "normalize_ui_advanced_style",
    "normalize_ui_corner_radii",
    "normalize_ui_paint",
    "normalize_ui_paints",
    "set_ui_corner_geometry",
    "set_ui_object_blend_mode",
]
