"""Hierarchy navigation helpers for Painter UI Design selection."""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, select_ui_object


def ui_layer_panel_order(
    value: Mapping[str, Any] | None,
    *,
    artboard_id: str = "",
) -> list[dict[str, Any]]:
    """Return visible layers in the same hierarchy order as Layers panel."""
    document = normalize_ui_document(value)
    target_artboard = str(
        artboard_id or document["active_artboard_id"] or ""
    )
    children: dict[str, list[dict[str, Any]]] = {}
    for row in document["objects"]:
        if (
            str(row.get("artboard_id") or "") != target_artboard
            or not bool(row.get("visible", True))
        ):
            continue
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    for rows in children.values():
        rows.sort(key=lambda row: int(row.get("z_index", 0)), reverse=True)
    ordered: list[dict[str, Any]] = []
    visited: set[str] = set()

    def append_children(parent_id: str) -> None:
        for row in children.get(parent_id, []):
            object_id = str(row["id"])
            if object_id in visited:
                continue
            visited.add(object_id)
            ordered.append(row)
            append_children(object_id)

    append_children("")
    return ordered


def ui_select_layer_rows(
    value: Mapping[str, Any] | None,
    hit_object_ids: list[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    """Filter pointer hits into official Select layer menu order."""
    hits = {str(object_id) for object_id in hit_object_ids if object_id}
    return [
        row
        for row in ui_layer_panel_order(value)
        if str(row["id"]) in hits
    ]


def parent_ui_object_id(
    value: Mapping[str, Any] | None,
    object_id: str = "",
) -> str:
    document = normalize_ui_document(value)
    target = str(
        object_id or document["selection"]["object_id"] or ""
    )
    row = next(
        (item for item in document["objects"] if item["id"] == target),
        None,
    )
    if row is None:
        return ""
    return str(row.get("parent_id") or row["id"])


def sibling_ui_object_id(
    value: Mapping[str, Any] | None,
    object_id: str = "",
    *,
    previous: bool = False,
) -> str:
    document = normalize_ui_document(value)
    target = str(
        object_id or document["selection"]["object_id"] or ""
    )
    by_id = {str(row["id"]): row for row in document["objects"]}
    current = by_id.get(target)
    if current is None:
        return ""
    siblings = [
        row
        for row in document["objects"]
        if str(row.get("artboard_id") or "")
        == str(current.get("artboard_id") or "")
        and str(row.get("parent_id") or "")
        == str(current.get("parent_id") or "")
        and bool(row.get("visible", True))
        and not bool(row.get("locked"))
    ]
    siblings.sort(
        key=lambda row: int(row.get("z_index", 0)),
        reverse=True,
    )
    ids = [str(row["id"]) for row in siblings]
    if target not in ids:
        return ""
    index = ids.index(target) + (-1 if previous else 1)
    return ids[index] if 0 <= index < len(ids) else ""


def ui_selection_path(
    value: Mapping[str, Any] | None,
    object_id: str = "",
    *,
    normalize: bool = True,
) -> list[dict[str, Any]]:
    # Read-only: callers holding a canonical document skip the defensive
    # copy, which dominates click latency on large imported files.
    document = normalize_ui_document(value) if normalize else value
    target = str(
        object_id
        or document["selection"]["object_id"]
        or ""
    )
    objects = {row["id"]: row for row in document["objects"]}
    current = objects.get(target)
    path: list[dict[str, Any]] = []
    seen: set[str] = set()
    while current is not None and current["id"] not in seen:
        seen.add(current["id"])
        path.append(current)
        current = objects.get(str(current.get("parent_id") or ""))
    path.reverse()
    return path


def select_parent_ui_object(
    value: Mapping[str, Any] | None,
    object_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = parent_ui_object_id(document, object_id)
    if target:
        document = select_ui_object(document, target)
    return document, {
        "selected_object_id": target,
        "path": [
            {"id": row["id"], "name": row["name"], "kind": row["kind"]}
            for row in ui_selection_path(document)
        ],
    }


def select_deep_ui_object(
    value: Mapping[str, Any] | None,
    object_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    current_id = str(
        object_id
        or document["selection"]["object_id"]
        or ""
    )
    children: dict[str, list[dict[str, Any]]] = {}
    for row in document["objects"]:
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        rows = children.get(current_id, [])
        if not rows:
            break
        current_id = str(
            max(
                enumerate(rows),
                key=lambda item: (
                    int(item[1].get("z_index", item[0])),
                    item[0],
                ),
            )[1]["id"]
        )
    if current_id:
        document = select_ui_object(document, current_id)
    return document, {
        "selected_object_id": current_id,
        "path": [
            {"id": row["id"], "name": row["name"], "kind": row["kind"]}
            for row in ui_selection_path(document)
        ],
    }


__all__ = [
    "parent_ui_object_id",
    "select_deep_ui_object",
    "select_parent_ui_object",
    "sibling_ui_object_id",
    "ui_layer_panel_order",
    "ui_select_layer_rows",
    "ui_selection_path",
]
