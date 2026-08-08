"""Semantic QComboBox selection for Painter controls."""
from __future__ import annotations

from typing import Any


def select_combo_data(
    combo: Any,
    requested_data: object,
    *,
    fallback_data: object,
) -> bool:
    """Select by item data, using only the named fallback when missing.

    Returns whether ``requested_data`` was present. A missing fallback is a
    construction error; selecting the first visual row would silently change
    meaning when item order changes.
    """

    index = combo.findData(requested_data)
    matched = index >= 0
    if not matched:
        index = combo.findData(fallback_data)
    if index < 0:
        raise ValueError(f"combo fallback data is missing: {fallback_data!r}")
    combo.setCurrentIndex(index)
    return matched


__all__ = ["select_combo_data"]
