"""Convert Painter Auto Layout semantics to explicit Tiger UMG panel slots."""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_auto_layout import (
    grid_auto_layout_placements,
    normalize_ui_auto_layout,
)
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_scroll import normalize_ui_scroll


def _flow_slot(
    child: Mapping[str, Any],
    parent_layout: Mapping[str, Any],
    *,
    index: int,
    count: int,
) -> dict[str, Any]:
    mode = str(parent_layout["mode"])
    padding = dict(parent_layout["padding"])
    gap = float(parent_layout["gap"])
    child_layout = normalize_ui_auto_layout(child.get("layout"))
    cross = str(parent_layout["cross_alignment"])
    if mode == "horizontal":
        slot_padding = {
            "Left": padding["left"] if index == 0 else gap,
            "Top": padding["top"],
            "Right": padding["right"] if index == count - 1 else 0.0,
            "Bottom": padding["bottom"],
        }
        horizontal = "Fill"
        vertical = {
            "start": "Top",
            "center": "Center",
            "end": "Bottom",
            "stretch": "Fill",
        }[cross]
        fill = child_layout["width_sizing"] == "fill"
    else:
        slot_padding = {
            "Left": padding["left"],
            "Top": padding["top"] if index == 0 else gap,
            "Right": padding["right"],
            "Bottom": padding["bottom"] if index == count - 1 else 0.0,
        }
        horizontal = {
            "start": "Left",
            "center": "Center",
            "end": "Right",
            "stretch": "Fill",
        }[cross]
        vertical = "Fill"
        fill = child_layout["height_sizing"] == "fill"
    return {
        "Padding": slot_padding,
        "HorizontalAlignment": horizontal,
        "VerticalAlignment": vertical,
        "SizeRule": "Fill" if fill else "Auto",
        "FillCoefficient": 1.0,
    }


def _grid_slot(
    child: Mapping[str, Any],
    parent_layout: Mapping[str, Any],
    placement: tuple[int, int, int, int],
    *,
    row_count: int,
) -> dict[str, Any]:
    row, column, row_span, column_span = placement
    columns = int(parent_layout["grid_columns"])
    padding = dict(parent_layout["padding"])
    child_layout = normalize_ui_auto_layout(child.get("layout"))
    horizontal = {
        "start": "Left",
        "center": "Center",
        "end": "Right",
        "stretch": "Fill",
    }[str(child_layout["cell_horizontal_alignment"])]
    vertical = {
        "start": "Top",
        "center": "Center",
        "end": "Bottom",
        "stretch": "Fill",
    }[str(child_layout["cell_vertical_alignment"])]
    if child_layout["width_sizing"] == "fill":
        horizontal = "Fill"
    if child_layout["height_sizing"] == "fill":
        vertical = "Fill"
    return {
        "Padding": {
            "Left": padding["left"] if column == 0 else float(parent_layout["gap"]),
            "Top": padding["top"] if row == 0 else float(parent_layout["cross_gap"]),
            "Right": padding["right"] if column + column_span >= columns else 0.0,
            "Bottom": padding["bottom"] if row + row_span >= row_count else 0.0,
        },
        "HorizontalAlignment": horizontal,
        "VerticalAlignment": vertical,
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
        "Row": row,
        "Column": column,
        "RowSpan": row_span,
        "ColumnSpan": column_span,
    }


def painter_umg_auto_layout_contract(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return panel types, flow slots, and explicit conversion blockers."""
    document = normalize_ui_document(value)
    rows = list(document["objects"])
    by_id = {str(row["id"]): row for row in rows}
    children: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    for child_rows in children.values():
        child_rows.sort(key=lambda row: (int(row["z_index"]), str(row["id"])))

    panel_kind_by_id: dict[str, str] = {}
    flow_slot_by_id: dict[str, dict[str, Any]] = {}
    blockers_by_id: dict[str, list[str]] = {}
    for row in rows:
        object_id = str(row["id"])
        if str(row.get("kind") or "") not in {"frame", "group"}:
            continue
        layout = normalize_ui_auto_layout(row.get("layout"))
        mode = str(layout["mode"])
        panel_kind_by_id[object_id] = {
            "horizontal": "Horizontal",
            "vertical": "Vertical",
            "grid": "Grid",
        }.get(mode, "Canvas")
        if mode not in {"horizontal", "vertical", "grid"}:
            continue
        reasons: list[str] = []
        if mode != "grid" and bool(layout["wrap"]):
            reasons.append("auto_layout_wrap_requires_umg_wrap_panel")
        if mode != "grid" and str(layout["main_alignment"]) != "start":
            reasons.append(
                "auto_layout_main_alignment_unsupported:"
                + str(layout["main_alignment"])
            )
        all_children = children.get(object_id, [])
        flow_children = [
            child
            for child in all_children
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            != "absolute"
        ]
        absolute_children = [
            str(child["id"])
            for child in all_children
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            == "absolute"
            and normalize_ui_scroll(child.get("scroll"))["position"]
            != "fixed"
        ]
        reasons.extend(
            f"auto_layout_absolute_child_unsupported:{child_id}"
            for child_id in absolute_children
        )
        if reasons:
            blockers_by_id[object_id] = sorted(set(reasons))
            continue
        if mode == "grid":
            placements, row_count = grid_auto_layout_placements(
                flow_children,
                int(layout["grid_columns"]),
            )
            for child in flow_children:
                child_id = str(child["id"])
                flow_slot_by_id[child_id] = _grid_slot(
                    child,
                    layout,
                    placements[child_id],
                    row_count=row_count,
                )
        else:
            for index, child in enumerate(flow_children):
                flow_slot_by_id[str(child["id"])] = _flow_slot(
                    child,
                    layout,
                    index=index,
                    count=len(flow_children),
                )
    return {
        "schema": "tigerstudio.painter.umg.auto_layout.v1",
        "panel_kind_by_id": panel_kind_by_id,
        "flow_slot_by_id": flow_slot_by_id,
        "blockers_by_id": blockers_by_id,
        "converted_panel_ids": sorted(
            object_id
            for object_id, panel_kind in panel_kind_by_id.items()
            if panel_kind in {"Horizontal", "Vertical", "Grid"}
            and object_id not in blockers_by_id
        ),
        "object_count": len(by_id),
    }


__all__ = ["painter_umg_auto_layout_contract"]
