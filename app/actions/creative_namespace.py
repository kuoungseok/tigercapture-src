"""Creative layer, preset, node, transition, and typography action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_creative_readiness_actions(registry: Any) -> None:
    """Register creative-layer readiness diagnostics."""
    registry.register(
        ActionSpec(
            "creative_layer.readiness",
            "Return conservative readiness diagnostics for effects, transitions, typography, nodes, actors, and 3D compositing.",
            "creative_layer",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "creative_layer.readiness",
            registry.adapter.creative_layer_readiness(action_ids=tuple(registry._handlers.keys())),
        ),
    )


def register_preset_catalog_actions(registry: Any) -> None:
    """Register preset catalog read actions."""
    registry.register(
        ActionSpec(
            "preset.catalog",
            "Return preset catalog entries.",
            "preset",
            params_schema=schema_object(
                {
                    "kind": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                }
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "preset.catalog",
            registry.adapter.preset_catalog(
                kind=str(params.get("kind") or ""),
                query=str(params.get("query") or ""),
                limit=_as_int(params.get("limit", 120), 120),
            ),
        ),
    )


def register_creative_clip_actions(registry: Any) -> None:
    """Register clip FX/color, transition, node graph, and typography actions."""
    any_object = {"type": "object", "additionalProperties": True}
    registry.register_adapter_action(
        "clip.set_filter",
        "Set clip-level video filter parameters.",
        "clip",
        "set_clip_filter",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "params": any_object,
                "merge": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "params"),
        ),
        required=("track_id", "clip_id", "params"),
        undo_label="Set clip filter",
        dry_summary="clip filter would change",
    )
    registry.register_adapter_action(
        "clip.set_color_grade",
        "Set clip color grade parameters.",
        "clip",
        "set_clip_color_grade",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "grade": any_object,
                "merge": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "grade"),
        ),
        required=("track_id", "clip_id", "grade"),
        undo_label="Set clip color grade",
        dry_summary="clip color grade would change",
    )
    registry.register_adapter_action(
        "transition.apply",
        "Apply a transition preset or transition type to a clip edge.",
        "transition",
        "set_clip_transition",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "preset_id": {"type": "string"},
                "transition_type": {"type": "string", "enum": ["", "dissolve", "fade_black", "fade_white"]},
                "duration_ms": {"type": "integer", "minimum": 1},
                "side": {"type": "string", "enum": ["out", "end"]},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Apply transition",
        dry_summary="clip transition would be applied",
    )
    registry.register_adapter_action(
        "transition.clear",
        "Clear a clip transition edge.",
        "transition",
        "clear_clip_transition",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "side": {"type": "string", "enum": ["out", "end"]},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Clear transition",
        dry_summary="clip transition would be cleared",
    )
    registry.register_adapter_action(
        "node.graph.set",
        "Replace a track node graph payload.",
        "node",
        "set_node_graph",
        params_schema=schema_object({"track_id": {"type": "integer"}, "graph": any_object}, required=("track_id",)),
        required=("track_id",),
        undo_label="Set node graph",
        dry_summary="node graph would be replaced",
    )
    registry.register_adapter_action(
        "node.add",
        "Add a node to a track node graph.",
        "node",
        "add_node",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "kind": {"type": "string"},
                "label": {"type": "string"},
                "node_id": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "params": any_object,
                "auto_connect": {"type": "boolean"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Add node",
        dry_summary="node would be added",
    )
    registry.register_adapter_action(
        "node.connect",
        "Connect two node graph ports.",
        "node",
        "connect_node",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "src_node": {"type": "string"},
                "dst_node": {"type": "string"},
                "src_port": {"type": "string"},
                "dst_port": {"type": "string"},
            },
            required=("track_id", "src_node", "dst_node"),
        ),
        required=("track_id", "src_node", "dst_node"),
        undo_label="Connect node",
        dry_summary="node connection would change",
    )
    registry.register_adapter_action(
        "node.set_param",
        "Set node parameter payload.",
        "node",
        "set_node_param",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "node_id": {"type": "string"},
                "params": any_object,
                "merge": {"type": "boolean"},
            },
            required=("track_id", "node_id", "params"),
        ),
        required=("track_id", "node_id", "params"),
        undo_label="Set node parameters",
        dry_summary="node parameters would change",
    )
    registry.register_adapter_action(
        "node.delete",
        "Delete a node from a track node graph.",
        "node",
        "delete_node",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "node_id": {"type": "string"},
                "reconnect": {"type": "boolean"},
            },
            required=("track_id", "node_id"),
        ),
        required=("track_id", "node_id"),
        destructive=True,
        requires_review=True,
        undo_label="Delete node",
        dry_summary="node would be deleted",
    )
    registry.register_adapter_action(
        "text.add",
        "Add typography text to a video clip.",
        "text",
        "add_text",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "text": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 1},
                "style": any_object,
                "animation": any_object,
            },
            required=("track_id", "clip_id", "text"),
        ),
        required=("track_id", "clip_id", "text"),
        undo_label="Add text",
        dry_summary="text would be added",
    )
    registry.register_adapter_action(
        "text.set_keyframes",
        "Attach keyframe payloads to a text actor.",
        "text",
        "set_text_keyframes",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "text_id": {"type": "integer"},
                "keyframes": any_object,
            },
            required=("track_id", "clip_id", "text_id", "keyframes"),
        ),
        required=("track_id", "clip_id", "text_id", "keyframes"),
        undo_label="Set text keyframes",
        dry_summary="text keyframes would change",
    )
