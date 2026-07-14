"""Paint / drawing action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_paint_actions(registry: Any) -> None:
    any_object = {"type": "object", "additionalProperties": True}
    registry.register_adapter_action(
        "paint.editor_objects.list",
        "List editor typography, AR/PBR, and actor objects importable into Paint.",
        "paint",
        "paint_editor_objects_list",
        params_schema=schema_object(
            {
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="paint importable editor objects would be listed",
    )
    registry.register_adapter_action(
        "paint.editor_object.render",
        "Render one editor object to a Paint-import PNG without placing it.",
        "paint",
        "paint_editor_object_render",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "kind": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "output_dir": {"type": "string"},
                "force": {"type": "boolean"},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="editor object poster would be rendered for Paint",
    )
    registry.register_adapter_action(
        "paint.editor_object.import",
        "Import one editor object into Paint as a movable sticker layer.",
        "paint",
        "paint_editor_object_import",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "kind": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "x_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "width_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "height_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "output_dir": {"type": "string"},
                "force": {"type": "boolean"},
                "metadata": any_object,
            }
        ),
        undo_label="Import editor object into Paint",
        dry_summary="editor object would be imported into Paint as a sticker layer",
    )
    registry.register_adapter_action(
        "paint.export_png",
        "Export the current Paint overlays as a PNG from the editor window.",
        "paint",
        "paint_export_png",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "mode": {"type": "string", "enum": ["composited", "overlay", "transparent_overlay"]},
                "time_ms": {"type": "integer", "minimum": 0},
                "width": {"type": "integer", "minimum": 0},
                "height": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="current Paint overlays would be exported as PNG",
    )


__all__ = ["register_paint_actions"]
