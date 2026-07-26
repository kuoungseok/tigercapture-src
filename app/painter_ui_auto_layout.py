"""Deterministic Auto Layout rules shared by Painter UI surfaces."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping


_MODES = {"none", "horizontal", "vertical"}
_MAIN_ALIGNMENTS = {"start", "center", "end", "space_between"}
_CROSS_ALIGNMENTS = {"start", "center", "end", "stretch"}
_POSITIONING = {"auto", "absolute"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _padding(value: Any) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {
            edge: max(0.0, _number(value.get(edge)))
            for edge in ("left", "top", "right", "bottom")
        }
    if isinstance(value, (list, tuple)):
        values = [_number(item) for item in value]
        if len(values) >= 4:
            left, top, right, bottom = values[:4]
        elif len(values) >= 2:
            left = right = values[0]
            top = bottom = values[1]
        elif values:
            left = top = right = bottom = values[0]
        else:
            left = top = right = bottom = 0.0
        return {
            "left": max(0.0, left),
            "top": max(0.0, top),
            "right": max(0.0, right),
            "bottom": max(0.0, bottom),
        }
    amount = max(0.0, _number(value))
    return {edge: amount for edge in ("left", "top", "right", "bottom")}


def normalize_ui_auto_layout(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = copy.deepcopy(dict(value or {}))
    mode = str(
        source.get("mode")
        or source.get("direction")
        or source.get("type")
        or "none"
    ).strip().casefold()
    mode = {
        "row": "horizontal",
        "auto_horizontal": "horizontal",
        "column": "vertical",
        "auto_vertical": "vertical",
    }.get(mode, mode)
    main_alignment = str(
        source.get("main_alignment")
        or source.get("justify")
        or "start"
    ).strip().casefold()
    cross_alignment = str(
        source.get("cross_alignment")
        or source.get("align")
        or "start"
    ).strip().casefold()
    positioning = str(
        source.get("positioning")
        or source.get("position")
        or "auto"
    ).strip().casefold()
    source.update(
        {
            "mode": mode if mode in _MODES else "none",
            "padding": _padding(source.get("padding")),
            "gap": max(0.0, _number(source.get("gap"))),
            "main_alignment": (
                main_alignment
                if main_alignment in _MAIN_ALIGNMENTS
                else "start"
            ),
            "cross_alignment": (
                cross_alignment
                if cross_alignment in _CROSS_ALIGNMENTS
                else "start"
            ),
            "positioning": (
                positioning if positioning in _POSITIONING else "auto"
            ),
        }
    )
    for legacy_key in (
        "direction",
        "type",
        "justify",
        "align",
        "position",
    ):
        source.pop(legacy_key, None)
    return source


def _cross_size(
    value: float,
    available: float,
    constraints: Mapping[str, Any] | None,
    *,
    axis: str,
) -> float:
    row = constraints if isinstance(constraints, Mapping) else {}
    minimum = max(1.0, _number(row.get(f"min_{axis}"), 1.0))
    maximum = max(0.0, _number(row.get(f"max_{axis}"), 0.0))
    result = max(1.0, available if available >= 0.0 else value)
    result = max(minimum, result)
    return min(maximum, result) if maximum > 0.0 else result


def _main_axis_plan(
    sizes: list[float],
    available: float,
    gap: float,
    alignment: str,
) -> tuple[float, float]:
    if not sizes:
        return 0.0, gap
    total_without_gap = sum(sizes)
    total = total_without_gap + gap * max(0, len(sizes) - 1)
    remaining = max(0.0, available - total)
    if alignment == "center":
        return remaining * 0.5, gap
    if alignment == "end":
        return remaining, gap
    if alignment == "space_between" and len(sizes) > 1:
        distributed = max(
            gap,
            (available - total_without_gap) / (len(sizes) - 1),
        )
        return 0.0, distributed
    return 0.0, gap


def resolve_ui_auto_layout(
    document: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    objects = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    resolved = {
        object_id: {
            key: float(geometry.get(object_id, row)[key])
            for key in ("x", "y", "width", "height")
        }
        for object_id, row in objects.items()
    }
    children: dict[str, list[Mapping[str, Any]]] = {}
    for index, row in enumerate(document.get("objects", [])):
        if not isinstance(row, Mapping) or str(row.get("id") or "") not in objects:
            continue
        child = dict(row)
        child["_document_order"] = index
        children.setdefault(str(row.get("parent_id") or ""), []).append(child)
    for rows in children.values():
        rows.sort(
            key=lambda row: (
                int(_number(row.get("z_index"))),
                int(row["_document_order"]),
                str(row["id"]),
            )
        )

    visited: set[str] = set()

    def resolve_parent(parent_id: str, stack: tuple[str, ...] = ()) -> None:
        if parent_id in visited or parent_id in stack:
            return
        parent = objects.get(parent_id)
        parent_rect = resolved.get(parent_id)
        if parent is None or parent_rect is None:
            return
        layout = normalize_ui_auto_layout(parent.get("layout"))
        mode = layout["mode"]
        auto_children = [
            child
            for child in children.get(parent_id, [])
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            != "absolute"
        ]
        if mode in {"horizontal", "vertical"} and auto_children:
            padding = layout["padding"]
            content_x = parent_rect["x"] + padding["left"]
            content_y = parent_rect["y"] + padding["top"]
            content_width = max(
                0.0,
                parent_rect["width"] - padding["left"] - padding["right"],
            )
            content_height = max(
                0.0,
                parent_rect["height"] - padding["top"] - padding["bottom"],
            )
            sizes = [
                resolved[str(child["id"])][
                    "width" if mode == "horizontal" else "height"
                ]
                for child in auto_children
            ]
            available = content_width if mode == "horizontal" else content_height
            offset, effective_gap = _main_axis_plan(
                sizes,
                available,
                layout["gap"],
                layout["main_alignment"],
            )
            cursor = (content_x if mode == "horizontal" else content_y) + offset
            for child in auto_children:
                child_id = str(child["id"])
                rect = resolved[child_id]
                if mode == "horizontal":
                    rect["x"] = cursor
                    if layout["cross_alignment"] == "stretch":
                        rect["height"] = _cross_size(
                            rect["height"],
                            content_height,
                            child.get("constraints"),
                            axis="height",
                        )
                    cross_remaining = max(0.0, content_height - rect["height"])
                    rect["y"] = content_y + {
                        "center": cross_remaining * 0.5,
                        "end": cross_remaining,
                    }.get(layout["cross_alignment"], 0.0)
                    cursor += rect["width"] + effective_gap
                else:
                    rect["y"] = cursor
                    if layout["cross_alignment"] == "stretch":
                        rect["width"] = _cross_size(
                            rect["width"],
                            content_width,
                            child.get("constraints"),
                            axis="width",
                        )
                    cross_remaining = max(0.0, content_width - rect["width"])
                    rect["x"] = content_x + {
                        "center": cross_remaining * 0.5,
                        "end": cross_remaining,
                    }.get(layout["cross_alignment"], 0.0)
                    cursor += rect["height"] + effective_gap
        visited.add(parent_id)
        for child in children.get(parent_id, []):
            resolve_parent(str(child["id"]), (*stack, parent_id))

    roots = [row for row in objects.values() if not str(row.get("parent_id") or "")]
    for root in roots:
        resolve_parent(str(root["id"]))
    for object_id in objects:
        resolve_parent(object_id)
    return resolved


__all__ = [
    "normalize_ui_auto_layout",
    "resolve_ui_auto_layout",
]
