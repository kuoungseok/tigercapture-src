"""Provider-neutral artboard guides for Painter UI documents."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_GRID_MODES = {"none", "grid", "columns", "rows"}
_EDGES = ("left", "top", "right", "bottom")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _positions(value: Any, maximum: float) -> list[float]:
    rows = value if isinstance(value, (list, tuple)) else []
    result: list[float] = []
    for item in rows:
        position = max(0.0, min(maximum, _number(item)))
        if all(abs(position - existing) >= 0.001 for existing in result):
            result.append(position)
    return sorted(result)


def normalize_ui_artboard_layout(
    row: Mapping[str, Any] | None,
    *,
    width: float,
    height: float,
) -> dict[str, Any]:
    source = row if isinstance(row, Mapping) else {}
    raw_grid = source.get("layout_grid")
    raw_grid = raw_grid if isinstance(raw_grid, Mapping) else {}
    raw_grids = source.get("layout_grids")
    raw_grids = (
        [item for item in raw_grids if isinstance(item, Mapping)]
        if isinstance(raw_grids, list)
        else []
    )
    if not raw_grids:
        raw_grids = [raw_grid]
    elif raw_grid:
        # Mutation services synchronize both views. Keeping the legacy first
        # entry authoritative also preserves older direct-edit callers.
        raw_grids[0] = raw_grid

    def normalize_grid(item: Mapping[str, Any], index: int) -> dict[str, Any]:
        mode = str(item.get("mode") or "none").strip().casefold()
        mode = mode if mode in _GRID_MODES else "none"
        axis_extent = float(height if mode == "rows" else width)
        alignment = str(item.get("alignment") or "stretch").strip().casefold()
        return {
            "id": str(item.get("id") or f"layout-grid-{index + 1}"),
            "name": str(item.get("name") or mode.title() or f"Grid {index + 1}"),
            "mode": mode,
            "visible": bool(item.get("visible", mode != "none")),
            "size": max(2.0, min(512.0, _number(item.get("size"), 8.0))),
            "count": max(1, min(64, int(_number(item.get("count"), 12)))),
            "gutter": max(
                0.0,
                min(max(0.0, axis_extent), _number(item.get("gutter"), 20.0)),
            ),
            "margin": max(
                0.0,
                min(
                    max(0.0, axis_extent * 0.5),
                    _number(item.get("margin"), 24.0),
                ),
            ),
            "alignment": alignment if alignment in {"stretch", "center"} else "stretch",
            "color": str(item.get("color") or "#4C9AFF32"),
        }

    grids = [normalize_grid(item, index) for index, item in enumerate(raw_grids)]
    raw_safe = source.get("safe_area")
    raw_safe = raw_safe if isinstance(raw_safe, Mapping) else {}
    raw_guides = source.get("guides")
    raw_guides = raw_guides if isinstance(raw_guides, Mapping) else {}
    return {
        "layout_grid": dict(grids[0]),
        "layout_grids": grids,
        "safe_area": {
            edge: max(
                0,
                min(
                    int(round(float(width if edge in {"left", "right"} else height))),
                    int(round(_number(raw_safe.get(edge)))),
                ),
            )
            for edge in _EDGES
        },
        "safe_area_visible": bool(source.get("safe_area_visible", False)),
        "guides": {
            "visible": bool(raw_guides.get("visible", True)),
            "locked": bool(raw_guides.get("locked", False)),
            "origin": {
                "x": _number(
                    (
                        raw_guides.get("origin")
                        if isinstance(raw_guides.get("origin"), Mapping)
                        else {}
                    ).get("x")
                ),
                "y": _number(
                    (
                        raw_guides.get("origin")
                        if isinstance(raw_guides.get("origin"), Mapping)
                        else {}
                    ).get("y")
                ),
            },
            "vertical": _positions(raw_guides.get("vertical"), float(width)),
            "horizontal": _positions(raw_guides.get("horizontal"), float(height)),
        },
    }


__all__ = ["normalize_ui_artboard_layout"]
