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
from app.painter_ui_json_copy import json_deepcopy


UI_OBJECT_BLEND_MODES = set(UI_EFFECT_BLEND_MODES) | {
    "pass_through",
    "linear_burn",
    "linear_dodge",
}
UI_PAINT_TYPES = {
    "solid",
    "linear",
    "radial",
    "pattern",
    "image",
    "video",
    "shader",
}
UI_STROKE_ALIGNS = {"inside", "center", "outside"}
UI_INDIVIDUAL_STROKE_SIDES = ("top", "right", "bottom", "left")


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
        "blend_mode": str(row.get("blend_mode") or "normal").strip().casefold(),
    }
    if paint_type in {"linear", "radial"}:
        result["gradient"] = normalize_ui_gradient(
            {
                **dict(row.get("gradient") or {}),
                "type": paint_type,
            }
        )
    elif paint_type == "pattern":
        pattern = row.get("pattern") if isinstance(row.get("pattern"), Mapping) else {}
        result["pattern"] = {
            "kind": str(pattern.get("kind") or "dots").strip().casefold(),
            "foreground": str(pattern.get("foreground") or "#C8D2E0FF"),
            "background": str(pattern.get("background") or "#FFFFFFFF"),
            "scale": max(2.0, min(128.0, _number(pattern.get("scale"), 12.0))),
            "scale_percent": max(1.0, min(1000.0, _number(
                pattern.get("scale_percent"),
                _number(pattern.get("scale"), 12.0) / 12.0 * 100.0,
            ))),
            "gap_x": max(-1000.0, min(1000.0, _number(pattern.get("gap_x"), 0.0))),
            "gap_y": max(-1000.0, min(1000.0, _number(pattern.get("gap_y"), 0.0))),
            "alignment": str(pattern.get("alignment") or "top_left").strip().casefold(),
            "tile_type": str(pattern.get("tile_type") or "grid").strip().casefold(),
            "source_id": str(pattern.get("source_id") or ""),
        }
    elif paint_type in {"image", "video"}:
        result["source_path"] = str(row.get("source_path") or "")
        fit = str(row.get("fit") or "fill").strip().casefold()
        result["fit"] = fit if fit in {"fill", "fit", "crop", "stretch", "tile"} else "fill"
        result["rotation"] = _number(row.get("rotation"), 0.0)
        result["focal_x"] = max(0.0, min(1.0, _number(row.get("focal_x"), 0.5)))
        result["focal_y"] = max(0.0, min(1.0, _number(row.get("focal_y"), 0.5)))
        result["tile_scale"] = max(0.05, min(16.0, _number(row.get("tile_scale"), 1.0)))
        result["original_width"] = max(0.0, _number(row.get("original_width"), 0.0))
        result["original_height"] = max(0.0, _number(row.get("original_height"), 0.0))
        if isinstance(row.get("crop"), (Mapping, list, tuple)):
            result["crop"] = json_deepcopy(row["crop"])
        if isinstance(row.get("image_transform"), list):
            result["image_transform"] = json_deepcopy(
                row["image_transform"]
            )
        if paint_type == "image":
            adjustments = row.get("adjustments") if isinstance(row.get("adjustments"), Mapping) else {}
            result["adjustments"] = {
                key: max(-100.0, min(100.0, _number(adjustments.get(key), 0.0)))
                for key in (
                    "exposure", "contrast", "saturation", "temperature",
                    "tint", "highlights",
                )
            }
        if paint_type == "video":
            result["poster_path"] = str(row.get("poster_path") or "")
            result["frame_time_ms"] = max(0.0, _number(row.get("frame_time_ms"), 0.0))
            result["autoplay"] = bool(row.get("autoplay", True))
            result["loop"] = bool(row.get("loop", True))
            result["muted"] = bool(row.get("muted", True))
    elif paint_type == "shader":
        result["shader_preset"] = str(row.get("shader_preset") or "mesh_gradient").strip().casefold()
        parameters = row.get("shader_parameters") if isinstance(row.get("shader_parameters"), Mapping) else {}
        result["shader_parameters"] = json_deepcopy(dict(parameters))
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


def normalize_ui_individual_stroke_weights(value: object) -> dict[str, float]:
    """Normalize Figma's per-edge rectangle stroke widths.

    An empty mapping means that the object uses the legacy uniform
    ``stroke_width``.  Keeping this as an explicit style field prevents a
    mixed border from silently collapsing to Figma's fallback strokeWeight.
    """

    if not isinstance(value, Mapping):
        return {}
    return {
        side: max(0.0, _number(value.get(side)))
        for side in UI_INDIVIDUAL_STROKE_SIDES
    }


def normalize_ui_advanced_style(value: object) -> dict[str, Any]:
    style = json_deepcopy(dict(value)) if isinstance(value, Mapping) else {}
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
    style["corner_smoothing"] = max(
        0.0,
        min(1.0, _number(style.get("corner_smoothing"))),
    )
    align = str(style.get("stroke_align") or "center").strip().casefold()
    style["stroke_align"] = align if align in UI_STROKE_ALIGNS else "center"
    if "stroke_cap" in style:
        style["stroke_cap"] = str(
            style.get("stroke_cap") or "none"
        ).strip().casefold()
    if "stroke_join" in style:
        style["stroke_join"] = str(
            style.get("stroke_join") or "miter"
        ).strip().casefold()
    if "stroke_miter_limit" in style:
        style["stroke_miter_limit"] = max(
            0.0,
            _number(style.get("stroke_miter_limit"), 4.0),
        )
    if "stroke_dash" in style:
        style["stroke_dash"] = [
            max(0.0, _number(value))
            for value in (
                style.get("stroke_dash")
                if isinstance(style.get("stroke_dash"), list)
                else []
            )
        ]
    individual_stroke_weights = normalize_ui_individual_stroke_weights(
        style.get("individual_stroke_weights")
    )
    if individual_stroke_weights:
        style["individual_stroke_weights"] = individual_stroke_weights
    else:
        style.pop("individual_stroke_weights", None)
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
        "corner_smoothing": style["corner_smoothing"],
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
    corner_smoothing: float | None = None,
    stroke_align: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, style = _style(value, object_id)
    if corner_radii is not None:
        style["corner_radii"] = normalize_ui_corner_radii(corner_radii)
    if corner_smoothing is not None:
        style["corner_smoothing"] = max(
            0.0,
            min(1.0, _number(corner_smoothing)),
        )
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
    "normalize_ui_individual_stroke_weights",
    "normalize_ui_paint",
    "normalize_ui_paints",
    "set_ui_corner_geometry",
    "set_ui_object_blend_mode",
]
