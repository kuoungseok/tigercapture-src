"""MMD actor automation action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_mmd_actions(registry: Any) -> None:
    any_object = {"type": "object", "additionalProperties": True}
    registry.register_adapter_action(
        "mmd.summary",
        "Return MMD actor tracks and current settings.",
        "mmd",
        "mmd_summary",
        params_schema=schema_object({"limit": {"type": "integer", "minimum": 1}}),
        mutating=False,
        requires_owner=True,
        changed=False,
    )
    registry.register_adapter_action(
        "mmd.diagnostics",
        "Return active MMD track, material bucket, and render diagnostics.",
        "mmd",
        "mmd_diagnostics",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "pos_ms": {"type": "integer", "minimum": 0},
                "include_materials": {"type": "boolean"},
                "animate": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=True,
        changed=False,
    )
    registry.register_adapter_action(
        "mmd.qa.run",
        "Run the local MMD QA corpus diagnostics.",
        "mmd",
        "mmd_qa_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD QA corpus diagnostics would run",
    )
    registry.register_adapter_action(
        "mmd.qa.visual_run",
        "Render the local MMD QA corpus screenshots and contact sheet.",
        "mmd",
        "mmd_qa_visual_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "out_dir": {"type": "string"},
                "width": {"type": "integer", "minimum": 160},
                "height": {"type": "integer", "minimum": 120},
                "cpu_skinning": {"type": "boolean"},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD visual QA corpus screenshots would be rendered",
    )
    registry.register_adapter_action(
        "mmd.qa.composite_run",
        "Run MMD editor video-composite and export smoke QA.",
        "mmd",
        "mmd_qa_composite_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "width": {"type": "integer", "minimum": 160},
                "height": {"type": "integer", "minimum": 120},
                "duration_ms": {"type": "integer", "minimum": 500},
                "fps": {"type": "integer", "minimum": 4},
                "sample_time_ms": {"type": "integer", "minimum": 0},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD editor video-composite/export smoke QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.timeline_run",
        "Run multi-actor MMD timeline/export smoke QA.",
        "mmd",
        "mmd_qa_timeline_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "width": {"type": "integer", "minimum": 240},
                "height": {"type": "integer", "minimum": 135},
                "duration_ms": {"type": "integer", "minimum": 2000},
                "fps": {"type": "integer", "minimum": 4},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="Multi-actor MMD timeline/export smoke QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.segment_run",
        "Run MMD segment trim/speed export timing QA.",
        "mmd",
        "mmd_qa_segment_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "width": {"type": "integer", "minimum": 240},
                "height": {"type": "integer", "minimum": 135},
                "duration_ms": {"type": "integer", "minimum": 2600},
                "fps": {"type": "integer", "minimum": 4},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD segment trim/speed export timing QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.render_queue_run",
        "Run MMD render-queue export wiring QA.",
        "mmd",
        "mmd_qa_render_queue_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD render-queue export wiring QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.render_queue_export_run",
        "Run actual MMD render-queue MP4 export QA.",
        "mmd",
        "mmd_qa_render_queue_export_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "width": {"type": "integer", "minimum": 320},
                "height": {"type": "integer", "minimum": 180},
                "duration_ms": {"type": "integer", "minimum": 1800},
                "fps": {"type": "integer", "minimum": 8},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="Actual MMD render-queue MP4 export QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.long_project_run",
        "Run long-project MMD render-queue export QA.",
        "mmd",
        "mmd_qa_long_project_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "width": {"type": "integer", "minimum": 320},
                "height": {"type": "integer", "minimum": 180},
                "duration_ms": {"type": "integer", "minimum": 8000},
                "fps": {"type": "integer", "minimum": 6},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="Long-project MMD render-queue export QA would run",
    )
    registry.register_adapter_action(
        "mmd.qa.workflow_run",
        "Run MMD actor action workflow QA.",
        "mmd",
        "mmd_qa_workflow_run",
        params_schema=schema_object(
            {
                "manifest": {"type": "string"},
                "entry_id": {"type": "string"},
                "out_dir": {"type": "string"},
                "report_path": {"type": "string"},
                "include_reports": {"type": "boolean"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="qa",
        dry_summary="MMD actor action workflow QA would run",
    )
    registry.register_adapter_action(
        "mmd.actor.add",
        "Add an MMD model as an actor track.",
        "mmd",
        "mmd_add_actor",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
                "motion_path": {"type": "string"},
                "track_id": {"type": "string"},
            },
            required=("path",),
        ),
        required=("path",),
        undo_label="Add MMD actor",
        dry_summary="MMD actor track would be added",
    )
    registry.register_adapter_action(
        "mmd.actor.delete",
        "Delete an MMD actor track.",
        "mmd",
        "mmd_delete_actor",
        params_schema=schema_object({"track_id": {"type": "string"}}, required=("track_id",)),
        required=("track_id",),
        destructive=True,
        undo_label="Delete MMD actor",
        dry_summary="MMD actor track would be deleted",
    )
    registry.register_adapter_action(
        "mmd.actor.duplicate",
        "Duplicate an MMD actor track.",
        "mmd",
        "mmd_duplicate_actor",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "new_track_id": {"type": "string"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Duplicate MMD actor",
        dry_summary="MMD actor track would be duplicated",
    )
    registry.register_adapter_action(
        "mmd.track.move",
        "Move an MMD actor track in time.",
        "mmd",
        "mmd_move_track",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "delta_ms": {"type": "integer"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Move MMD actor",
        dry_summary="MMD actor track would be moved",
    )
    registry.register_adapter_action(
        "mmd.track.trim",
        "Trim an MMD actor track range.",
        "mmd",
        "mmd_trim_track",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Trim MMD actor",
        dry_summary="MMD actor track would be trimmed",
    )
    registry.register_adapter_action(
        "mmd.motion.list",
        "List VMD motions available for an MMD actor.",
        "mmd",
        "mmd_motion_list",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "model_path": {"type": "string"},
            }
        ),
        mutating=False,
        requires_owner=True,
        changed=False,
    )
    registry.register_adapter_action(
        "mmd.motion.add",
        "Add an external VMD motion to an MMD actor library.",
        "mmd",
        "mmd_add_motion",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "motion_path": {"type": "string"},
            },
            required=("track_id", "motion_path"),
        ),
        required=("track_id", "motion_path"),
        undo_label="Add MMD motion",
        dry_summary="VMD motion would be added to the MMD actor library",
    )
    registry.register_adapter_action(
        "mmd.motion.apply",
        "Apply a VMD motion to an MMD actor track.",
        "mmd",
        "mmd_apply_motion",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "motion_path": {"type": "string"},
            },
            required=("track_id", "motion_path"),
        ),
        required=("track_id", "motion_path"),
        undo_label="Apply MMD motion",
        dry_summary="VMD motion would be applied to the MMD actor",
    )
    registry.register_adapter_action(
        "mmd.settings.apply",
        "Apply MMD physics, lighting, and material settings.",
        "mmd",
        "mmd_apply_settings",
        params_schema=schema_object(
            {
                "track_id": {"type": "string"},
                "playback": any_object,
                "render": any_object,
                "material": any_object,
            },
            required=("track_id",),
            additional_properties=True,
        ),
        required=("track_id",),
        undo_label="Apply MMD settings",
        dry_summary="MMD actor settings would be applied",
    )
    registry.register_adapter_action(
        "mmd.editor.open",
        "Open the MMD Actor Editor for a track.",
        "mmd",
        "mmd_open_editor",
        params_schema=schema_object({"track_id": {"type": "string"}}, required=("track_id",)),
        required=("track_id",),
        mutating=False,
        undo_label="Open MMD editor",
        dry_summary="MMD Actor Editor would open",
        changed=False,
    )
