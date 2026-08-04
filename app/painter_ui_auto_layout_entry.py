"""Selection-level Auto Layout entry commands for Painter UI.

This module owns the deterministic internal mapping from Figma's public
"select layers, then add Auto Layout" behavior to the Painter UI document.
It deliberately does not own gap/padding editing; those are later stages of
the Auto Layout workflow.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_document import (
    PainterUIDocumentError,
    add_ui_object,
    normalize_ui_document,
    update_ui_object,
)


def _selected_rows(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    selected_ids = [
        str(value)
        for value in (document.get("selection") or {}).get("object_ids", [])
        if str(value)
    ]
    by_id = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    return [by_id[object_id] for object_id in selected_ids if object_id in by_id]


def _inferred_flow(rows: list[Mapping[str, Any]]) -> str:
    """Choose a stable initial flow while keeping Figma's heuristic internal."""
    if len(rows) < 2:
        return "horizontal"
    centers_x = [float(row["x"]) + float(row["width"]) * 0.5 for row in rows]
    centers_y = [float(row["y"]) + float(row["height"]) * 0.5 for row in rows]
    return (
        "horizontal"
        if max(centers_x) - min(centers_x) >= max(centers_y) - min(centers_y)
        else "vertical"
    )


def _flow_gap(rows: list[Mapping[str, Any]], mode: str) -> float:
    if len(rows) < 2:
        return 0.0
    if mode == "horizontal":
        ordered = sorted(rows, key=lambda row: (float(row["x"]), int(row["z_index"])))
        gaps = [
            float(next_row["x"])
            - (float(row["x"]) + float(row["width"]))
            for row, next_row in zip(ordered, ordered[1:])
        ]
    else:
        ordered = sorted(rows, key=lambda row: (float(row["y"]), int(row["z_index"])))
        gaps = [
            float(next_row["y"])
            - (float(row["y"]) + float(row["height"]))
            for row, next_row in zip(ordered, ordered[1:])
        ]
    return max(0.0, min(gaps, default=0.0))


def _entry_layout(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    mode = _inferred_flow(rows)
    return normalize_ui_auto_layout(
        {
            "mode": mode,
            "padding": 0.0,
            "gap": _flow_gap(rows, mode),
            "main_alignment": "start",
            "cross_alignment": "start",
            "width_sizing": "fixed",
            "height_sizing": "fixed",
        }
    )


def _next_frame_name(document: Mapping[str, Any]) -> str:
    names = {str(row.get("name") or "") for row in document.get("objects", [])}
    serial = 1
    while f"Frame {serial}" in names:
        serial += 1
    return f"Frame {serial}"


def add_auto_layout_to_selection(
    value: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply Auto Layout to a frame or wrap selected layers in a new frame."""
    document = normalize_ui_document(value)
    rows = _selected_rows(document)
    if not rows:
        raise PainterUIDocumentError("Add Auto Layout requires a selection")
    if len({str(row["artboard_id"]) for row in rows}) != 1:
        raise PainterUIDocumentError("Auto Layout selection must share an artboard")
    selected = {str(row["id"]) for row in rows}
    if any(str(row.get("parent_id") or "") in selected for row in rows):
        raise PainterUIDocumentError(
            "Select sibling layers rather than a parent and its child"
        )

    if len(rows) == 1 and str(rows[0].get("kind") or "") == "frame":
        target = rows[0]
        children = [
            row
            for row in document["objects"]
            if str(row.get("parent_id") or "") == str(target["id"])
        ]
        updated, changed = update_ui_object(
            document,
            str(target["id"]),
            {"layout": _entry_layout(children)},
        )
        return updated, {
            "operation": "apply",
            "frame_id": str(changed["id"]),
            "created_frame": False,
            "mode": str(changed["layout"]["mode"]),
            "child_object_ids": [str(row["id"]) for row in children],
        }

    parent_ids = {str(row.get("parent_id") or "") for row in rows}
    if len(parent_ids) != 1:
        raise PainterUIDocumentError("Auto Layout layers must share a parent")
    parent_id = next(iter(parent_ids))
    min_x = min(float(row["x"]) for row in rows)
    min_y = min(float(row["y"]) for row in rows)
    max_x = max(float(row["x"]) + float(row["width"]) for row in rows)
    max_y = max(float(row["y"]) + float(row["height"]) for row in rows)
    mode = _inferred_flow(rows)
    ordered = sorted(
        rows,
        key=(
            (lambda row: (float(row["x"]), float(row["y"]), int(row["z_index"])))
            if mode == "horizontal"
            else (lambda row: (float(row["y"]), float(row["x"]), int(row["z_index"])))
        ),
    )
    updated, frame = add_ui_object(
        document,
        kind="frame",
        name=_next_frame_name(document),
        artboard_id=str(rows[0]["artboard_id"]),
        parent_id=parent_id,
        x=min_x,
        y=min_y,
        width=max(1.0, max_x - min_x),
        height=max(1.0, max_y - min_y),
        style={"fill": "#00000000", "stroke": "#00000000"},
    )
    frame_id = str(frame["id"])
    order_by_id = {str(row["id"]): index for index, row in enumerate(ordered)}
    for row in updated["objects"]:
        object_id = str(row["id"])
        if object_id == frame_id:
            row["layout"] = _entry_layout(rows)
        elif object_id in selected:
            row["parent_id"] = frame_id
            row["z_index"] = order_by_id[object_id]
    updated = normalize_ui_document(updated)
    updated["selection"] = {"object_id": frame_id, "object_ids": [frame_id]}
    return updated, {
        "operation": "wrap",
        "frame_id": frame_id,
        "created_frame": True,
        "mode": mode,
        "child_object_ids": [str(row["id"]) for row in ordered],
    }


def remove_auto_layout_from_selection(
    value: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove Auto Layout without ungrouping or deleting its frame."""
    document = normalize_ui_document(value)
    rows = _selected_rows(document)
    targets = [
        row
        for row in rows
        if str(row.get("kind") or "") == "frame"
        and normalize_ui_auto_layout(row.get("layout"))["mode"] != "none"
    ]
    if not targets:
        raise PainterUIDocumentError(
            "Remove Auto Layout requires an Auto Layout frame selection"
        )
    updated = document
    removed_ids: list[str] = []
    for row in targets:
        updated, _changed = update_ui_object(
            updated,
            str(row["id"]),
            {"layout": {"mode": "none"}},
        )
        removed_ids.append(str(row["id"]))
    updated["selection"] = {
        "object_id": str((document.get("selection") or {}).get("object_id") or ""),
        "object_ids": [str(row["id"]) for row in rows],
    }
    return updated, {
        "operation": "remove",
        "removed_frame_ids": removed_ids,
        "created_frame": False,
    }
