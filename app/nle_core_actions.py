"""Core NLE action coverage contracts."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any


CORE_NLE_ACTION_COVERAGE_SCHEMA = "tigerstudio.nle.core_action_coverage.v1"


ACTION_GROUPS: dict[str, tuple[str, ...]] = {
    "timeline_edit": (
        "timeline.split",
        "timeline.trim_to_playhead",
        "timeline.ripple_delete",
        "timeline.lift",
        "timeline.extract",
        "timeline.cleanup_edges",
    ),
    "clipboard_and_insert": (
        "clip.copy",
        "timeline.insert_clipboard",
        "timeline.overwrite_clipboard",
    ),
    "source_record": (
        "source_record.workbench",
        "source_record.edit_decision_preview",
        "source_record.usability_board",
        "timeline.three_point_insert",
        "timeline.three_point_overwrite",
    ),
    "project_bin": (
        "project_bin.workbench",
        "project_bin.conform_report",
        "project_bin.conform_apply_review_board",
        "project_bin.proxy_plan",
        "project_bin.proxy_health",
        "project_bin.proxy_conflict_board",
        "project_bin.proxy_apply_review_board",
    ),
    "storyline": (
        "timeline.magnetic_storyline.status",
        "timeline.connected_clips.status",
        "timeline.role_lanes.status",
        "timeline.auditions.status",
        "timeline.storyline_gesture_polish_board",
    ),
    "multicam": (
        "timeline.multicam.summary",
        "timeline.multicam.sync_plan",
        "timeline.multicam.waveform_sync_board",
        "timeline.multicam.export_parity_board",
        "timeline.multicam.export_handoff",
    ),
    "undo_and_recovery": (
        "timeline.nle_fuzzer.status",
        "timeline.undo_health",
        "timeline.undo_review_board",
        "timeline.undo_recovery_playbook",
        "timeline.undo_stability_dashboard",
        "timeline.undo_long_session_plan",
        "timeline.nle_core_safety_matrix",
    ),
}


def build_core_nle_action_coverage(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Return a UI/QA-ready coverage matrix for the core NLE action surface."""

    actions = {str(action_id) for action_id in list(action_ids or []) if str(action_id or "").strip()}
    groups: list[dict[str, Any]] = []
    missing_all: list[str] = []
    for group_id, required in ACTION_GROUPS.items():
        missing = [action_id for action_id in required if action_id not in actions]
        available = [action_id for action_id in required if action_id in actions]
        missing_all.extend(missing)
        groups.append(
            {
                "id": group_id,
                "required_count": len(required),
                "available_count": len(available),
                "missing_count": len(missing),
                "ready": not missing,
                "available_actions": available,
                "missing_actions": missing,
            }
        )
    ready_group_count = sum(1 for row in groups if bool(row.get("ready")))
    return {
        "schema": CORE_NLE_ACTION_COVERAGE_SCHEMA,
        "kind": "core_nle_action_coverage",
        "ready": not missing_all,
        "summary": {
            "registered_action_count": len(actions),
            "group_count": len(groups),
            "ready_group_count": ready_group_count,
            "missing_action_count": len(missing_all),
            "coverage_ratio": round(ready_group_count / len(groups), 4) if groups else 0.0,
        },
        "groups": groups,
        "missing_actions": missing_all,
        "commands": {
            "open_action_list_enabled": True,
            "open_missing_action_filter_enabled": bool(missing_all),
            "run_nle_readiness_enabled": True,
        },
        "readiness": {
            "core_action_coverage_ready": not missing_all,
            "registered_action_surface_ready": len(actions) >= 70,
            "nle_group_matrix_ready": bool(groups),
        },
    }


__all__ = ["ACTION_GROUPS", "CORE_NLE_ACTION_COVERAGE_SCHEMA", "build_core_nle_action_coverage"]
