"""Figma-compatible sections and their review-comment associations."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document


def normalize_ui_section(value: object, index: int = 0) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    return {
        "id": str(row.get("id") or f"ui-section-{index + 1}"),
        "name": str(row.get("name") or f"Section {index + 1}"),
        "page_name": str(row.get("page_name") or ""),
        "x": float(row.get("x") or 0.0),
        "y": float(row.get("y") or 0.0),
        "width": max(1.0, float(row.get("width") or 640.0)),
        "height": max(1.0, float(row.get("height") or 480.0)),
        "object_ids": [
            str(item)
            for item in row.get("object_ids", [])
            if str(item or "")
        ],
        "collapsed": bool(row.get("collapsed", False)),
        "figma_node_id": str(row.get("figma_node_id") or ""),
    }


def _next_section_id(rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    index = 1
    while f"ui-section-{index}" in used:
        index += 1
    return f"ui-section-{index}"


def inspect_ui_sections(
    value: Mapping[str, Any] | None,
    *,
    section_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    rows = [
        copy.deepcopy(row)
        for row in document.get("sections", [])
        if not section_id or row["id"] == str(section_id)
    ]
    return {
        "revision": document["revision"],
        "count": len(rows),
        "sections": rows,
    }


def create_ui_section(
    value: Mapping[str, Any] | None,
    section: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    rows = list(document.get("sections", []))
    payload = dict(section)
    payload.setdefault("id", _next_section_id(rows))
    row = normalize_ui_section(payload, len(rows))
    if row["id"] in {item["id"] for item in rows}:
        raise PainterUIDocumentError(f"Duplicate UI section ID: {row['id']}")
    object_ids = {item["id"] for item in document["objects"]}
    missing = [item for item in row["object_ids"] if item not in object_ids]
    if missing:
        raise PainterUIDocumentError(
            f"UI section object not found: {missing[0]}"
        )
    rows.append(row)
    document["sections"] = rows
    document["revision"] += 1
    return document, copy.deepcopy(row)


def update_ui_section(
    value: Mapping[str, Any] | None,
    section_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    rows = list(document.get("sections", []))
    for index, row in enumerate(rows):
        if row["id"] != str(section_id):
            continue
        updated = normalize_ui_section(
            {**row, **dict(changes), "id": row["id"]},
            index,
        )
        object_ids = {item["id"] for item in document["objects"]}
        missing = [
            item for item in updated["object_ids"] if item not in object_ids
        ]
        if missing:
            raise PainterUIDocumentError(
                f"UI section object not found: {missing[0]}"
            )
        rows[index] = updated
        document["sections"] = rows
        document["revision"] += 1
        return document, copy.deepcopy(updated)
    raise PainterUIDocumentError(f"UI section not found: {section_id}")


def remove_ui_section(
    value: Mapping[str, Any] | None,
    section_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    rows = [
        row
        for row in document.get("sections", [])
        if row["id"] != str(section_id)
    ]
    if len(rows) == len(document.get("sections", [])):
        raise PainterUIDocumentError(f"UI section not found: {section_id}")
    document["sections"] = rows
    document["revision"] += 1
    return document


__all__ = [
    "create_ui_section",
    "inspect_ui_sections",
    "normalize_ui_section",
    "remove_ui_section",
    "update_ui_section",
]
