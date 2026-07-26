"""Provider-neutral artboard guides for Painter UI documents."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_GRID_MODES = {"none", "grid", "columns"}
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
    mode = str(raw_grid.get("mode") or "none").strip().casefold()
    raw_safe = source.get("safe_area")
    raw_safe = raw_safe if isinstance(raw_safe, Mapping) else {}
    raw_guides = source.get("guides")
    raw_guides = raw_guides if isinstance(raw_guides, Mapping) else {}
    return {
        "layout_grid": {
            "mode": mode if mode in _GRID_MODES else "none",
            "visible": bool(raw_grid.get("visible", mode != "none")),
            "size": max(2.0, min(512.0, _number(raw_grid.get("size"), 8.0))),
            "count": max(1, min(64, int(_number(raw_grid.get("count"), 12)))),
            "gutter": max(
                0.0,
                min(max(0.0, float(width)), _number(raw_grid.get("gutter"), 20.0)),
            ),
            "margin": max(
                0.0,
                min(
                    max(0.0, float(width) * 0.5),
                    _number(raw_grid.get("margin"), 24.0),
                ),
            ),
            "color": str(raw_grid.get("color") or "#4C9AFF32"),
        },
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
            "vertical": _positions(raw_guides.get("vertical"), float(width)),
            "horizontal": _positions(raw_guides.get("horizontal"), float(height)),
        },
    }


__all__ = ["normalize_ui_artboard_layout"]
