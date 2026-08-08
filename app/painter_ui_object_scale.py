"""Figma-style proportional scaling for Painter UI objects."""
from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from typing import Any


UI_SCALE_ORIGINS = {
    "center",
    "top_left",
    "top_right",
    "bottom_left",
    "bottom_right",
}


def _finite_scale(value: object, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return result


def _scaled_number(value: object, factor: float) -> object:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return float(value) * factor


def _scale_effect(effect: Mapping[str, Any], sx: float, sy: float) -> dict[str, Any]:
    result = copy.deepcopy(dict(effect))
    visual = math.sqrt(sx * sy)
    for key, factor in (
        ("x", sx),
        ("y", sy),
        ("blur", visual),
        ("spread", visual),
        ("radius", visual),
    ):
        if key in result:
            result[key] = _scaled_number(result[key], factor)
    return result


def _scale_style(style: Mapping[str, Any], sx: float, sy: float) -> dict[str, Any]:
    result = copy.deepcopy(dict(style))
    visual = math.sqrt(sx * sy)
    for key in (
        "radius",
        "stroke_width",
        "font_size",
        "letter_spacing",
        "paragraph_spacing",
    ):
        if key in result:
            result[key] = _scaled_number(result[key], visual)
    corner_radii = result.get("corner_radii")
    if isinstance(corner_radii, Mapping):
        result["corner_radii"] = {
            key: _scaled_number(value, visual)
            for key, value in corner_radii.items()
        }
    strokes = result.get("strokes")
    if isinstance(strokes, list):
        result["strokes"] = [
            {
                **copy.deepcopy(dict(row)),
                "width": _scaled_number(row.get("width"), visual),
            }
            if isinstance(row, Mapping) and "width" in row
            else copy.deepcopy(row)
            for row in strokes
        ]
    effects = result.get("effects")
    if isinstance(effects, list):
        result["effects"] = [
            _scale_effect(row, sx, sy)
            if isinstance(row, Mapping)
            else copy.deepcopy(row)
            for row in effects
        ]
    shadow = result.get("shadow")
    if isinstance(shadow, Mapping):
        result["shadow"] = _scale_effect(shadow, sx, sy)
    return result


def _scale_content(content: Mapping[str, Any], visual: float) -> dict[str, Any]:
    result = copy.deepcopy(dict(content))
    nine_slice = result.get("nine_slice")
    if isinstance(nine_slice, Mapping):
        result["nine_slice"] = {
            key: _scaled_number(value, visual)
            for key, value in nine_slice.items()
        }
    return result


def _pivot(
    rows: Sequence[Mapping[str, Any]],
    origin: str,
) -> tuple[float, float]:
    left = min(float(row["x"]) for row in rows)
    top = min(float(row["y"]) for row in rows)
    right = max(float(row["x"]) + float(row["width"]) for row in rows)
    bottom = max(float(row["y"]) + float(row["height"]) for row in rows)
    x = {
        "top_left": left,
        "bottom_left": left,
        "center": (left + right) * 0.5,
        "top_right": right,
        "bottom_right": right,
    }[origin]
    y = {
        "top_left": top,
        "top_right": top,
        "center": (top + bottom) * 0.5,
        "bottom_left": bottom,
        "bottom_right": bottom,
    }[origin]
    return x, y


def scale_ui_objects(
    value: Mapping[str, Any],
    object_ids: Sequence[str],
    *,
    scale_x: float,
    scale_y: float | None = None,
    origin: str = "center",
    scale_visuals: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Scale one selection in its shared parent coordinate space."""
    from app.painter_ui_batch_mutation import apply_ui_object_batch
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    sx = _finite_scale(scale_x, "scale_x")
    sy = _finite_scale(scale_y if scale_y is not None else scale_x, "scale_y")
    normalized_origin = str(origin or "center").strip().casefold()
    if normalized_origin not in UI_SCALE_ORIGINS:
        raise ValueError(f"Unsupported UI scale origin: {origin}")
    ids = list(
        dict.fromkeys(
            str(object_id)
            for object_id in object_ids
            if str(object_id)
        )
    )
    rows_by_id = {row["id"]: row for row in document["objects"]}
    missing = [object_id for object_id in ids if object_id not in rows_by_id]
    if missing:
        raise ValueError(f"UI object not found: {missing[0]}")
    rows = [rows_by_id[object_id] for object_id in ids]
    if not rows:
        raise ValueError("Select at least one Painter UI object to scale")
    coordinate_spaces = {
        (str(row["artboard_id"]), str(row["parent_id"]))
        for row in rows
    }
    if len(coordinate_spaces) != 1:
        raise ValueError("Scale selection must share one parent coordinate space")
    pivot_x, pivot_y = _pivot(rows, normalized_origin)
    visual = math.sqrt(sx * sy)
    changes_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        changes: dict[str, Any] = {
            "x": pivot_x + (float(row["x"]) - pivot_x) * sx,
            "y": pivot_y + (float(row["y"]) - pivot_y) * sy,
            "width": max(1.0, float(row["width"]) * sx),
            "height": max(1.0, float(row["height"]) * sy),
        }
        if scale_visuals:
            changes["style"] = _scale_style(row["style"], sx, sy)
            changes["content"] = _scale_content(row["content"], visual)
        changes_by_id[row["id"]] = changes
    updated, changed_ids = apply_ui_object_batch(document, changes_by_id)
    return updated, {
        "object_ids": changed_ids,
        "scale_x": sx,
        "scale_y": sy,
        "origin": normalized_origin,
        "scale_visuals": bool(scale_visuals),
        "pivot": {"x": pivot_x, "y": pivot_y},
    }


__all__ = ["UI_SCALE_ORIGINS", "scale_ui_objects"]
