"""Preview-first, reference-safe Find/Replace for Painter UI documents."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document, validate_ui_document


FIND_REPLACE_SCHEMA = "tigerstudio.painter.ui.find_replace.v1"
FIND_REPLACE_CATEGORIES = (
    "text",
    "component",
    "style",
    "variable",
    "font",
    "asset",
)


def _normalized_categories(value: Sequence[str] | None) -> list[str]:
    if value is None:
        return list(FIND_REPLACE_CATEGORIES)
    categories = []
    for item in value:
        category = str(item or "").strip().casefold()
        if category not in FIND_REPLACE_CATEGORIES:
            raise ValueError(f"Unsupported Find/Replace category: {item}")
        if category not in categories:
            categories.append(category)
    return categories


def _matches(
    value: str,
    find: str,
    *,
    case_sensitive: bool,
    whole_value: bool,
) -> bool:
    source = value if case_sensitive else value.casefold()
    needle = find if case_sensitive else find.casefold()
    return source == needle if whole_value else needle in source


def _replace(
    value: str,
    find: str,
    replacement: str,
    *,
    case_sensitive: bool,
    whole_value: bool,
) -> str:
    if whole_value:
        return replacement if _matches(
            value,
            find,
            case_sensitive=case_sensitive,
            whole_value=True,
        ) else value
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.sub(re.escape(find), lambda _match: replacement, value, flags=flags)


def _match_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "ui-find-" + hashlib.sha1(encoded).hexdigest()[:16]


def _reference_index(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, list[Mapping[str, Any]]]]:
    by_id = {str(row["id"]): row for row in rows}
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_name.setdefault(str(row.get("name") or "").casefold(), []).append(row)
    return by_id, by_name


def _resolve_reference(
    replacement: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str]:
    target = str(replacement or "").strip()
    if not target:
        return "", ""
    by_id, by_name = _reference_index(rows)
    if target in by_id:
        return target, ""
    named = by_name.get(target.casefold(), [])
    if len(named) == 1:
        return str(named[0]["id"]), ""
    if not named:
        return "", f"Reference target not found: {target}"
    return "", f"Reference name is ambiguous: {target}"


def _display_reference(
    reference_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> str:
    row = next(
        (item for item in rows if str(item["id"]) == str(reference_id)),
        None,
    )
    if row is None:
        return str(reference_id)
    return f"{row.get('name') or row['id']} [{row['id']}]"


def _append_match(
    matches: list[dict[str, Any]],
    *,
    category: str,
    target_type: str,
    target_id: str,
    target_name: str,
    path: str,
    current: str,
    proposed: str,
    valid: bool = True,
    reason: str = "",
    proposed_value: str | None = None,
) -> None:
    payload = {
        "category": category,
        "target_type": target_type,
        "target_id": target_id,
        "path": path,
        "current": current,
        "proposed": proposed,
    }
    matches.append(
        {
            "match_id": _match_id(payload),
            **payload,
            "target_name": target_name,
            "valid": bool(valid),
            "reason": str(reason or ""),
            "proposed_value": (
                proposed if proposed_value is None else proposed_value
            ),
        }
    )


def _plain_match(
    matches: list[dict[str, Any]],
    *,
    category: str,
    target_type: str,
    row: Mapping[str, Any],
    path: str,
    current: Any,
    find: str,
    replacement: str,
    case_sensitive: bool,
    whole_value: bool,
    allow_empty: bool = True,
) -> None:
    current_text = str(current or "")
    if not current_text or not _matches(
        current_text,
        find,
        case_sensitive=case_sensitive,
        whole_value=whole_value,
    ):
        return
    proposed = _replace(
        current_text,
        find,
        replacement,
        case_sensitive=case_sensitive,
        whole_value=whole_value,
    )
    valid = allow_empty or bool(proposed.strip())
    _append_match(
        matches,
        category=category,
        target_type=target_type,
        target_id=str(row["id"]),
        target_name=str(row.get("name") or row["id"]),
        path=path,
        current=current_text,
        proposed=proposed,
        valid=valid,
        reason="" if valid else "Name cannot be empty.",
    )


def _reference_match(
    matches: list[dict[str, Any]],
    *,
    category: str,
    target_type: str,
    row: Mapping[str, Any],
    path: str,
    reference_id: str,
    references: Sequence[Mapping[str, Any]],
    find: str,
    replacement: str,
    case_sensitive: bool,
    whole_value: bool,
    allow_detach: bool = True,
    replacement_supported: bool = True,
) -> None:
    current_display = _display_reference(reference_id, references)
    if not _matches(
        current_display,
        find,
        case_sensitive=case_sensitive,
        whole_value=whole_value,
    ) and not _matches(
        reference_id,
        find,
        case_sensitive=case_sensitive,
        whole_value=whole_value,
    ):
        return
    proposed_id, reason = _resolve_reference(replacement, references)
    if not replacement.strip() and not allow_detach:
        reason = "This reference cannot be detached by Find/Replace."
    if not replacement_supported:
        reason = "Use the component Instance Swap command for this reference."
    proposed_display = (
        _display_reference(proposed_id, references)
        if proposed_id
        else "(detach)" if not replacement.strip() else replacement
    )
    _append_match(
        matches,
        category=category,
        target_type=target_type,
        target_id=str(row["id"]),
        target_name=str(row.get("name") or row["id"]),
        path=path,
        current=current_display,
        proposed=proposed_display,
        valid=not reason,
        reason=reason,
        proposed_value=proposed_id,
    )


def inspect_ui_find_replace(
    value: Mapping[str, Any] | None,
    *,
    find: str,
    replacement: str = "",
    categories: Sequence[str] | None = None,
    case_sensitive: bool = False,
    whole_value: bool = False,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    needle = str(find or "")
    if not needle:
        raise ValueError("Find text cannot be empty.")
    replacement_text = str(replacement or "")
    selected_categories = _normalized_categories(categories)
    matches: list[dict[str, Any]] = []
    components = list(document["components"])
    styles = list(document["styles"])
    tokens = list(document["tokens"])

    for row in document["objects"]:
        content = dict(row.get("content") or {})
        style = dict(row.get("style") or {})
        if "text" in selected_categories:
            _plain_match(
                matches,
                category="text",
                target_type="object",
                row=row,
                path="content.text",
                current=content.get("text"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
            )
        if "font" in selected_categories:
            _plain_match(
                matches,
                category="font",
                target_type="object",
                row=row,
                path="style.font_family",
                current=style.get("font_family"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                allow_empty=False,
            )
        if "asset" in selected_categories:
            for key in ("source_path", "path", "resource_id"):
                _plain_match(
                    matches,
                    category="asset",
                    target_type="object",
                    row=row,
                    path=f"content.{key}",
                    current=content.get(key),
                    find=needle,
                    replacement=replacement_text,
                    case_sensitive=case_sensitive,
                    whole_value=whole_value,
                )
        if (
            "component" in selected_categories
            and row.get("component_id")
            and row.get("component_role") == "instance"
        ):
            _reference_match(
                matches,
                category="component",
                target_type="object",
                row=row,
                path="component_id",
                reference_id=str(row["component_id"]),
                references=components,
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                replacement_supported=False,
            )
        if "style" in selected_categories:
            for kind, style_id in dict(row.get("style_ids") or {}).items():
                _reference_match(
                    matches,
                    category="style",
                    target_type="object",
                    row=row,
                    path=f"style_ids.{kind}",
                    reference_id=str(style_id),
                    references=styles,
                    find=needle,
                    replacement=replacement_text,
                    case_sensitive=case_sensitive,
                    whole_value=whole_value,
                )
        if "variable" in selected_categories:
            for path, token_id in dict(row.get("token_bindings") or {}).items():
                _reference_match(
                    matches,
                    category="variable",
                    target_type="object",
                    row=row,
                    path=f"token_bindings::{path}",
                    reference_id=str(token_id),
                    references=tokens,
                    find=needle,
                    replacement=replacement_text,
                    case_sensitive=case_sensitive,
                    whole_value=whole_value,
                )

    if "component" in selected_categories:
        for row in components:
            _plain_match(
                matches,
                category="component",
                target_type="component",
                row=row,
                path="name",
                current=row.get("name"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                allow_empty=False,
            )
    for row in styles:
        if "style" in selected_categories:
            _plain_match(
                matches,
                category="style",
                target_type="style",
                row=row,
                path="name",
                current=row.get("name"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                allow_empty=False,
            )
        if "font" in selected_categories:
            _plain_match(
                matches,
                category="font",
                target_type="style",
                row=row,
                path="properties.font_family",
                current=dict(row.get("properties") or {}).get("font_family"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                allow_empty=False,
            )
    if "variable" in selected_categories:
        for row in tokens:
            _plain_match(
                matches,
                category="variable",
                target_type="token",
                row=row,
                path="name",
                current=row.get("name"),
                find=needle,
                replacement=replacement_text,
                case_sensitive=case_sensitive,
                whole_value=whole_value,
                allow_empty=False,
            )

    matches.sort(
        key=lambda row: (
            FIND_REPLACE_CATEGORIES.index(row["category"]),
            row["target_type"],
            row["target_name"].casefold(),
            row["path"],
        )
    )
    return {
        "schema": FIND_REPLACE_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "find": needle,
        "replacement": replacement_text,
        "categories": selected_categories,
        "case_sensitive": bool(case_sensitive),
        "whole_value": bool(whole_value),
        "matches": matches,
        "match_count": len(matches),
        "valid_match_count": sum(bool(row["valid"]) for row in matches),
        "invalid_match_count": sum(not bool(row["valid"]) for row in matches),
    }


def _set_path(row: dict[str, Any], path: str, value: Any) -> None:
    if str(path).startswith("token_bindings::"):
        binding_path = str(path).split("::", 1)[1]
        bindings = dict(row.get("token_bindings") or {})
        if value:
            bindings[binding_path] = str(value)
        else:
            bindings.pop(binding_path, None)
        row["token_bindings"] = bindings
        return
    parts = [part for part in str(path).split(".") if part]
    target = row
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = dict(child) if isinstance(child, Mapping) else {}
            target[part] = child
        target = child
    target[parts[-1]] = copy.deepcopy(value)


def apply_ui_find_replace(
    value: Mapping[str, Any] | None,
    *,
    find: str,
    replacement: str = "",
    categories: Sequence[str] | None = None,
    case_sensitive: bool = False,
    whole_value: bool = False,
    selected_match_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    preview = inspect_ui_find_replace(
        document,
        find=find,
        replacement=replacement,
        categories=categories,
        case_sensitive=case_sensitive,
        whole_value=whole_value,
    )
    selected = (
        {str(match_id) for match_id in selected_match_ids}
        if selected_match_ids is not None
        else {
            row["match_id"]
            for row in preview["matches"]
            if bool(row["valid"])
        }
    )
    chosen = [
        row for row in preview["matches"] if row["match_id"] in selected
    ]
    invalid = [row for row in chosen if not row["valid"]]
    if invalid:
        raise ValueError(
            "Selected Find/Replace matches are invalid: "
            + ", ".join(row["match_id"] for row in invalid)
        )
    if not chosen:
        return document, {**preview, "applied_match_ids": [], "applied_count": 0}

    updated = copy.deepcopy(document)
    row_maps = {
        "object": {row["id"]: row for row in updated["objects"]},
        "component": {row["id"]: row for row in updated["components"]},
        "style": {row["id"]: row for row in updated["styles"]},
        "token": {row["id"]: row for row in updated["tokens"]},
    }
    for match in chosen:
        target = row_maps[match["target_type"]][match["target_id"]]
        _set_path(target, match["path"], match["proposed_value"])
    updated["revision"] = int(document["revision"]) + 1
    updated = normalize_ui_document(updated)
    validation = validate_ui_document(updated)
    if not validation["ok"]:
        raise ValueError(
            "Find/Replace would invalidate the UI document: "
            + ", ".join(validation["errors"])
        )
    return updated, {
        **preview,
        "applied_match_ids": [row["match_id"] for row in chosen],
        "applied_count": len(chosen),
        "result_revision": updated["revision"],
    }


__all__ = [
    "FIND_REPLACE_CATEGORIES",
    "FIND_REPLACE_SCHEMA",
    "apply_ui_find_replace",
    "inspect_ui_find_replace",
]
