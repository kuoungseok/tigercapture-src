"""Provider-neutral Tiger UMG Canvas-slot layout records.

The v5 layout contract separates a widget's render-transform pivot from its
``UCanvasPanelSlot`` anchors, offsets, and alignment.  The calculations here
mirror ``SConstraintCanvas::OnArrangeChildren`` so every authoring provider
serializes the same layout meaning.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


TIGER_UMG_SCHEMA_VERSION = 13
TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION = 16
TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION = 17
TIGER_UMG_PANEL_KINDS = frozenset(
    {"None", "Canvas", "Horizontal", "Vertical", "Grid", "Overlay"}
)
TIGER_UMG_WIDGET_VISIBILITIES = frozenset(
    {
        "Visible",
        "HitTestInvisible",
    }
)
_ANCHOR_EPSILON = 0.000001


def validate_umg_panel_record(
    layer: Mapping[str, Any] | None,
    *,
    document_schema_version: int,
) -> list[str]:
    """Validate one provider-neutral panel-kind record.

    ``Overlay`` is deliberately gated at schema 17.  Schemas 4-16 keep their
    existing Canvas/flow meaning, so an older producer cannot accidentally
    request a panel class its matching Unreal plugin did not generate.
    """

    source = layer if isinstance(layer, Mapping) else {}
    panel_kind = str(source.get("PanelKind") or "None")
    layer_kind = str(source.get("Kind") or "")
    if panel_kind not in TIGER_UMG_PANEL_KINDS:
        return [f"umg_panel_kind_unsupported:{panel_kind}"]
    if panel_kind not in {"None", "Canvas"} and layer_kind != "Group":
        return ["umg_panel_kind_requires_group"]
    schema_version = int(document_schema_version)
    if (
        panel_kind == "Overlay"
        and schema_version < TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION
    ):
        return ["umg_overlay_panel_requires_schema_17"]
    spacing_strategy = str(source.get("SpacingStrategy") or "Padding")
    spacer_size_rule = str(source.get("SpacerSizeRule") or "Auto")
    spacer_fill_coefficient = source.get("SpacerFillCoefficient", 1.0)
    reasons: list[str] = []
    if schema_version >= TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION:
        if layer_kind == "Group" and "SpacingStrategy" not in source:
            reasons.append("umg_spacing_strategy_record_invalid")
        if layer_kind == "Group" and "SpacerSizeRule" not in source:
            reasons.append("umg_spacer_size_rule_record_invalid")
        if layer_kind == "Group" and "SpacerFillCoefficient" not in source:
            reasons.append("umg_spacer_fill_coefficient_invalid")
    elif spacing_strategy != "Padding":
        reasons.append("umg_spacing_strategy_requires_schema_17")
    if spacing_strategy not in {"Padding", "Spacer"}:
        reasons.append("umg_spacing_strategy_unsupported")
    if spacer_size_rule not in {"Auto", "Fill"}:
        reasons.append("umg_spacer_size_rule_unsupported")
    if not (
        isinstance(spacer_fill_coefficient, (int, float))
        and not isinstance(spacer_fill_coefficient, bool)
        and math.isfinite(float(spacer_fill_coefficient))
        and float(spacer_fill_coefficient) > 0.0
    ):
        reasons.append("umg_spacer_fill_coefficient_invalid")
    if spacing_strategy == "Spacer" and panel_kind not in {
        "Horizontal",
        "Vertical",
    }:
        reasons.append("umg_spacer_strategy_requires_linear_panel")
    return sorted(set(reasons))


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _pair(
    value: object,
    default: tuple[float, float],
) -> tuple[float, float]:
    if isinstance(value, Mapping):
        return (
            _number(value.get("X", value.get("x")), default[0]),
            _number(value.get("Y", value.get("y")), default[1]),
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        rows = list(value)
        return (
            _number(rows[0], default[0]) if rows else float(default[0]),
            _number(rows[1], default[1])
            if len(rows) > 1
            else float(default[1]),
        )
    return float(default[0]), float(default[1])


def _vector(x: float, y: float) -> dict[str, float]:
    return {"X": float(x), "Y": float(y)}


def _offsets(
    value: Mapping[str, Any] | Sequence[object],
) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {
            key: _number(value.get(key, value.get(key.casefold())))
            for key in ("Left", "Top", "Right", "Bottom")
        }
    rows = list(value)
    rows.extend([0.0] * (4 - len(rows)))
    return {
        key: _number(rows[index])
        for index, key in enumerate(("Left", "Top", "Right", "Bottom"))
    }


def canvas_slot_record(
    *,
    anchor_minimum: object = (0.0, 0.0),
    anchor_maximum: object | None = None,
    offsets: Mapping[str, Any] | Sequence[object] = (0.0, 0.0, 100.0, 100.0),
    alignment: object = (0.5, 0.5),
) -> dict[str, Any]:
    """Return the serialized v5 ``UCanvasPanelSlot`` layout record."""
    minimum_x, minimum_y = _pair(anchor_minimum, (0.0, 0.0))
    maximum_x, maximum_y = _pair(
        anchor_maximum if anchor_maximum is not None else anchor_minimum,
        (minimum_x, minimum_y),
    )
    alignment_x, alignment_y = _pair(alignment, (0.5, 0.5))
    return {
        "AnchorMinimum": _vector(minimum_x, minimum_y),
        "AnchorMaximum": _vector(maximum_x, maximum_y),
        "Offsets": _offsets(offsets),
        "Alignment": _vector(alignment_x, alignment_y),
    }


def _layer_layout_fields(
    *,
    position: tuple[float, float],
    size: tuple[float, float],
    render_transform_pivot: tuple[float, float],
    canvas_slot: Mapping[str, Any],
) -> dict[str, Any]:
    pivot = _vector(*render_transform_pivot)
    return {
        # Position, Size, and Anchor remain in v5 for old document readers.
        "Position": _vector(*position),
        "Size": _vector(*size),
        "Anchor": dict(pivot),
        "RenderTransformPivot": dict(pivot),
        "CanvasSlot": dict(canvas_slot),
    }


def motion_layer_layout(
    *,
    position: object,
    size: object,
    anchor: object,
) -> dict[str, Any]:
    """Map Motion's pivot-position model to a top-left Canvas point anchor."""
    position_x, position_y = _pair(position, (0.0, 0.0))
    width, height = _pair(size, (100.0, 100.0))
    pivot_x, pivot_y = _pair(anchor, (0.5, 0.5))
    pivot_x = max(0.0, min(1.0, pivot_x))
    pivot_y = max(0.0, min(1.0, pivot_y))
    slot = canvas_slot_record(
        anchor_minimum=(0.0, 0.0),
        anchor_maximum=(0.0, 0.0),
        offsets=(position_x, position_y, width, height),
        alignment=(pivot_x, pivot_y),
    )
    return _layer_layout_fields(
        position=(position_x, position_y),
        size=(width, height),
        render_transform_pivot=(pivot_x, pivot_y),
        canvas_slot=slot,
    )


def _axis_slot(
    *,
    mode: str,
    start: float,
    size: float,
    parent_size: float,
    alignment: float,
    leading_mode: str,
    trailing_mode: str,
    anchor_minimum: float | None = None,
    anchor_maximum: float | None = None,
) -> tuple[float, float, float, float]:
    """Return minimum, maximum, leading offset, and trailing/size offset."""
    normalized_mode = str(mode or leading_mode).strip().casefold()
    parent_size = max(0.0001, float(parent_size))
    if normalized_mode == "custom":
        minimum = max(
            0.0,
            min(1.0, _number(anchor_minimum, 0.0)),
        )
        maximum = max(
            0.0,
            min(1.0, _number(anchor_maximum, minimum)),
        )
        minimum, maximum = min(minimum, maximum), max(minimum, maximum)
        if abs(maximum - minimum) <= _ANCHOR_EPSILON:
            # SConstraintCanvas uses exact inequality to choose its stretch
            # branch, so emit an exactly collapsed point anchor here.
            maximum = minimum
            return (
                minimum,
                maximum,
                start + size * alignment - minimum * parent_size,
                size,
            )
        return (
            minimum,
            maximum,
            start - minimum * parent_size,
            maximum * parent_size - start - size,
        )
    if normalized_mode == "stretch":
        return 0.0, 1.0, start, parent_size - start - size
    if normalized_mode == "scale":
        return (
            start / parent_size,
            (start + size) / parent_size,
            0.0,
            0.0,
        )
    point = {
        leading_mode: 0.0,
        "center": 0.5,
        trailing_mode: 1.0,
    }.get(normalized_mode, 0.0)
    # In UE's non-stretched branch, alignment is subtracted after the point
    # anchor and offset have been applied. Store the pivot location as Offset.
    offset = start + size * alignment - point * parent_size
    return point, point, offset, size


def painter_layer_layout(
    *,
    rect: Mapping[str, Any],
    parent_rect: Mapping[str, Any],
    constraints: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Map a resolved absolute Painter rect and constraints to Canvas layout."""
    parent_x = _number(parent_rect.get("x"))
    parent_y = _number(parent_rect.get("y"))
    parent_width = max(0.0001, _number(parent_rect.get("width"), 1.0))
    parent_height = max(0.0001, _number(parent_rect.get("height"), 1.0))
    local_x = _number(rect.get("x")) - parent_x
    local_y = _number(rect.get("y")) - parent_y
    width = max(0.0001, _number(rect.get("width"), 100.0))
    height = max(0.0001, _number(rect.get("height"), 100.0))
    source = constraints if isinstance(constraints, Mapping) else {}
    pivot_x = max(0.0, min(1.0, _number(source.get("pivot_x"), 0.5)))
    pivot_y = max(0.0, min(1.0, _number(source.get("pivot_y"), 0.5)))

    anchor_min_x, anchor_max_x, left, right = _axis_slot(
        mode=str(source.get("horizontal") or "left"),
        start=local_x,
        size=width,
        parent_size=parent_width,
        alignment=pivot_x,
        leading_mode="left",
        trailing_mode="right",
        anchor_minimum=_number(source.get("anchor_min_x"), 0.0),
        anchor_maximum=_number(source.get("anchor_max_x"), 0.0),
    )
    anchor_min_y, anchor_max_y, top, bottom = _axis_slot(
        mode=str(source.get("vertical") or "top"),
        start=local_y,
        size=height,
        parent_size=parent_height,
        alignment=pivot_y,
        leading_mode="top",
        trailing_mode="bottom",
        anchor_minimum=_number(source.get("anchor_min_y"), 0.0),
        anchor_maximum=_number(source.get("anchor_max_y"), 0.0),
    )
    slot = canvas_slot_record(
        anchor_minimum=(anchor_min_x, anchor_min_y),
        anchor_maximum=(anchor_max_x, anchor_max_y),
        offsets=(left, top, right, bottom),
        alignment=(pivot_x, pivot_y),
    )
    return _layer_layout_fields(
        position=(
            local_x + width * pivot_x,
            local_y + height * pivot_y,
        ),
        size=(width, height),
        render_transform_pivot=(pivot_x, pivot_y),
        canvas_slot=slot,
    )


def validate_umg_widget_visibility(
    value: object,
    *,
    document_schema_version: int | None = None,
) -> list[str]:
    """Validate the optional schema-16 ``ESlateVisibility`` layer value."""

    if value is None:
        if document_schema_version is not None:
            try:
                schema_version = int(document_schema_version)
            except (TypeError, ValueError):
                schema_version = 0
            if (
                schema_version
                >= TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION
            ):
                return ["umg_visibility_record_invalid"]
        return []
    if not isinstance(value, str):
        return ["umg_visibility_record_invalid"]
    if value not in TIGER_UMG_WIDGET_VISIBILITIES:
        return ["umg_visibility_unsupported"]
    if document_schema_version is not None:
        try:
            schema_version = int(document_schema_version)
        except (TypeError, ValueError):
            schema_version = 0
        if (
            value != "Visible"
            and schema_version
            < TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION
        ):
            return ["umg_visibility_requires_schema_16"]
    return []


__all__ = [
    "TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION",
    "TIGER_UMG_PANEL_KINDS",
    "TIGER_UMG_SCHEMA_VERSION",
    "TIGER_UMG_WIDGET_VISIBILITIES",
    "TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION",
    "canvas_slot_record",
    "motion_layer_layout",
    "painter_layer_layout",
    "validate_umg_panel_record",
    "validate_umg_widget_visibility",
]
