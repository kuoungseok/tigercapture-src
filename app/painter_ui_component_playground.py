"""Non-destructive component property playground planning."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.painter_ui_components import (
    component_property_defaults,
    detach_ui_component_instance,
    instantiate_ui_component,
    normalize_ui_component_property_definitions,
    set_ui_instance_component_property,
)
from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document


COMPONENT_PLAYGROUND_SCHEMA = "tigerstudio.painter.ui.component_playground.v1"


def build_ui_component_playground(
    value: Mapping[str, Any] | None,
    *,
    component_id: str,
    property_values: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize an isolated component preview without touching its source."""
    canonical = normalize_ui_document(value)
    component = next(
        (
            row
            for row in canonical["components"]
            if row["id"] == str(component_id)
        ),
        None,
    )
    if component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    values = component_property_defaults(component)
    for name, item in dict(property_values or {}).items():
        if str(name) not in definitions:
            raise PainterUIDocumentError(
                f"Component property not found: {name}"
            )
        values[str(name)] = copy.deepcopy(item)

    preview, instance = instantiate_ui_component(
        canonical,
        component_id=component["id"],
        artboard_id=canonical["active_artboard_id"],
        x=40.0,
        y=40.0,
    )
    root_id = str(instance["root_object_id"])
    for name, item in values.items():
        preview, _ = set_ui_instance_component_property(
            preview,
            instance_root_id=root_id,
            property_name=name,
            property_value=item,
        )
    preview, detached = detach_ui_component_instance(
        preview,
        instance_root_id=root_id,
    )
    object_ids = set(detached["object_ids"])
    rows = [
        copy.deepcopy(row)
        for row in preview["objects"]
        if row["id"] in object_ids
    ]
    if rows:
        minimum_x = min(float(row["x"]) for row in rows)
        minimum_y = min(float(row["y"]) for row in rows)
        maximum_x = max(float(row["x"]) + float(row["width"]) for row in rows)
        maximum_y = max(float(row["y"]) + float(row["height"]) for row in rows)
        for row in rows:
            row["x"] = float(row["x"]) - minimum_x + 40.0
            row["y"] = float(row["y"]) - minimum_y + 40.0
        content_width = maximum_x - minimum_x
        content_height = maximum_y - minimum_y
    else:
        content_width = 320.0
        content_height = 180.0
    artboard = copy.deepcopy(
        next(
            row
            for row in preview["artboards"]
            if row["id"] == preview["active_artboard_id"]
        )
    )
    artboard.update(
        {
            "x": 0.0,
            "y": 0.0,
            "name": f"{component['name']} Playground",
            "width": int(max(320.0, min(1440.0, content_width + 80.0))),
            "height": int(max(240.0, min(1000.0, content_height + 80.0))),
        }
    )
    preview["artboards"] = [artboard]
    preview["objects"] = rows
    preview["components"] = []
    preview["interactions"] = []
    preview["sections"] = []
    preview["selection"] = {"object_id": "", "object_ids": []}
    preview["revision"] = canonical["revision"]
    preview = normalize_ui_document(preview)
    return preview, {
        "schema": COMPONENT_PLAYGROUND_SCHEMA,
        "preview_only": True,
        "canonical_revision": int(canonical["revision"]),
        "component_id": component["id"],
        "component_name": component["name"],
        "property_definitions": definitions,
        "property_values": values,
        "preview_object_count": len(rows),
        "preview_artboard": {
            "width": artboard["width"],
            "height": artboard["height"],
        },
    }


__all__ = [
    "COMPONENT_PLAYGROUND_SCHEMA",
    "build_ui_component_playground",
]
