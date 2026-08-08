"""Preview-first batch rename service for Painter UI objects."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document, validate_ui_document


BATCH_RENAME_SCHEMA = "tigerstudio.painter.ui.batch_rename.v1"


def _replace_text(
    value: str,
    find: str,
    replacement: str,
    *,
    case_sensitive: bool,
) -> str:
    if not find:
        return value
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.sub(re.escape(find), lambda _match: replacement, value, flags=flags)


def _match_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "ui-rename-" + hashlib.sha1(encoded).hexdigest()[:16]


def _ordered_object_ids(
    document: Mapping[str, Any],
    object_ids: Sequence[str] | None,
) -> list[str]:
    available = {
        str(row["id"]): row for row in document.get("objects", [])
    }
    requested = (
        [str(value) for value in object_ids]
        if object_ids is not None
        else [
            str(value)
            for value in (document.get("selection") or {}).get(
                "object_ids", []
            )
        ]
    )
    missing = [object_id for object_id in requested if object_id not in available]
    if missing:
        raise ValueError(
            "Painter UI object not found: " + ", ".join(missing)
        )
    unique = []
    for object_id in requested:
        if object_id not in unique:
            unique.append(object_id)
    order = {
        str(row["id"]): index
        for index, row in enumerate(document.get("objects", []))
    }
    return sorted(
        unique,
        key=lambda object_id: (
            str(available[object_id].get("artboard_id") or ""),
            int(available[object_id].get("z_index") or 0),
            order[object_id],
        ),
    )


def inspect_ui_batch_rename(
    value: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    find: str = "",
    replacement: str = "",
    prefix: str = "",
    suffix: str = "",
    numbering: bool = False,
    number_start: int = 1,
    number_padding: int = 0,
    number_separator: str = " ",
    case_sensitive: bool = False,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    ordered_ids = _ordered_object_ids(document, object_ids)
    objects = {str(row["id"]): row for row in document["objects"]}
    start = int(number_start)
    padding = max(0, min(8, int(number_padding)))
    matches = []
    for index, object_id in enumerate(ordered_ids):
        row = objects[object_id]
        current = str(row.get("name") or "")
        base = _replace_text(
            current,
            str(find or ""),
            str(replacement or ""),
            case_sensitive=bool(case_sensitive),
        )
        proposed = f"{prefix}{base}{suffix}"
        if numbering:
            number = str(start + index).zfill(padding)
            proposed = f"{proposed}{number_separator}{number}"
        proposed = proposed.strip()
        if proposed == current:
            continue
        valid = bool(proposed)
        payload = {
            "object_id": object_id,
            "current": current,
            "proposed": proposed,
        }
        matches.append(
            {
                "match_id": _match_id(payload),
                **payload,
                "kind": str(row.get("kind") or ""),
                "artboard_id": str(row.get("artboard_id") or ""),
                "valid": valid,
                "reason": "" if valid else "Name cannot be empty.",
            }
        )
    return {
        "schema": BATCH_RENAME_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "object_ids": ordered_ids,
        "find": str(find or ""),
        "replacement": str(replacement or ""),
        "prefix": str(prefix or ""),
        "suffix": str(suffix or ""),
        "numbering": bool(numbering),
        "number_start": start,
        "number_padding": padding,
        "number_separator": str(number_separator),
        "case_sensitive": bool(case_sensitive),
        "matches": matches,
        "match_count": len(matches),
        "valid_match_count": sum(bool(row["valid"]) for row in matches),
        "invalid_match_count": sum(not bool(row["valid"]) for row in matches),
    }


def apply_ui_batch_rename(
    value: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    find: str = "",
    replacement: str = "",
    prefix: str = "",
    suffix: str = "",
    numbering: bool = False,
    number_start: int = 1,
    number_padding: int = 0,
    number_separator: str = " ",
    case_sensitive: bool = False,
    selected_match_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    report = inspect_ui_batch_rename(
        document,
        object_ids=object_ids,
        find=find,
        replacement=replacement,
        prefix=prefix,
        suffix=suffix,
        numbering=numbering,
        number_start=number_start,
        number_padding=number_padding,
        number_separator=number_separator,
        case_sensitive=case_sensitive,
    )
    selected = (
        {str(match_id) for match_id in selected_match_ids}
        if selected_match_ids is not None
        else {
            row["match_id"]
            for row in report["matches"]
            if bool(row["valid"])
        }
    )
    chosen = [
        row for row in report["matches"] if row["match_id"] in selected
    ]
    invalid = [row for row in chosen if not row["valid"]]
    if invalid:
        raise ValueError(
            "Selected Batch Rename matches are invalid: "
            + ", ".join(row["match_id"] for row in invalid)
        )
    if not chosen:
        return document, {
            **report,
            "applied_match_ids": [],
            "applied_count": 0,
        }
    updated = copy.deepcopy(document)
    objects = {str(row["id"]): row for row in updated["objects"]}
    for match in chosen:
        objects[match["object_id"]]["name"] = match["proposed"]
    updated["revision"] = int(document["revision"]) + 1
    updated = normalize_ui_document(updated)
    validation = validate_ui_document(updated)
    if not validation["ok"]:
        raise ValueError(
            "Batch Rename would invalidate the UI document: "
            + ", ".join(validation["errors"])
        )
    return updated, {
        **report,
        "applied_match_ids": [row["match_id"] for row in chosen],
        "applied_count": len(chosen),
        "result_revision": updated["revision"],
    }


__all__ = [
    "BATCH_RENAME_SCHEMA",
    "apply_ui_batch_rename",
    "inspect_ui_batch_rename",
]
