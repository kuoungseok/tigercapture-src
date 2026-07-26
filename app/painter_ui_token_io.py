"""Deterministic JSON import/export for Painter UI design-token libraries."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document, validate_ui_document


TOKEN_LIBRARY_SCHEMA = "tigerstudio.painter.ui.token_library.v1"
TOKEN_IMPORT_POLICIES = ("update", "skip", "regenerate")


def ui_token_library_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    return {
        "schema": TOKEN_LIBRARY_SCHEMA,
        "source_document_id": document["document_id"],
        "source_revision": document["revision"],
        "tokens": copy.deepcopy(document["tokens"]),
    }


def export_ui_token_library(
    value: Mapping[str, Any],
    path: str | Path,
) -> dict[str, Any]:
    payload = ui_token_library_payload(value)
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return {
        "schema": "tigerstudio.painter.ui.token_library.export.v1",
        "ok": True,
        "path": str(target),
        "token_count": len(payload["tokens"]),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _read_token_payload(
    source: str | Path | Mapping[str, Any] | Sequence[Any],
) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    value: Any = source
    if isinstance(source, (str, Path)):
        path = Path(source).expanduser().resolve()
        value = json.loads(path.read_text(encoding="utf-8"))
        metadata["path"] = str(path)
    if isinstance(value, Mapping):
        schema = str(value.get("schema") or "")
        if schema and schema != TOKEN_LIBRARY_SCHEMA:
            raise ValueError(f"Unsupported token library schema: {schema}")
        rows = value.get("tokens")
        metadata.update(
            {
                "source_document_id": str(
                    value.get("source_document_id") or ""
                ),
                "source_revision": int(value.get("source_revision") or 0),
            }
        )
    else:
        rows = value
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("Token library must contain a tokens array")
    typed_rows = [row for row in rows if isinstance(row, Mapping)]
    if len(typed_rows) != len(rows):
        raise ValueError("Token library contains a non-object token")
    source_ids = [str(row.get("id") or "") for row in typed_rows]
    explicit_ids = [token_id for token_id in source_ids if token_id]
    if len(explicit_ids) != len(set(explicit_ids)):
        raise ValueError("Token library contains duplicate token IDs")
    normalized = normalize_ui_document({"tokens": typed_rows})["tokens"]
    return normalized, metadata


def _next_token_id(reserved: set[str]) -> str:
    serial = 1
    while f"ui-token-{serial}" in reserved:
        serial += 1
    token_id = f"ui-token-{serial}"
    reserved.add(token_id)
    return token_id


def import_ui_token_library(
    value: Mapping[str, Any],
    source: str | Path | Mapping[str, Any] | Sequence[Any],
    *,
    conflict_policy: str = "update",
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = str(conflict_policy or "update").strip().casefold()
    if policy not in TOKEN_IMPORT_POLICIES:
        raise ValueError(f"Unsupported token conflict policy: {policy}")
    document = normalize_ui_document(value)
    incoming, metadata = _read_token_payload(source)
    existing_ids = {row["id"] for row in document["tokens"]}
    reserved = set(existing_ids)
    id_map: dict[str, str] = {}
    skipped_ids: list[str] = []
    for row in incoming:
        source_id = str(row["id"])
        if source_id in existing_ids:
            if policy == "regenerate":
                id_map[source_id] = _next_token_id(reserved)
            else:
                id_map[source_id] = source_id
                if policy == "skip":
                    skipped_ids.append(source_id)
        else:
            target_id = source_id or _next_token_id(reserved)
            if target_id in reserved:
                target_id = _next_token_id(reserved)
            else:
                reserved.add(target_id)
            id_map[source_id] = target_id

    token_index = {
        row["id"]: index for index, row in enumerate(document["tokens"])
    }
    added_ids: list[str] = []
    updated_ids: list[str] = []
    for row in incoming:
        source_id = str(row["id"])
        target_id = id_map[source_id]
        if source_id in skipped_ids:
            continue
        imported = copy.deepcopy(row)
        imported["id"] = target_id
        alias_id = str(imported["alias_token_id"])
        if alias_id in id_map:
            imported["alias_token_id"] = id_map[alias_id]
        if target_id in token_index:
            document["tokens"][token_index[target_id]] = imported
            updated_ids.append(target_id)
        else:
            token_index[target_id] = len(document["tokens"])
            document["tokens"].append(imported)
            added_ids.append(target_id)

    document["revision"] = int(document["revision"]) + 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Invalid imported token library: "
            + ", ".join(validation["errors"])
        )
    report = {
        "schema": "tigerstudio.painter.ui.token_library.import.v1",
        "ok": True,
        "conflict_policy": policy,
        "source_token_count": len(incoming),
        "added_ids": added_ids,
        "updated_ids": updated_ids,
        "skipped_ids": skipped_ids,
        "id_map": id_map,
        "token_count": len(document["tokens"]),
        **metadata,
    }
    return document, report


__all__ = [
    "TOKEN_IMPORT_POLICIES",
    "TOKEN_LIBRARY_SCHEMA",
    "export_ui_token_library",
    "import_ui_token_library",
    "ui_token_library_payload",
]
