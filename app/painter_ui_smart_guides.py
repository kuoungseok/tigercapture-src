"""Resolved-geometry Smart Guide planning for Painter UI moves."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_constraints import resolve_ui_constraints
from app.painter_ui_motion_bridge import resolved_ui_geometry


def _rect(row: Mapping[str, float]) -> dict[str, float]:
    x = float(row["x"])
    y = float(row["y"])
    width = float(row["width"])
    height = float(row["height"])
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "left": x,
        "right": x + width,
        "top": y,
        "bottom": y + height,
        "center_x": x + width * 0.5,
        "center_y": y + height * 0.5,
    }


def _overlaps(first: dict[str, float], second: dict[str, float], axis: str) -> bool:
    if axis == "horizontal":
        return min(first["bottom"], second["bottom"]) >= max(
            first["top"], second["top"]
        )
    return min(first["right"], second["right"]) >= max(
        first["left"], second["left"]
    )


def plan_ui_move_guides(
    document: Mapping[str, Any],
    *,
    object_id: str,
    x: float,
    y: float,
    excluded_object_ids: Sequence[str] = (),
    tolerance: float = 6.0,
    geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Plan one X and one Y snap plus contextual guide annotations."""
    by_id = {str(row["id"]): row for row in document.get("objects", [])}
    moving = by_id.get(str(object_id))
    empty = {
        "schema": "tigerstudio.painter.ui.smart_guides.v1",
        "eligible": False,
        "reason": "missing_object",
        "object_id": str(object_id),
        "x": float(x),
        "y": float(y),
        "guides": [],
    }
    if moving is None:
        return empty
    resolved = (
        {str(key): dict(value) for key, value in geometry.items()}
        if geometry is not None
        else resolve_ui_constraints(document, resolved_ui_geometry(document))
    )
    moving_geometry = resolved.get(str(object_id), moving)
    moving_rect = _rect(
        {
            **moving_geometry,
            "x": float(x),
            "y": float(y),
        }
    )
    excluded = {str(value) for value in excluded_object_ids}
    excluded.add(str(object_id))
    others = [
        row
        for row in document.get("objects", [])
        if (
            str(row["id"]) not in excluded
            and bool(row.get("visible", True))
            and str(row["artboard_id"]) == str(moving["artboard_id"])
            and str(row["id"]) in resolved
        )
    ]
    candidates: dict[str, list[dict[str, Any]]] = {
        "horizontal": [],
        "vertical": [],
    }

    def add(axis: str, delta: float, position: float, kind: str, **extra) -> None:
        if abs(delta) <= float(tolerance):
            candidates[axis].append(
                {
                    "axis": axis,
                    "delta": float(delta),
                    "position": float(position),
                    "kind": kind,
                    **extra,
                }
            )

    anchors_x = (
        ("edge", moving_rect["left"]),
        ("center", moving_rect["center_x"]),
        ("edge", moving_rect["right"]),
    )
    anchors_y = (
        ("edge", moving_rect["top"]),
        ("center", moving_rect["center_y"]),
        ("edge", moving_rect["bottom"]),
    )
    for other in others:
        other_rect = _rect(resolved[str(other["id"])])
        for target in (
            other_rect["left"],
            other_rect["center_x"],
            other_rect["right"],
        ):
            for kind, anchor in anchors_x:
                add(
                    "horizontal",
                    target - anchor,
                    target,
                    kind,
                    target_object_id=str(other["id"]),
                )
        for target in (
            other_rect["top"],
            other_rect["center_y"],
            other_rect["bottom"],
        ):
            for kind, anchor in anchors_y:
                add(
                    "vertical",
                    target - anchor,
                    target,
                    kind,
                    target_object_id=str(other["id"]),
                )
        if moving["kind"] == "text" and other["kind"] == "text":
            moving_baseline = moving_rect["top"] + float(
                (moving.get("style") or {}).get("font_size") or 14.0
            ) * 0.8
            other_baseline = other_rect["top"] + float(
                (other.get("style") or {}).get("font_size") or 14.0
            ) * 0.8
            add(
                "vertical",
                other_baseline - moving_baseline,
                other_baseline,
                "baseline",
                target_object_id=str(other["id"]),
            )

    parent = by_id.get(str(moving.get("parent_id") or ""))
    if parent is not None and str(parent["id"]) in resolved:
        parent_rect = _rect(resolved[str(parent["id"])])
        padding = normalize_ui_auto_layout(parent.get("layout"))["padding"]
        padding_targets = (
            ("horizontal", parent_rect["left"] + padding["left"], moving_rect["left"]),
            (
                "horizontal",
                parent_rect["right"] - padding["right"],
                moving_rect["right"],
            ),
            ("vertical", parent_rect["top"] + padding["top"], moving_rect["top"]),
            (
                "vertical",
                parent_rect["bottom"] - padding["bottom"],
                moving_rect["bottom"],
            ),
        )
        for axis, target, anchor in padding_targets:
            add(
                axis,
                target - anchor,
                target,
                "padding",
                target_object_id=str(parent["id"]),
            )

    horizontal = [
        _rect(resolved[str(row["id"])])
        for row in others
        if _overlaps(
            moving_rect,
            _rect(resolved[str(row["id"])]),
            "horizontal",
        )
    ]
    left = [row for row in horizontal if row["right"] <= moving_rect["left"]]
    right = [row for row in horizontal if row["left"] >= moving_rect["right"]]
    if left and right:
        left_row = max(left, key=lambda row: row["right"])
        right_row = min(right, key=lambda row: row["left"])
        target_x = (
            left_row["right"] + right_row["left"] - moving_rect["width"]
        ) * 0.5
        gap = target_x - left_row["right"]
        add(
            "horizontal",
            target_x - moving_rect["left"],
            target_x,
            "equal_gap",
            value=max(0.0, gap),
        )

    vertical = [
        _rect(resolved[str(row["id"])])
        for row in others
        if _overlaps(
            moving_rect,
            _rect(resolved[str(row["id"])]),
            "vertical",
        )
    ]
    above = [row for row in vertical if row["bottom"] <= moving_rect["top"]]
    below = [row for row in vertical if row["top"] >= moving_rect["bottom"]]
    if above and below:
        above_row = max(above, key=lambda row: row["bottom"])
        below_row = min(below, key=lambda row: row["top"])
        target_y = (
            above_row["bottom"] + below_row["top"] - moving_rect["height"]
        ) * 0.5
        gap = target_y - above_row["bottom"]
        add(
            "vertical",
            target_y - moving_rect["top"],
            target_y,
            "equal_gap",
            value=max(0.0, gap),
        )

    priority = {"padding": 0, "baseline": 1, "equal_gap": 2, "edge": 3, "center": 4}
    guides: list[dict[str, Any]] = []
    next_x = float(x)
    next_y = float(y)
    for axis in ("horizontal", "vertical"):
        options = candidates[axis]
        if not options:
            continue
        chosen = min(
            options,
            key=lambda row: (
                abs(float(row["delta"])),
                priority.get(str(row["kind"]), 9),
            ),
        )
        guides.append(chosen)
        if axis == "horizontal":
            next_x += float(chosen["delta"])
        else:
            next_y += float(chosen["delta"])
    return {
        **empty,
        "eligible": True,
        "reason": "",
        "x": next_x,
        "y": next_y,
        "guides": guides,
    }


def plan_ui_resize_guides(
    document: Mapping[str, Any],
    *,
    object_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    excluded_object_ids: Sequence[str] = (),
    tolerance: float = 6.0,
    geometry: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Snap resize dimensions to visible peers on the same artboard."""
    by_id = {str(row["id"]): row for row in document.get("objects", [])}
    moving = by_id.get(str(object_id))
    report = {
        "schema": "tigerstudio.painter.ui.smart_guides.v1",
        "operation": "resize",
        "eligible": moving is not None,
        "reason": "" if moving is not None else "missing_object",
        "object_id": str(object_id),
        "x": float(x),
        "y": float(y),
        "width": float(width),
        "height": float(height),
        "guides": [],
    }
    if moving is None:
        return report
    resolved = (
        {str(key): dict(value) for key, value in geometry.items()}
        if geometry is not None
        else resolve_ui_constraints(document, resolved_ui_geometry(document))
    )
    excluded = {str(value) for value in excluded_object_ids}
    excluded.add(str(object_id))
    others = [
        row
        for row in document.get("objects", [])
        if (
            str(row["id"]) not in excluded
            and bool(row.get("visible", True))
            and str(row["artboard_id"]) == str(moving["artboard_id"])
            and str(row["id"]) in resolved
        )
    ]
    width_matches = [
        (
            abs(float(resolved[row["id"]]["width"]) - float(width)),
            row,
            float(resolved[row["id"]]["width"]),
        )
        for row in others
        if abs(float(resolved[row["id"]]["width"]) - float(width))
        <= float(tolerance)
    ]
    height_matches = [
        (
            abs(float(resolved[row["id"]]["height"]) - float(height)),
            row,
            float(resolved[row["id"]]["height"]),
        )
        for row in others
        if abs(float(resolved[row["id"]]["height"]) - float(height))
        <= float(tolerance)
    ]
    if width_matches:
        _delta, row, target = min(
            width_matches,
            key=lambda item: (item[0], int(item[1]["z_index"]), item[1]["id"]),
        )
        report["width"] = target
        report["guides"].append(
            {
                "axis": "horizontal",
                "kind": "equal_width",
                "value": target,
                "position": float(x) + target,
                "target_object_id": str(row["id"]),
            }
        )
    if height_matches:
        _delta, row, target = min(
            height_matches,
            key=lambda item: (item[0], int(item[1]["z_index"]), item[1]["id"]),
        )
        report["height"] = target
        report["guides"].append(
            {
                "axis": "vertical",
                "kind": "equal_height",
                "value": target,
                "position": float(y) + target,
                "target_object_id": str(row["id"]),
            }
        )
    return report


__all__ = ["plan_ui_move_guides", "plan_ui_resize_guides"]
