"""Ephemeral desktop, tablet, and mobile preview documents."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.painter_ui_document import normalize_ui_document


RESPONSIVE_PREVIEW_SCHEMA = "tigerstudio.painter.ui.responsive_preview.v1"
RESPONSIVE_PREVIEW_CONTEXTS = (
    ("desktop", "portrait", 900, 1440),
    ("desktop", "landscape", 1440, 900),
    ("tablet", "portrait", 768, 1024),
    ("tablet", "landscape", 1024, 768),
    ("mobile", "portrait", 390, 844),
    ("mobile", "landscape", 844, 390),
)


def build_ui_responsive_preview_matrix(
    value: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build six isolated documents without changing the authored document."""
    canonical = normalize_ui_document(value)
    active_artboard_id = str(canonical["active_artboard_id"])
    source_artboard = next(
        row
        for row in canonical["artboards"]
        if row["id"] == active_artboard_id
    )
    source_object_ids = {
        str(row["id"])
        for row in canonical["objects"]
        if str(row.get("artboard_id") or "") == active_artboard_id
    }
    documents: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    for breakpoint, orientation, width, height in RESPONSIVE_PREVIEW_CONTEXTS:
        preview = copy.deepcopy(canonical)
        artboard = copy.deepcopy(source_artboard)
        artboard.update(
            {
                "x": 0.0,
                "y": 0.0,
                "width": float(width),
                "height": float(height),
                "breakpoint": breakpoint,
                "orientation": orientation,
                "name": (
                    f"{breakpoint.title()} "
                    f"{orientation.title()} · {width} × {height}"
                ),
            }
        )
        preview["artboards"] = [artboard]
        preview["active_artboard_id"] = active_artboard_id
        preview["objects"] = [
            row
            for row in preview["objects"]
            if str(row["id"]) in source_object_ids
        ]
        preview["selection"] = {"object_id": "", "object_ids": []}
        preview["layout_grid_styles"] = []
        preview = normalize_ui_document(preview)
        documents.append(preview)
        contexts.append(
            {
                "breakpoint": breakpoint,
                "orientation": orientation,
                "width": width,
                "height": height,
                "artboard_id": active_artboard_id,
                "object_count": len(preview["objects"]),
                "label": artboard["name"],
            }
        )
    return documents, {
        "schema": RESPONSIVE_PREVIEW_SCHEMA,
        "preview_only": True,
        "canonical_revision": int(canonical["revision"]),
        "active_artboard_id": active_artboard_id,
        "active_artboard_name": str(source_artboard["name"]),
        "context_count": len(contexts),
        "contexts": contexts,
    }


__all__ = [
    "RESPONSIVE_PREVIEW_CONTEXTS",
    "RESPONSIVE_PREVIEW_SCHEMA",
    "build_ui_responsive_preview_matrix",
]
