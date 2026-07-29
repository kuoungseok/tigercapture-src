"""Select-similar inspection for Painter UI documents."""
from __future__ import annotations

import json
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, select_ui_objects


SELECT_SIMILAR_SCHEMA = "tigerstudio.painter.ui.select_similar.v1"
SELECT_SIMILAR_CRITERIA = (
    "kind",
    "fill",
    "stroke",
    "text_style",
    "component",
    "variant",
    "token",
    "effect",
    "interaction",
)
SELECT_SIMILAR_SCOPES = ("active_artboard",)


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _interaction_signature(
    document: Mapping[str, Any],
    object_id: str,
) -> str:
    rows = []
    for row in document.get("interactions", []):
        if str(row.get("source_object_id") or "") != object_id:
            continue
        rows.append(
            {
                "trigger": row.get("trigger"),
                "action": row.get("action"),
                "transition": row.get("transition"),
                "parameters": row.get("parameters"),
            }
        )
    return _stable(rows) if rows else ""


def _criterion_value(
    document: Mapping[str, Any],
    row: Mapping[str, Any],
    criterion: str,
) -> Any:
    style = dict(row.get("style") or {})
    if criterion == "kind":
        return str(row.get("kind") or "")
    if criterion == "fill":
        return style.get("fill")
    if criterion == "stroke":
        return {
            "stroke": style.get("stroke"),
            "stroke_width": style.get("stroke_width"),
        }
    if criterion == "text_style":
        if str(row.get("kind") or "") not in {"text", "button"}:
            return None
        return {
            key: style.get(key)
            for key in (
                "font_family",
                "font_size",
                "font_weight",
                "font_style",
                "font_axes",
                "text_align",
                "line_height",
                "letter_spacing",
                "text_color",
            )
        }
    if criterion == "component":
        return str(row.get("component_id") or "") or None
    if criterion == "variant":
        return str(row.get("variant") or "") or None
    if criterion == "token":
        token_ids = sorted(
            {
                str(token_id)
                for token_id in dict(row.get("token_bindings") or {}).values()
                if str(token_id or "")
            }
        )
        return token_ids or None
    if criterion == "effect":
        effect = {}
        for key in (
            "shadow",
            "text_shadow",
            "blur",
            "background_blur",
            "blend_mode",
        ):
            effect_value = style.get(key)
            if effect_value in (None, "", [], {}):
                continue
            if key == "blend_mode" and str(effect_value).casefold() == "normal":
                continue
            effect[key] = effect_value
        return effect or None
    if criterion == "interaction":
        return _interaction_signature(document, str(row.get("id") or "")) or None
    raise ValueError(f"Unsupported select-similar criterion: {criterion}")


def _candidate_rows(
    document: Mapping[str, Any],
    scope: str,
) -> list[dict[str, Any]]:
    return [
        row
        for row in document["objects"]
        if row["artboard_id"] == document["active_artboard_id"]
    ]


def inspect_ui_select_similar(
    value: Mapping[str, Any] | None,
    *,
    criterion: str = "kind",
    scope: str = "active_artboard",
    object_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    normalized_criterion = str(criterion or "kind").strip().casefold()
    normalized_scope = str(scope or "active_artboard").strip().casefold()
    if normalized_criterion not in SELECT_SIMILAR_CRITERIA:
        raise ValueError(
            "criterion must be one of " + ", ".join(SELECT_SIMILAR_CRITERIA)
        )
    if normalized_scope not in SELECT_SIMILAR_SCOPES:
        raise ValueError(
            "scope must be one of " + ", ".join(SELECT_SIMILAR_SCOPES)
        )
    selected_id = str(
        object_id or document["selection"]["object_id"] or ""
    )
    selected = next(
        (row for row in document["objects"] if row["id"] == selected_id),
        None,
    )
    if selected is None:
        return {
            "schema": SELECT_SIMILAR_SCHEMA,
            "criterion": normalized_criterion,
            "scope": normalized_scope,
            "source_object_id": "",
            "available": False,
            "reason": "Select one UI object first.",
            "match_object_ids": [],
            "match_count": 0,
        }
    source_value = _criterion_value(document, selected, normalized_criterion)
    if source_value in (None, "", [], {}):
        return {
            "schema": SELECT_SIMILAR_SCHEMA,
            "criterion": normalized_criterion,
            "scope": normalized_scope,
            "source_object_id": selected_id,
            "available": False,
            "reason": f"Selected object has no {normalized_criterion} value.",
            "match_object_ids": [],
            "match_count": 0,
        }
    source_signature = _stable(source_value)
    match_ids = [
        row["id"]
        for row in _candidate_rows(document, normalized_scope)
        if _stable(
            _criterion_value(document, row, normalized_criterion)
        )
        == source_signature
    ]
    return {
        "schema": SELECT_SIMILAR_SCHEMA,
        "criterion": normalized_criterion,
        "scope": normalized_scope,
        "source_object_id": selected_id,
        "available": True,
        "reason": "",
        "match_object_ids": match_ids,
        "match_count": len(match_ids),
        "value": source_value,
    }


def select_similar_ui_objects(
    value: Mapping[str, Any] | None,
    *,
    criterion: str = "kind",
    scope: str = "active_artboard",
    object_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    report = inspect_ui_select_similar(
        document,
        criterion=criterion,
        scope=scope,
        object_id=object_id,
    )
    if not report["available"]:
        return document, report
    updated = select_ui_objects(
        document,
        report["match_object_ids"],
        primary_object_id=report["source_object_id"],
    )
    return updated, report


__all__ = [
    "SELECT_SIMILAR_CRITERIA",
    "SELECT_SIMILAR_SCHEMA",
    "SELECT_SIMILAR_SCOPES",
    "inspect_ui_select_similar",
    "select_similar_ui_objects",
]
