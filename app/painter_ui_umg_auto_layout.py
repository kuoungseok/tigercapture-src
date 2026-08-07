"""Convert Painter Auto Layout semantics to explicit Tiger UMG panel slots."""
from __future__ import annotations

from typing import Any, Mapping

from app.painter_ui_auto_layout import (
    grid_auto_layout_placements,
    normalize_ui_auto_layout,
)
from app.painter_ui_constraints import normalize_ui_constraints
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_scroll import normalize_ui_scroll


def _flow_slot(
    child: Mapping[str, Any],
    parent_layout: Mapping[str, Any],
    *,
    index: int,
    count: int,
) -> dict[str, Any]:
    mode = str(parent_layout["mode"])
    padding = dict(parent_layout["padding"])
    gap = float(parent_layout["gap"])
    child_layout = normalize_ui_auto_layout(child.get("layout"))
    cross = str(parent_layout["cross_alignment"])
    if mode == "horizontal":
        slot_padding = {
            "Left": padding["left"] if index == 0 else gap,
            "Top": padding["top"],
            "Right": padding["right"] if index == count - 1 else 0.0,
            "Bottom": padding["bottom"],
        }
        horizontal = "Fill"
        vertical = {
            "start": "Top",
            "center": "Center",
            "end": "Bottom",
            "stretch": "Fill",
        }[cross]
        fill = child_layout["width_sizing"] == "fill"
    else:
        slot_padding = {
            "Left": padding["left"],
            "Top": padding["top"] if index == 0 else gap,
            "Right": padding["right"],
            "Bottom": padding["bottom"] if index == count - 1 else 0.0,
        }
        horizontal = {
            "start": "Left",
            "center": "Center",
            "end": "Right",
            "stretch": "Fill",
        }[cross]
        vertical = "Fill"
        fill = child_layout["height_sizing"] == "fill"
    return {
        "Padding": slot_padding,
        "HorizontalAlignment": horizontal,
        "VerticalAlignment": vertical,
        "SizeRule": "Fill" if fill else "Auto",
        "FillCoefficient": 1.0,
    }


def _grid_slot(
    child: Mapping[str, Any],
    parent_layout: Mapping[str, Any],
    placement: tuple[int, int, int, int],
    *,
    row_count: int,
) -> dict[str, Any]:
    row, column, row_span, column_span = placement
    columns = int(parent_layout["grid_columns"])
    padding = dict(parent_layout["padding"])
    child_layout = normalize_ui_auto_layout(child.get("layout"))
    horizontal = {
        "start": "Left",
        "center": "Center",
        "end": "Right",
        "stretch": "Fill",
    }[str(child_layout["cell_horizontal_alignment"])]
    vertical = {
        "start": "Top",
        "center": "Center",
        "end": "Bottom",
        "stretch": "Fill",
    }[str(child_layout["cell_vertical_alignment"])]
    if child_layout["width_sizing"] == "fill":
        horizontal = "Fill"
    if child_layout["height_sizing"] == "fill":
        vertical = "Fill"
    return {
        "Padding": {
            "Left": padding["left"] if column == 0 else float(parent_layout["gap"]),
            "Top": padding["top"] if row == 0 else float(parent_layout["cross_gap"]),
            "Right": padding["right"] if column + column_span >= columns else 0.0,
            "Bottom": padding["bottom"] if row + row_span >= row_count else 0.0,
        },
        "HorizontalAlignment": horizontal,
        "VerticalAlignment": vertical,
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
        "Row": row,
        "Column": column,
        "RowSpan": row_span,
        "ColumnSpan": column_span,
    }


def _overlay_axis_slot(
    *,
    mode: str,
    start: float,
    size: float,
    parent_size: float,
    leading_alignment: str,
    trailing_alignment: str,
) -> tuple[str, float, float]:
    """Return the UOverlaySlot alignment and margins for one axis."""

    trailing = parent_size - start - size
    if mode == "stretch":
        return "Fill", start, trailing
    if mode == "center":
        # TBasicLayoutWidgetSlot centers inside the area remaining after its
        # margins.  An asymmetric doubled margin therefore preserves the
        # authored center while retaining native Center alignment semantics.
        center_delta = start + size * 0.5 - parent_size * 0.5
        return (
            "Center",
            max(0.0, center_delta * 2.0),
            max(0.0, -center_delta * 2.0),
        )
    if mode in {"right", "bottom"}:
        return trailing_alignment, 0.0, trailing
    return leading_alignment, start, 0.0


def _overlay_slot(
    child: Mapping[str, Any],
    parent: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Project authored Painter geometry to one native ``UOverlaySlot``."""

    child_x = float(child.get("x") or 0.0)
    child_y = float(child.get("y") or 0.0)
    child_width = max(0.0001, float(child.get("width") or 0.0))
    child_height = max(0.0001, float(child.get("height") or 0.0))
    parent_x = float(parent.get("x") or 0.0)
    parent_y = float(parent.get("y") or 0.0)
    parent_width = max(0.0001, float(parent.get("width") or 0.0))
    parent_height = max(0.0001, float(parent.get("height") or 0.0))
    constraints = normalize_ui_constraints(
        child.get("constraints"),
        width=child_width,
        height=child_height,
    )
    reasons: list[str] = []
    horizontal_mode = str(constraints["horizontal"])
    vertical_mode = str(constraints["vertical"])
    if horizontal_mode in {"scale", "custom"}:
        reasons.append(
            "overlay_child_horizontal_constraint_requires_canvas:"
            + str(child.get("id") or "")
            + ":"
            + horizontal_mode
        )
        horizontal_mode = "left"
    if vertical_mode in {"scale", "custom"}:
        reasons.append(
            "overlay_child_vertical_constraint_requires_canvas:"
            + str(child.get("id") or "")
            + ":"
            + vertical_mode
        )
        vertical_mode = "top"
    horizontal, left, right = _overlay_axis_slot(
        mode=horizontal_mode,
        start=child_x - parent_x,
        size=child_width,
        parent_size=parent_width,
        leading_alignment="Left",
        trailing_alignment="Right",
    )
    vertical, top, bottom = _overlay_axis_slot(
        mode=vertical_mode,
        start=child_y - parent_y,
        size=child_height,
        parent_size=parent_height,
        leading_alignment="Top",
        trailing_alignment="Bottom",
    )
    return (
        {
            "Padding": {
                "Left": left,
                "Top": top,
                "Right": right,
                "Bottom": bottom,
            },
            "HorizontalAlignment": horizontal,
            "VerticalAlignment": vertical,
            # UOverlaySlot has no size rule.  Keep the shared FlowSlot's
            # neutral defaults so one typed record remains sufficient.
            "SizeRule": "Auto",
            "FillCoefficient": 1.0,
        },
        reasons,
    )


def _overlay_slots(
    parent: Mapping[str, Any],
    child_rows: list[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return native Overlay slots and every lossy-constraint reason."""

    slots: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    for child in child_rows:
        child_id = str(child.get("id") or "")
        slot, slot_reasons = _overlay_slot(child, parent)
        slots[child_id] = slot
        reasons.extend(slot_reasons)
    return slots, sorted(set(reasons))


def painter_umg_auto_layout_contract(
    value: Mapping[str, Any] | None,
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    """Return panel types, flow slots, and explicit conversion blockers.

    Read-only, so ``normalize=False`` lets a caller with a canonical document
    skip re-deriving every row on each selection change.
    """
    document = (
        value
        if not normalize and isinstance(value, Mapping)
        else normalize_ui_document(value)
    )
    rows = list(document["objects"])
    by_id = {str(row["id"]): row for row in rows}
    children: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    for child_rows in children.values():
        child_rows.sort(key=lambda row: (int(row["z_index"]), str(row["id"])))

    panel_kind_by_id: dict[str, str] = {}
    classification_by_id: dict[str, dict[str, Any]] = {}
    spacing_strategy_by_id: dict[str, str] = {}
    spacer_size_rule_by_id: dict[str, str] = {}
    spacer_fill_coefficient_by_id: dict[str, float] = {}
    flow_slot_by_id: dict[str, dict[str, Any]] = {}
    blockers_by_id: dict[str, list[str]] = {}
    for row in rows:
        object_id = str(row["id"])
        if str(row.get("kind") or "") not in {"frame", "group"}:
            continue
        layout = normalize_ui_auto_layout(row.get("layout"))
        mode = str(layout["mode"])
        requested_panel_mode = str(layout["umg_panel_mode"])
        all_children = children.get(object_id, [])
        spacing_strategy = str(layout["umg_spacing_strategy"]).title()
        spacing_strategy_by_id[object_id] = spacing_strategy
        spacer_size_rule_by_id[object_id] = str(
            layout["umg_spacer_size_rule"]
        ).title()
        spacer_fill_coefficient_by_id[object_id] = float(
            layout["umg_spacer_fill_coefficient"]
        )
        layout_panel_kind = {
            "horizontal": "Horizontal",
            "vertical": "Vertical",
            "grid": "Grid",
            "overlay": "Overlay",
        }.get(mode)
        if layout_panel_kind is not None:
            panel_kind_by_id[object_id] = layout_panel_kind
            classification_by_id[object_id] = {
                "policy": "layout",
                "requested": requested_panel_mode,
                "effective": layout_panel_kind,
                "reasons": [f"layout_mode_requires_{mode}_panel"],
            }
        else:
            candidate_slots, candidate_reasons = _overlay_slots(
                row,
                all_children,
            )
            if requested_panel_mode == "canvas":
                effective_panel_kind = "Canvas"
                policy = "explicit"
                classification_reasons = ["explicit_canvas_panel"]
            elif requested_panel_mode == "overlay":
                effective_panel_kind = "Overlay"
                policy = "explicit"
                classification_reasons = (
                    candidate_reasons or ["explicit_overlay_panel"]
                )
            elif candidate_reasons:
                effective_panel_kind = "Canvas"
                policy = "auto"
                classification_reasons = candidate_reasons
            else:
                effective_panel_kind = "Overlay"
                policy = "auto"
                classification_reasons = [
                    "all_children_support_overlay_slots"
                ]
            panel_kind_by_id[object_id] = effective_panel_kind
            classification_by_id[object_id] = {
                "policy": policy,
                "requested": requested_panel_mode,
                "effective": effective_panel_kind,
                "reasons": classification_reasons,
            }
            if effective_panel_kind == "Overlay":
                flow_slot_by_id.update(candidate_slots)
                if candidate_reasons:
                    blockers_by_id[object_id] = candidate_reasons
        if mode not in {"horizontal", "vertical", "grid", "overlay"}:
            if spacing_strategy != "Padding":
                blockers_by_id.setdefault(object_id, []).append(
                    "umg_spacer_strategy_requires_linear_panel"
                )
                blockers_by_id[object_id] = sorted(
                    set(blockers_by_id[object_id])
                )
            continue
        reasons: list[str] = []
        if mode == "overlay":
            if spacing_strategy != "Padding":
                reasons.append("umg_overlay_spacing_strategy_unsupported")
            if bool(layout.get("reverse_z_index", False)):
                reasons.append(
                    "overlay_reverse_z_index_requires_document_child_reorder"
                )
            overlay_slots, overlay_reasons = _overlay_slots(
                row,
                all_children,
            )
            flow_slot_by_id.update(overlay_slots)
            reasons.extend(overlay_reasons)
            if reasons:
                blockers_by_id[object_id] = sorted(set(reasons))
            continue
        if mode == "grid" and spacing_strategy == "Spacer":
            reasons.append("umg_spacer_strategy_requires_linear_panel")
        if (
            mode in {"horizontal", "vertical"}
            and spacing_strategy == "Spacer"
            and float(layout["gap"]) < 0.0
        ):
            reasons.append("umg_spacer_size_must_be_nonnegative")
        if bool(layout.get("reverse_z_index", False)):
            # Horizontal/Vertical/Grid panels couple child order to both
            # flow and paint order. Figma reverses paint stacking only, so a
            # layered panel path is required before this can be native UMG.
            reasons.append(
                "auto_layout_reverse_z_index_requires_overlay_stack_support"
            )
        if bool(layout.get("include_strokes", False)):
            # UMG panel slots do not include a widget's outside/center brush
            # stroke in their desired size.  Keep this explicit until the
            # shared backend can add deterministic stroke-footprint spacers.
            reasons.append(
                "auto_layout_strokes_included_requires_"
                "deterministic_bake_or_slot_spacers"
            )
        if mode != "grid" and bool(layout["wrap"]):
            reasons.append("auto_layout_wrap_requires_umg_wrap_panel")
        if mode != "grid" and str(layout["main_alignment"]) != "start":
            reasons.append(
                "auto_layout_main_alignment_unsupported:"
                + str(layout["main_alignment"])
            )
        if mode != "grid" and str(layout["cross_alignment"]) == "baseline":
            # Horizontal/Vertical Box slots expose edge, center, and fill
            # alignment but no shared typographic baseline metric.  Keep the
            # imported Figma semantic explicit until TigerStudioUMG has a
            # deterministic baseline-aware panel or bake path.
            reasons.append(
                "auto_layout_cross_alignment_unsupported:baseline"
            )
        flow_children = [
            child
            for child in all_children
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            != "absolute"
        ]
        absolute_children = [
            str(child["id"])
            for child in all_children
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            == "absolute"
            and normalize_ui_scroll(child.get("scroll"))["position"]
            != "fixed"
        ]
        reasons.extend(
            f"auto_layout_absolute_child_unsupported:{child_id}"
            for child_id in absolute_children
        )
        if reasons:
            blockers_by_id[object_id] = sorted(set(reasons))
            continue
        if mode == "grid":
            placements, row_count = grid_auto_layout_placements(
                flow_children,
                int(layout["grid_columns"]),
            )
            for child in flow_children:
                child_id = str(child["id"])
                flow_slot_by_id[child_id] = _grid_slot(
                    child,
                    layout,
                    placements[child_id],
                    row_count=row_count,
                )
        else:
            for index, child in enumerate(flow_children):
                flow_slot_by_id[str(child["id"])] = _flow_slot(
                    child,
                    layout,
                    index=index,
                    count=len(flow_children),
                )
    return {
        "schema": "tigerstudio.painter.umg.auto_layout.v1",
        "panel_kind_by_id": panel_kind_by_id,
        "classification_by_id": classification_by_id,
        "spacing_strategy_by_id": spacing_strategy_by_id,
        "spacer_size_rule_by_id": spacer_size_rule_by_id,
        "spacer_fill_coefficient_by_id": spacer_fill_coefficient_by_id,
        "flow_slot_by_id": flow_slot_by_id,
        "blockers_by_id": blockers_by_id,
        "converted_panel_ids": sorted(
            object_id
            for object_id, panel_kind in panel_kind_by_id.items()
            if panel_kind in {"Horizontal", "Vertical", "Grid", "Overlay"}
            and object_id not in blockers_by_id
        ),
        "object_count": len(by_id),
    }


__all__ = ["painter_umg_auto_layout_contract"]
