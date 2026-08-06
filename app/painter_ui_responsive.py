"""Responsive object overrides for Painter UI documents."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.painter_ui_json_copy import json_deepcopy


_ORIENTATIONS = {"any", "portrait", "landscape"}
_SCALAR_KEYS = {"x", "y", "width", "height", "rotation", "opacity"}
_BOOLEAN_KEYS = {"visible"}
_MAPPING_KEYS = {"style", "content", "constraints", "layout"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def responsive_context(
    artboard: Mapping[str, Any],
) -> tuple[str, str]:
    breakpoint = str(artboard.get("breakpoint") or "custom").strip().casefold()
    orientation = str(artboard.get("orientation") or "").strip().casefold()
    if orientation not in {"portrait", "landscape"}:
        orientation = (
            "landscape"
            if float(artboard.get("width") or 1.0)
            >= float(artboard.get("height") or 1.0)
            else "portrait"
        )
    return breakpoint or "custom", orientation


def normalize_ui_responsive_changes(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    result: dict[str, Any] = {}
    for key in _SCALAR_KEYS:
        if key not in source:
            continue
        number = _number(source[key])
        if key in {"width", "height"}:
            number = max(1.0, number)
        elif key == "opacity":
            number = max(0.0, min(1.0, number))
        result[key] = number
    for key in _BOOLEAN_KEYS:
        if key in source:
            result[key] = bool(source[key])
    for key in _MAPPING_KEYS:
        if isinstance(source.get(key), Mapping):
            result[key] = json_deepcopy(dict(source[key]))
    return result


def normalize_ui_responsive_overrides(
    value: Any,
    *,
    object_id: str,
) -> list[dict[str, Any]]:
    rows = value if isinstance(value, (list, tuple)) else []
    result: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_contexts: set[tuple[str, str]] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            continue
        breakpoint = str(raw.get("breakpoint") or "any").strip().casefold()
        orientation = str(raw.get("orientation") or "any").strip().casefold()
        if orientation not in _ORIENTATIONS:
            orientation = "any"
        context = (breakpoint or "any", orientation)
        if context in used_contexts:
            continue
        override_id = str(
            raw.get("id") or f"{object_id}-responsive-{index + 1}"
        )
        if override_id in used_ids:
            override_id = f"{object_id}-responsive-{index + 1}"
        used_ids.add(override_id)
        used_contexts.add(context)
        result.append(
            {
                "id": override_id,
                "breakpoint": context[0],
                "orientation": context[1],
                "changes": normalize_ui_responsive_changes(raw.get("changes")),
            }
        )
    return result


def responsive_override_for_context(
    row: Mapping[str, Any],
    *,
    breakpoint: str,
    orientation: str,
) -> dict[str, Any] | None:
    matches = _responsive_overrides_for_context(
        row,
        breakpoint=breakpoint,
        orientation=orientation,
    )
    return dict(matches[-1]) if matches else None


def _responsive_overrides_for_context(
    row: Mapping[str, Any],
    *,
    breakpoint: str,
    orientation: str,
) -> list[Mapping[str, Any]]:
    matches: list[tuple[int, int, Mapping[str, Any]]] = []
    for index, override in enumerate(row.get("responsive_overrides", [])):
        if not isinstance(override, Mapping):
            continue
        override_breakpoint = str(override.get("breakpoint") or "any")
        override_orientation = str(override.get("orientation") or "any")
        if override_breakpoint not in {"any", breakpoint}:
            continue
        if override_orientation not in {"any", orientation}:
            continue
        specificity = int(override_breakpoint != "any") + int(
            override_orientation != "any"
        )
        matches.append((specificity, index, override))
    matches.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in matches]


def resolve_ui_responsive_object(
    row: Mapping[str, Any],
    *,
    breakpoint: str,
    orientation: str,
) -> dict[str, Any]:
    result = json_deepcopy(dict(row))
    overrides = _responsive_overrides_for_context(
        row,
        breakpoint=breakpoint,
        orientation=orientation,
    )
    if not overrides:
        return result
    for override in overrides:
        for key, value in normalize_ui_responsive_changes(
            override.get("changes")
        ).items():
            if key in _MAPPING_KEYS:
                result[key] = {
                    **dict(result.get(key) or {}),
                    **json_deepcopy(dict(value)),
                }
            else:
                result[key] = json_deepcopy(value)
    result["responsive_override_id"] = str(overrides[-1]["id"])
    return result


def resolve_ui_responsive_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    result = json_deepcopy(dict(document))
    artboards = {
        str(row["id"]): row
        for row in result.get("artboards", [])
        if isinstance(row, Mapping)
    }
    resolved: list[dict[str, Any]] = []
    for row in result.get("objects", []):
        artboard = artboards.get(str(row.get("artboard_id") or ""))
        if artboard is None:
            resolved.append(dict(row))
            continue
        breakpoint, orientation = responsive_context(artboard)
        resolved.append(
            resolve_ui_responsive_object(
                row,
                breakpoint=breakpoint,
                orientation=orientation,
            )
        )
    result["objects"] = resolved
    return result


def set_ui_responsive_override(
    row: Mapping[str, Any],
    *,
    breakpoint: str,
    orientation: str,
    changes: Mapping[str, Any],
) -> list[dict[str, Any]]:
    object_id = str(row["id"])
    rows = normalize_ui_responsive_overrides(
        row.get("responsive_overrides"),
        object_id=object_id,
    )
    target_breakpoint = str(breakpoint or "any").strip().casefold()
    target_orientation = str(orientation or "any").strip().casefold()
    if target_orientation not in _ORIENTATIONS:
        target_orientation = "any"
    normalized_changes = normalize_ui_responsive_changes(changes)
    for override in rows:
        if (
            override["breakpoint"] == target_breakpoint
            and override["orientation"] == target_orientation
        ):
            override["changes"] = {
                **override["changes"],
                **normalized_changes,
            }
            return rows
    rows.append(
        {
            "id": f"{object_id}-responsive-{len(rows) + 1}",
            "breakpoint": target_breakpoint,
            "orientation": target_orientation,
            "changes": normalized_changes,
        }
    )
    return rows


def remove_ui_responsive_override(
    row: Mapping[str, Any],
    *,
    breakpoint: str,
    orientation: str,
) -> list[dict[str, Any]]:
    return [
        override
        for override in normalize_ui_responsive_overrides(
            row.get("responsive_overrides"),
            object_id=str(row["id"]),
        )
        if not (
            override["breakpoint"] == str(breakpoint).strip().casefold()
            and override["orientation"] == str(orientation).strip().casefold()
        )
    ]


__all__ = [
    "normalize_ui_responsive_changes",
    "normalize_ui_responsive_overrides",
    "remove_ui_responsive_override",
    "resolve_ui_responsive_document",
    "resolve_ui_responsive_object",
    "responsive_context",
    "responsive_override_for_context",
    "set_ui_responsive_override",
]
