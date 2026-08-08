"""Parent-frame resolution for objects created on the Painter UI canvas."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _contains_point(row: Mapping[str, Any], x: float, y: float) -> bool:
    left = float(row.get("x") or 0.0)
    top = float(row.get("y") or 0.0)
    return (
        left <= float(x) <= left + float(row.get("width") or 0.0)
        and top <= float(y) <= top + float(row.get("height") or 0.0)
    )


def creation_parent_frame_id(
    document: Mapping[str, Any] | None,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    artboard_id: str = "",
) -> str:
    """Return the deepest visible frame containing a new object's center.

    Painter UI keeps object geometry in artboard coordinates even when an
    object has a parent. Parenting therefore changes hierarchy, clipping and
    layout ownership without rebasing the new object's geometry.
    """
    value = document if isinstance(document, Mapping) else {}
    active_artboard = str(
        artboard_id or value.get("active_artboard_id") or ""
    )
    rows = [
        row
        for row in value.get("objects", [])
        if isinstance(row, Mapping)
        and str(row.get("artboard_id") or "") == active_artboard
        and str(row.get("kind") or "") == "frame"
        and bool(row.get("visible", True))
        and not bool((row.get("content") or {}).get("export_slice", False))
    ]
    if not rows:
        return ""
    center_x = float(x) + float(width) * 0.5
    center_y = float(y) + float(height) * 0.5
    by_id = {str(row.get("id") or ""): row for row in rows}

    def depth(row: Mapping[str, Any]) -> int:
        result = 0
        parent_id = str(row.get("parent_id") or "")
        visited: set[str] = set()
        while parent_id and parent_id not in visited:
            visited.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                break
            result += 1
            parent_id = str(parent.get("parent_id") or "")
        return result

    candidates = [
        row for row in rows if _contains_point(row, center_x, center_y)
    ]
    if not candidates:
        return ""
    candidates.sort(
        key=lambda row: (
            depth(row),
            int(row.get("z_index") or 0),
            -float(row.get("width") or 0.0)
            * float(row.get("height") or 0.0),
        ),
        reverse=True,
    )
    return str(candidates[0].get("id") or "")


__all__ = ["creation_parent_frame_id"]
