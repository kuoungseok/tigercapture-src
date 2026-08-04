"""Figma-style distribution and Tidy up plans for Painter UI objects."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document


def _intervals_overlap(rows: Sequence[Mapping[str, Any]], axis: str) -> bool:
    position_key = "x" if axis == "x" else "y"
    size_key = "width" if axis == "x" else "height"
    return max(float(row[position_key]) for row in rows) < min(
        float(row[position_key]) + float(row[size_key]) for row in rows
    )


def _mode_gap(values: Sequence[float]) -> float:
    rounded = [round(value) for value in values]
    counts = Counter(rounded)
    return (
        float(max(counts, key=lambda value: (counts[value], -rounded.index(value))))
        if rounded
        else 0.0
    )


def _grid_rows(rows: Sequence[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    """Group a 2D selection into visual rows without changing layer order."""

    ordered = sorted(
        rows,
        key=lambda row: (
            float(row["y"]) + float(row["height"]) * 0.5,
            float(row["x"]),
            str(row["id"]),
        ),
    )
    result: list[list[Mapping[str, Any]]] = []
    for row in ordered:
        row_top = float(row["y"])
        row_bottom = row_top + float(row["height"])
        best: list[Mapping[str, Any]] | None = None
        best_overlap = 0.0
        for candidate in result:
            candidate_top = max(float(item["y"]) for item in candidate)
            candidate_bottom = min(
                float(item["y"]) + float(item["height"])
                for item in candidate
            )
            overlap = min(row_bottom, candidate_bottom) - max(
                row_top, candidate_top
            )
            if overlap > best_overlap:
                best = candidate
                best_overlap = overlap
        if best is None:
            result.append([row])
        else:
            best.append(row)
    result.sort(key=lambda group: min(float(item["y"]) for item in group))
    for group in result:
        group.sort(key=lambda row: (float(row["x"]), str(row["id"])))
    return result


def _inspect_grid(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    visual_rows = _grid_rows(rows)
    horizontal_gaps = [
        float(right["x"]) - (float(left["x"]) + float(left["width"]))
        for group in visual_rows
        for left, right in zip(group, group[1:])
    ]
    row_bounds = [
        (
            min(float(item["y"]) for item in group),
            max(float(item["y"]) + float(item["height"]) for item in group),
        )
        for group in visual_rows
    ]
    vertical_gaps = [
        next_top - previous_bottom
        for (_previous_top, previous_bottom), (next_top, _next_bottom)
        in zip(row_bounds, row_bounds[1:])
    ]
    horizontal_gap = _mode_gap(horizontal_gaps)
    vertical_gap = _mode_gap(vertical_gaps)
    return {
        "grid_rows": [
            [str(item["id"]) for item in group]
            for group in visual_rows
        ],
        "horizontal_gaps": horizontal_gaps,
        "vertical_gaps": vertical_gaps,
        "horizontal_gap": horizontal_gap,
        "vertical_gap": vertical_gap,
        "uniform_horizontal": bool(
            horizontal_gaps
            and max(horizontal_gaps) - min(horizontal_gaps) <= 1.0
        ),
        "uniform_vertical": bool(
            vertical_gaps
            and max(vertical_gaps) - min(vertical_gaps) <= 1.0
        ),
    }


def _selection_ids(
    document: Mapping[str, Any],
    object_ids: Sequence[str] | None,
) -> list[str]:
    raw = (
        object_ids
        if object_ids is not None
        else document.get("selection", {}).get("object_ids", [])
    )
    return list(dict.fromkeys(str(value) for value in raw if str(value)))


def inspect_ui_selection_spacing(
    document: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    axis: str = "auto",
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    selected_ids = _selection_ids(normalized, object_ids)
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    rows = [by_id[object_id] for object_id in selected_ids if object_id in by_id]
    requested_axis = str(axis or "auto").casefold()
    if requested_axis not in {"auto", "horizontal", "vertical"}:
        raise ValueError("axis must be auto, horizontal, or vertical")
    reason = ""
    if len(rows) < 2:
        reason = "Select at least two objects."
    elif len(rows) != len(selected_ids):
        reason = "One or more selected objects no longer exist."
    elif any(bool(row.get("locked", False)) for row in rows):
        reason = "Locked objects cannot be tidied."
    elif len({str(row.get("artboard_id") or "") for row in rows}) != 1:
        reason = "Tidy Up requires one artboard."
    elif len({str(row.get("parent_id") or "") for row in rows}) != 1:
        reason = "Tidy Up requires one parent container."
    if reason:
        return {
            "eligible": False,
            "reason": reason,
            "axis": requested_axis,
            "object_ids": selected_ids,
            "ordered_object_ids": [],
            "gaps": [],
            "uniform": False,
            "gap": None,
            "suggested_gap": None,
        }
    center_x = [
        float(row["x"]) + float(row["width"]) * 0.5
        for row in rows
    ]
    center_y = [
        float(row["y"]) + float(row["height"]) * 0.5
        for row in rows
    ]
    resolved_axis = requested_axis
    if resolved_axis == "auto":
        overlaps_x = _intervals_overlap(rows, "x")
        overlaps_y = _intervals_overlap(rows, "y")
        if overlaps_y and not overlaps_x:
            resolved_axis = "horizontal"
        elif overlaps_x and not overlaps_y:
            resolved_axis = "vertical"
        elif overlaps_x and overlaps_y:
            resolved_axis = (
                "horizontal"
                if max(center_x) - min(center_x) >= max(center_y) - min(center_y)
                else "vertical"
            )
        else:
            resolved_axis = "grid"
    if resolved_axis == "grid":
        grid = _inspect_grid(rows)
        return {
            "eligible": True,
            "reason": "",
            "axis": "grid",
            "object_ids": selected_ids,
            "ordered_object_ids": [
                object_id
                for group in grid["grid_rows"]
                for object_id in group
            ],
            "gaps": [],
            "uniform": bool(
                grid["uniform_horizontal"] and grid["uniform_vertical"]
            ),
            "gap": None,
            "suggested_gap": None,
            **grid,
        }
    position_key = "x" if resolved_axis == "horizontal" else "y"
    size_key = "width" if resolved_axis == "horizontal" else "height"
    ordered = sorted(
        rows,
        key=lambda row: (
            float(row[position_key]),
            int(row.get("z_index", 0)),
            str(row["id"]),
        ),
    )
    gaps = [
        float(right[position_key])
        - (
            float(left[position_key])
            + float(left[size_key])
        )
        for left, right in zip(ordered, ordered[1:])
    ]
    # Figma uses the most common space-between value (the mode), not the
    # arithmetic mean.  Pixel-grid rounding may differ by 1 px, so integer
    # gaps are grouped at display precision before the mode is selected.
    suggested_gap = _mode_gap(gaps)
    uniform = bool(
        gaps
        and max(gaps) - min(gaps) <= 1.0
    )
    return {
        "eligible": True,
        "reason": "",
        "axis": resolved_axis,
        "object_ids": selected_ids,
        "ordered_object_ids": [str(row["id"]) for row in ordered],
        "gaps": gaps,
        "uniform": uniform,
        "gap": gaps[0] if uniform else None,
        "suggested_gap": suggested_gap,
    }


def plan_ui_selection_tidy(
    document: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    axis: str = "auto",
    gap: float | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(
        normalized,
        object_ids=object_ids,
        axis=axis,
    )
    if not report["eligible"]:
        return {**report, "changes_by_id": {}}
    if report["axis"] == "grid":
        horizontal_gap = (
            float(gap.get("horizontal", report["horizontal_gap"]))
            if isinstance(gap, Mapping)
            else float(report["horizontal_gap"])
        )
        vertical_gap = (
            float(gap.get("vertical", report["vertical_gap"]))
            if isinstance(gap, Mapping)
            else float(report["vertical_gap"])
        )
        by_id = {str(row["id"]): row for row in normalized["objects"]}
        visual_rows = [
            [by_id[object_id] for object_id in group]
            for group in report["grid_rows"]
        ]
        origin_x = min(float(row["x"]) for row in by_id.values() if str(row["id"]) in report["object_ids"])
        origin_y = min(float(row["y"]) for row in by_id.values() if str(row["id"]) in report["object_ids"])
        column_count = max(len(group) for group in visual_rows)
        column_widths = [
            max(
                float(group[index]["width"])
                for group in visual_rows
                if index < len(group)
            )
            for index in range(column_count)
        ]
        row_heights = [
            max(float(row["height"]) for row in group)
            for group in visual_rows
        ]
        column_x: list[float] = []
        cursor_x = origin_x
        for width in column_widths:
            column_x.append(cursor_x)
            cursor_x += width + horizontal_gap
        changes_by_id: dict[str, dict[str, float]] = {}
        cursor_y = origin_y
        for row_index, group in enumerate(visual_rows):
            for column_index, row in enumerate(group):
                changes_by_id[str(row["id"])] = {
                    "x": column_x[column_index],
                    "y": cursor_y,
                }
            cursor_y += row_heights[row_index] + vertical_gap
        return {
            **report,
            "horizontal_gap": horizontal_gap,
            "vertical_gap": vertical_gap,
            "changes_by_id": changes_by_id,
        }
    target_gap = (
        float(report["suggested_gap"] or 0.0)
        if gap is None
        else float(gap)
    )
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    position_key = "x" if report["axis"] == "horizontal" else "y"
    size_key = "width" if report["axis"] == "horizontal" else "height"
    ordered = [
        by_id[object_id]
        for object_id in report["ordered_object_ids"]
    ]
    cursor = float(ordered[0][position_key])
    changes_by_id: dict[str, dict[str, float]] = {}
    for row in ordered:
        object_id = str(row["id"])
        changes_by_id[object_id] = {position_key: cursor}
        cursor += float(row[size_key]) + target_gap
    return {
        **report,
        "gap": target_gap,
        "changes_by_id": changes_by_id,
    }


def plan_ui_selection_distribution(
    document: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    axis: str,
) -> dict[str, Any]:
    """Plan Figma's one-axis Distribute command.

    The two outermost objects remain fixed and the interior objects are placed
    so the space between every adjacent pair is equal.  Unlike Tidy up, the
    original selection bounds are retained, so the computed gap may be
    negative when objects overlap.
    """

    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(
        normalized,
        object_ids=object_ids,
        axis=axis,
    )
    if not report["eligible"]:
        return {**report, "changes_by_id": {}}
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    ordered = [by_id[object_id] for object_id in report["ordered_object_ids"]]
    if len(ordered) < 3:
        return {
            **report,
            "eligible": False,
            "reason": "Select at least three objects to distribute spacing.",
            "changes_by_id": {},
        }
    position_key = "x" if report["axis"] == "horizontal" else "y"
    size_key = "width" if report["axis"] == "horizontal" else "height"
    first_position = float(ordered[0][position_key])
    last_edge = float(ordered[-1][position_key]) + float(ordered[-1][size_key])
    total_size = sum(float(row[size_key]) for row in ordered)
    gap = (last_edge - first_position - total_size) / (len(ordered) - 1)
    cursor = first_position
    changes_by_id: dict[str, dict[str, float]] = {}
    for index, row in enumerate(ordered):
        object_id = str(row["id"])
        if 0 < index < len(ordered) - 1:
            changes_by_id[object_id] = {position_key: cursor}
        cursor += float(row[size_key]) + gap
    return {
        **report,
        "gap": gap,
        "changes_by_id": changes_by_id,
    }


def plan_ui_smart_reorder(
    document: Mapping[str, Any] | None,
    *,
    marked_ids: Sequence[str],
    target_index: int,
    axis: str,
) -> dict[str, Any]:
    """Reorder a 1D Smart selection without changing layer hierarchy."""

    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(normalized, axis=axis)
    if not report["eligible"] or not report["uniform"]:
        return {**report, "changes_by_id": {}, "reordered_object_ids": []}
    if report["axis"] not in {"horizontal", "vertical"}:
        return {
            **report,
            "eligible": False,
            "reason": "One-dimensional Smart selection required.",
            "changes_by_id": {},
            "reordered_object_ids": [],
        }
    ordered_ids = [str(value) for value in report["ordered_object_ids"]]
    marked_set = {str(value) for value in marked_ids}
    marked = [object_id for object_id in ordered_ids if object_id in marked_set]
    remaining = [object_id for object_id in ordered_ids if object_id not in marked_set]
    if not marked or not remaining:
        return {
            **report,
            "eligible": False,
            "reason": "Mark part of the Smart selection to reorder.",
            "changes_by_id": {},
            "reordered_object_ids": ordered_ids,
        }
    insert_at = max(0, min(len(remaining), int(target_index)))
    reordered = remaining[:insert_at] + marked + remaining[insert_at:]
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    position_key = "x" if report["axis"] == "horizontal" else "y"
    size_key = "width" if report["axis"] == "horizontal" else "height"
    cursor = min(float(by_id[object_id][position_key]) for object_id in ordered_ids)
    gap = float(report["gap"] or 0.0)
    changes_by_id: dict[str, dict[str, float]] = {}
    for object_id in reordered:
        row = by_id[object_id]
        changes_by_id[object_id] = {position_key: cursor}
        cursor += float(row[size_key]) + gap
    return {
        **report,
        "gap": gap,
        "changes_by_id": changes_by_id,
        "reordered_object_ids": reordered,
        "target_index": insert_at,
    }


def plan_ui_smart_grid_reorder(
    document: Mapping[str, Any] | None,
    *,
    marked_id: str,
    target_row: int,
    target_column: int,
    swap_target_id: str = "",
) -> dict[str, Any]:
    """Reorder one item in a 2D Smart selection's visual row lists."""

    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(normalized, axis="auto")
    if (
        not report["eligible"]
        or not report["uniform"]
        or report["axis"] != "grid"
    ):
        return {**report, "changes_by_id": {}, "grid_rows": []}
    marked_id = str(marked_id)
    grid_rows = [list(group) for group in report["grid_rows"]]
    source = next(
        (
            (row_index, column_index)
            for row_index, group in enumerate(grid_rows)
            for column_index, object_id in enumerate(group)
            if object_id == marked_id
        ),
        None,
    )
    if source is None:
        return {
            **report,
            "eligible": False,
            "reason": "Marked object is not in the Smart selection.",
            "changes_by_id": {},
            "grid_rows": grid_rows,
        }
    source_row, source_column = source
    swap_target_id = str(swap_target_id or "")
    if swap_target_id and swap_target_id != marked_id:
        target = next(
            (
                (row_index, column_index)
                for row_index, group in enumerate(grid_rows)
                for column_index, object_id in enumerate(group)
                if object_id == swap_target_id
            ),
            None,
        )
        if target is not None:
            target_row_index, target_column_index = target
            grid_rows[source_row][source_column] = swap_target_id
            grid_rows[target_row_index][target_column_index] = marked_id
    else:
        grid_rows[source_row].pop(source_column)
        if not grid_rows[source_row]:
            grid_rows.pop(source_row)
            if source_row < target_row:
                target_row -= 1
        target_row = max(0, min(len(grid_rows) - 1, int(target_row)))
        target_column = max(
            0,
            min(len(grid_rows[target_row]), int(target_column)),
        )
        grid_rows[target_row].insert(target_column, marked_id)

    by_id = {str(row["id"]): row for row in normalized["objects"]}
    origin_x = min(float(by_id[object_id]["x"]) for group in grid_rows for object_id in group)
    origin_y = min(float(by_id[object_id]["y"]) for group in grid_rows for object_id in group)
    column_count = max(len(group) for group in grid_rows)
    column_widths = [
        max(
            float(by_id[group[index]]["width"])
            for group in grid_rows
            if index < len(group)
        )
        for index in range(column_count)
    ]
    row_heights = [
        max(float(by_id[object_id]["height"]) for object_id in group)
        for group in grid_rows
    ]
    column_x: list[float] = []
    cursor_x = origin_x
    for width in column_widths:
        column_x.append(cursor_x)
        cursor_x += width + float(report["horizontal_gap"])
    changes_by_id: dict[str, dict[str, float]] = {}
    cursor_y = origin_y
    for row_index, group in enumerate(grid_rows):
        for column_index, object_id in enumerate(group):
            changes_by_id[object_id] = {
                "x": column_x[column_index],
                "y": cursor_y,
            }
        cursor_y += row_heights[row_index] + float(report["vertical_gap"])
    return {
        **report,
        "changes_by_id": changes_by_id,
        "grid_rows": grid_rows,
        "swap_target_id": swap_target_id,
    }


def capture_ui_smart_layout(
    document: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Capture the stable spacing/topology needed after a Smart mutation."""

    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(
        normalized, object_ids=object_ids, axis="auto"
    )
    if not report["eligible"] or not report["uniform"]:
        return {**report, "captured": False}
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    ids = list(report["ordered_object_ids"])
    return {
        **report,
        "captured": True,
        "origin_x": min(float(by_id[item]["x"]) for item in ids),
        "origin_y": min(float(by_id[item]["y"]) for item in ids),
    }


def plan_ui_smart_mutation_reflow(
    document: Mapping[str, Any] | None,
    *,
    layout: Mapping[str, Any],
    removed_ids: Sequence[str] = (),
    duplicate_id_map: Mapping[str, str] | None = None,
    resize: bool = False,
) -> dict[str, Any]:
    """Reflow a captured Smart selection after duplicate/delete/resize."""

    normalized = normalize_ui_document(document)
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    removed = {str(value) for value in removed_ids}
    duplicates = {
        str(source): str(clone)
        for source, clone in dict(duplicate_id_map or {}).items()
    }
    axis = str(layout.get("axis") or "")
    changes: dict[str, dict[str, float]] = {}
    if axis in {"horizontal", "vertical"}:
        sequence: list[str] = []
        for object_id in layout.get("ordered_object_ids", []):
            object_id = str(object_id)
            if object_id not in removed and object_id in by_id:
                sequence.append(object_id)
                if object_id in duplicates and duplicates[object_id] in by_id:
                    sequence.append(duplicates[object_id])
        key = "x" if axis == "horizontal" else "y"
        size = "width" if axis == "horizontal" else "height"
        cursor = float(layout.get(f"origin_{key}") or 0.0)
        for object_id in sequence:
            changes[object_id] = {key: cursor}
            cursor += float(by_id[object_id][size]) + float(layout.get("gap") or 0.0)
        return {"changes_by_id": changes, "ordered_object_ids": sequence}
    if axis != "grid":
        return {"changes_by_id": {}}

    original_rows = [
        [str(value) for value in group]
        for group in layout.get("grid_rows", [])
    ]
    rows = [
        [object_id for object_id in group if object_id not in removed]
        for group in original_rows
    ]
    if resize:
        rows = [group for group in rows if group]
    else:
        columns: list[list[str]] = []
        for column in range(max((len(group) for group in original_rows), default=0)):
            values = [
                group[column]
                for group in original_rows
                if column < len(group) and group[column] not in removed
            ]
            expanded: list[str] = []
            for object_id in values:
                if object_id in by_id:
                    expanded.append(object_id)
                    clone = duplicates.get(object_id, "")
                    if clone in by_id:
                        expanded.append(clone)
            columns.append(expanded)
        x = float(layout.get("origin_x") or 0.0)
        for column in columns:
            y = float(layout.get("origin_y") or 0.0)
            for object_id in column:
                changes[object_id] = {"x": x, "y": y}
                y += float(by_id[object_id]["height"]) + float(layout.get("vertical_gap") or 0.0)
            if column:
                x += max(float(by_id[item]["width"]) for item in column) + float(layout.get("horizontal_gap") or 0.0)
        return {"changes_by_id": changes}

    x_positions: list[float] = []
    x = float(layout.get("origin_x") or 0.0)
    for column in range(max((len(group) for group in rows), default=0)):
        values = [group[column] for group in rows if column < len(group)]
        x_positions.append(x)
        x += max(float(by_id[item]["width"]) for item in values) + float(layout.get("horizontal_gap") or 0.0)
    y = float(layout.get("origin_y") or 0.0)
    for group in rows:
        for column, object_id in enumerate(group):
            if object_id in by_id:
                changes[object_id] = {"x": x_positions[column], "y": y}
        y += max(float(by_id[item]["height"]) for item in group) + float(layout.get("vertical_gap") or 0.0)
    return {"changes_by_id": changes}
