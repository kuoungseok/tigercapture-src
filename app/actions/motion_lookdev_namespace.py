"""Registered Motion painterly look-development actions."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_motion_lookdev_actions(registry: Any) -> None:
    layer_ref = {
        "composition_id": {"type": "string"},
        "layer_id": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.lookdev.preset.list",
        "List provider-neutral painterly look presets.",
        "motion",
        "motion_lookdev_presets",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.lookdev.get",
        "Inspect the painterly look on a Motion layer.",
        "motion",
        "motion_lookdev_get",
        params_schema=schema_object(
            layer_ref,
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.lookdev.set",
        "Apply a toon, painted, ink, paper, or realistic look.",
        "motion",
        "motion_lookdev_set",
        params_schema=schema_object({
            **layer_ref,
            "preset": {
                "type": "string",
                "enum": ["realistic", "toon", "painted", "ink", "paper"],
            },
            "settings": {"type": "object"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Set Painterly Look",
        dry_summary="A provider-neutral painterly look would be applied",
    )
    registry.register_adapter_action(
        "motion.lookdev.clear",
        "Remove the painterly look from a Motion layer.",
        "motion",
        "motion_lookdev_clear",
        params_schema=schema_object(
            layer_ref,
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        undo_label="Clear Painterly Look",
        dry_summary="The painterly look would be removed",
    )
    registry.register_adapter_action(
        "motion.lookdev.line.set",
        "Set stable image-space painterly line controls.",
        "motion",
        "motion_lookdev_line_set",
        params_schema=schema_object({
            **layer_ref,
            "color": {"type": "string"},
            "strength": {"type": "number", "minimum": 0, "maximum": 2},
            "threshold": {"type": "number", "minimum": 0, "maximum": 1},
            "softness": {
                "type": "number",
                "minimum": 0.001,
                "maximum": 1,
            },
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Set Painterly Lines",
        dry_summary="Stable painterly line controls would be updated",
    )
    registry.register_adapter_action(
        "motion.lookdev.material.override",
        "Store an explicit material-ID painterly override.",
        "motion",
        "motion_lookdev_material_override",
        params_schema=schema_object({
            **layer_ref,
            "material_id": {"type": "string"},
            "settings": {"type": "object"},
        }, required=("composition_id", "layer_id", "material_id")),
        required=("composition_id", "layer_id", "material_id"),
        undo_label="Set Painterly Material Override",
        dry_summary="A material-ID override would be stored and preflighted",
    )
    registry.register_adapter_action(
        "motion.lookdev.texture.project",
        "Project a durable texture over the painterly result.",
        "motion",
        "motion_lookdev_texture_project",
        params_schema=schema_object({
            **layer_ref,
            "uri": {"type": "string"},
            "blend_mode": {
                "type": "string",
                "enum": ["multiply", "screen", "overlay"],
            },
            "opacity": {"type": "number", "minimum": 0, "maximum": 1},
        }, required=("composition_id", "layer_id", "uri")),
        required=("composition_id", "layer_id", "uri"),
        undo_label="Project Painterly Texture",
        dry_summary="A durable painterly texture would be linked",
    )
    registry.register_adapter_action(
        "motion.lookdev.preflight",
        "Validate painterly resources, temporal stability, and output paths.",
        "motion",
        "motion_lookdev_preflight",
        params_schema=schema_object(
            layer_ref,
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )


__all__ = ["register_motion_lookdev_actions"]
