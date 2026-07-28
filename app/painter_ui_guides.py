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


def update_ui_guide(
    document: Mapping[str, Any],
    *,
    orientation: str,
    position: float,
    next_position: float,
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
    nearest = min(
        guides[key],
        key=lambda value: abs(float(value) - target),
        default=None,
    )
    if nearest is None or abs(float(nearest) - target) > threshold:
        return normalized
    maximum = float(row["height"] if key == "horizontal" else row["width"])
    replacement = max(0.0, min(maximum, float(next_position)))
    values = [
        float(value)
        for value in guides[key]
        if value != nearest
    ]
    if all(abs(replacement - value) >= 0.5 for value in values):
        values.append(replacement)
    guides[key] = sorted(values)
    updated, _row = update_ui_artboard(
        normalized,
        row["id"],
        {"guides": guides},
    )
    return updated


def set_ui_guides_visibility(
    document: Mapping[str, Any],
    *,
    visible: bool,
    artboard_id: str = "",
) -> dict[str, Any]:
    return _set_ui_guide_options(
        document,
        artboard_id=artboard_id,
        changes={"visible": bool(visible)},
    )


def set_ui_guides_locked(
    document: Mapping[str, Any],
    *,
    locked: bool,
    artboard_id: str = "",
) -> dict[str, Any]:
    return _set_ui_guide_options(
        document,
        artboard_id=artboard_id,
        changes={"locked": bool(locked)},
    )


def set_ui_ruler_origin(
    document: Mapping[str, Any],
    *,
    x: float,
    y: float,
    artboard_id: str = "",
) -> dict[str, Any]:
    return _set_ui_guide_options(
        document,
        artboard_id=artboard_id,
        changes={"origin": {"x": float(x), "y": float(y)}},
    )


def reset_ui_ruler_origin(
    document: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    return set_ui_ruler_origin(
        document,
        artboard_id=artboard_id,
        x=0.0,
        y=0.0,
    )


def _set_ui_guide_options(
    document: Mapping[str, Any],
    *,
    artboard_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    normalized, row = _target_artboard(document, artboard_id)
    layout = normalize_ui_artboard_layout(
        row,
        width=float(row["width"]),
        height=float(row["height"]),
    )
    guides = dict(layout["guides"])
    guides.update(dict(changes))
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
    "reset_ui_ruler_origin",
    "set_ui_guides_locked",
    "set_ui_guides_visibility",
    "set_ui_ruler_origin",
    "update_ui_guide",
]
