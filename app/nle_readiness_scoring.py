"""Scoring helpers for conservative NLE readiness reports."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def score_ladder(*rules: tuple[bool, int], default: int) -> int:
    """Return the first matching score from a top-down readiness ladder."""

    for condition, score in rules:
        if bool(condition):
            return int(score)
    return int(default)


def build_score_breakdown(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return a compact id->score/status map for UI, QA, and local AI surfaces."""

    breakdown: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get("id") or "")
        if not row_id:
            continue
        breakdown[row_id] = {
            "score": int(row.get("score") or 0),
            "status": str(row.get("status") or ""),
            "label": str(row.get("label") or row_id),
        }
    return breakdown


def score_core_nle_actions(
    *,
    real_world_score_unlock: bool,
    core_action_coverage_ready: bool,
    core_group_matrix_ready: bool,
    core_safety_matrix_ready: bool,
    core_registered_surface_ready: bool,
) -> int:
    return score_ladder(
        (real_world_score_unlock and core_action_coverage_ready and core_group_matrix_ready, 96),
        (core_action_coverage_ready and core_group_matrix_ready and core_safety_matrix_ready, 90),
        (core_action_coverage_ready and core_group_matrix_ready, 88),
        (core_registered_surface_ready, 86),
        default=72,
    )


def score_source_record_monitor(
    *,
    real_world_score_unlock: bool,
    source_decision_preview_ready: bool,
    source_patch_matrix_ready: bool,
    source_monitor_layout_ready: bool,
    source_apply_board_ready: bool,
    source_keyboard_overlay_ready: bool,
    source_usability_board_ready: bool,
    evidence_ok: bool,
) -> int:
    return score_ladder(
        (
            real_world_score_unlock
            and source_decision_preview_ready
            and source_patch_matrix_ready
            and source_monitor_layout_ready
            and source_apply_board_ready
            and source_keyboard_overlay_ready
            and evidence_ok,
            96,
        ),
        (
            source_decision_preview_ready
            and source_patch_matrix_ready
            and source_monitor_layout_ready
            and source_apply_board_ready
            and source_keyboard_overlay_ready
            and source_usability_board_ready
            and evidence_ok,
            91,
        ),
        (
            source_decision_preview_ready
            and source_patch_matrix_ready
            and source_monitor_layout_ready
            and source_apply_board_ready
            and source_keyboard_overlay_ready
            and evidence_ok,
            90,
        ),
        (
            source_decision_preview_ready
            and source_patch_matrix_ready
            and source_monitor_layout_ready
            and source_apply_board_ready
            and evidence_ok,
            89,
        ),
        (
            source_decision_preview_ready
            and source_patch_matrix_ready
            and source_monitor_layout_ready
            and evidence_ok,
            86,
        ),
        (source_decision_preview_ready and source_patch_matrix_ready and evidence_ok, 84),
        (source_decision_preview_ready and evidence_ok, 81),
        (evidence_ok, 78),
        default=62,
    )


def score_storyline(
    *,
    magnetic_actions_ready: bool,
    magnetic_ready: bool,
    connected_clip_contract_ready: bool,
    role_lane_contract_ready: bool,
    visual_feedback_contract_ready: bool,
    audition_contract_ready: bool,
    storyline_gesture_polish_ready: bool,
    role_filter_panel_ready: bool,
    cross_row_anchor_ui_ready: bool,
    audition_card_model_ready: bool,
    magnetic_drag_visual_language_ready: bool,
    connected_issue_count: int,
    audition_issue_count: int,
) -> int:
    no_issues = int(connected_issue_count) == 0 and int(audition_issue_count) == 0
    polished_visuals = (
        role_filter_panel_ready
        and cross_row_anchor_ui_ready
        and audition_card_model_ready
        and magnetic_drag_visual_language_ready
        and no_issues
    )
    return score_ladder(
        (
            magnetic_actions_ready
            and connected_clip_contract_ready
            and role_lane_contract_ready
            and visual_feedback_contract_ready
            and audition_contract_ready
            and storyline_gesture_polish_ready
            and polished_visuals,
            93,
        ),
        (
            magnetic_actions_ready
            and connected_clip_contract_ready
            and role_lane_contract_ready
            and visual_feedback_contract_ready
            and audition_contract_ready
            and polished_visuals,
            91,
        ),
        (
            magnetic_actions_ready
            and magnetic_ready
            and connected_clip_contract_ready
            and role_lane_contract_ready
            and visual_feedback_contract_ready
            and audition_contract_ready
            and no_issues,
            87,
        ),
        (
            magnetic_actions_ready
            and connected_clip_contract_ready
            and role_lane_contract_ready
            and visual_feedback_contract_ready
            and audition_contract_ready,
            85,
        ),
        (
            magnetic_actions_ready
            and connected_clip_contract_ready
            and role_lane_contract_ready
            and audition_contract_ready,
            84,
        ),
        (magnetic_actions_ready and connected_clip_contract_ready, 83),
        (magnetic_actions_ready, 81),
        default=62,
    )


def score_multicam(
    *,
    multicam_workbench_ready: bool,
    multicam_angle_bins_ready: bool,
    multicam_tile_board_ready: bool,
    multicam_review_board_ready: bool,
    multicam_live_dashboard_ready: bool,
    multicam_sync_quality_board_ready: bool,
    multicam_waveform_sync_board_ready: bool,
    multicam_export_parity_board_ready: bool,
    multicam_export_handoff_ready: bool,
    evidence_ok: bool,
) -> int:
    return score_ladder(
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_review_board_ready
            and multicam_live_dashboard_ready
            and multicam_sync_quality_board_ready
            and multicam_waveform_sync_board_ready
            and multicam_export_parity_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            92,
        ),
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_review_board_ready
            and multicam_live_dashboard_ready
            and multicam_sync_quality_board_ready
            and multicam_waveform_sync_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            90,
        ),
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_review_board_ready
            and multicam_sync_quality_board_ready
            and multicam_waveform_sync_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            89,
        ),
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_review_board_ready
            and multicam_sync_quality_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            88,
        ),
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_review_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            87,
        ),
        (
            multicam_workbench_ready
            and multicam_angle_bins_ready
            and multicam_tile_board_ready
            and multicam_export_handoff_ready
            and evidence_ok,
            84,
        ),
        (multicam_workbench_ready and multicam_angle_bins_ready and evidence_ok, 80),
        (multicam_workbench_ready and evidence_ok, 76),
        (evidence_ok, 72),
        default=18,
    )


def score_proxy_media_management(
    *,
    proxy_plan_ready: bool,
    proxy_health_ready: bool,
    proxy_review_ready: bool,
    proxy_regeneration_board_ready: bool,
    proxy_conflict_board_ready: bool,
    proxy_safe_background_regeneration_ready: bool,
    proxy_search_filter_ready: bool,
    proxy_metadata_columns_ready: bool,
    proxy_apply_review_ready: bool,
    evidence_ok: bool,
    has_media_pool: bool,
) -> int:
    return score_ladder(
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and proxy_conflict_board_ready
            and proxy_safe_background_regeneration_ready
            and proxy_search_filter_ready
            and proxy_metadata_columns_ready
            and proxy_apply_review_ready
            and evidence_ok,
            91,
        ),
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and proxy_conflict_board_ready
            and proxy_safe_background_regeneration_ready
            and proxy_search_filter_ready
            and proxy_metadata_columns_ready
            and evidence_ok,
            89,
        ),
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and proxy_conflict_board_ready
            and proxy_safe_background_regeneration_ready
            and evidence_ok,
            88,
        ),
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and proxy_search_filter_ready
            and proxy_metadata_columns_ready
            and evidence_ok,
            87,
        ),
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and proxy_safe_background_regeneration_ready
            and evidence_ok,
            87,
        ),
        (
            proxy_plan_ready
            and proxy_health_ready
            and proxy_review_ready
            and proxy_regeneration_board_ready
            and evidence_ok,
            86,
        ),
        (proxy_plan_ready and proxy_health_ready and proxy_review_ready and evidence_ok, 84),
        (proxy_plan_ready and proxy_health_ready and evidence_ok, 82),
        (proxy_plan_ready and evidence_ok, 78),
        (evidence_ok, 72),
        default=55 if has_media_pool else 42,
    )


def score_conform_project_bin(
    *,
    project_bin_batch_ready: bool,
    project_bin_conform_ready: bool,
    project_bin_review_board_ready: bool,
    project_bin_conform_apply_review_ready: bool,
    project_bin_offline_browser_ready: bool,
    project_bin_relink_candidate_board_ready: bool,
    project_bin_search_filter_ready: bool,
    project_bin_metadata_columns_ready: bool,
    evidence_ok: bool,
    has_project: bool,
) -> int:
    return score_ladder(
        (
            project_bin_batch_ready
            and project_bin_conform_ready
            and project_bin_review_board_ready
            and project_bin_conform_apply_review_ready
            and project_bin_offline_browser_ready
            and project_bin_relink_candidate_board_ready
            and project_bin_search_filter_ready
            and project_bin_metadata_columns_ready
            and evidence_ok,
            91,
        ),
        (
            project_bin_batch_ready
            and project_bin_conform_ready
            and project_bin_review_board_ready
            and project_bin_offline_browser_ready
            and project_bin_relink_candidate_board_ready
            and project_bin_search_filter_ready
            and project_bin_metadata_columns_ready
            and evidence_ok,
            89,
        ),
        (
            project_bin_batch_ready
            and project_bin_conform_ready
            and project_bin_review_board_ready
            and project_bin_offline_browser_ready
            and evidence_ok,
            87,
        ),
        (project_bin_batch_ready and project_bin_conform_ready and project_bin_review_board_ready and evidence_ok, 84),
        (project_bin_batch_ready and project_bin_conform_ready and evidence_ok, 80),
        (project_bin_batch_ready and evidence_ok, 77),
        (evidence_ok, 74),
        default=48 if has_project else 36,
    )


def score_undo_edge_case_qa(
    *,
    timeline_fuzzer_ready: bool,
    undo_health_ready: bool,
    undo_review_board_ready: bool,
    undo_recovery_playbook_ready: bool,
    undo_stability_dashboard_ready: bool,
    undo_long_session_plan_ready: bool,
    evidence_ok: bool,
) -> int:
    return score_ladder(
        (
            timeline_fuzzer_ready
            and undo_health_ready
            and undo_review_board_ready
            and undo_recovery_playbook_ready
            and undo_stability_dashboard_ready
            and undo_long_session_plan_ready
            and evidence_ok,
            91,
        ),
        (
            timeline_fuzzer_ready
            and undo_health_ready
            and undo_review_board_ready
            and undo_recovery_playbook_ready
            and undo_stability_dashboard_ready
            and evidence_ok,
            89,
        ),
        (
            timeline_fuzzer_ready
            and undo_health_ready
            and undo_review_board_ready
            and undo_recovery_playbook_ready
            and evidence_ok,
            87,
        ),
        (timeline_fuzzer_ready and undo_health_ready and undo_review_board_ready and evidence_ok, 84),
        (timeline_fuzzer_ready and undo_health_ready and evidence_ok, 82),
        (timeline_fuzzer_ready and evidence_ok, 78),
        (evidence_ok, 72),
        default=58,
    )


def score_long_large_project_validation(
    *,
    real_project_corpus_ready: bool,
    real_world_score_unlock: bool,
    long_project_stress_ok: bool,
    real_project_corpus_intake_ready: bool,
    real_project_corpus_collection_kit_ready: bool,
    real_project_corpus_workbench_ready: bool,
    real_project_corpus_validation_plan_ready: bool,
    evidence_ok: bool,
    project_duration_ms: int,
) -> int:
    return score_ladder(
        (real_project_corpus_ready and real_world_score_unlock, 96),
        (real_project_corpus_ready, 84),
        (
            long_project_stress_ok
            and real_project_corpus_intake_ready
            and real_project_corpus_collection_kit_ready
            and real_project_corpus_workbench_ready
            and real_project_corpus_validation_plan_ready,
            86,
        ),
        (
            long_project_stress_ok
            and real_project_corpus_intake_ready
            and real_project_corpus_collection_kit_ready
            and real_project_corpus_validation_plan_ready,
            83,
        ),
        (long_project_stress_ok and real_project_corpus_intake_ready and real_project_corpus_collection_kit_ready, 82),
        (long_project_stress_ok and real_project_corpus_intake_ready, 80),
        (long_project_stress_ok, 78),
        (evidence_ok, 72),
        default=44 if int(project_duration_ms) >= 60_000 else 30,
    )


__all__ = [
    "build_score_breakdown",
    "score_conform_project_bin",
    "score_core_nle_actions",
    "score_ladder",
    "score_long_large_project_validation",
    "score_multicam",
    "score_proxy_media_management",
    "score_source_record_monitor",
    "score_storyline",
    "score_undo_edge_case_qa",
]
