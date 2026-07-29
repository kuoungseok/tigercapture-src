"""Provider-neutral distance measurements for Painter UI selections."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.painter_ui_constraints import resolve_ui_constraints
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_bridge import resolved_ui_geometry


_SCHEMA = "tigerstudio.painter.ui.measurements.v1"


def _bounds(
    rows: Sequence[Mapping[str, Any]],
    geometry: Mapping[str, Mapping[str, float]],
) -> dict[str, float]:
    rects = [geometry[str(row["id"])] for row in rows]
    left = min(float(row["x"]) for row in rects)
    top = min(float(row["y"]) for row in rects)
    right = max(float(row["x"]) + float(row["width"]) for row in rects)
    bottom = max(float(row["y"]) + float(row["height"]) for row in rects)
    return {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
    }


def _overlap_center(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> float | None:
    start = max(first_start, second_start)
    end = min(first_end, second_end)
    return (start + end) * 0.5 if end >= start else None


def _descendant_ids(
    objects: Sequence[Mapping[str, Any]],
    root_ids: set[str],
) -> set[str]:
    excluded = set(root_ids)
    changed = True
    while changed:
        before = len(excluded)
        excluded.update(
            str(row["id"])
            for row in objects
            if str(row.get("parent_id") or "") in excluded
        )
        changed = len(excluded) != before
    return excluded


def inspect_ui_selection_measurements(
    value: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return nearest directional gaps for a same-artboard UI selection."""
    document = normalize_ui_document(value)
    objects = document["objects"]
    by_id = {str(row["id"]): row for row in objects}
    requested = [
        str(object_id)
        for object_id in (
            object_ids
            if object_ids is not None
            else document["selection"]["object_ids"]
        )
        if str(object_id)
    ]
    selected = [
        by_id[object_id]
        for object_id in requested
        if object_id in by_id and by_id[object_id]["visible"]
    ]
    report: dict[str, Any] = {
        "schema": _SCHEMA,
        "eligible": False,
        "reason": "no_selection",
        "artboard_id": "",
        "object_ids": [str(row["id"]) for row in selected],
        "selection_bounds": {},
        "distances": [],
    }
    if not selected:
        return report
    artboard_ids = {str(row["artboard_id"]) for row in selected}
    if len(artboard_ids) != 1:
        report["reason"] = "selection_spans_artboards"
        return report
    artboard_id = next(iter(artboard_ids))
    artboard = next(
        row for row in document["artboards"] if row["id"] == artboard_id
    )
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(document),
    )
    selection_bounds = _bounds(selected, geometry)
    excluded = _descendant_ids(objects, set(report["object_ids"]))
    candidates = [
        row
        for row in objects
        if (
            row["visible"]
            and str(row["artboard_id"]) == artboard_id
            and str(row["id"]) not in excluded
        )
    ]

    directional: dict[str, list[dict[str, Any]]] = {
        "left": [],
        "right": [],
        "top": [],
        "bottom": [],
    }
    for row in candidates:
        rect = geometry[str(row["id"])]
        left = float(rect["x"])
        top = float(rect["y"])
        right = left + float(rect["width"])
        bottom = top + float(rect["height"])
        vertical_center = _overlap_center(
            selection_bounds["top"],
            selection_bounds["bottom"],
            top,
            bottom,
        )
        horizontal_center = _overlap_center(
            selection_bounds["left"],
            selection_bounds["right"],
            left,
            right,
        )
        common = {
            "target_object_id": str(row["id"]),
            "target_name": str(row.get("name") or row["id"]),
            "target_kind": "object",
        }
        if vertical_center is not None and right <= selection_bounds["left"]:
            directional["left"].append(
                {
                    **common,
                    "value": selection_bounds["left"] - right,
                    "start": [right, vertical_center],
                    "end": [selection_bounds["left"], vertical_center],
                }
            )
        if vertical_center is not None and left >= selection_bounds["right"]:
            directional["right"].append(
                {
                    **common,
                    "value": left - selection_bounds["right"],
                    "start": [selection_bounds["right"], vertical_center],
                    "end": [left, vertical_center],
                }
            )
        if horizontal_center is not None and bottom <= selection_bounds["top"]:
            directional["top"].append(
                {
                    **common,
                    "value": selection_bounds["top"] - bottom,
                    "start": [horizontal_center, bottom],
                    "end": [horizontal_center, selection_bounds["top"]],
                }
            )
        if horizontal_center is not None and top >= selection_bounds["bottom"]:
            directional["bottom"].append(
                {
                    **common,
                    "value": top - selection_bounds["bottom"],
                    "start": [horizontal_center, selection_bounds["bottom"]],
                    "end": [horizontal_center, top],
                }
            )

    center_x = (selection_bounds["left"] + selection_bounds["right"]) * 0.5
    center_y = (selection_bounds["top"] + selection_bounds["bottom"]) * 0.5
    edges = {
        "left": {
            "value": selection_bounds["left"],
            "start": [0.0, center_y],
            "end": [selection_bounds["left"], center_y],
        },
        "right": {
            "value": float(artboard["width"]) - selection_bounds["right"],
            "start": [selection_bounds["right"], center_y],
            "end": [float(artboard["width"]), center_y],
        },
        "top": {
            "value": selection_bounds["top"],
            "start": [center_x, 0.0],
            "end": [center_x, selection_bounds["top"]],
        },
        "bottom": {
            "value": float(artboard["height"]) - selection_bounds["bottom"],
            "start": [center_x, selection_bounds["bottom"]],
            "end": [center_x, float(artboard["height"])],
        },
    }
    distances: list[dict[str, Any]] = []
    for side in ("left", "right", "top", "bottom"):
        options = directional[side]
        chosen = (
            min(
                options,
                key=lambda row: (
                    float(row["value"]),
                    str(row["target_name"]),
                ),
            )
            if options
            else {
                **edges[side],
                "target_object_id": "",
                "target_name": str(artboard.get("name") or "Artboard"),
                "target_kind": "artboard",
            }
        )
        distances.append(
            {
                "axis": (
                    "horizontal"
                    if side in {"left", "right"}
                    else "vertical"
                ),
                "side": side,
                **chosen,
            }
        )
    report.update(
        {
            "eligible": True,
            "reason": "",
            "artboard_id": artboard_id,
            "selection_bounds": selection_bounds,
            "distances": distances,
        }
    )
    return report


__all__ = ["inspect_ui_selection_measurements"]
