"""Figma-style spacing analysis and Tidy Up plans for Painter UI objects."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document


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
        resolved_axis = (
            "horizontal"
            if max(center_x) - min(center_x) >= max(center_y) - min(center_y)
            else "vertical"
        )
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
    suggested_gap = (
        max(0.0, sum(gaps) / len(gaps))
        if gaps
        else 0.0
    )
    uniform = bool(
        gaps
        and max(gaps) - min(gaps) <= 0.5
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
    gap: float | None = None,
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    report = inspect_ui_selection_spacing(
        normalized,
        object_ids=object_ids,
        axis=axis,
    )
    if not report["eligible"]:
        return {**report, "changes_by_id": {}}
    target_gap = (
        max(0.0, float(report["suggested_gap"] or 0.0))
        if gap is None
        else max(0.0, float(gap))
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
