"""Variable-font contracts shared by Painter UI, Actions, and renderers."""
from __future__ import annotations

import copy
import math
from collections.abc import Mapping
from typing import Any


UI_VARIABLE_FONT_AXIS_DEFAULTS: dict[str, float] = {
    "wght": 400.0,
    "wdth": 100.0,
    "opsz": 14.0,
}


def normalize_ui_font_axes(value: object) -> dict[str, float]:
    """Return deterministic, valid OpenType axis tags and finite values."""
    if not isinstance(value, Mapping):
        return {}
    axes: dict[str, float] = {}
    for raw_tag, raw_value in value.items():
        tag = str(raw_tag or "").strip()
        if len(tag) != 4 or not tag.isascii() or not tag.isalnum():
            continue
        try:
            axis_value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(axis_value):
            axes[tag] = axis_value
    return dict(sorted(axes.items()))


def set_ui_variable_font_axis(
    value: Mapping[str, Any] | None,
    object_id: str,
    axis: str,
    axis_value: object,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Set one named axis through the canonical Painter object mutation."""
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        update_ui_object,
    )

    tag = str(axis or "").strip()
    normalized = normalize_ui_font_axes({tag: axis_value})
    if tag not in normalized:
        raise PainterUIDocumentError(f"Invalid OpenType variable-font axis: {axis}")
    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    if row["kind"] not in {"text", "button"}:
        raise PainterUIDocumentError("Variable-font axes require a text or button object")
    style = copy.deepcopy(dict(row.get("style") or {}))
    axes = normalize_ui_font_axes(style.get("font_axes"))
    axes[tag] = normalized[tag]
    style["font_axes"] = normalize_ui_font_axes(axes)
    return update_ui_object(document, str(object_id), {"style": style})


def reset_ui_variable_font_axis(
    value: Mapping[str, Any] | None,
    object_id: str,
    axis: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove one named axis, or all variable axes when no tag is supplied."""
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        update_ui_object,
    )

    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    if row["kind"] not in {"text", "button"}:
        raise PainterUIDocumentError("Variable-font axes require a text or button object")
    style = copy.deepcopy(dict(row.get("style") or {}))
    axes = normalize_ui_font_axes(style.get("font_axes"))
    tag = str(axis or "").strip()
    if tag:
        if len(tag) != 4 or not tag.isascii() or not tag.isalnum():
            raise PainterUIDocumentError(f"Invalid OpenType variable-font axis: {axis}")
        axes.pop(tag, None)
    else:
        axes.clear()
    if axes:
        style["font_axes"] = axes
    else:
        style.pop("font_axes", None)
    return update_ui_object(document, str(object_id), {"style": style})


def apply_ui_font_axes(font: Any, value: object) -> list[str]:
    """Apply normalized axes to a QFont and return unsupported tags."""
    from PySide6.QtGui import QFont

    invalid: list[str] = []
    for tag_name, axis_value in normalize_ui_font_axes(value).items():
        tag = QFont.Tag.fromString(tag_name)
        if not tag.isValid():
            invalid.append(tag_name)
            continue
        font.setVariableAxis(tag, axis_value)
    return invalid


__all__ = [
    "UI_VARIABLE_FONT_AXIS_DEFAULTS",
    "apply_ui_font_axes",
    "normalize_ui_font_axes",
    "reset_ui_variable_font_axis",
    "set_ui_variable_font_axis",
]
