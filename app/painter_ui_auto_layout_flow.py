"""Axis-aware ordering services for Painter UI Auto Layout children."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_document import _revised, normalize_ui_document


FLOW_MODES = {"horizontal", "vertical"}


def inspect_auto_layout_child(
    document: Mapping[str, Any] | None,
    child_id: str,
) -> dict[str, Any]:
    """Return the canonical one-axis reorder context for one child."""
    normalized = normalize_ui_document(document)
    by_id = {str(row["id"]): row for row in normalized["objects"]}
    child = by_id.get(str(child_id or ""))
    report: dict[str, Any] = {
        "eligible": False,
        "child_id": str(child_id or ""),
        "parent_id": "",
        "mode": "none",
        "ordered_child_ids": [],
        "index": -1,
        "blocker": "missing_child",
    }
    if child is None:
        return report
    parent_id = str(child.get("parent_id") or "")
    parent = by_id.get(parent_id)
    report["parent_id"] = parent_id
    if parent is None:
        report["blocker"] = "missing_auto_layout_parent"
        return report
    mode = str(normalize_ui_auto_layout(parent.get("layout"))["mode"])
    report["mode"] = mode
    if mode not in FLOW_MODES:
        report["blocker"] = "parent_not_auto_layout"
        return report
    if str(parent.get("component_role") or "") == "instance":
        report["blocker"] = "component_instance_order_locked"
        return report
    if normalize_ui_auto_layout(child.get("layout"))["positioning"] == "absolute":
        report["blocker"] = "absolute_child_out_of_flow"
        return report
    document_order = {
        str(row["id"]): index for index, row in enumerate(normalized["objects"])
    }
    siblings = [
        row
        for row in normalized["objects"]
        if str(row.get("parent_id") or "") == parent_id
        and normalize_ui_auto_layout(row.get("layout"))["positioning"] != "absolute"
    ]
    siblings.sort(
        key=lambda row: (
            int(row.get("z_index") or 0),
            document_order[str(row["id"])],
            str(row["id"]),
        )
    )
    ordered = [str(row["id"]) for row in siblings]
    report["ordered_child_ids"] = ordered
    if str(child_id) not in ordered:
        report["blocker"] = "child_not_in_flow"
        return report
    report.update(
        eligible=True,
        index=ordered.index(str(child_id)),
        blocker="",
    )
    return report


def reorder_auto_layout_child(
    document: Mapping[str, Any] | None,
    child_id: str,
    *,
    target_index: int | None = None,
    delta: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Move one flow child while preserving the parent's existing z slots."""
    normalized = normalize_ui_document(document)
    context = inspect_auto_layout_child(normalized, child_id)
    report = {
        "changed": False,
        **context,
        "previous_index": int(context.get("index", -1)),
        "target_index": int(context.get("index", -1)),
    }
    if not context["eligible"]:
        return normalized, report
    ordered = list(context["ordered_child_ids"])
    previous = int(context["index"])
    requested = previous + int(delta) if target_index is None else int(target_index)
    requested = max(0, min(len(ordered) - 1, requested))
    report["target_index"] = requested
    if requested == previous:
        return normalized, report
    moved = ordered.pop(previous)
    ordered.insert(requested, moved)
    rows_by_id = {str(row["id"]): row for row in normalized["objects"]}
    z_slots = sorted(int(rows_by_id[object_id].get("z_index") or 0) for object_id in ordered)
    updated = copy.deepcopy(normalized)
    updated_by_id = {str(row["id"]): row for row in updated["objects"]}
    for object_id, z_index in zip(ordered, z_slots):
        updated_by_id[object_id]["z_index"] = z_index
    updated = _revised(updated)
    report.update(
        changed=True,
        ordered_child_ids=ordered,
        revision=int(updated["revision"]),
    )
    return updated, report


def set_auto_layout_flow(
    document: Mapping[str, Any] | None,
    container_id: str,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Switch an Auto Layout container between the official H/V flows."""
    normalized = normalize_ui_document(document)
    requested = str(mode or "").strip().casefold()
    report = {
        "changed": False,
        "container_id": str(container_id or ""),
        "mode": requested,
        "blocker": "",
    }
    if requested not in FLOW_MODES:
        report["blocker"] = "invalid_flow_mode"
        return normalized, report
    target = next(
        (row for row in normalized["objects"] if str(row["id"]) == str(container_id)),
        None,
    )
    if target is None:
        report["blocker"] = "missing_container"
        return normalized, report
    if str(target.get("kind") or "") not in {"frame", "group"}:
        report["blocker"] = "unsupported_container_kind"
        return normalized, report
    layout = normalize_ui_auto_layout(target.get("layout"))
    if layout["mode"] == requested:
        return normalized, report
    layout["mode"] = requested
    target["layout"] = layout
    updated = _revised(normalized)
    report.update(changed=True, revision=int(updated["revision"]))
    return updated, report
