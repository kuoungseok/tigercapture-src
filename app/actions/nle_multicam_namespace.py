"""Multicam action registration helpers."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_multicam_actions(registry: Any) -> None:
    """Register multicam group, switcher, and export handoff actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.multicam.summary",
            "Return multicam group candidates, angle counts, and stored project multicam groups.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.multicam.summary", adapter.multicam_summary()),
    )
    registry.register_adapter_action(
        "timeline.multicam.create_group",
        "Create or refresh a project multicam group from timeline angle tracks.",
        "timeline",
        "create_multicam_group",
        params_schema=schema_object(
            {
                "group_id": {"type": "string"},
                "name": {"type": "string"},
                "track_ids": {"type": "array"},
            },
            additional_properties=True,
        ),
        mutating=True,
        requires_owner=True,
        undo_label="Create multicam group",
        dry_summary="multicam group would be created from timeline angles",
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.sync_plan",
            "Build multicam angle sync offsets from timecode, audio-marker, or timeline placement metadata.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {
                        "type": "string",
                        "enum": ["hybrid", "timeline", "timecode", "tc", "audio", "audio_marker", "slate", "clap"],
                    },
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.sync_plan",
            adapter.multicam_sync_plan(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "hybrid"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.sync_quality_board",
            "Return multicam sync confidence rows and review recommendations for timecode/audio/timeline sync.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {
                        "type": "string",
                        "enum": ["hybrid", "timeline", "timecode", "tc", "audio", "audio_marker", "slate", "clap"],
                    },
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.sync_quality_board",
            adapter.multicam_sync_quality_board(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "hybrid"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.waveform_sync_board",
            "Return a multicam waveform/fingerprint sync board from cached transient metadata.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {
                        "type": "string",
                        "enum": ["hybrid", "waveform", "audio_waveform", "fingerprint", "timeline"],
                    },
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.waveform_sync_board",
            adapter.multicam_waveform_sync_board(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "waveform"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.switch_plan",
            "Build a deterministic multicam active-angle switch plan for review.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["round_robin", "first", "coverage", "longest"]},
                    "max_segments": {"type": "integer", "minimum": 1},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.switch_plan",
            adapter.multicam_switch_plan(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "round_robin"),
                max_segments=_as_int(params.get("max_segments", 240), 240),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.angle_bins",
            "Return UI-ready multicam angle bins with coverage gaps and sync readiness.",
            "timeline",
            params_schema=schema_object({"group_id": {"type": "string"}}, additional_properties=True),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.angle_bins",
            adapter.multicam_angle_bins(group_id=str(params.get("group_id") or "")),
        ),
    )
    registry.register_adapter_action(
        "timeline.multicam.set_active_angle",
        "Store a multicam active-angle decision at the current playhead or given time.",
        "timeline",
        "set_multicam_active_angle",
        params_schema=schema_object(
            {
                "group_id": {"type": "string"},
                "angle_id": {"type": "string"},
                "at_ms": {"type": "integer", "minimum": 0},
            },
            required=("angle_id",),
            additional_properties=True,
        ),
        required=("angle_id",),
        mutating=True,
        requires_owner=True,
        undo_label="Set multicam active angle",
        dry_summary="multicam active-angle switch would be recorded",
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.switcher_workbench",
            "Return UI-ready multicam switcher angle tiles, sync status, active angle, and export handoff state.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["round_robin", "first", "coverage", "longest"]},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.switcher_workbench",
            adapter.multicam_switcher_workbench(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "round_robin"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.tile_board",
            "Return a visual multicam switcher tile board with active angle, keyboard hotkeys, sync badges, and export readiness.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["round_robin", "first", "coverage", "longest"]},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.tile_board",
            adapter.multicam_switcher_tile_board(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "round_robin"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.review_board",
            "Return a multicam switch review board with angle tiles, coverage diagnostics, switch decisions, and bake/export readiness.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["round_robin", "first", "coverage", "longest"]},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.review_board",
            adapter.multicam_switch_review_board(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "round_robin"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.live_switch_dashboard",
            "Return one live multicam dashboard with angle tiles, switch decisions, sync quality, waveform status, and bake/export commands.",
            "timeline",
            params_schema=schema_object(
                {
                    "group_id": {"type": "string"},
                    "strategy": {"type": "string", "enum": ["round_robin", "first", "coverage", "longest"]},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.live_switch_dashboard",
            adapter.multicam_live_switch_dashboard(
                group_id=str(params.get("group_id") or ""),
                strategy=str(params.get("strategy") or "round_robin"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.multicam.export_handoff",
            "Return flattened multicam edit decisions for export or timeline bake.",
            "timeline",
            params_schema=schema_object({"group_id": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.multicam.export_handoff",
            adapter.multicam_export_handoff(group_id=str(params.get("group_id") or "")),
        ),
    )


__all__ = ["register_multicam_actions"]
