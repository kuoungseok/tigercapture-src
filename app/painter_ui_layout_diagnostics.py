"""Deterministic diagnostics for Painter UI layout contracts."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.painter_ui_artboard_layout import normalize_ui_artboard_layout
from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_constraints import normalize_ui_constraints
from app.painter_ui_scroll import inspect_ui_scroll, normalize_ui_scroll

# Several panels each ask for the whole document's diagnostics and then filter
# the result down to one artboard or object, so a single canvas refresh solved
# the same report more than once. The resolved theme document is itself cached
# and shared, so its identity is a sound key: the same resolved object always
# yields the same diagnostics. Strong references keep the ids from being reused.
_LAST_RESOLVED: dict[str, Any] | None = None
_LAST_REPORT: dict[str, Any] | None = None


def _diagnostic(
    severity: str,
    code: str,
    owner_id: str,
    message: str,
    *,
    axis: str = "",
    related_id: str = "",
) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "owner_id": owner_id,
        "axis": axis,
        "related_id": related_id,
        "message": message,
    }


def diagnose_ui_layout(
    document: Mapping[str, Any],
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    from app.painter_ui_themes import resolve_ui_theme_document

    # Diagnostics only read the resolved document and never touch selection or
    # revision, so they can share the cached resolution instead of cloning it.
    document = resolve_ui_theme_document(
        document,
        normalize=normalize,
        shared=True,
    )
    global _LAST_RESOLVED, _LAST_REPORT
    if document is _LAST_RESOLVED and _LAST_REPORT is not None:
        return _LAST_REPORT
    diagnostics: list[dict[str, str]] = []
    objects = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    children: dict[str, list[Mapping[str, Any]]] = {}
    for row in objects.values():
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)

    for artboard in document.get("artboards", []):
        if not isinstance(artboard, Mapping):
            continue
        artboard_id = str(artboard.get("id") or "")
        width = float(artboard.get("width") or 1.0)
        height = float(artboard.get("height") or 1.0)
        layout = normalize_ui_artboard_layout(
            artboard,
            width=width,
            height=height,
        )
        safe = layout["safe_area"]
        if safe["left"] + safe["right"] >= width:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "artboard_safe_area_collapsed",
                    artboard_id,
                    "Left and right safe-area insets leave no usable width.",
                    axis="width",
                )
            )
        if safe["top"] + safe["bottom"] >= height:
            diagnostics.append(
                _diagnostic(
                    "error",
                    "artboard_safe_area_collapsed",
                    artboard_id,
                    "Top and bottom safe-area insets leave no usable height.",
                    axis="height",
                )
            )
        grid = layout["layout_grid"]
        if grid["mode"] == "columns":
            reserved = (
                float(grid["margin"]) * 2.0
                + float(grid["gutter"]) * max(0, int(grid["count"]) - 1)
            )
            if reserved >= width:
                diagnostics.append(
                    _diagnostic(
                        "error",
                        "artboard_columns_collapsed",
                        artboard_id,
                        "Column margins and gutters leave no positive column width.",
                        axis="width",
                    )
                )

    for row in objects.values():
        object_id = str(row["id"])
        constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=float(row.get("width") or 1.0),
            height=float(row.get("height") or 1.0),
        )
        for axis in ("width", "height"):
            minimum = float(constraints[f"min_{axis}"])
            maximum = float(constraints[f"max_{axis}"])
            if maximum > 0.0 and minimum > maximum:
                diagnostics.append(
                    _diagnostic(
                        "error",
                        "constraint_min_exceeds_max",
                        object_id,
                        f"Minimum {axis} exceeds maximum {axis}.",
                        axis=axis,
                    )
                )

        scroll_report = inspect_ui_scroll(
            document,
            object_id,
            object_index=objects,
        )
        for reason in scroll_report["reasons"]:
            diagnostics.append(
                _diagnostic(
                    "error",
                    reason,
                    object_id,
                    {
                        "scroll_overflow_requires_frame": (
                            "Overflow scrolling is available only on frames."
                        ),
                        "scroll_overflow_requires_clip_content": (
                            "Enable Clip content before using overflow scrolling."
                        ),
                        "scroll_position_requires_scrollable_parent": (
                            "Fixed and sticky objects require a scrollable parent frame."
                        ),
                        "sticky_requires_vertical_overflow": (
                            "Sticky positioning requires vertical parent overflow."
                        ),
                        "fixed_in_auto_layout_requires_ignore_auto_layout": (
                            "A fixed Auto Layout child must Ignore auto layout."
                        ),
                    }.get(reason, reason.replace("_", " ").capitalize()),
                )
            )
        scroll = normalize_ui_scroll(row.get("scroll"))
        if scroll["overflow"] != "none":
            frame_left = float(row.get("x") or 0.0)
            frame_top = float(row.get("y") or 0.0)
            frame_right = frame_left + float(row.get("width") or 1.0)
            frame_bottom = frame_top + float(row.get("height") or 1.0)
            direct_children = children.get(object_id, [])
            horizontal_overflow = any(
                float(child.get("x") or 0.0) < frame_left
                or float(child.get("x") or 0.0)
                + float(child.get("width") or 1.0)
                > frame_right
                for child in direct_children
            )
            vertical_overflow = any(
                float(child.get("y") or 0.0) < frame_top
                or float(child.get("y") or 0.0)
                + float(child.get("height") or 1.0)
                > frame_bottom
                for child in direct_children
            )
            needs_horizontal = scroll["overflow"] in {"horizontal", "both"}
            needs_vertical = scroll["overflow"] in {"vertical", "both"}
            if (
                (needs_horizontal and not horizontal_overflow)
                or (needs_vertical and not vertical_overflow)
            ):
                diagnostics.append(
                    _diagnostic(
                        "warning",
                        "scroll_overflow_has_no_overflow_content",
                        object_id,
                        "The selected scroll axis has no content beyond the frame bounds.",
                    )
                )

        layout = normalize_ui_auto_layout(row.get("layout"))
        mode = layout["mode"]
        if mode not in {"horizontal", "vertical", "grid"}:
            continue
        if mode == "grid":
            continue
        main_axis = "width" if mode == "horizontal" else "height"
        padding = layout["padding"]
        available = float(row.get(main_axis) or 1.0) - (
            padding["left"] + padding["right"]
            if main_axis == "width"
            else padding["top"] + padding["bottom"]
        )
        flow_children = [
            child
            for child in children.get(object_id, [])
            if normalize_ui_auto_layout(child.get("layout"))["positioning"]
            != "absolute"
        ]
        if layout["wrap"] and layout[f"{main_axis}_sizing"] == "hug":
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "wrap_ignored_on_hug_axis",
                    object_id,
                    "Wrap is ignored when the container hugs its main axis.",
                    axis=main_axis,
                )
            )
        for child in flow_children:
            child_id = str(child["id"])
            child_layout = normalize_ui_auto_layout(child.get("layout"))
            for axis in ("width", "height"):
                if (
                    layout[f"{axis}_sizing"] == "hug"
                    and child_layout[f"{axis}_sizing"] == "fill"
                ):
                    diagnostics.append(
                        _diagnostic(
                            "error",
                            "layout_hug_fill_cycle",
                            object_id,
                            "A Fill child cannot determine the size of a Hug parent.",
                            axis=axis,
                            related_id=child_id,
                        )
                    )
        if flow_children and available <= 0.0:
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "auto_layout_no_content_space",
                    object_id,
                    "Padding leaves no content space on the main axis.",
                    axis=main_axis,
                )
            )
            continue
        fixed_total = 0.0
        for child in flow_children:
            child_layout = normalize_ui_auto_layout(child.get("layout"))
            if child_layout[f"{main_axis}_sizing"] != "fill":
                fixed_total += float(child.get(main_axis) or 1.0)
        fixed_total += float(layout["gap"]) * max(0, len(flow_children) - 1)
        if (
            flow_children
            and not layout["wrap"]
            and fixed_total > max(0.0, available) + 0.001
        ):
            diagnostics.append(
                _diagnostic(
                    "warning",
                    "auto_layout_fixed_overflow",
                    object_id,
                    "Fixed children and gaps exceed the available main-axis space.",
                    axis=main_axis,
                )
            )

    diagnostics.sort(
        key=lambda row: (
            row["severity"] != "error",
            row["owner_id"],
            row["code"],
            row["axis"],
            row["related_id"],
        )
    )
    errors = [
        f"{row['code']}:{row['owner_id']}"
        + (f":{row['axis']}" if row["axis"] else "")
        + (f":{row['related_id']}" if row["related_id"] else "")
        for row in diagnostics
        if row["severity"] == "error"
    ]
    warnings = [
        f"{row['code']}:{row['owner_id']}"
        + (f":{row['axis']}" if row["axis"] else "")
        for row in diagnostics
        if row["severity"] == "warning"
    ]
    report = {
        "schema": "tigerstudio.painter.ui.layout_diagnostics.v1",
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
    }
    _LAST_RESOLVED = document
    _LAST_REPORT = report
    return report


__all__ = ["diagnose_ui_layout"]
