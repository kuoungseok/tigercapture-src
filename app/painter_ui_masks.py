"""Provider-neutral mask groups for Painter UI documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


def normalize_ui_mask(value: object) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    return {
        "enabled": bool(row.get("enabled", False)),
        "inverted": bool(row.get("inverted", False)),
        "outline": bool(row.get("outline", False)),
        "target_ids": [
            str(item)
            for item in row.get("target_ids", [])
            if str(item or "")
        ],
    }


def ui_mask_render_groups(
    objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return mask sources with their complete source/target subtrees."""

    children_by_parent: dict[str, list[str]] = {}
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in objects:
        object_id = str(row.get("id") or "")
        if not object_id:
            continue
        rows_by_id[object_id] = row
        children_by_parent.setdefault(
            str(row.get("parent_id") or ""),
            [],
        ).append(object_id)

    def subtree_ids(root_id: str) -> list[str]:
        result: list[str] = []
        pending = [str(root_id or "")]
        seen: set[str] = set()
        while pending:
            object_id = pending.pop()
            if not object_id or object_id in seen:
                continue
            seen.add(object_id)
            if object_id in rows_by_id:
                result.append(object_id)
            pending.extend(reversed(children_by_parent.get(object_id, [])))
        return result

    groups: list[dict[str, Any]] = []
    claimed_targets: set[str] = set()
    for row in objects:
        mask = normalize_ui_mask(row.get("mask"))
        if not mask["enabled"]:
            continue
        target_ids: list[str] = []
        for target_root_id in mask["target_ids"]:
            for target_id in subtree_ids(target_root_id):
                if target_id in claimed_targets:
                    continue
                claimed_targets.add(target_id)
                target_ids.append(target_id)
        groups.append(
            {
                "source": row,
                "mask": mask,
                "source_ids": subtree_ids(str(row.get("id") or "")),
                "target_ids": target_ids,
            }
        )
    return groups


def index_ui_mask_rendering(
    objects: list[dict[str, Any]],
) -> tuple[
    dict[str, tuple[dict[str, Any], dict[str, Any]]],
    set[str],
]:
    """Index effective mask targets and non-rendering mask source rows.

    A Figma/Painter mask targets sibling roots, but its visual effect applies
    to the complete subtree below each target.  Conversely, the mask source
    subtree supplies mask geometry/alpha and must not be painted as ordinary
    content.  Keeping both rules in one provider-neutral index prevents the
    interactive canvas and deterministic asset renderer from drifting apart.

    The current document contract can associate one mask source with a target
    row.  When malformed or nested input associates several sources with the
    same row, document order wins deterministically; exact nested composition
    remains an explicit export/preflight concern rather than silently changing
    masks between renderers.
    """

    source_by_target: dict[
        str,
        tuple[dict[str, Any], dict[str, Any]],
    ] = {}
    hidden_source_ids: set[str] = set()
    for group in ui_mask_render_groups(objects):
        row = group["source"]
        mask = group["mask"]
        hidden_source_ids.update(group["source_ids"])
        for target_id in group["target_ids"]:
            source_by_target.setdefault(target_id, (row, mask))
    return source_by_target, hidden_source_ids


def _object(document: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    return row


def _validate_targets(
    document: Mapping[str, Any],
    mask_row: Mapping[str, Any],
    target_ids: list[str],
) -> list[str]:
    by_id = {row["id"]: row for row in document["objects"]}
    result: list[str] = []
    for target_id in target_ids:
        target = by_id.get(str(target_id))
        if target is None:
            raise PainterUIDocumentError(
                f"UI mask target not found: {target_id}"
            )
        if target["id"] == mask_row["id"]:
            raise PainterUIDocumentError("A UI mask cannot target itself")
        if target["artboard_id"] != mask_row["artboard_id"]:
            raise PainterUIDocumentError(
                f"UI mask target artboard mismatch: {target_id}"
            )
        if target["parent_id"] != mask_row["parent_id"]:
            raise PainterUIDocumentError(
                f"UI mask target must be a sibling: {target_id}"
            )
        if target["id"] not in result:
            result.append(target["id"])
    return result


def inspect_ui_mask(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    mask = normalize_ui_mask(row.get("mask"))
    return {
        "object_id": row["id"],
        "supported": row["kind"] not in {"line", "motion_actor"},
        "revision": document["revision"],
        **mask,
    }


def create_ui_mask(
    value: Mapping[str, Any] | None,
    object_id: str,
    *,
    target_ids: list[str] | None = None,
    inverted: bool = False,
    outline: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    if row["kind"] in {"line", "motion_actor"}:
        raise PainterUIDocumentError(
            f"UI object cannot be used as a mask: {row['kind']}"
        )
    if target_ids is None:
        target_ids = [
            item["id"]
            for item in document["objects"]
            if item["artboard_id"] == row["artboard_id"]
            and item["parent_id"] == row["parent_id"]
            and item["z_index"] > row["z_index"]
        ]
    mask = {
        "enabled": True,
        "inverted": bool(inverted),
        "outline": bool(outline),
        "target_ids": _validate_targets(document, row, list(target_ids)),
    }
    return update_ui_object(document, row["id"], {"mask": mask})


def update_ui_mask(
    value: Mapping[str, Any] | None,
    object_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    current = normalize_ui_mask(row.get("mask"))
    merged = normalize_ui_mask({**current, **dict(changes)})
    merged["target_ids"] = _validate_targets(
        document,
        row,
        merged["target_ids"],
    )
    return update_ui_object(document, row["id"], {"mask": merged})


def remove_ui_mask(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    document, _updated = update_ui_object(
        document,
        row["id"],
        {"mask": normalize_ui_mask(None)},
    )
    return document


def reorder_ui_mask_targets(
    value: Mapping[str, Any] | None,
    object_id: str,
    target_ids: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    return update_ui_mask(
        value,
        object_id,
        {"target_ids": list(target_ids)},
    )


def mask_for_target(
    value: Mapping[str, Any] | None,
    target_id: str,
) -> dict[str, Any] | None:
    document = normalize_ui_document(value)
    source = index_ui_mask_rendering(document["objects"])[0].get(
        str(target_id)
    )
    if source is None:
        return None
    row, mask = source
    return {"object": copy.deepcopy(row), "mask": copy.deepcopy(mask)}


__all__ = [
    "create_ui_mask",
    "index_ui_mask_rendering",
    "inspect_ui_mask",
    "mask_for_target",
    "normalize_ui_mask",
    "remove_ui_mask",
    "reorder_ui_mask_targets",
    "ui_mask_render_groups",
    "update_ui_mask",
]
