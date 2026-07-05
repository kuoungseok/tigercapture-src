"""UI popout action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


_TARGET_SCHEMA = {
    "type": "string",
    "description": (
        "Popout target. Common values: preview, timeline, media_pool, workbench, color, subtitle, "
        "node_graph, ai_command, vtuber_studio, actor_library, effects_library, title_presets, "
        "transitions, workflow_presets, creator_assist, script_edit, render_queue, audio_workspace, "
        "pip, audio_mixer."
    ),
}


def _geometry_schema(required_path: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "target": _TARGET_SCHEMA,
        "surface": {"type": "string", "description": "Alias for target, accepted for review-runner compatibility."},
        "x": {"type": "integer"},
        "y": {"type": "integer"},
        "width": {"type": "integer", "minimum": 120},
        "height": {"type": "integer", "minimum": 90},
        "open_if_missing": {"type": "boolean"},
        "show": {"type": "boolean"},
        "activate": {"type": "boolean"},
    }
    required: tuple[str, ...] = ()
    if required_path:
        properties["path"] = {"type": "string"}
        properties["settle_ms"] = {"type": "integer", "minimum": 0, "maximum": 2000}
        required = ("path",)
    return schema_object(properties, required=required, additional_properties=True)


def register_ui_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "ui.viewer.compare.set",
        "Set the viewer Comparison Templates preview mode for the active video track.",
        "ui",
        "set_viewer_compare",
        params_schema=schema_object(
            {
                "mode": {
                    "type": "string",
                    "enum": ["off", "none", "", "before", "original", "split", "wipe"],
                },
                "labels_enabled": {"type": "boolean"},
                "track_id": {"type": "integer"},
            },
            additional_properties=True,
        ),
        undo_label="Set viewer comparison",
        async_kind="ui",
        dry_summary="viewer comparison mode would change",
    )
    registry.register_adapter_action(
        "ui.viewer.fit",
        "Fit the current viewer preview frame to the available viewer area.",
        "ui",
        "fit_viewer_preview",
        params_schema=schema_object({}, additional_properties=True),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="viewer preview would be fit to the available area",
    )
    registry.register_adapter_action(
        "ui.popout.list",
        "List detachable editor popout windows and current geometry.",
        "ui",
        "list_ui_popouts",
        params_schema=schema_object({}, additional_properties=True),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="popout targets would be listed",
    )
    registry.register_adapter_action(
        "ui.popout.open",
        "Open or raise a detachable editor popout window.",
        "ui",
        "open_ui_popout",
        params_schema=_geometry_schema(),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="popout window would be opened or raised",
    )
    registry.register_adapter_action(
        "ui.popout.set_geometry",
        "Resize or move a detachable editor popout window.",
        "ui",
        "set_ui_popout_geometry",
        params_schema=_geometry_schema(),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="popout window geometry would be changed",
    )
    registry.register_adapter_action(
        "ui.popout.capture",
        "Capture a screenshot of a detachable editor popout window.",
        "ui",
        "capture_ui_popout",
        params_schema=_geometry_schema(required_path=True),
        required=("path",),
        mutating=False,
        changed=False,
        async_kind="capture",
        dry_summary="popout window would be captured",
    )
    registry.register_adapter_action(
        "ui.popout.close",
        "Close a detachable editor popout window.",
        "ui",
        "close_ui_popout",
        params_schema=schema_object(
            {
                "target": _TARGET_SCHEMA,
                "surface": {"type": "string", "description": "Alias for target."},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="popout window would be closed",
    )
