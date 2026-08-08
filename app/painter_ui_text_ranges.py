"""Mixed text-style ranges for Painter UI text objects."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


TEXT_RANGE_STYLE_KEYS = {
    "font_family",
    "font_size",
    "font_weight",
    "italic",
    "underline",
    "color",
    "letter_spacing",
    "line_height",
}


def normalize_ui_text_ranges(value: object, text: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    limit = len(str(text))
    rows: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        start = max(0, min(limit, int(raw.get("start") or 0)))
        end = max(start, min(limit, int(raw.get("end") or start)))
        if end <= start:
            continue
        style = {
            str(key): copy.deepcopy(item)
            for key, item in dict(raw.get("style") or {}).items()
            if str(key) in TEXT_RANGE_STYLE_KEYS
        }
        if style:
            rows.append({"start": start, "end": end, "style": style})
    rows.sort(key=lambda row: (row["start"], row["end"]))
    return rows


def _text_object(
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
    if row["kind"] not in {"text", "button"}:
        raise PainterUIDocumentError("Mixed text style requires text or button")
    content = copy.deepcopy(dict(row.get("content") or {}))
    return document, row, content


def inspect_ui_text_ranges(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document, row, content = _text_object(value, object_id)
    text = str(content.get("text") or "")
    return {
        "object_id": row["id"],
        "revision": document["revision"],
        "text_length": len(text),
        "ranges": normalize_ui_text_ranges(content.get("text_ranges"), text),
    }


def set_ui_text_range_style(
    value: Mapping[str, Any] | None,
    object_id: str,
    start: int,
    end: int,
    style: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, row, content = _text_object(value, object_id)
    text = str(content.get("text") or "")
    ranges = normalize_ui_text_ranges(content.get("text_ranges"), text)
    candidate = normalize_ui_text_ranges(
        [{"start": start, "end": end, "style": dict(style)}],
        text,
    )
    if not candidate:
        raise PainterUIDocumentError("Text range must be non-empty and styled")
    ranges = [
        item
        for item in ranges
        if item["end"] <= candidate[0]["start"]
        or item["start"] >= candidate[0]["end"]
    ]
    ranges.append(candidate[0])
    ranges.sort(key=lambda item: (item["start"], item["end"]))
    content["text_ranges"] = ranges
    document, _updated = update_ui_object(
        document,
        row["id"],
        {"content": content},
    )
    return document, copy.deepcopy(candidate[0])


def remove_ui_text_range_style(
    value: Mapping[str, Any] | None,
    object_id: str,
    start: int,
    end: int,
) -> dict[str, Any]:
    document, row, content = _text_object(value, object_id)
    text = str(content.get("text") or "")
    content["text_ranges"] = [
        item
        for item in normalize_ui_text_ranges(content.get("text_ranges"), text)
        if item["end"] <= int(start) or item["start"] >= int(end)
    ]
    document, _updated = update_ui_object(
        document,
        row["id"],
        {"content": content},
    )
    return document


__all__ = [
    "inspect_ui_text_ranges",
    "normalize_ui_text_ranges",
    "remove_ui_text_range_style",
    "set_ui_text_range_style",
]
