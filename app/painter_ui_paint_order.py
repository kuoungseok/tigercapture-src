"""Provider-neutral Painter UI hierarchy paint ordering."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def apply_ui_reverse_z_paint_order(
    rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reverse direct-child subtree blocks for opted-in Auto Layout parents.

    Figma ``itemReverseZIndex`` changes overlapping paint stacking only.  It
    must not reverse Auto Layout flow iteration or mutate any object geometry.
    The caller supplies its normal flat paint order; this function replaces
    only the slots occupied by a reverse-Z parent's child subtrees, preserving
    every subtree's internal order and all unrelated row positions.
    """

    ordered = list(rows)
    if len(ordered) < 2:
        return ordered
    by_id = {
        str(row.get("id") or ""): row
        for row in ordered
        if str(row.get("id") or "")
    }
    original_position = {
        str(row.get("id") or ""): index
        for index, row in enumerate(ordered)
        if str(row.get("id") or "")
    }
    children_by_parent: dict[str, list[str]] = {}
    for row in ordered:
        object_id = str(row.get("id") or "")
        parent_id = str(row.get("parent_id") or "")
        if object_id and parent_id in by_id:
            children_by_parent.setdefault(parent_id, []).append(object_id)
    for children in children_by_parent.values():
        children.sort(key=lambda object_id: original_position[object_id])

    subtree_cache: dict[str, set[str]] = {}

    def subtree_ids(root_id: str, visiting: set[str] | None = None) -> set[str]:
        cached = subtree_cache.get(root_id)
        if cached is not None:
            return cached
        active = set(visiting or ())
        if root_id in active:
            return {root_id}
        active.add(root_id)
        result = {root_id}
        for child_id in children_by_parent.get(root_id, []):
            result.update(subtree_ids(child_id, active))
        subtree_cache[root_id] = result
        return result

    def depth(object_id: str) -> int:
        result = 0
        seen: set[str] = set()
        current = by_id.get(object_id)
        while current is not None:
            parent_id = str(current.get("parent_id") or "")
            if not parent_id or parent_id in seen or parent_id not in by_id:
                break
            seen.add(parent_id)
            result += 1
            current = by_id.get(parent_id)
        return result

    reverse_parents: list[str] = []
    for object_id, row in by_id.items():
        layout = row.get("layout")
        layout = layout if isinstance(layout, Mapping) else {}
        if (
            str(layout.get("mode") or "none").casefold()
            not in {"horizontal", "vertical", "grid"}
            or not bool(layout.get("reverse_z_index", False))
            or len(children_by_parent.get(object_id, [])) < 2
        ):
            continue
        reverse_parents.append(object_id)

    # Inner reverse-Z containers are resolved first so an outer parent moves
    # each already-ordered descendant subtree as one indivisible block.
    reverse_parents.sort(key=depth, reverse=True)
    for parent_id in reverse_parents:
        child_groups: list[list[dict[str, Any]]] = []
        occupied_ids: set[str] = set()
        for child_id in children_by_parent.get(parent_id, []):
            child_ids = subtree_ids(child_id)
            occupied_ids.update(child_ids)
            child_groups.append(
                [
                    row
                    for row in ordered
                    if str(row.get("id") or "") in child_ids
                ]
            )
        replacement = [
            row
            for group in reversed(child_groups)
            for row in group
        ]
        slots = [
            index
            for index, row in enumerate(ordered)
            if str(row.get("id") or "") in occupied_ids
        ]
        if len(slots) != len(replacement):
            continue
        for index, row in zip(slots, replacement):
            ordered[index] = row
    return ordered


__all__ = ["apply_ui_reverse_z_paint_order"]
