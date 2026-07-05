"""NLE-related action registration helpers.

This module keeps public action IDs stable while moving high-growth action
namespaces out of the central registry file.
"""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_project_bin_actions(registry: Any) -> None:
    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "project_bin.workbench",
            "Return project-bin, conform, proxy, offline-media, and relink readiness state.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.workbench", adapter.project_bin_workbench()),
    )
    registry.register(
        ActionSpec(
            "project_bin.batch_plan",
            "Return a read-only batch plan for relink, proxy refresh, and conform checks.",
            "project_bin",
            params_schema=schema_object(
                {
                    "operation": {
                        "type": "string",
                        "enum": ["all", "relink", "offline", "proxy", "proxy_refresh", "conform", "duplicates"],
                    }
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.batch_plan",
            adapter.project_bin_batch_plan(operation=str(params.get("operation") or "all")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.conform_report",
            "Return timeline-to-media-pool conform diagnostics for clip source matching and relink review.",
            "project_bin",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("project_bin.conform_report", adapter.project_bin_conform_report()),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_plan",
            "Return proxy readiness, preview policy, usable proxies, and regeneration queue.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_plan",
            adapter.project_bin_proxy_plan(target=str(params.get("target") or "timeline")),
        ),
    )
    registry.register(
        ActionSpec(
            "project_bin.proxy_health",
            "Return product-facing proxy health cards, queue status, and safe regeneration command state.",
            "project_bin",
            params_schema=schema_object(
                {"target": {"type": "string", "enum": ["timeline", "preview", "export", "all"]}},
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project_bin.proxy_health",
            adapter.project_bin_proxy_health(target=str(params.get("target") or "timeline")),
        ),
    )


def register_nle_readiness_actions(registry: Any) -> None:
    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.professional_nle_readiness",
            "Return conservative professional NLE readiness diagnostics and claim blockers.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.professional_nle_readiness",
            adapter.professional_nle_readiness(
                action_count=len(registry._handlers),
                action_ids=tuple(registry._handlers.keys()),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_evidence",
            "Return evidence used by NLE readiness scoring without mutating the project.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "timeline.nle_evidence",
            adapter.nle_evidence(action_ids=tuple(registry._handlers.keys())),
        ),
    )
    registry.register(
        ActionSpec(
            "nle.real_corpus.status",
            "Return real long-project corpus registration and readiness status.",
            "nle",
            params_schema=schema_object({"manifest_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "nle.real_corpus.status",
            adapter.nle_real_corpus_status(manifest_path=str(params.get("manifest_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_fuzzer.status",
            "Return timeline fuzzer readiness for undo and edge-case NLE QA.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.nle_fuzzer.status",
            adapter.nle_timeline_stress_status(report_path=str(params.get("report_path") or "")),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.undo_health",
            "Return UI-ready undo/redo and edge-case health matrix from timeline fuzzer evidence.",
            "timeline",
            params_schema=schema_object({"report_path": {"type": "string"}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.undo_health",
            adapter.nle_undo_health(report_path=str(params.get("report_path") or "")),
        ),
    )


def register_multicam_actions(registry: Any) -> None:
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


def register_source_record_actions(registry: Any) -> None:
    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "source_record.workbench",
            "Return UI-ready Source/Record monitor state, patching, command enablement, and edit navigation.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.workbench", adapter.source_record_workbench()),
    )
    registry.register(
        ActionSpec(
            "source_record.edit_decision_preview",
            "Return a reviewed 3-point insert/overwrite decision before mutating the timeline.",
            "source_record",
            params_schema=schema_object({"mode": {"type": "string", "enum": ["insert", "overwrite"]}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "source_record.edit_decision_preview",
            adapter.source_record_edit_decision_preview(mode=str(params.get("mode") or "insert")),
        ),
    )
    registry.register(
        ActionSpec(
            "source_record.patch_matrix",
            "Return Source/Record video/audio patch matrix and insert/overwrite command cards.",
            "source_record",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("source_record.patch_matrix", adapter.source_record_patch_matrix()),
    )


def register_nle_namespace_actions(registry: Any) -> None:
    """Register the NLE namespace in the same public-ID order as the old registry."""

    register_project_bin_actions(registry)
    register_nle_readiness_actions(registry)
    register_multicam_actions(registry)
