from __future__ import annotations

import operator


def catalog_index_after_active_deletion(active_index: object, *, remaining_count: object) -> int:
    active = _strict_index(active_index, field="active_index")
    remaining = _strict_index(remaining_count, field="remaining_count")
    if remaining <= 0:
        raise ValueError("Painter brush catalog must retain at least one preset")
    return max(0, min(remaining - 1, active - 1))


def moved_custom_brush_index(index: object, *, count: object, direction: object) -> int:
    current = _strict_index(index, field="index")
    size = _strict_index(count, field="count")
    delta = _strict_index(direction, field="direction")
    if size <= 0 or not 0 <= current < size:
        raise IndexError("Painter custom brush index is outside the catalog")
    if delta not in (-1, 1):
        raise ValueError("Painter custom brush direction must be -1 or 1")
    return max(0, min(size - 1, current + delta))


def _strict_index(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Painter brush {field} must be an integer, not bool")
    try:
        return operator.index(value)
    except TypeError as exc:
        raise TypeError(f"Painter brush {field} must be an integer") from exc
