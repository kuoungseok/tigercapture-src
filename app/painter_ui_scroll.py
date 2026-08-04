"""Prototype scroll and overflow contracts for Painter UI frames."""
from __future__ import annotations

import copy
from typing import Any, Mapping


_OVERFLOW = {"none", "horizontal", "vertical", "both"}
_POSITIONS = {"scroll", "fixed", "sticky"}


def normalize_ui_scroll(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = copy.deepcopy(dict(value or {}))
    overflow = str(source.get("overflow") or "none").strip().casefold()
    position = str(source.get("position") or "scroll").strip().casefold()
    source.update(
        {
            "overflow": overflow if overflow in _OVERFLOW else "none",
            "position": position if position in _POSITIONS else "scroll",
            "preserve_position": bool(source.get("preserve_position", True)),
        }
    )
    return source


def inspect_ui_scroll(
    document: Mapping[str, Any],
    object_id: str,
) -> dict[str, Any]:
    rows = {
        str(row.get("id") or ""): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    row = rows.get(str(object_id))
    if row is None:
        return {
            "eligible": False,
            "reasons": ["scroll_object_missing"],
            "scroll": normalize_ui_scroll(None),
        }
    scroll = normalize_ui_scroll(row.get("scroll"))
    parent = rows.get(str(row.get("parent_id") or ""))
    parent_scroll = normalize_ui_scroll(parent.get("scroll") if parent else None)
    reasons: list[str] = []
    if scroll["overflow"] != "none" and str(row.get("kind") or "") != "frame":
        reasons.append("scroll_overflow_requires_frame")
    if scroll["overflow"] != "none" and not bool(row.get("clip_content", False)):
        reasons.append("scroll_overflow_requires_clip_content")
    if scroll["position"] != "scroll":
        if parent is None or parent_scroll["overflow"] == "none":
            reasons.append("scroll_position_requires_scrollable_parent")
        if scroll["position"] == "sticky" and parent_scroll["overflow"] not in {
            "vertical",
            "both",
        }:
            reasons.append("sticky_requires_vertical_overflow")
        if scroll["position"] == "fixed":
            from app.painter_ui_auto_layout import normalize_ui_auto_layout

            parent_layout = normalize_ui_auto_layout(parent.get("layout") if parent else None)
            own_layout = normalize_ui_auto_layout(row.get("layout"))
            if (
                parent_layout["mode"] in {"horizontal", "vertical", "grid"}
                and own_layout["positioning"] != "absolute"
            ):
                reasons.append("fixed_in_auto_layout_requires_ignore_auto_layout")
    return {
        "eligible": not reasons,
        "object_id": str(object_id),
        "scroll": scroll,
        "parent_scroll": parent_scroll,
        "reasons": reasons,
    }


__all__ = ["inspect_ui_scroll", "normalize_ui_scroll"]
