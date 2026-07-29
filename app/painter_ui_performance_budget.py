"""Document-scale performance budgets for Painter UI Design."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.painter_ui_document import normalize_ui_document


SCHEMA = "tigerstudio.painter.ui.performance_budget.v1"

_BUDGETS: tuple[tuple[str, str, int, int], ...] = (
    ("objects", "Objects", 2000, 5000),
    ("artboards", "Artboards", 100, 250),
    ("images", "Images", 300, 800),
    ("components", "Components", 500, 1500),
    ("prototype_transitions", "Prototype transitions", 500, 2000),
)


def _hierarchy_depth(objects: list[dict[str, Any]]) -> tuple[int, bool]:
    parents = {
        str(row.get("id") or ""): str(row.get("parent_id") or "")
        for row in objects
    }
    maximum = 0
    cycle = False
    for object_id in parents:
        current = object_id
        seen: set[str] = set()
        depth = 0
        while current and current in parents:
            if current in seen:
                cycle = True
                break
            seen.add(current)
            current = parents[current]
            depth += 1
        maximum = max(maximum, depth)
    return maximum, cycle


def _budget_row(
    budget_id: str,
    label: str,
    value: int,
    warning_limit: int,
    block_limit: int,
) -> dict[str, Any]:
    if value >= block_limit:
        status = "blocked"
    elif value >= warning_limit:
        status = "warning"
    else:
        status = "covered"
    return {
        "id": budget_id,
        "label": label,
        "value": int(value),
        "warning_limit": int(warning_limit),
        "block_limit": int(block_limit),
        "warning_ratio": round(
            float(value) / float(max(1, warning_limit)),
            4,
        ),
        "status": status,
    }


def inspect_painter_ui_performance_budget(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Inspect document scale without mutating or benchmarking wall-clock time."""

    document = normalize_ui_document(value)
    objects = list(document.get("objects") or [])
    counts = {
        "objects": len(objects),
        "artboards": len(document.get("artboards") or []),
        "images": sum(
            str(row.get("kind") or "") == "image"
            for row in objects
        ),
        "components": len(document.get("components") or []),
        "prototype_transitions": len(document.get("interactions") or []),
    }
    rows = [
        _budget_row(
            budget_id,
            label,
            counts[budget_id],
            warning_limit,
            block_limit,
        )
        for budget_id, label, warning_limit, block_limit in _BUDGETS
    ]
    maximum_depth, hierarchy_cycle = _hierarchy_depth(objects)
    depth_row = _budget_row(
        "hierarchy_depth",
        "Hierarchy depth",
        maximum_depth,
        32,
        64,
    )
    if hierarchy_cycle:
        depth_row["status"] = "blocked"
        depth_row["reason"] = "hierarchy_cycle"
    rows.append(depth_row)
    warning_count = sum(row["status"] == "warning" for row in rows)
    blocked_count = sum(row["status"] == "blocked" for row in rows)
    status = (
        "blocked"
        if blocked_count
        else "warning"
        if warning_count
        else "covered"
    )
    return {
        "schema": SCHEMA,
        "ok": blocked_count == 0,
        "status": status,
        "document_id": str(document.get("document_id") or ""),
        "revision": int(document.get("revision") or 0),
        "budget_count": len(rows),
        "covered_count": sum(row["status"] == "covered" for row in rows),
        "warning_count": warning_count,
        "blocked_count": blocked_count,
        "hierarchy_cycle": hierarchy_cycle,
        "budgets": rows,
        "policy": {
            "warning": "Review document scale and split heavy pages or assets.",
            "blocked": "Release preflight must block until document scale is reduced.",
            "wall_clock_claim": "not_measured",
        },
    }


__all__ = ["SCHEMA", "inspect_painter_ui_performance_budget"]
