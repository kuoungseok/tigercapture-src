"""Deterministic Auto Layout rules shared by Painter UI surfaces."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from app.painter_ui_json_copy import json_deepcopy


_MODES = {"none", "horizontal", "vertical", "grid", "overlay"}
_MAIN_ALIGNMENTS = {"start", "center", "end", "space_between"}
_CROSS_ALIGNMENTS = {"start", "center", "end", "stretch", "baseline"}
_POSITIONING = {"auto", "absolute"}
_SIZING_MODES = {"fixed", "hug", "fill"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _padding(value: Any) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {
            edge: max(0.0, _number(value.get(edge)))
            for edge in ("left", "top", "right", "bottom")
        }
    if isinstance(value, (list, tuple)):
        values = [_number(item) for item in value]
        if len(values) >= 4:
            left, top, right, bottom = values[:4]
        elif len(values) >= 2:
            left = right = values[0]
            top = bottom = values[1]
        elif values:
            left = top = right = bottom = values[0]
        else:
            left = top = right = bottom = 0.0
        return {
            "left": max(0.0, left),
            "top": max(0.0, top),
            "right": max(0.0, right),
            "bottom": max(0.0, bottom),
        }
    amount = max(0.0, _number(value))
    return {edge: amount for edge in ("left", "top", "right", "bottom")}


def _zero_edges() -> dict[str, float]:
    return {edge: 0.0 for edge in ("left", "top", "right", "bottom")}


def _effective_padding(layout: Mapping[str, Any]) -> dict[str, float]:
    """Return authored padding plus any Figma layout stroke inset.

    Figma's ``strokesIncludedInLayout`` makes a visible inside/center stroke
    part of the container's content inset.  The importer records the exact
    per-edge inset instead of making the generic solver infer paint state.
    """

    padding = _padding(layout.get("padding"))
    if not bool(layout.get("include_strokes", False)):
        return padding
    insets = _padding(layout.get("stroke_insets"))
    return {
        edge: padding[edge] + insets[edge]
        for edge in ("left", "top", "right", "bottom")
    }


def _child_stroke_outsets(
    child: Mapping[str, Any],
    *,
    include_strokes: bool,
) -> dict[str, float]:
    if not include_strokes:
        return _zero_edges()
    layout = ui_auto_layout_view(child.get("layout"))
    return _padding(layout.get("stroke_outsets"))


def _axis_outsets(
    child: Mapping[str, Any],
    *,
    axis: str,
    include_strokes: bool,
) -> tuple[float, float]:
    outsets = _child_stroke_outsets(
        child,
        include_strokes=include_strokes,
    )
    if axis == "width":
        return outsets["left"], outsets["right"]
    return outsets["top"], outsets["bottom"]


def _axis_footprint_size(
    child: Mapping[str, Any],
    rect: Mapping[str, float],
    *,
    axis: str,
    include_strokes: bool,
) -> float:
    leading, trailing = _axis_outsets(
        child,
        axis=axis,
        include_strokes=include_strokes,
    )
    return float(rect[axis]) + leading + trailing


def normalize_ui_auto_layout(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = json_deepcopy(dict(value or {}))
    mode = str(
        source.get("mode")
        or source.get("direction")
        or source.get("type")
        or "none"
    ).strip().casefold()
    mode = {
        "row": "horizontal",
        "auto_horizontal": "horizontal",
        "column": "vertical",
        "auto_vertical": "vertical",
    }.get(mode, mode)
    main_alignment = str(
        source.get("main_alignment")
        or source.get("justify")
        or "start"
    ).strip().casefold()
    cross_alignment = str(
        source.get("cross_alignment")
        or source.get("align")
        or "start"
    ).strip().casefold()
    positioning = str(
        source.get("positioning")
        or source.get("position")
        or "auto"
    ).strip().casefold()
    width_sizing = str(
        source.get("width_sizing")
        or source.get("horizontal_sizing")
        or "fixed"
    ).strip().casefold()
    height_sizing = str(
        source.get("height_sizing")
        or source.get("vertical_sizing")
        or "fixed"
    ).strip().casefold()
    source.update(
        {
            "mode": mode if mode in _MODES else "none",
            "padding": _padding(source.get("padding")),
            # Figma/Slate both support negative main-axis spacing for
            # deliberately overlapped stacks. Cross-track spacing remains
            # non-negative below.
            "gap": _number(source.get("gap")),
            "cross_gap": max(
                0.0,
                _number(
                    source.get("cross_gap"),
                    _number(source.get("gap")),
                ),
            ),
            "main_alignment": (
                main_alignment
                if main_alignment in _MAIN_ALIGNMENTS
                else "start"
            ),
            "cross_alignment": (
                cross_alignment
                if cross_alignment in _CROSS_ALIGNMENTS
                else "start"
            ),
            "positioning": (
                positioning if positioning in _POSITIONING else "auto"
            ),
            "wrap": bool(source.get("wrap", False)),
            "width_sizing": (
                width_sizing if width_sizing in _SIZING_MODES else "fixed"
            ),
            "height_sizing": (
                height_sizing if height_sizing in _SIZING_MODES else "fixed"
            ),
            "grid_columns": max(1, int(_number(source.get("grid_columns"), 2))),
            "grid_column_span": max(
                1, int(_number(source.get("grid_column_span"), 1))
            ),
            "grid_row_span": max(
                1, int(_number(source.get("grid_row_span"), 1))
            ),
            "cell_horizontal_alignment": (
                str(source.get("cell_horizontal_alignment") or "stretch")
                .strip()
                .casefold()
                if str(source.get("cell_horizontal_alignment") or "stretch")
                .strip()
                .casefold()
                in {"start", "center", "end", "stretch"}
                else "stretch"
            ),
            "cell_vertical_alignment": (
                str(source.get("cell_vertical_alignment") or "stretch")
                .strip()
                .casefold()
                if str(source.get("cell_vertical_alignment") or "stretch")
                .strip()
                .casefold()
                in {"start", "center", "end", "stretch"}
                else "stretch"
            ),
        }
    )
    for legacy_key in (
        "direction",
        "type",
        "justify",
        "align",
        "position",
        "horizontal_sizing",
        "vertical_sizing",
    ):
        source.pop(legacy_key, None)
    if "reverse_z_index" in source:
        # This changes only overlapping-child paint order. It must never be
        # used to reverse Auto Layout flow iteration.
        source["reverse_z_index"] = bool(source["reverse_z_index"])
    if "baseline_offset" in source:
        # Distance from this child's top edge to the baseline used by its
        # horizontal Auto Layout parent.  Figma REST/archive payloads do not
        # expose font ascent directly, so the importer derives this value
        # from Figma's already-resolved sibling geometry.
        source["baseline_offset"] = max(
            0.0,
            _number(source.get("baseline_offset")),
        )
    return source


_CANONICAL_LAYOUT_KEYS = frozenset(
    {
        "mode",
        "padding",
        "gap",
        "cross_gap",
        "main_alignment",
        "cross_alignment",
        "positioning",
        "wrap",
        "width_sizing",
        "height_sizing",
        "grid_columns",
        "grid_column_span",
        "grid_row_span",
        "cell_horizontal_alignment",
        "cell_vertical_alignment",
    }
)
_LEGACY_LAYOUT_KEYS = frozenset(
    {
        "direction",
        "type",
        "justify",
        "align",
        "position",
        "horizontal_sizing",
        "vertical_sizing",
    }
)


def ui_auto_layout_view(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a read-only canonical view of a layout mapping.

    ``normalize_ui_auto_layout`` deep copies its input and re-derives every
    field. For rows that came out of ``_normalize_object`` the layout is
    already canonical, so all of that is pure overhead — and on a large
    imported document it is most of the per-edit cost. This returns such
    mappings untouched and only falls back to normalizing when the input is
    not already canonical.

    The returned mapping MUST NOT be mutated: for canonical input it *is* the
    row's own layout mapping. Callers that mutate the result have to keep
    using ``normalize_ui_auto_layout``.
    """
    if type(value) is dict:
        keys = value.keys()
        if (
            keys >= _CANONICAL_LAYOUT_KEYS
            and keys.isdisjoint(_LEGACY_LAYOUT_KEYS)
            and value["mode"] in _MODES
            and value["positioning"] in _POSITIONING
            and value["main_alignment"] in _MAIN_ALIGNMENTS
            and value["cross_alignment"] in _CROSS_ALIGNMENTS
            and value["width_sizing"] in _SIZING_MODES
            and value["height_sizing"] in _SIZING_MODES
            and type(value["padding"]) is dict
        ):
            return value
    return normalize_ui_auto_layout(value)


def grid_auto_layout_placements(
    rows: list[Mapping[str, Any]],
    columns: int,
) -> tuple[dict[str, tuple[int, int, int, int]], int]:
    columns = max(1, int(columns))
    occupied: set[tuple[int, int]] = set()
    result: dict[str, tuple[int, int, int, int]] = {}
    cursor_row = 0
    cursor_column = 0
    for child in rows:
        layout = ui_auto_layout_view(child.get("layout"))
        column_span = min(columns, max(1, int(layout["grid_column_span"])))
        row_span = max(1, int(layout["grid_row_span"]))
        while True:
            if cursor_column + column_span > columns:
                cursor_row += 1
                cursor_column = 0
                continue
            cells = {
                (row_index, column_index)
                for row_index in range(cursor_row, cursor_row + row_span)
                for column_index in range(
                    cursor_column,
                    cursor_column + column_span,
                )
            }
            if not cells.intersection(occupied):
                occupied.update(cells)
                result[str(child["id"])] = (
                    cursor_row,
                    cursor_column,
                    row_span,
                    column_span,
                )
                cursor_column += column_span
                break
            cursor_column += 1
            if cursor_column >= columns:
                cursor_row += 1
                cursor_column = 0
    row_count = max((row + span for row, _col, span, _cspan in result.values()), default=0)
    return result, row_count


def _bounded_axis_size(
    value: float,
    constraints: Mapping[str, Any] | None,
    *,
    axis: str,
) -> float:
    row = constraints if isinstance(constraints, Mapping) else {}
    minimum = max(1.0, _number(row.get(f"min_{axis}"), 1.0))
    maximum = max(0.0, _number(row.get(f"max_{axis}"), 0.0))
    result = max(1.0, value)
    result = max(minimum, result)
    return min(maximum, result) if maximum > 0.0 else result


def _main_axis_plan(
    sizes: list[float],
    available: float,
    gap: float,
    alignment: str,
) -> tuple[float, float]:
    if not sizes:
        return 0.0, gap
    total_without_gap = sum(sizes)
    total = total_without_gap + gap * max(0, len(sizes) - 1)
    # Figma keeps CENTER/END alignment centered on the authored content box
    # even when children or padding overflow a fixed-size parent.  The free
    # space is therefore allowed to be negative; clamping it to zero shifts
    # compressed components toward the leading padding edge.
    remaining = available - total
    if alignment == "center":
        return remaining * 0.5, gap
    if alignment == "end":
        return remaining, gap
    if alignment == "space_between" and len(sizes) > 1:
        distributed = (
            available - total_without_gap
        ) / (len(sizes) - 1)
        # Figma's SPACE_BETWEEN still fits both edge children when their
        # combined desired size exceeds the content box.  In that overflow
        # case the effective spacing becomes negative (intentional overlap)
        # instead of being clamped back to the authored non-negative gap.
        # When there is spare room, retain the authored gap as a minimum.
        if distributed >= 0.0:
            distributed = max(gap, distributed)
        return 0.0, distributed
    return 0.0, gap


def _baseline_line_plan(
    line: list[Mapping[str, Any]],
    resolved: Mapping[str, Mapping[str, float]],
    *,
    cross_axis: str,
    include_strokes: bool,
) -> tuple[float, float]:
    """Return the baseline position and cross footprint for one flow line.

    ``baseline_offset`` is measured from the widget's own top/left edge.  A
    child's optional stroke outsets are folded into the line metric while the
    returned baseline remains relative to the line's footprint origin.
    Widgets without an authored/imported baseline use their trailing edge,
    matching the conventional baseline fallback for non-text boxes.
    """

    metrics: list[tuple[float, float]] = []
    for child in line:
        rect = resolved[str(child["id"])]
        leading, trailing = _axis_outsets(
            child,
            axis=cross_axis,
            include_strokes=include_strokes,
        )
        footprint = leading + float(rect[cross_axis]) + trailing
        child_layout = ui_auto_layout_view(child.get("layout"))
        baseline = leading + _number(
            child_layout.get("baseline_offset"),
            float(rect[cross_axis]),
        )
        baseline = min(footprint, max(0.0, baseline))
        metrics.append((baseline, footprint - baseline))
    if not metrics:
        return 0.0, 0.0
    baseline = max(item[0] for item in metrics)
    descent = max(item[1] for item in metrics)
    return baseline, baseline + descent


def _flow_lines(
    rows: list[Mapping[str, Any]],
    resolved: Mapping[str, Mapping[str, float]],
    *,
    mode: str,
    available: float,
    gap: float,
    wrap: bool,
    include_strokes: bool = False,
) -> list[list[Mapping[str, Any]]]:
    if not rows:
        return []
    if not wrap or available <= 0.0:
        return [rows]
    axis = "width" if mode == "horizontal" else "height"
    lines: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    used = 0.0
    for row in rows:
        size = _axis_footprint_size(
            row,
            resolved[str(row["id"])],
            axis=axis,
            include_strokes=include_strokes,
        )
        candidate = size if not current else used + gap + size
        if current and candidate > available:
            lines.append(current)
            current = [row]
            used = size
        else:
            current.append(row)
            used = candidate
    if current:
        lines.append(current)
    return lines


def _line_content_size(
    line: list[Mapping[str, Any]],
    resolved: Mapping[str, Mapping[str, float]],
    *,
    mode: str,
    gap: float,
    cross_alignment: str = "start",
    include_strokes: bool = False,
) -> tuple[float, float]:
    if not line:
        return 0.0, 0.0
    main_axis = "width" if mode == "horizontal" else "height"
    cross_axis = "height" if mode == "horizontal" else "width"
    main = sum(
        _axis_footprint_size(
            row,
            resolved[str(row["id"])],
            axis=main_axis,
            include_strokes=include_strokes,
        )
        for row in line
    )
    main += gap * max(0, len(line) - 1)
    if mode == "horizontal" and cross_alignment == "baseline":
        _baseline, cross = _baseline_line_plan(
            line,
            resolved,
            cross_axis=cross_axis,
            include_strokes=include_strokes,
        )
    else:
        cross = max(
            _axis_footprint_size(
                row,
                resolved[str(row["id"])],
                axis=cross_axis,
                include_strokes=include_strokes,
            )
            for row in line
        )
    return main, cross


def _distribute_fill_sizes(
    rows: list[Mapping[str, Any]],
    available: float,
    *,
    axis: str,
) -> dict[str, float]:
    """Distribute flex space while honoring per-child min/max constraints."""
    pending = list(rows)
    remaining = max(0.0, float(available))
    result: dict[str, float] = {}
    while pending:
        share = remaining / len(pending)
        clamped: list[tuple[Mapping[str, Any], float]] = []
        for row in pending:
            size = _bounded_axis_size(share, row.get("constraints"), axis=axis)
            if abs(size - share) > 0.001:
                clamped.append((row, size))
        if not clamped:
            for row in pending:
                result[str(row["id"])] = share
            break
        clamped_ids = {str(row["id"]) for row, _size in clamped}
        for row, size in clamped:
            result[str(row["id"])] = size
            remaining -= size
        remaining = max(0.0, remaining)
        pending = [row for row in pending if str(row["id"]) not in clamped_ids]
    return result


def resolve_ui_auto_layout(
    document: Mapping[str, Any],
    geometry: Mapping[str, Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    objects = {
        str(row["id"]): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and row.get("id")
    }
    resolved = {
        object_id: {
            key: float(geometry.get(object_id, row)[key])
            for key in ("x", "y", "width", "height")
        }
        for object_id, row in objects.items()
    }
    children: dict[str, list[Mapping[str, Any]]] = {}
    for index, row in enumerate(document.get("objects", [])):
        if not isinstance(row, Mapping) or str(row.get("id") or "") not in objects:
            continue
        child = dict(row)
        child["_document_order"] = index
        children.setdefault(str(row.get("parent_id") or ""), []).append(child)
    for rows in children.values():
        rows.sort(
            key=lambda row: (
                int(_number(row.get("z_index"))),
                int(row["_document_order"]),
                str(row["id"]),
            )
        )

    roots = [row for row in objects.values() if not str(row.get("parent_id") or "")]
    measured: set[str] = set()
    effective_visibility: dict[str, bool] = {}

    def is_effectively_visible(
        object_id: str,
        stack: tuple[str, ...] = (),
    ) -> bool:
        cached = effective_visibility.get(object_id)
        if cached is not None:
            return cached
        row = objects.get(object_id)
        if row is None or object_id in stack:
            return True
        if not bool(row.get("visible", True)):
            effective_visibility[object_id] = False
            return False
        parent_id = str(row.get("parent_id") or "")
        visible = (
            is_effectively_visible(parent_id, (*stack, object_id))
            if parent_id in objects
            else True
        )
        effective_visibility[object_id] = visible
        return visible

    def flow_children(parent_id: str) -> list[Mapping[str, Any]]:
        return [
            child
            for child in children.get(parent_id, [])
            if bool(child.get("visible", True))
            and ui_auto_layout_view(child.get("layout"))["positioning"]
            != "absolute"
        ]

    def measure(object_id: str, stack: tuple[str, ...] = ()) -> None:
        if object_id in measured or object_id in stack:
            return
        row = objects.get(object_id)
        rect = resolved.get(object_id)
        if row is None or rect is None:
            return
        if not is_effectively_visible(object_id):
            # A hidden Figma layer is excluded from rendering and from its
            # parent's flow. Preserve the imported snapshot for its complete
            # subtree instead of re-running stale component Auto Layout data.
            measured.add(object_id)
            return
        for child in children.get(object_id, []):
            measure(str(child["id"]), (*stack, object_id))
        layout = ui_auto_layout_view(row.get("layout"))
        mode = layout["mode"]
        rows = flow_children(object_id)
        if mode == "grid" and rows:
            padding = _effective_padding(layout)
            columns = int(layout["grid_columns"])
            placements, row_count = grid_auto_layout_placements(rows, columns)
            column_widths = [0.0] * columns
            row_heights = [0.0] * row_count
            for child in rows:
                child_id = str(child["id"])
                row_index, column_index, row_span, column_span = placements[child_id]
                share_width = resolved[child_id]["width"] / column_span
                share_height = resolved[child_id]["height"] / row_span
                for index in range(column_index, column_index + column_span):
                    column_widths[index] = max(column_widths[index], share_width)
                for index in range(row_index, row_index + row_span):
                    row_heights[index] = max(row_heights[index], share_height)
            desired_width = sum(column_widths) + layout["gap"] * max(0, columns - 1)
            desired_height = sum(row_heights) + layout["cross_gap"] * max(0, row_count - 1)
            if layout["width_sizing"] == "hug":
                rect["width"] = _bounded_axis_size(
                    desired_width + padding["left"] + padding["right"],
                    row.get("constraints"),
                    axis="width",
                )
            if layout["height_sizing"] == "hug":
                rect["height"] = _bounded_axis_size(
                    desired_height + padding["top"] + padding["bottom"],
                    row.get("constraints"),
                    axis="height",
                )
        elif mode in {"horizontal", "vertical"} and rows:
            padding = _effective_padding(layout)
            include_strokes = bool(layout.get("include_strokes", False))
            main_axis = "width" if mode == "horizontal" else "height"
            cross_axis = "height" if mode == "horizontal" else "width"
            main_padding = (
                padding["left"] + padding["right"]
                if mode == "horizontal"
                else padding["top"] + padding["bottom"]
            )
            cross_padding = (
                padding["top"] + padding["bottom"]
                if mode == "horizontal"
                else padding["left"] + padding["right"]
            )
            available = max(0.0, rect[main_axis] - main_padding)
            wrap = bool(layout["wrap"]) and layout[f"{main_axis}_sizing"] != "hug"
            lines = _flow_lines(
                rows,
                resolved,
                mode=mode,
                available=available,
                gap=layout["gap"],
                wrap=wrap,
                include_strokes=include_strokes,
            )
            line_sizes = [
                _line_content_size(
                    line,
                    resolved,
                    mode=mode,
                    gap=layout["gap"],
                    cross_alignment=layout["cross_alignment"],
                    include_strokes=include_strokes,
                )
                for line in lines
            ]
            desired_main = max((size[0] for size in line_sizes), default=0.0)
            desired_cross = sum(size[1] for size in line_sizes)
            desired_cross += layout["cross_gap"] * max(0, len(line_sizes) - 1)
            if layout[f"{main_axis}_sizing"] == "hug":
                rect[main_axis] = _bounded_axis_size(
                    desired_main + main_padding,
                    row.get("constraints"),
                    axis=main_axis,
                )
            if layout[f"{cross_axis}_sizing"] == "hug":
                rect[cross_axis] = _bounded_axis_size(
                    desired_cross + cross_padding,
                    row.get("constraints"),
                    axis=cross_axis,
                )
        measured.add(object_id)

    for root in roots:
        measure(str(root["id"]))
    for object_id in objects:
        measure(object_id)

    placed: set[str] = set()

    def place(parent_id: str, stack: tuple[str, ...] = ()) -> None:
        if parent_id in placed or parent_id in stack:
            return
        parent = objects.get(parent_id)
        parent_rect = resolved.get(parent_id)
        if parent is None or parent_rect is None:
            return
        if not is_effectively_visible(parent_id):
            placed.add(parent_id)
            return
        layout = ui_auto_layout_view(parent.get("layout"))
        mode = layout["mode"]
        rows = flow_children(parent_id)
        if mode == "grid" and rows:
            padding = _effective_padding(layout)
            columns = int(layout["grid_columns"])
            placements, row_count = grid_auto_layout_placements(rows, columns)
            content_x = parent_rect["x"] + padding["left"]
            content_y = parent_rect["y"] + padding["top"]
            content_width = max(
                0.0,
                parent_rect["width"] - padding["left"] - padding["right"],
            )
            content_height = max(
                0.0,
                parent_rect["height"] - padding["top"] - padding["bottom"],
            )
            column_width = max(
                0.0,
                (content_width - layout["gap"] * max(0, columns - 1)) / columns,
            )
            row_height = max(
                0.0,
                (content_height - layout["cross_gap"] * max(0, row_count - 1))
                / max(1, row_count),
            )
            for child in rows:
                child_id = str(child["id"])
                rect = resolved[child_id]
                child_layout = ui_auto_layout_view(child.get("layout"))
                row_index, column_index, row_span, column_span = placements[child_id]
                cell_x = content_x + column_index * (column_width + layout["gap"])
                cell_y = content_y + row_index * (row_height + layout["cross_gap"])
                cell_width = column_width * column_span + layout["gap"] * (column_span - 1)
                cell_height = row_height * row_span + layout["cross_gap"] * (row_span - 1)
                horizontal = str(child_layout["cell_horizontal_alignment"])
                vertical = str(child_layout["cell_vertical_alignment"])
                if horizontal == "stretch" or child_layout["width_sizing"] == "fill":
                    rect["width"] = _bounded_axis_size(
                        cell_width, child.get("constraints"), axis="width"
                    )
                if vertical == "stretch" or child_layout["height_sizing"] == "fill":
                    rect["height"] = _bounded_axis_size(
                        cell_height, child.get("constraints"), axis="height"
                    )
                rect["x"] = cell_x + {
                    "center": max(0.0, cell_width - rect["width"]) * 0.5,
                    "end": max(0.0, cell_width - rect["width"]),
                }.get(horizontal, 0.0)
                rect["y"] = cell_y + {
                    "center": max(0.0, cell_height - rect["height"]) * 0.5,
                    "end": max(0.0, cell_height - rect["height"]),
                }.get(vertical, 0.0)
        elif mode in {"horizontal", "vertical"} and rows:
            padding = _effective_padding(layout)
            include_strokes = bool(layout.get("include_strokes", False))
            content_x = parent_rect["x"] + padding["left"]
            content_y = parent_rect["y"] + padding["top"]
            content_width = (
                parent_rect["width"] - padding["left"] - padding["right"]
            )
            content_height = (
                parent_rect["height"] - padding["top"] - padding["bottom"]
            )
            available_main = (
                content_width if mode == "horizontal" else content_height
            )
            available_cross = (
                content_height if mode == "horizontal" else content_width
            )
            lines = _flow_lines(
                rows,
                resolved,
                mode=mode,
                available=available_main,
                gap=layout["gap"],
                wrap=bool(layout["wrap"]),
                include_strokes=include_strokes,
            )
            cross_cursor = content_y if mode == "horizontal" else content_x
            for line in lines:
                main_axis = "width" if mode == "horizontal" else "height"
                cross_axis = "height" if mode == "horizontal" else "width"
                fill_rows = [
                    row
                    for row in line
                    if ui_auto_layout_view(row.get("layout"))[
                        f"{main_axis}_sizing"
                    ]
                    == "fill"
                ]
                fixed_total = sum(
                    _axis_footprint_size(
                        row,
                        resolved[str(row["id"])],
                        axis=main_axis,
                        include_strokes=include_strokes,
                    )
                    for row in line
                    if row not in fill_rows
                )
                fill_outset_total = sum(
                    sum(
                        _axis_outsets(
                            row,
                            axis=main_axis,
                            include_strokes=include_strokes,
                        )
                    )
                    for row in fill_rows
                )
                remaining = max(
                    0.0,
                    available_main
                    - fixed_total
                    - fill_outset_total
                    - layout["gap"] * max(0, len(line) - 1),
                )
                fill_sizes = _distribute_fill_sizes(
                    fill_rows,
                    remaining,
                    axis=main_axis,
                )
                for child in fill_rows:
                    resolved[str(child["id"])][main_axis] = fill_sizes[
                        str(child["id"])
                    ]
                line_cross = max(
                    _axis_footprint_size(
                        row,
                        resolved[str(row["id"])],
                        axis=cross_axis,
                        include_strokes=include_strokes,
                    )
                    for row in line
                )
                baseline_line = 0.0
                if mode == "horizontal" and layout["cross_alignment"] == "baseline":
                    baseline_line, line_cross = _baseline_line_plan(
                        line,
                        resolved,
                        cross_axis=cross_axis,
                        include_strokes=include_strokes,
                    )
                if len(lines) == 1:
                    line_cross = available_cross
                sizes = [
                    _axis_footprint_size(
                        row,
                        resolved[str(row["id"])],
                        axis=main_axis,
                        include_strokes=include_strokes,
                    )
                    for row in line
                ]
                offset, effective_gap = _main_axis_plan(
                    sizes,
                    available_main,
                    layout["gap"],
                    layout["main_alignment"],
                )
                main_cursor = (
                    content_x if mode == "horizontal" else content_y
                ) + offset
                for child in line:
                    child_id = str(child["id"])
                    rect = resolved[child_id]
                    child_layout = ui_auto_layout_view(child.get("layout"))
                    fill_cross = (
                        child_layout[f"{cross_axis}_sizing"] == "fill"
                        or layout["cross_alignment"] == "stretch"
                    )
                    cross_leading, cross_trailing = _axis_outsets(
                        child,
                        axis=cross_axis,
                        include_strokes=include_strokes,
                    )
                    if fill_cross:
                        rect[cross_axis] = _bounded_axis_size(
                            max(
                                0.0,
                                line_cross - cross_leading - cross_trailing,
                            ),
                            child.get("constraints"),
                            axis=cross_axis,
                        )
                    cross_footprint = (
                        rect[cross_axis] + cross_leading + cross_trailing
                    )
                    cross_remaining = line_cross - cross_footprint
                    if mode == "horizontal" and layout["cross_alignment"] == "baseline":
                        child_baseline = cross_leading + _number(
                            child_layout.get("baseline_offset"),
                            float(rect[cross_axis]),
                        )
                        child_baseline = min(
                            cross_footprint,
                            max(0.0, child_baseline),
                        )
                        cross_offset = baseline_line - child_baseline
                    else:
                        cross_offset = {
                            "center": cross_remaining * 0.5,
                            "end": cross_remaining,
                        }.get(layout["cross_alignment"], 0.0)
                    main_leading, main_trailing = _axis_outsets(
                        child,
                        axis=main_axis,
                        include_strokes=include_strokes,
                    )
                    if mode == "horizontal":
                        rect["x"] = main_cursor + main_leading
                        rect["y"] = (
                            cross_cursor + cross_offset + cross_leading
                        )
                    else:
                        rect["y"] = main_cursor + main_leading
                        rect["x"] = (
                            cross_cursor + cross_offset + cross_leading
                        )
                    main_cursor += (
                        rect[main_axis]
                        + main_leading
                        + main_trailing
                        + effective_gap
                    )
                cross_cursor += line_cross + layout["cross_gap"]
        placed.add(parent_id)
        for child in children.get(parent_id, []):
            place(str(child["id"]), (*stack, parent_id))

    for root in roots:
        place(str(root["id"]))
    for object_id in objects:
        place(object_id)
    return resolved


__all__ = [
    "grid_auto_layout_placements",
    "normalize_ui_auto_layout",
    "resolve_ui_auto_layout",
]
