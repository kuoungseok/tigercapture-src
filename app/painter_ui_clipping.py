"""Shared frame-clipping mutations for Painter UI and automation."""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


def inspect_ui_clip(
    document: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    row = next(
        (
            item
            for item in normalized["objects"]
            if item["id"] == str(object_id)
        ),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    children = [
        item["id"]
        for item in normalized["objects"]
        if item["parent_id"] == row["id"]
    ]
    return {
        "object_id": row["id"],
        "kind": row["kind"],
        "supported": row["kind"] == "frame",
        "clip_content": bool(row.get("clip_content", False)),
        "child_ids": children,
        "child_count": len(children),
        "revision": normalized["revision"],
    }


def set_ui_clip(
    document: Mapping[str, Any] | None,
    object_id: str,
    clip_content: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report = inspect_ui_clip(document, object_id)
    if not report["supported"]:
        raise PainterUIDocumentError(
            "Clip content is supported only for frame objects"
        )
    return update_ui_object(
        document,
        str(object_id),
        {"clip_content": bool(clip_content)},
    )


def clipping_ancestor_rows(
    document: Mapping[str, Any] | None,
    object_id: str,
) -> list[dict[str, Any]]:
    normalized = normalize_ui_document(document)
    rows = {row["id"]: row for row in normalized["objects"]}
    current = rows.get(str(object_id))
    if current is None:
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    parent_id = str(current.get("parent_id") or "")
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        parent = rows.get(parent_id)
        if parent is None:
            break
        if parent["kind"] == "frame" and bool(parent.get("clip_content", False)):
            result.append(parent)
        parent_id = str(parent.get("parent_id") or "")
    result.reverse()
    return result


__all__ = [
    "clipping_ancestor_rows",
    "inspect_ui_clip",
    "set_ui_clip",
]
