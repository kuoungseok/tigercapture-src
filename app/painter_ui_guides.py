"""Shared Painter UI ruler-guide document mutations."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.painter_ui_artboard_layout import normalize_ui_artboard_layout
from app.painter_ui_document import (
    normalize_ui_document,
    update_ui_artboard,
)


def _target_artboard(
    document: Mapping[str, Any],
    artboard_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = normalize_ui_document(document)
    target = str(artboard_id or normalized["active_artboard_id"])
    row = next(
        (
            item
            for item in normalized["artboards"]
            if item["id"] == target
        ),
        None,
    )
    if row is None:
        raise ValueError(f"Painter UI artboard not found: {target}")
    return normalized, row


def add_ui_guide(
    document: Mapping[str, Any],
    *,
    orientation: str,
    position: float,
    artboard_id: str = "",
) -> dict[str, Any]:
    normalized, row = _target_artboard(document, artboard_id)
    layout = normalize_ui_artboard_layout(
        row,
        width=float(row["width"]),
        height=float(row["height"]),
    )
    guides = dict(layout["guides"])
    key = (
        "horizontal"
        if str(orientation).strip().casefold() == "horizontal"
        else "vertical"
    )
    maximum = float(row["height"] if key == "horizontal" else row["width"])
    value = max(0.0, min(maximum, float(position)))
    values = list(guides[key])
    if all(abs(value - existing) >= 0.5 for existing in values):
        values.append(value)
    guides[key] = sorted(values)
    guides["visible"] = True
    updated, _row = update_ui_artboard(
        normalized,
        row["id"],
        {"guides": guides},
    )
    return updated


def remove_ui_guide(
    document: Mapping[str, Any],
    *,
    orientation: str,
    position: float,
    artboard_id: str = "",
    tolerance: float = 0.5,
) -> dict[str, Any]:
    normalized, row = _target_artboard(document, artboard_id)
    layout = normalize_ui_artboard_layout(
        row,
        width=float(row["width"]),
        height=float(row["height"]),
    )
    guides = dict(layout["guides"])
    key = (
        "horizontal"
        if str(orientation).strip().casefold() == "horizontal"
        else "vertical"
    )
    target = float(position)
    threshold = max(0.01, float(tolerance))
    guides[key] = [
        value
        for value in guides[key]
        if abs(float(value) - target) > threshold
    ]
    updated, _row = update_ui_artboard(
        normalized,
        row["id"],
        {"guides": guides},
    )
    return updated


def clear_ui_guides(
    document: Mapping[str, Any],
    *,
    artboard_id: str = "",
    orientation: str = "",
) -> dict[str, Any]:
    normalized, row = _target_artboard(document, artboard_id)
    layout = normalize_ui_artboard_layout(
        row,
        width=float(row["width"]),
        height=float(row["height"]),
    )
    guides = dict(layout["guides"])
    requested = str(orientation or "").strip().casefold()
    if requested in {"horizontal", "vertical"}:
        guides[requested] = []
    else:
        guides["horizontal"] = []
        guides["vertical"] = []
    updated, _row = update_ui_artboard(
        normalized,
        row["id"],
        {"guides": guides},
    )
    return updated


__all__ = [
    "add_ui_guide",
    "clear_ui_guides",
    "remove_ui_guide",
]
