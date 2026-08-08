"""Recovery workflow for unavailable Figma/library components."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


def normalize_remote_component(value: object) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    present = bool(row)
    return {
        "component_key": str(row.get("component_key") or ""),
        "component_name": str(row.get("component_name") or ""),
        "source_file_key": str(row.get("source_file_key") or ""),
        "source_node_id": str(row.get("source_node_id") or ""),
        "status": str(
            row.get("status") or ("missing" if present else "")
        ).strip().casefold(),
        "replacement_component_id": str(
            row.get("replacement_component_id") or ""
        ),
    }


def inspect_remote_components(
    value: Mapping[str, Any] | None,
    *,
    object_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    rows = []
    for row in document["objects"]:
        if object_id and row["id"] != str(object_id):
            continue
        remote = normalize_remote_component(
            (row.get("content") or {}).get("remote_component")
        )
        if remote["component_key"] or remote["status"] == "missing":
            rows.append({"object_id": row["id"], **remote})
    return {
        "revision": document["revision"],
        "count": len(rows),
        "missing_count": sum(row["status"] == "missing" for row in rows),
        "components": rows,
    }


def _remote_object(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    content = copy.deepcopy(dict(row.get("content") or {}))
    remote = normalize_remote_component(content.get("remote_component"))
    if not remote["component_key"] and remote["status"] != "missing":
        raise PainterUIDocumentError(
            f"UI object is not a remote component: {object_id}"
        )
    return document, row, content


def relink_remote_component(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    component_key: str,
    source_file_key: str = "",
    source_node_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, row, content = _remote_object(value, object_id)
    remote = normalize_remote_component(content.get("remote_component"))
    remote.update(
        {
            "component_key": str(component_key),
            "source_file_key": str(source_file_key),
            "source_node_id": str(source_node_id),
            "status": "linked",
        }
    )
    content["remote_component"] = remote
    return update_ui_object(document, row["id"], {"content": content})


def localize_remote_component(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    name: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, row, content = _remote_object(value, object_id)
    remote = normalize_remote_component(content.get("remote_component"))
    remote["status"] = "localized"
    content["remote_component"] = remote
    document, row = update_ui_object(
        document,
        row["id"],
        {
            "content": content,
            "name": str(name or row["name"]),
        },
    )
    from app.painter_ui_components import convert_ui_object_to_component

    document, _component = convert_ui_object_to_component(
        document,
        root_object_id=row["id"],
        name=str(name or row["name"]),
    )
    localized = next(
        item for item in document["objects"] if item["id"] == row["id"]
    )
    return document, copy.deepcopy(localized)


def replace_remote_component(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    component_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, row, content = _remote_object(value, object_id)
    if str(component_id) not in {
        item["id"] for item in document["components"]
    }:
        raise PainterUIDocumentError(
            f"Replacement UI component not found: {component_id}"
        )
    remote = normalize_remote_component(content.get("remote_component"))
    remote.update(
        {
            "status": "replaced",
            "replacement_component_id": str(component_id),
        }
    )
    content["remote_component"] = remote
    return update_ui_object(
        document,
        row["id"],
        {
            "content": content,
            "component_id": str(component_id),
            "component_role": "instance",
        },
    )


__all__ = [
    "inspect_remote_components",
    "localize_remote_component",
    "normalize_remote_component",
    "relink_remote_component",
    "replace_remote_component",
]
