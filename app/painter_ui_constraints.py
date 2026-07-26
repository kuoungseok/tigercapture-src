"""Constraint and pivot rules shared by Painter UI editing surfaces."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF


_HORIZONTAL = {"left", "center", "right", "stretch", "scale"}
_VERTICAL = {"top", "center", "bottom", "stretch", "scale"}


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def normalize_ui_constraints(
    value: Mapping[str, Any] | None,
    *,
    width: float = 160.0,
    height: float = 64.0,
) -> dict[str, Any]:
    source = copy.deepcopy(dict(value or {}))
    horizontal = str(source.get("horizontal") or "left").strip().casefold()
    vertical = str(source.get("vertical") or "top").strip().casefold()
    source["horizontal"] = horizontal if horizontal in _HORIZONTAL else "left"
    source["vertical"] = vertical if vertical in _VERTICAL else "top"
    source["pivot_x"] = max(0.0, min(1.0, _number(source.get("pivot_x"), 0.5)))
    source["pivot_y"] = max(0.0, min(1.0, _number(source.get("pivot_y"), 0.5)))
    source["min_width"] = max(1.0, _number(source.get("min_width"), 1.0))
    source["min_height"] = max(1.0, _number(source.get("min_height"), 1.0))
    source["preferred_width"] = max(
        0.0,
        _number(source.get("preferred_width"), width),
    )
    source["preferred_height"] = max(
        0.0,
        _number(source.get("preferred_height"), height),
    )
    source["max_width"] = max(0.0, _number(source.get("max_width"), 0.0))
    source["max_height"] = max(0.0, _number(source.get("max_height"), 0.0))
    source["lock_aspect"] = bool(source.get("lock_aspect", False))
    source["aspect_ratio"] = max(
        0.0001,
        _number(source.get("aspect_ratio"), width / max(0.0001, height)),
    )
    return source


def constrain_ui_size(
    width: float,
    height: float,
    constraints: Mapping[str, Any] | None,
    *,
    force_ratio: bool = False,
    fallback_ratio: float = 1.0,
) -> tuple[float, float]:
    normalized = normalize_ui_constraints(
        constraints,
        width=width,
        height=height,
    )
    width = max(1.0, float(width))
    height = max(1.0, float(height))
    minimum_width = float(normalized["min_width"])
    minimum_height = float(normalized["min_height"])
    maximum_width = float(normalized["max_width"]) or math.inf
    maximum_height = float(normalized["max_height"]) or math.inf
    preserve_ratio = bool(normalized["lock_aspect"]) or bool(force_ratio)
    if not preserve_ratio:
        return (
            min(maximum_width, max(minimum_width, width)),
            min(maximum_height, max(minimum_height, height)),
        )

    ratio = (
        float(normalized["aspect_ratio"])
        if normalized["lock_aspect"]
        else max(0.0001, float(fallback_ratio))
    )
    if width / max(0.0001, height) >= ratio:
        candidate_width = width
    else:
        candidate_width = height * ratio
    effective_minimum = max(minimum_width, minimum_height * ratio)
    effective_maximum = min(maximum_width, maximum_height * ratio)
    if effective_maximum < effective_minimum:
        effective_maximum = effective_minimum
    candidate_width = min(
        effective_maximum,
        max(effective_minimum, candidate_width),
    )
    return candidate_width, candidate_width / ratio


def constraint_parent_geometry(
    document: Mapping[str, Any],
    row: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, float]:
    parent_id = str(row.get("parent_id") or "")
    if parent_id:
        parent = next(
            item for item in document["objects"] if item["id"] == parent_id
        )
        parent_geometry = (geometry or {}).get(parent_id, parent)
        return {
            key: float(parent_geometry[key])
            for key in ("x", "y", "width", "height")
        }
    artboard = next(
        item
        for item in document["artboards"]
        if item["id"] == row["artboard_id"]
    )
    return {
        "x": 0.0,
        "y": 0.0,
        "width": float(artboard["width"]),
        "height": float(artboard["height"]),
    }


def capture_ui_constraints(
    row: Mapping[str, Any],
    parent: Mapping[str, float],
    updates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    constraints = normalize_ui_constraints(
        {**dict(row.get("constraints") or {}), **dict(updates or {})},
        width=float(row["width"]),
        height=float(row["height"]),
    )
    parent_x = float(parent["x"])
    parent_y = float(parent["y"])
    parent_width = max(1.0, float(parent["width"]))
    parent_height = max(1.0, float(parent["height"]))
    x = float(row["x"])
    y = float(row["y"])
    width = float(row["width"])
    height = float(row["height"])
    constraints.update(
        {
            "reference_parent_width": parent_width,
            "reference_parent_height": parent_height,
            "left": x - parent_x,
            "right": parent_x + parent_width - x - width,
            "top": y - parent_y,
            "bottom": parent_y + parent_height - y - height,
            "center_offset_x": (
                x + width * 0.5 - (parent_x + parent_width * 0.5)
            ),
            "center_offset_y": (
                y + height * 0.5 - (parent_y + parent_height * 0.5)
            ),
        }
    )
    if constraints["lock_aspect"]:
        constraints["aspect_ratio"] = width / max(0.0001, height)
    return constraints


def resolve_ui_constraints(
    document: Mapping[str, Any],
    base_geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    objects = {str(row["id"]): row for row in document["objects"]}
    geometry = {
        object_id: {
            key: float((base_geometry or {}).get(object_id, row)[key])
            for key in ("x", "y", "width", "height")
        }
        for object_id, row in objects.items()
    }
    resolved: set[str] = set()

    def resolve(object_id: str, stack: tuple[str, ...] = ()) -> None:
        if object_id in resolved or object_id in stack:
            return
        row = objects[object_id]
        parent_id = str(row.get("parent_id") or "")
        if parent_id in objects:
            resolve(parent_id, (*stack, object_id))
        parent = constraint_parent_geometry(document, row, geometry)
        rect = geometry[object_id]
        constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=rect["width"],
            height=rect["height"],
        )
        horizontal = constraints["horizontal"]
        vertical = constraints["vertical"]
        reference_width = max(
            1.0,
            _number(
                constraints.get("reference_parent_width"),
                parent["width"],
            ),
        )
        reference_height = max(
            1.0,
            _number(
                constraints.get("reference_parent_height"),
                parent["height"],
            ),
        )
        left = _number(constraints.get("left"), rect["x"] - parent["x"])
        right = _number(
            constraints.get("right"),
            parent["x"] + parent["width"] - rect["x"] - rect["width"],
        )
        top = _number(constraints.get("top"), rect["y"] - parent["y"])
        bottom = _number(
            constraints.get("bottom"),
            parent["y"] + parent["height"] - rect["y"] - rect["height"],
        )
        if horizontal == "right":
            rect["x"] = parent["x"] + parent["width"] - right - rect["width"]
        elif horizontal == "center":
            rect["x"] = (
                parent["x"]
                + parent["width"] * 0.5
                + _number(constraints.get("center_offset_x"))
                - rect["width"] * 0.5
            )
        elif horizontal == "stretch":
            rect["x"] = parent["x"] + left
            rect["width"] = max(1.0, parent["width"] - left - right)
        elif horizontal == "scale":
            scale_x = parent["width"] / reference_width
            rect["x"] = parent["x"] + left * scale_x
            rect["width"] *= scale_x
        else:
            rect["x"] = parent["x"] + left
        if vertical == "bottom":
            rect["y"] = parent["y"] + parent["height"] - bottom - rect["height"]
        elif vertical == "center":
            rect["y"] = (
                parent["y"]
                + parent["height"] * 0.5
                + _number(constraints.get("center_offset_y"))
                - rect["height"] * 0.5
            )
        elif vertical == "stretch":
            rect["y"] = parent["y"] + top
            rect["height"] = max(1.0, parent["height"] - top - bottom)
        elif vertical == "scale":
            scale_y = parent["height"] / reference_height
            rect["y"] = parent["y"] + top * scale_y
            rect["height"] *= scale_y
        else:
            rect["y"] = parent["y"] + top
        rect["width"], rect["height"] = constrain_ui_size(
            rect["width"],
            rect["height"],
            constraints,
        )
        resolved.add(object_id)

    for target_id in objects:
        resolve(target_id)
    from app.painter_ui_auto_layout import resolve_ui_auto_layout

    return resolve_ui_auto_layout(document, geometry)


def ui_pivot_point(
    rect: QRectF,
    constraints: Mapping[str, Any] | None,
) -> QPointF:
    normalized = normalize_ui_constraints(
        constraints,
        width=rect.width(),
        height=rect.height(),
    )
    return QPointF(
        rect.left() + rect.width() * float(normalized["pivot_x"]),
        rect.top() + rect.height() * float(normalized["pivot_y"]),
    )


def reanchor_resize_rect(
    rect: QRectF,
    original: QRectF,
    handle: str,
    *,
    center_based: bool,
    width: float,
    height: float,
) -> QRectF:
    if center_based:
        center = original.center()
        return QRectF(
            center.x() - width * 0.5,
            center.y() - height * 0.5,
            width,
            height,
        )
    anchor = {
        "nw": original.bottomRight(),
        "ne": original.bottomLeft(),
        "sw": original.topRight(),
        "se": original.topLeft(),
    }[str(handle)]
    if handle == "nw":
        return QRectF(anchor.x() - width, anchor.y() - height, width, height)
    if handle == "ne":
        return QRectF(anchor.x(), anchor.y() - height, width, height)
    if handle == "sw":
        return QRectF(anchor.x() - width, anchor.y(), width, height)
    return QRectF(anchor.x(), anchor.y(), width, height)


__all__ = [
    "capture_ui_constraints",
    "constrain_ui_size",
    "constraint_parent_geometry",
    "normalize_ui_constraints",
    "reanchor_resize_rect",
    "resolve_ui_constraints",
    "ui_pivot_point",
]
