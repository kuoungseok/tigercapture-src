"""Shared multi-object mutation service for Painter UI and Actions."""
from __future__ import annotations

from typing import Any, Mapping


def apply_ui_object_batch(
    document: Mapping[str, Any],
    changes_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    from app.painter_ui_constraints import (
        capture_ui_constraints,
        constraint_parent_geometry,
    )
    from app.painter_ui_document import normalize_ui_document, update_ui_object

    updated = normalize_ui_document(document)
    changed_ids: list[str] = []
    for raw_object_id, raw_changes in changes_by_id.items():
        object_id = str(raw_object_id or "")
        if not object_id or not isinstance(raw_changes, Mapping):
            continue
        row = next(
            (
                item
                for item in updated["objects"]
                if item["id"] == object_id
            ),
            None,
        )
        if row is None:
            raise ValueError(f"UI object not found: {object_id}")
        changes = dict(raw_changes)
        if {"x", "y", "width", "height"} & changes.keys():
            candidate = {**row, **changes}
            changes["constraints"] = capture_ui_constraints(
                candidate,
                constraint_parent_geometry(updated, candidate),
                candidate.get("constraints"),
            )
        if all(row.get(key) == value for key, value in changes.items()):
            continue
        updated, _row = update_ui_object(updated, object_id, changes)
        changed_ids.append(object_id)
    return updated, changed_ids


__all__ = ["apply_ui_object_batch"]
