"""UI focus, capture evidence, and review scenario action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_evidence_actions(registry: Any) -> None:
    """Register UI/capture/review evidence actions outside the core registry."""
    registry.register_adapter_action(
        "render.queue.stage",
        "Stage one or more render jobs in the live Render Queue.",
        "render",
        "stage_render_queue_jobs",
        params_schema=schema_object(
            {
                "jobs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "render_queue_jobs": {
                    "type": "array",
                    "items": {"type": "object", "additionalProperties": True},
                },
                "open_panel": {"type": "boolean"},
            },
            additional_properties=True,
        ),
        mutating=True,
        async_kind="render",
        dry_summary="render queue jobs would be staged",
    )
    registry.register_adapter_action(
        "ui.focus_surface",
        "Focus an existing editor surface before evidence capture.",
        "ui",
        "focus_ui_surface",
        params_schema=schema_object(
            {
                "surface": {
                    "type": "string",
                    "enum": [
                        "timeline",
                        "node",
                        "node_graph",
                        "vfx",
                        "color",
                        "color_grading",
                        "audio",
                        "sound_editor",
                        "live2d",
                        "spine",
                        "actors",
                        "export",
                        "render",
                        "metadata",
                    ],
                },
                "kind": {"type": "string", "enum": ["video", "audio", "live2d", "spine", "actor"]},
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "inspector_tab": {"type": "string", "enum": ["", "clip", "audio", "fx", "mask", "meta"]},
                "show_audio_mixer": {"type": "boolean"},
                "show_audio_scopes": {"type": "boolean"},
                "open_aux_window": {"type": "boolean"},
            },
            additional_properties=True,
        ),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="editor surface would be focused",
    )
    registry.register_adapter_action(
        "capture.screenshot",
        "Capture a screenshot from a live editor widget.",
        "capture",
        "capture_screenshot",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "target": {"type": "string"},
            }
        ),
        mutating=False,
        changed=False,
        async_kind="capture",
        dry_summary="screenshot would be captured",
    )
    registry.register_adapter_action(
        "capture.gif",
        "Capture an animated GIF through a live capture backend.",
        "capture",
        "capture_gif",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "target": {"type": "string"},
                "duration_ms": {"type": "integer", "minimum": 1},
                "fps": {"type": "integer", "minimum": 1},
            }
        ),
        mutating=False,
        changed=False,
        async_kind="capture",
        dry_summary="GIF capture would run",
    )
    registry.register_adapter_action(
        "review.scenario.run",
        "Run or plan a review automation scenario.",
        "review",
        "run_review_scenario",
        params_schema=schema_object(
            {"scenario": {"type": "string"}, "params": {"type": "object", "additionalProperties": True}},
            required=("scenario",),
            additional_properties=True,
        ),
        required=("scenario",),
        requires_owner=False,
        mutating=False,
        changed=False,
        async_kind="review",
        dry_summary="review scenario would run",
    )
