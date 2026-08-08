"""Reusable named layout-grid styles for Painter UI artboards."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


def normalize_ui_layout_grid_style(
    row: Mapping[str, Any] | None,
    index: int = 0,
) -> dict[str, Any]:
    from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

    source = row if isinstance(row, Mapping) else {}
    layout = normalize_ui_artboard_layout(
        {"layout_grids": source.get("layout_grids")},
        width=16384,
        height=16384,
    )
    return {
        "id": str(source.get("id") or f"ui-layout-grid-style-{index + 1}"),
        "name": str(source.get("name") or f"Grid Style {index + 1}"),
        "layout_grids": copy.deepcopy(layout["layout_grids"]),
        "description": str(source.get("description") or ""),
    }


def _next_style_id(rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"ui-layout-grid-style-{serial}" in used:
        serial += 1
    return f"ui-layout-grid-style-{serial}"


def add_ui_layout_grid_style(
    value: Mapping[str, Any],
    *,
    name: str,
    layout_grids: list[Mapping[str, Any]],
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    rows = document["layout_grid_styles"]
    row = normalize_ui_layout_grid_style(
        {
            "id": _next_style_id(rows),
            "name": str(name or f"Grid Style {len(rows) + 1}"),
            "layout_grids": layout_grids,
            "description": description,
        },
        len(rows),
    )
    rows.append(row)
    document["revision"] += 1
    return document, copy.deepcopy(row)


def update_ui_layout_grid_style(
    value: Mapping[str, Any],
    style_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document

    document = normalize_ui_document(value)
    for index, row in enumerate(document["layout_grid_styles"]):
        if row["id"] != str(style_id):
            continue
        updated = normalize_ui_layout_grid_style(
            {**row, **dict(changes), "id": row["id"]},
            index,
        )
        document["layout_grid_styles"][index] = updated
        for artboard in document["artboards"]:
            if artboard.get("layout_grid_style_id") != row["id"]:
                continue
            artboard["layout_grids"] = copy.deepcopy(updated["layout_grids"])
            artboard["layout_grid"] = copy.deepcopy(updated["layout_grids"][0])
        document["revision"] += 1
        return document, copy.deepcopy(updated)
    raise PainterUIDocumentError(f"UI layout-grid style not found: {style_id}")


def apply_ui_layout_grid_style(
    value: Mapping[str, Any],
    *,
    artboard_id: str,
    style_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        update_ui_artboard,
    )

    document = normalize_ui_document(value)
    style = next(
        (
            row
            for row in document["layout_grid_styles"]
            if row["id"] == str(style_id)
        ),
        None,
    )
    if style is None:
        raise PainterUIDocumentError(f"UI layout-grid style not found: {style_id}")
    updated, artboard = update_ui_artboard(
        document,
        str(artboard_id),
        {
            "layout_grid_style_id": style["id"],
            "layout_grids": copy.deepcopy(style["layout_grids"]),
        },
    )
    return updated, artboard


def remove_ui_layout_grid_style(
    value: Mapping[str, Any],
    style_id: str,
    *,
    detach_references: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document

    document = normalize_ui_document(value)
    if style_id not in {row["id"] for row in document["layout_grid_styles"]}:
        raise PainterUIDocumentError(f"UI layout-grid style not found: {style_id}")
    artboard_ids = [
        row["id"]
        for row in document["artboards"]
        if row.get("layout_grid_style_id") == str(style_id)
    ]
    if artboard_ids and not detach_references:
        raise PainterUIDocumentError(f"UI layout-grid style is referenced: {style_id}")
    document["layout_grid_styles"] = [
        row for row in document["layout_grid_styles"] if row["id"] != style_id
    ]
    if detach_references:
        for artboard in document["artboards"]:
            if artboard.get("layout_grid_style_id") == style_id:
                artboard["layout_grid_style_id"] = ""
    document["revision"] += 1
    return document, {
        "style_id": str(style_id),
        "detached_artboard_ids": artboard_ids,
    }


__all__ = [
    "add_ui_layout_grid_style",
    "apply_ui_layout_grid_style",
    "normalize_ui_layout_grid_style",
    "remove_ui_layout_grid_style",
    "update_ui_layout_grid_style",
]
