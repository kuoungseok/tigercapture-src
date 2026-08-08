"""Registered actions for linked Remotion-style TSX sources."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_motion_remotion_tsx_actions(registry: Any) -> None:
    cid = {"composition_id": {"type": "string"}}
    registry.register_adapter_action(
        "motion.remotion_tsx.runtime.status",
        "Inspect local TSX preview runtime availability.",
        "motion", "motion_remotion_tsx_runtime_status",
        params_schema=schema_object({}), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.remotion_tsx.runtime.install",
        "Install Tiger's local React/esbuild TSX compatibility runtime.",
        "motion", "motion_remotion_tsx_runtime_install",
        params_schema=schema_object({}), mutating=True, changed=False,
    )
    registry.register_adapter_action(
        "motion.remotion_tsx.inspect",
        "Inspect a TSX source without executing or changing it.",
        "motion", "motion_remotion_tsx_inspect",
        params_schema=schema_object(
            {"path": {"type": "string"}}, required=("path",),
        ),
        required=("path",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.remotion_tsx.import",
        "Link an unchanged TSX source as a Motion layer and optionally prepare its preview.",
        "motion", "motion_remotion_tsx_import",
        params_schema=schema_object({
            **cid,
            "path": {"type": "string"},
            "trust_source": {"type": "boolean"},
            "prepare_preview": {"type": "boolean"},
            "duration_ms": {"type": "integer", "minimum": 1},
        }, required=("composition_id", "path")),
        required=("composition_id", "path"),
        undo_label="Import Linked Remotion TSX",
        dry_summary="The original TSX source would be linked without modification",
    )
    registry.register_adapter_action(
        "motion.remotion_tsx.refresh",
        "Re-read a linked TSX source and rebuild its preview cache.",
        "motion", "motion_remotion_tsx_refresh",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "trust_source": {"type": "boolean"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Refresh Linked Remotion TSX",
        dry_summary="The linked TSX source would be re-read without modification",
    )


__all__ = ["register_motion_remotion_tsx_actions"]
