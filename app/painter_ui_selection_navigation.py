"""Hierarchy navigation helpers for Painter UI Design selection."""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, select_ui_object


def ui_selection_path(
    value: Mapping[str, Any] | None,
    object_id: str = "",
) -> list[dict[str, Any]]:
    document = normalize_ui_document(value)
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
    path = ui_selection_path(document, object_id)
    target = (
        str(path[-2]["id"])
        if len(path) >= 2
        else str(path[-1]["id"])
        if path
        else ""
    )
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
    "select_deep_ui_object",
    "select_parent_ui_object",
    "ui_selection_path",
]
