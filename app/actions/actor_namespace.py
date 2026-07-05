"""Live2D and Spine actor Python action namespace registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_actor_actions(registry: Any) -> None:
    """Register actor-track actions without growing the core registry."""
    any_object = {"type": "object", "additionalProperties": True}
    registry.register_adapter_action(
        "actor.add",
        "Add a Live2D or Spine actor clip.",
        "actor",
        "add_actor",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["live2d", "spine"]},
                "path": {"type": "string"},
                "track_id": {"type": "integer"},
                "start_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
                "pos_x": {"type": "number"},
                "pos_y": {"type": "number"},
                "scale": {"type": "number"},
                "opacity": {"type": "number"},
                "atlas_path": {"type": "string"},
                "texture_path": {"type": "string"},
                "anim_name": {"type": "string"},
                "skin_name": {"type": "string"},
            },
            required=("kind", "path"),
            additional_properties=True,
        ),
        required=("kind", "path"),
        undo_label="Add actor",
        dry_summary="actor would be added",
    )
    registry.register_adapter_action(
        "actor.set_transform",
        "Set Live2D or Spine actor transform.",
        "actor",
        "set_actor_transform",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["live2d", "spine"]},
                "track_id": {"type": "integer"},
                "clip_index": {"type": "integer"},
                "start_ms": {"type": "integer"},
                "duration_ms": {"type": "integer"},
                "pos_x": {"type": "number"},
                "pos_y": {"type": "number"},
                "scale": {"type": "number"},
                "opacity": {"type": "number"},
            },
            required=("kind", "track_id"),
            additional_properties=True,
        ),
        required=("kind", "track_id"),
        undo_label="Set actor transform",
        dry_summary="actor transform would change",
    )
    registry.register_adapter_action(
        "actor.set_keyframes",
        "Set Live2D/Spine actor keyframe payloads.",
        "actor",
        "set_actor_keyframes",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["live2d", "spine"]},
                "track_id": {"type": "integer"},
                "clip_index": {"type": "integer"},
                "keyframes": any_object,
            },
            required=("kind", "track_id", "keyframes"),
        ),
        required=("kind", "track_id", "keyframes"),
        undo_label="Set actor keyframes",
        dry_summary="actor keyframes would change",
    )
    registry.register_adapter_action(
        "actor.live2d.apply_performance_source",
        "Retarget an input-only Performance Source to a Live2D actor clip.",
        "actor",
        "apply_live2d_performance_source",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_index": {"type": "integer", "minimum": 0},
                "time_ms": {"type": "integer", "minimum": 0},
                "source_path": {"type": "string"},
                "mocap_frames": {"type": "array", "items": any_object},
                "mocap_payload": any_object,
                "framing_payload": any_object,
                "framing_control": any_object,
                "preset": {"type": "string"},
                "analyze_video": {"type": "boolean"},
                "sample_fps": {"type": "number", "minimum": 1.0, "maximum": 60.0},
                "max_samples": {"type": "integer", "minimum": 1},
                "fit_duration": {"type": "boolean"},
                "apply_mocap": {"type": "boolean"},
                "apply_framing": {"type": "boolean"},
                "replace_transform": {"type": "boolean"},
            },
            required=("track_id",),
            additional_properties=True,
        ),
        required=("track_id",),
        undo_label="Apply Live2D Performance Source",
        async_kind="analysis",
        dry_summary="Performance Source tracking would be mapped to a Live2D actor",
    )
