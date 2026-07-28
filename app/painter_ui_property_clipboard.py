"""Stable-ID-safe property clipboard operations for Painter UI objects."""
from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any


UI_PROPERTY_CLIPBOARD_SCHEMA = "tigerstudio.painter.ui.property_clipboard.v1"
_CONTENT_PROPERTY_KEYS = {
    "image_fit",
    "tile_scale",
    "nine_slice_enabled",
    "nine_slice",
}
_PROPERTY_KEYS = ("style", "opacity", "clip_content", "layout")
_REPLACE_KEYS = (
    "kind",
    "width",
    "height",
    "rotation",
    "opacity",
    "visible",
    "clip_content",
    "style",
    "content",
    "mask",
    "layout",
    "accessibility",
)


def _object(document: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    row = next(
        (
            item
            for item in document.get("objects", [])
            if str(item.get("id") or "") == str(object_id)
        ),
        None,
    )
    if row is None:
        raise ValueError(f"UI object not found: {object_id}")
    return row


def copy_ui_object_payload(
    value: Mapping[str, Any],
    object_id: str,
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    row = _object(document, object_id)
    properties = {
        key: copy.deepcopy(row[key])
        for key in _PROPERTY_KEYS
    }
    content_properties = {
        key: copy.deepcopy(value)
        for key, value in row["content"].items()
        if key in _CONTENT_PROPERTY_KEYS
    }
    if content_properties:
        properties["content"] = content_properties
    return {
        "schema": UI_PROPERTY_CLIPBOARD_SCHEMA,
        "source_object_id": row["id"],
        "source_kind": row["kind"],
        "properties": properties,
        "object": copy.deepcopy(row),
    }


def normalize_ui_property_clipboard(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    if source.get("schema") != UI_PROPERTY_CLIPBOARD_SCHEMA:
        raise ValueError("Unsupported Painter UI property clipboard payload")
    properties = source.get("properties")
    row = source.get("object")
    if not isinstance(properties, Mapping) or not isinstance(row, Mapping):
        raise ValueError("Incomplete Painter UI property clipboard payload")
    return {
        "schema": UI_PROPERTY_CLIPBOARD_SCHEMA,
        "source_object_id": str(source.get("source_object_id") or ""),
        "source_kind": str(source.get("source_kind") or ""),
        "properties": copy.deepcopy(dict(properties)),
        "object": copy.deepcopy(dict(row)),
    }


def paste_ui_object_properties(
    value: Mapping[str, Any],
    target_object_ids: Sequence[str],
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_batch_mutation import apply_ui_object_batch
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    clipboard = normalize_ui_property_clipboard(payload)
    changes_by_id: dict[str, dict[str, Any]] = {}
    for object_id in dict.fromkeys(str(value) for value in target_object_ids):
        target = _object(document, object_id)
        changes = copy.deepcopy(clipboard["properties"])
        copied_content = changes.pop("content", None)
        if isinstance(copied_content, Mapping) and target["kind"] == clipboard["source_kind"]:
            changes["content"] = {
                **target["content"],
                **copy.deepcopy(dict(copied_content)),
            }
        changes_by_id[object_id] = changes
    updated, changed_ids = apply_ui_object_batch(document, changes_by_id)
    return updated, {
        "source_object_id": clipboard["source_object_id"],
        "target_object_ids": changed_ids,
        "mode": "properties",
    }


def paste_replace_ui_objects(
    value: Mapping[str, Any],
    target_object_ids: Sequence[str],
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_batch_mutation import apply_ui_object_batch
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    clipboard = normalize_ui_property_clipboard(payload)
    source = clipboard["object"]
    changes = {
        key: copy.deepcopy(source[key])
        for key in _REPLACE_KEYS
        if key in source
    }
    changes_by_id = {
        str(object_id): copy.deepcopy(changes)
        for object_id in dict.fromkeys(str(value) for value in target_object_ids)
    }
    updated, changed_ids = apply_ui_object_batch(document, changes_by_id)
    return updated, {
        "source_object_id": clipboard["source_object_id"],
        "target_object_ids": changed_ids,
        "mode": "replace",
    }


__all__ = [
    "UI_PROPERTY_CLIPBOARD_SCHEMA",
    "copy_ui_object_payload",
    "normalize_ui_property_clipboard",
    "paste_replace_ui_objects",
    "paste_ui_object_properties",
]
