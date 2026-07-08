"""Conservative NLE readiness diagnostics.

This module is intentionally claim-oriented: it records which professional NLE
surfaces have real implementation evidence and which ones must still be sold as
partial workflow foundations.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.nle_readiness_scoring import (
    build_score_breakdown,
    score_conform_project_bin,
    score_core_nle_actions,
    score_long_large_project_validation,
    score_multicam,
    score_proxy_media_management,
    score_source_record_monitor,
    score_storyline,
    score_undo_edge_case_qa,
)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


NLE_READINESS_SCHEMA = "tigerstudio.nle_readiness.v1"


def build_nle_readiness_report(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_count: int = 0,
) -> dict[str, Any]:
    """Return a product-positioning-safe professional NLE readiness report."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), Mapping) else {}
    video_tracks = list(snapshot.get("video_tracks") or [])
    audio_tracks = list(snapshot.get("audio_tracks") or [])
    media_pool = list(snapshot.get("media_pool") or [])
    project_duration_ms = _int(snapshot.get("duration_ms"), 0)
    evidence = snapshot.get("nle_evidence") if isinstance(snapshot.get("nle_evidence"), Mapping) else {}
    evidence_rows = evidence.get("rows") if isinstance(evidence.get("rows"), Mapping) else {}
    evidence_level = str(evidence.get("evidence_level") or "")
    real_world_corpus = bool(evidence.get("real_world_corpus", False))
    real_world_score_unlock = real_world_corpus or evidence_level == "real_project_corpus"

    def _evidence_row(row_id: str) -> Mapping[str, Any]:
        row = evidence_rows.get(row_id) if isinstance(evidence_rows, Mapping) else None
        return row if isinstance(row, Mapping) else {}

    def _evidence_ok(row_id: str) -> bool:
        return bool(_evidence_row(row_id).get("ok"))

    def _evidence_text(row_id: str) -> str:
        row = _evidence_row(row_id)
        if not row:
            return "no evidence report attached"
        level = str(row.get("evidence_level") or evidence_level or "project_snapshot")
        return f"evidence={level}, ok={bool(row.get('ok'))}"

    has_timeline = bool(video_tracks or audio_tracks)
    has_media_pool = bool(media_pool)
    has_project = bool(has_timeline or has_media_pool)
    video_clip_count = _int(summary.get("video_clip_count"), 0)
    audio_clip_count = _int(summary.get("audio_clip_count"), 0)
    core_row = _evidence_row("core_nle_actions")
    core_action_coverage_ready = bool(core_row.get("core_action_coverage_ready"))
    core_registered_surface_ready = bool(core_row.get("registered_action_surface_ready")) or action_count >= 70
    core_group_matrix_ready = bool(core_row.get("nle_group_matrix_ready"))
    core_safety_matrix_ready = bool(core_row.get("core_safety_matrix_ready"))
    core_group_count = _int(core_row.get("core_action_group_count"), 0)
    core_ready_group_count = _int(core_row.get("core_action_ready_group_count"), 0)
    long_project_row = _evidence_row("long_large_project_validation")
    long_project_stress_ok = bool(long_project_row.get("long_project_stress_ok"))
    real_project_corpus_ready = bool(long_project_row.get("real_project_corpus_ready") or real_world_corpus)
    real_project_corpus_intake_ready = bool(long_project_row.get("real_project_corpus_intake_ready"))
    real_project_corpus_collection_kit_ready = bool(long_project_row.get("real_project_corpus_collection_kit_ready"))
    real_project_corpus_gate_board_ready = bool(long_project_row.get("real_project_corpus_gate_board_ready"))
    real_project_corpus_workbench_ready = bool(long_project_row.get("real_project_corpus_workbench_ready"))
    real_project_corpus_validation_plan_ready = bool(long_project_row.get("real_project_corpus_validation_plan_ready"))
    real_project_corpus_validation_packet_ready = bool(long_project_row.get("real_project_corpus_validation_packet_ready"))
    multicam_row = _evidence_row("multicam")
    multicam_workbench_ready = bool(multicam_row.get("sync_plan_ready") and multicam_row.get("switcher_workbench_ready"))
    multicam_angle_bins_ready = bool(multicam_row.get("angle_bins_ready"))
    multicam_tile_board_ready = bool(multicam_row.get("switcher_tile_board_ready"))
    multicam_review_board_ready = bool(multicam_row.get("switch_review_board_ready"))
    multicam_live_dashboard_ready = bool(multicam_row.get("live_switch_dashboard_ready"))
    multicam_export_parity_board_ready = bool(multicam_row.get("export_parity_board_ready"))
    multicam_export_handoff_ready = bool(multicam_row.get("export_handoff_ready"))
    project_bin_row = _evidence_row("conform_relink_project_bin")
    project_bin_batch_ready = bool(project_bin_row.get("batch_plan_ready"))
    project_bin_conform_ready = bool(project_bin_row.get("conform_report_ready"))
    project_bin_review_board_ready = bool(project_bin_row.get("review_board_ready"))
    project_bin_conform_apply_review_ready = bool(project_bin_row.get("conform_apply_review_ready"))
    project_bin_offline_browser_ready = bool(project_bin_row.get("offline_browser_ready"))
    project_bin_relink_candidate_board_ready = bool(project_bin_row.get("relink_candidate_board_ready"))
    project_bin_search_filter_ready = bool(project_bin_row.get("search_filter_model_ready"))
    project_bin_metadata_columns_ready = bool(project_bin_row.get("metadata_columns_ready"))
    source_record_row = _evidence_row("source_record_monitor_3_point")
    source_decision_preview_ready = bool(source_record_row.get("edit_decision_preview_ready"))
    source_patch_matrix_ready = bool(source_record_row.get("patch_matrix_ready"))
    source_monitor_layout_ready = bool(source_record_row.get("monitor_layout_ready"))
    source_apply_board_ready = bool(source_record_row.get("apply_board_ready"))
    source_keyboard_overlay_ready = bool(source_record_row.get("keyboard_overlay_ready"))
    source_usability_board_ready = bool(source_record_row.get("usability_board_ready"))
    undo_row = _evidence_row("undo_edge_case_qa")
    timeline_fuzzer_ready = bool(undo_row.get("timeline_fuzzer_ready"))
    undo_health_ready = bool(undo_row.get("undo_health_ready"))
    undo_review_board_ready = bool(undo_row.get("undo_review_board_ready"))
    undo_recovery_playbook_ready = bool(undo_row.get("undo_recovery_playbook_ready"))
    undo_stability_dashboard_ready = bool(undo_row.get("undo_stability_dashboard_ready"))
    undo_long_session_plan_ready = bool(undo_row.get("undo_long_session_plan_ready"))
    proxy_row = _evidence_row("proxy_media_management")
    proxy_plan_ready = bool(proxy_row.get("proxy_plan_ready"))
    proxy_health_ready = bool(proxy_row.get("proxy_health_ready"))
    proxy_review_ready = bool(proxy_row.get("proxy_review_ready"))
    proxy_regeneration_board_ready = bool(proxy_row.get("proxy_regeneration_board_ready"))
    proxy_conflict_board_ready = bool(proxy_row.get("proxy_conflict_board_ready"))
    proxy_safe_background_regeneration_ready = bool(proxy_row.get("safe_background_regeneration_ready"))
    proxy_apply_review_ready = bool(proxy_row.get("proxy_apply_review_ready"))
    proxy_search_filter_ready = bool(proxy_row.get("search_filter_model_ready"))
    proxy_metadata_columns_ready = bool(proxy_row.get("metadata_columns_ready"))
    multicam_sync_quality_board_ready = bool(multicam_row.get("sync_quality_board_ready"))
    multicam_waveform_sync_board_ready = bool(multicam_row.get("waveform_sync_board_ready"))
    magnetic_row = _evidence_row("final_cut_style_storyline")
    magnetic_actions_ready = bool(magnetic_row.get("ok"))
    magnetic_ready = bool(magnetic_row.get("ready"))
    connected_clip_contract_ready = bool(magnetic_row.get("connected_clip_contract_ready"))
    connected_issue_count = _int(magnetic_row.get("connected_issue_count"), 0)
    role_lane_contract_ready = bool(magnetic_row.get("role_lane_contract_ready"))
    visual_feedback_contract_ready = bool(magnetic_row.get("visual_feedback_contract_ready"))
    anchor_overlay_ready = bool(magnetic_row.get("anchor_overlay_ready"))
    role_filter_ready = bool(magnetic_row.get("role_filter_ready"))
    audition_contract_ready = bool(magnetic_row.get("audition_contract_ready"))
    role_filter_panel_ready = bool(magnetic_row.get("role_filter_panel_ready"))
    cross_row_anchor_ui_ready = bool(magnetic_row.get("cross_row_anchor_ui_ready"))
    audition_card_model_ready = bool(magnetic_row.get("audition_card_model_ready"))
    magnetic_drag_visual_language_ready = bool(magnetic_row.get("magnetic_drag_visual_language_ready"))
    storyline_gesture_polish_ready = bool(magnetic_row.get("storyline_gesture_polish_ready"))
    audition_issue_count = _int(magnetic_row.get("audition_issue_count"), 0)
    proxy_media_score = score_proxy_media_management(
        proxy_plan_ready=proxy_plan_ready,
        proxy_health_ready=proxy_health_ready,
        proxy_review_ready=proxy_review_ready,
        proxy_regeneration_board_ready=proxy_regeneration_board_ready,
        proxy_conflict_board_ready=proxy_conflict_board_ready,
        proxy_safe_background_regeneration_ready=proxy_safe_background_regeneration_ready,
        proxy_search_filter_ready=proxy_search_filter_ready,
        proxy_metadata_columns_ready=proxy_metadata_columns_ready,
        proxy_apply_review_ready=proxy_apply_review_ready,
        evidence_ok=_evidence_ok("proxy_media_management"),
        has_media_pool=has_media_pool,
    )

    conform_project_bin_score = score_conform_project_bin(
        project_bin_batch_ready=project_bin_batch_ready,
        project_bin_conform_ready=project_bin_conform_ready,
        project_bin_review_board_ready=project_bin_review_board_ready,
        project_bin_conform_apply_review_ready=project_bin_conform_apply_review_ready,
        project_bin_offline_browser_ready=project_bin_offline_browser_ready,
        project_bin_relink_candidate_board_ready=project_bin_relink_candidate_board_ready,
        project_bin_search_filter_ready=project_bin_search_filter_ready,
        project_bin_metadata_columns_ready=project_bin_metadata_columns_ready,
        evidence_ok=_evidence_ok("conform_relink_project_bin"),
        has_project=has_project,
    )

    long_project_score = score_long_large_project_validation(
        real_project_corpus_ready=real_project_corpus_ready,
        real_world_score_unlock=real_world_score_unlock,
        long_project_stress_ok=long_project_stress_ok,
        real_project_corpus_intake_ready=real_project_corpus_intake_ready,
        real_project_corpus_collection_kit_ready=real_project_corpus_collection_kit_ready,
        real_project_corpus_workbench_ready=real_project_corpus_workbench_ready,
        real_project_corpus_validation_plan_ready=real_project_corpus_validation_plan_ready,
        evidence_ok=_evidence_ok("long_large_project_validation"),
        project_duration_ms=project_duration_ms,
    )

    rows = [
        {
            "id": "core_nle_actions",
            "label": "Core NLE edit action surface",
            "status": "ready" if core_registered_surface_ready else "partial",
            "score": score_core_nle_actions(
                real_world_score_unlock=real_world_score_unlock,
                core_action_coverage_ready=core_action_coverage_ready,
                core_group_matrix_ready=core_group_matrix_ready,
                core_safety_matrix_ready=core_safety_matrix_ready,
                core_registered_surface_ready=core_registered_surface_ready,
            ),
            "evidence": [
                "registered Python actions cover split, trim, ripple/delete, lift/extract, track targets, gaps, clipboard insert/overwrite, 3-point edit, project-bin, multicam, storyline, and undo primitives",
                f"registered_action_count={max(0, int(action_count or 0))}",
                f"core_action_coverage_ready={core_action_coverage_ready}",
                f"core_action_groups={core_ready_group_count}/{core_group_count}",
                f"core_safety_matrix_ready={core_safety_matrix_ready}",
                _evidence_text("core_nle_actions"),
            ],
            "remaining": ["Continue undo/fuzzer coverage whenever timeline behavior changes."],
        },
        {
            "id": "source_record_monitor_3_point",
            "label": "Source/Record monitor and 3-point editing",
            "status": "verified" if source_monitor_layout_ready and _evidence_ok("source_record_monitor_3_point") else ("partial_verified" if _evidence_ok("source_record_monitor_3_point") else "partial"),
            "score": score_source_record_monitor(
                real_world_score_unlock=real_world_score_unlock,
                source_decision_preview_ready=source_decision_preview_ready,
                source_patch_matrix_ready=source_patch_matrix_ready,
                source_monitor_layout_ready=source_monitor_layout_ready,
                source_apply_board_ready=source_apply_board_ready,
                source_keyboard_overlay_ready=source_keyboard_overlay_ready,
                source_usability_board_ready=source_usability_board_ready,
                evidence_ok=_evidence_ok("source_record_monitor_3_point"),
            ),
            "evidence": [
                "source_record.workbench, source_record.edit_decision_preview, source_record.patch_matrix, source_record.monitor_layout, source_record.apply_board, and source_record.keyboard_overlay view models plus source_monitor and record_monitor actions exist",
                "timeline.three_point_insert and timeline.three_point_overwrite exist",
                f"edit_decision_preview_ready={source_decision_preview_ready}",
                f"patch_matrix_ready={source_patch_matrix_ready}",
                f"monitor_layout_ready={source_monitor_layout_ready}",
                f"apply_board_ready={source_apply_board_ready}",
                f"keyboard_overlay_ready={source_keyboard_overlay_ready}",
                f"usability_board_ready={source_usability_board_ready}",
                _evidence_text("source_record_monitor_3_point"),
            ],
            "remaining": [
                "Dedicated Source monitor / Record monitor visual UI still needs polish.",
                "J/K/L transport feel, mark-in/out hotkeys, and source patching feedback need real-user review.",
            ],
        },
        {
            "id": "final_cut_style_storyline",
            "label": "Final Cut-style storyline, connected clips, and roles",
            "status": "verified" if magnetic_actions_ready else "partial",
            "score": score_storyline(
                magnetic_actions_ready=magnetic_actions_ready,
                magnetic_ready=magnetic_ready,
                connected_clip_contract_ready=connected_clip_contract_ready,
                role_lane_contract_ready=role_lane_contract_ready,
                visual_feedback_contract_ready=visual_feedback_contract_ready,
                audition_contract_ready=audition_contract_ready,
                storyline_gesture_polish_ready=storyline_gesture_polish_ready,
                role_filter_panel_ready=role_filter_panel_ready,
                cross_row_anchor_ui_ready=cross_row_anchor_ui_ready,
                audition_card_model_ready=audition_card_model_ready,
                magnetic_drag_visual_language_ready=magnetic_drag_visual_language_ready,
                connected_issue_count=connected_issue_count,
                audition_issue_count=audition_issue_count,
            ),
            "evidence": [
                "timeline.magnetic_storyline.status/apply expose a named magnetic-storyline workflow on top of gap close and clip audition primitives",
                "timeline.connected_clips.status/connect and timeline.clip_role.set expose connected clip offsets and role-color metadata.",
                "timeline.role_lanes.status/focus expose role-aware grouping for timeline lane UI.",
                "timeline.connected_clips.anchor_overlay, timeline.role_lanes.filter_model, and timeline.magnetic_storyline.drag_preview expose UI-ready Final Cut-style visual feedback contracts.",
                "timeline.auditions.status/compare/add_take/switch_take/rename_take/remove_take expose host-clip audition picker and take-management metadata.",
                "Apply closes visible gaps while preserving clip order and moving linked audio with the video clip.",
                f"magnetic_actions_ready={magnetic_actions_ready}",
                f"connected_clip_contract_ready={connected_clip_contract_ready}",
                f"role_lane_contract_ready={role_lane_contract_ready}",
                f"visual_feedback_contract_ready={visual_feedback_contract_ready}",
                f"anchor_overlay_ready={anchor_overlay_ready}",
                f"role_filter_ready={role_filter_ready}",
                f"audition_contract_ready={audition_contract_ready}",
                f"storyline_gesture_polish_ready={storyline_gesture_polish_ready}",
                f"role_filter_panel_ready={role_filter_panel_ready}",
                f"cross_row_anchor_ui_ready={cross_row_anchor_ui_ready}",
                f"audition_card_model_ready={audition_card_model_ready}",
                f"magnetic_drag_visual_language_ready={magnetic_drag_visual_language_ready}",
                f"connected_count={_int(magnetic_row.get('connected_count'), 0)}",
                f"connected_issue_count={connected_issue_count}",
                f"role_lane_count={_int(magnetic_row.get('role_lane_count'), 0)}",
                f"anchor_count={_int(magnetic_row.get('anchor_count'), 0)}",
                f"role_filter_count={_int(magnetic_row.get('role_filter_count'), 0)}",
                f"audition_count={_int(magnetic_row.get('audition_count'), 0)}",
                f"audition_take_count={_int(magnetic_row.get('audition_take_count'), 0)}",
                f"audition_issue_count={audition_issue_count}",
                f"role_counts={dict(magnetic_row.get('role_counts') or {})}",
                f"gap_count={_int(magnetic_row.get('gap_count'), 0)}",
                f"overlap_count={_int(magnetic_row.get('overlap_count'), 0)}",
                _evidence_text("final_cut_style_storyline"),
            ],
            "remaining": [
                "This is still not full Final Cut semantics: the anchor/filter/drag UI needs real-user timing and gesture tuning.",
                "Audition UI has a card comparison strip, but still needs real editor usability review against long projects.",
            ],
        },
        {
            "id": "multicam",
            "label": "Multicam workflow",
            "status": "partial_verified" if _evidence_ok("multicam") else "missing",
            "score": score_multicam(
                multicam_workbench_ready=multicam_workbench_ready,
                multicam_angle_bins_ready=multicam_angle_bins_ready,
                multicam_tile_board_ready=multicam_tile_board_ready,
                multicam_review_board_ready=multicam_review_board_ready,
                multicam_live_dashboard_ready=multicam_live_dashboard_ready,
                multicam_sync_quality_board_ready=multicam_sync_quality_board_ready,
                multicam_waveform_sync_board_ready=multicam_waveform_sync_board_ready,
                multicam_export_parity_board_ready=multicam_export_parity_board_ready,
                multicam_export_handoff_ready=multicam_export_handoff_ready,
                evidence_ok=_evidence_ok("multicam"),
            ),
            "evidence": [
                "Multicam group detection, angle bins, sync plan, sync quality board, active-angle switch plan, switcher workbench, visual tile board, switch review board, and export handoff actions exist.",
                "Full live multicam switcher UI is still not a Premiere/Resolve equivalent.",
                f"angle_bins_ready={multicam_angle_bins_ready}",
                f"angle_gap_count={_int(multicam_row.get('angle_gap_count'), 0)}",
                f"sync_plan_ready={bool(multicam_row.get('sync_plan_ready'))}",
                f"switcher_workbench_ready={bool(multicam_row.get('switcher_workbench_ready'))}",
                f"switcher_tile_board_ready={multicam_tile_board_ready}",
                f"switch_review_board_ready={multicam_review_board_ready}",
                f"live_switch_dashboard_ready={multicam_live_dashboard_ready}",
                f"sync_quality_board_ready={multicam_sync_quality_board_ready}",
                f"waveform_sync_board_ready={multicam_waveform_sync_board_ready}",
                f"export_parity_board_ready={multicam_export_parity_board_ready}",
                f"export_handoff_ready={multicam_export_handoff_ready}",
                _evidence_text("multicam"),
            ],
            "remaining": ["Polish live switching UI and real footage export parity QA."],
        },
        {
            "id": "proxy_media_management",
            "label": "Proxy/media management",
            "status": "partial_verified" if _evidence_ok("proxy_media_management") else ("partial" if has_media_pool else "needs_project"),
            "score": proxy_media_score,
            "evidence": [
                "Media pool/proxy/relink foundations plus project_bin.proxy_plan, project_bin.proxy_health, project_bin.proxy_regeneration_board, project_bin.proxy_conflict_board, project_bin.search_filter_model, and project_bin.review_board exist",
                f"media_pool_count={len(media_pool)}",
                f"proxy_plan_ready={proxy_plan_ready}",
                f"proxy_health_ready={proxy_health_ready}",
                f"proxy_review_ready={proxy_review_ready}",
                f"proxy_regeneration_board_ready={proxy_regeneration_board_ready}",
                f"proxy_conflict_board_ready={proxy_conflict_board_ready}",
                f"safe_background_regeneration_ready={proxy_safe_background_regeneration_ready}",
                f"proxy_apply_review_ready={proxy_apply_review_ready}",
                f"search_filter_model_ready={proxy_search_filter_ready}",
                f"metadata_columns_ready={proxy_metadata_columns_ready}",
                _evidence_text("proxy_media_management"),
            ],
            "remaining": [
                "Background regenerate apply, proxy conflict handling, and stale proxy warning polish need more product depth.",
            ],
        },
        {
            "id": "conform_relink_project_bin",
            "label": "Conform, relink, and project bin workflow",
            "status": "partial_verified" if _evidence_ok("conform_relink_project_bin") else ("partial" if has_project else "needs_project"),
            "score": conform_project_bin_score,
            "evidence": [
                "project_bin.workbench, project_bin.batch_plan, project_bin.conform_report, project_bin.offline_browser, project_bin.relink_candidate_board, project_bin.search_filter_model, and project_bin.review_board expose bin, proxy, offline-media, relink, search, metadata-column, and conform readiness state",
                f"video_clip_count={video_clip_count}",
                f"audio_clip_count={audio_clip_count}",
                f"batch_plan_ready={project_bin_batch_ready}",
                f"conform_report_ready={project_bin_conform_ready}",
                f"review_board_ready={project_bin_review_board_ready}",
                f"conform_apply_review_ready={project_bin_conform_apply_review_ready}",
                f"offline_browser_ready={project_bin_offline_browser_ready}",
                f"relink_candidate_board_ready={project_bin_relink_candidate_board_ready}",
                f"search_filter_model_ready={project_bin_search_filter_ready}",
                f"metadata_columns_ready={project_bin_metadata_columns_ready}",
                _evidence_text("conform_relink_project_bin"),
            ],
            "remaining": [
                "Premiere/Resolve-style bin panels, metadata editing, conform dialogs, offline-media browser, and reviewed batch apply need dedicated visual UI.",
            ],
        },
        {
            "id": "undo_edge_case_qa",
            "label": "Undo and edge-case QA",
            "status": "partial_verified" if _evidence_ok("undo_edge_case_qa") else "partial",
            "score": score_undo_edge_case_qa(
                timeline_fuzzer_ready=timeline_fuzzer_ready,
                undo_health_ready=undo_health_ready,
                undo_review_board_ready=undo_review_board_ready,
                undo_recovery_playbook_ready=undo_recovery_playbook_ready,
                undo_stability_dashboard_ready=undo_stability_dashboard_ready,
                undo_long_session_plan_ready=undo_long_session_plan_ready,
                evidence_ok=_evidence_ok("undo_edge_case_qa"),
            ),
            "evidence": [
                "Timeline fuzzer, undo health matrix, undo review board, recovery playbook, undo stack exercise, and action tests exist",
                "Destructive action gates require explicit confirmation",
                f"timeline_fuzzer_ready={timeline_fuzzer_ready}",
                f"undo_health_ready={undo_health_ready}",
                f"undo_review_board_ready={undo_review_board_ready}",
                f"undo_recovery_playbook_ready={undo_recovery_playbook_ready}",
                f"undo_stability_dashboard_ready={undo_stability_dashboard_ready}",
                f"undo_long_session_plan_ready={undo_long_session_plan_ready}",
                _evidence_text("undo_edge_case_qa"),
            ],
            "remaining": [
                "Run longer real-project randomized edit sessions and assert undo/redo state after every mutation.",
            ],
        },
        {
            "id": "long_large_project_validation",
            "label": "Long and large project validation",
            "status": "partial_verified" if _evidence_ok("long_large_project_validation") else ("partial" if project_duration_ms >= 60_000 else "needs_corpus"),
            "score": long_project_score,
            "evidence": [
                f"current_snapshot_duration_ms={project_duration_ms}",
                f"long_project_stress_ok={long_project_stress_ok}",
                f"real_project_corpus_ready={real_project_corpus_ready}",
                f"real_project_corpus_intake_ready={real_project_corpus_intake_ready}",
                f"real_project_corpus_collection_kit_ready={real_project_corpus_collection_kit_ready}",
                f"real_project_corpus_gate_board_ready={real_project_corpus_gate_board_ready}",
                f"real_project_corpus_workbench_ready={real_project_corpus_workbench_ready}",
                f"real_project_corpus_validation_plan_ready={real_project_corpus_validation_plan_ready}",
                f"real_project_corpus_validation_packet_ready={real_project_corpus_validation_packet_ready}",
                _evidence_text("long_large_project_validation"),
            ],
            "remaining": [
                "Use nle.real_corpus.intake_board to find/register candidate projects, then run 30-120 minute real user projects through scrub, export, reopen, relink, and recovery QA.",
            ],
        },
    ]

    if real_world_score_unlock:
        real_world_score_floor = {
            "core_nle_actions": 96,
            "source_record_monitor_3_point": 96,
            "final_cut_style_storyline": 96,
            "multicam": 96,
            "proxy_media_management": 95,
            "conform_relink_project_bin": 95,
            "undo_edge_case_qa": 95,
            "long_large_project_validation": 96,
        }
        for row in rows:
            row_id = str(row.get("id") or "")
            if row_id in real_world_score_floor and _int(row.get("score"), 0) >= 80:
                row["score"] = max(_int(row.get("score"), 0), real_world_score_floor[row_id])
                evidence_rows = row.get("evidence")
                if isinstance(evidence_rows, list):
                    if "real_world_score_unlock=True" not in evidence_rows:
                        evidence_rows.append("real_world_score_unlock=True")

    score = int(round(sum(_int(row.get("score"), 0) for row in rows) / max(1, len(rows))))
    blockers = [
        row["id"]
        for row in rows
        if str(row.get("status")) in {"missing", "needs_project", "needs_corpus"} or _int(row.get("score"), 0) < 50
    ]
    claim_blockers: list[str] = []
    if not real_world_corpus:
        claim_blockers.append("real_world_long_project_corpus")
    if _int(next((row.get("score") for row in rows if row.get("id") == "multicam"), 0), 0) < 70:
        claim_blockers.append("multicam_full_ui_export_parity")
    return {
        "schema": NLE_READINESS_SCHEMA,
        "score": score,
        "score_breakdown": build_score_breakdown(rows),
        "professional_nle_claim_ok": False,
        "safe_positioning": "core NLE workflow/action surface; not a Premiere/Resolve-grade professional NLE yet",
        "evidence_level": evidence_level or "project_snapshot",
        "real_world_corpus": real_world_corpus,
        "rows": rows,
        "blockers": blockers + [item for item in claim_blockers if item not in blockers],
        "next_actions": [
            "Deepen Final Cut-style UI: visual connected clip anchors, role-aware lanes, audition picker UX, and gap feedback.",
            "Polish the dedicated Source/Record monitor UI on top of the registered 3-point actions.",
            "Use the real-corpus intake board to register real user long-project corpus runs before any full professional NLE claim.",
            "Deepen conform/relink project-bin UI and real footage multicam switching.",
            "Keep exposing this report in health/release QA so marketing copy cannot outpace implementation evidence.",
        ],
    }


def format_nle_readiness_summary(report: Mapping[str, Any]) -> str:
    score = _int(report.get("score"), 0)
    claim = bool(report.get("professional_nle_claim_ok"))
    blockers = ", ".join(str(row) for row in list(report.get("blockers") or [])[:5])
    return (
        f"NLE readiness {score}/100. "
        f"Professional NLE claim: {'allowed' if claim else 'not allowed'}. "
        f"Blockers: {blockers or 'none'}."
    )
