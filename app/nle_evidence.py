"""Evidence helpers for conservative NLE readiness scoring."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _action_set(action_ids: Sequence[str] | None) -> set[str]:
    return {str(action_id) for action_id in (action_ids or ()) if str(action_id or "").strip()}


def _clips(snapshot: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for track in list(snapshot.get(key) or []):
        if not isinstance(track, Mapping):
            continue
        for clip in list(track.get("clips") or []):
            if isinstance(clip, Mapping):
                rows.append(clip)
    return rows


def _snapshot_video_tracks(snapshot: Mapping[str, Any]) -> list[Any]:
    rows: list[Any] = []
    for track in list(snapshot.get("video_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        rows.append(
            type(
                "_SnapshotTrack",
                (),
                {
                    "id": track.get("id"),
                    "locked": track.get("locked", False),
                    "clips": [
                        type("_SnapshotClip", (), dict(clip))()
                        for clip in list(track.get("clips") or [])
                        if isinstance(clip, Mapping)
                    ],
                },
            )()
        )
    return rows


def _media_kind_counts(media_pool: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in media_pool:
        kind = str(item.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def build_nle_evidence_report(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Sequence[str] | None = None,
    evidence_level: str = "project_snapshot",
) -> dict[str, Any]:
    """Return feature evidence without claiming Premiere/Resolve parity.

    The report can be generated from a real editor snapshot or from the
    synthetic validation corpus used by QA.  Synthetic evidence is useful for
    guarding action contracts, but it deliberately keeps the professional NLE
    claim blocked until real long projects are supplied.
    """

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), Mapping) else {}
    media_pool = [row for row in list(snapshot.get("media_pool") or []) if isinstance(row, Mapping)]
    video_clips = _clips(snapshot, "video_tracks")
    audio_clips = _clips(snapshot, "audio_tracks")
    action_set = _action_set(action_ids)

    duration_ms = _int(snapshot.get("duration_ms"), 0)
    video_count = _int(summary.get("video_clip_count"), len(video_clips))
    audio_count = _int(summary.get("audio_clip_count"), len(audio_clips))
    media_count = _int(summary.get("media_pool_count"), len(media_pool))
    kind_counts = _media_kind_counts(media_pool)
    proxy_ready = sum(1 for row in media_pool if str(row.get("proxy_state") or "").lower() in {"ready", "active", "fresh"})
    relink_candidates = sum(1 for row in media_pool if _int(row.get("relink_candidate_count"), 0) > 0)

    source_record_actions = {
        "source_record.workbench",
        "source_record.edit_decision_preview",
        "source_record.usability_board",
        "source_monitor.load_media",
        "source_monitor.set_in",
        "source_monitor.set_out",
        "record_monitor.set_in",
        "record_monitor.set_out",
        "source_record.patch_matrix",
        "source_record.monitor_layout",
        "source_record.apply_board",
        "source_record.keyboard_overlay",
        "timeline.three_point_insert",
        "timeline.three_point_overwrite",
    }
    edit_actions = {
        "timeline.split",
        "timeline.trim_to_playhead",
        "timeline.ripple_delete",
        "timeline.lift",
        "timeline.extract",
        "timeline.insert_clipboard",
        "timeline.overwrite_clipboard",
        "timeline.cleanup_edges",
        "timeline.undo_health",
        "timeline.undo_review_board",
        "timeline.undo_recovery_playbook",
        "timeline.undo_stability_dashboard",
        "timeline.undo_long_session_plan",
    }
    core_nle_actions = {
        "timeline.core_action_coverage",
        "timeline.nle_core_safety_matrix",
    }
    multicam_actions = {
        "timeline.multicam.summary",
        "timeline.multicam.create_group",
        "timeline.multicam.sync_plan",
        "timeline.multicam.switch_plan",
        "timeline.multicam.angle_bins",
        "timeline.multicam.set_active_angle",
        "timeline.multicam.switcher_workbench",
        "timeline.multicam.tile_board",
        "timeline.multicam.review_board",
        "timeline.multicam.live_switch_dashboard",
        "timeline.multicam.sync_quality_board",
        "timeline.multicam.waveform_sync_board",
        "timeline.multicam.export_parity_board",
        "timeline.multicam.export_handoff",
    }
    project_bin_actions = {
        "project_bin.workbench",
        "project_bin.batch_plan",
        "project_bin.conform_report",
        "project_bin.review_board",
        "project_bin.conform_apply_review_board",
        "project_bin.offline_browser",
        "project_bin.relink_candidate_board",
        "project_bin.proxy_regeneration_board",
        "project_bin.proxy_conflict_board",
        "project_bin.proxy_apply_review_board",
        "project_bin.search_filter_model",
        "project_bin.proxy_plan",
        "project_bin.proxy_health",
        "media.summary",
        "project.snapshot",
    }
    proxy_actions = {
        "project_bin.proxy_plan",
        "project_bin.proxy_health",
        "project_bin.review_board",
        "project_bin.proxy_regeneration_board",
        "project_bin.proxy_conflict_board",
        "project_bin.proxy_apply_review_board",
        "project_bin.search_filter_model",
        "media.summary",
        "project.snapshot",
    }
    magnetic_actions = {
        "timeline.magnetic_storyline.status",
        "timeline.magnetic_storyline.apply",
        "timeline.close_all_gaps",
        "timeline.play_clip_range",
    }
    connected_clip_actions = {
        "timeline.connected_clips.status",
        "timeline.connected_clips.connect",
        "timeline.clip_role.set",
        "timeline.role_colors.status",
    }
    role_lane_actions = {
        "timeline.role_lanes.status",
        "timeline.role_lanes.focus",
    }
    visual_feedback_actions = {
        "timeline.connected_clips.anchor_overlay",
        "timeline.role_lanes.filter_model",
        "timeline.magnetic_storyline.drag_preview",
        "timeline.storyline_gesture_polish_board",
    }
    audition_actions = {
        "timeline.auditions.status",
        "timeline.audition.compare",
        "timeline.audition.add_take",
        "timeline.audition.switch_take",
        "timeline.audition.rename_take",
        "timeline.audition.remove_take",
    }

    multicam_angles = {
        str(row.get("camera_id") or row.get("angle") or row.get("source_path") or row.get("name") or "")
        for row in video_clips
    }
    multicam_angles.discard("")
    try:
        from app.nle_core_actions import build_core_nle_action_coverage

        core_action_coverage = build_core_nle_action_coverage(action_set)
    except Exception:
        core_action_coverage = {"ready": False, "summary": {}, "readiness": {}, "groups": []}
    try:
        from app.nle_multicam import multicam_contract_evidence

        multicam_contract = multicam_contract_evidence(snapshot, action_ids=tuple(action_set))
    except Exception:
        multicam_contract = {
            "ok": False,
            "required_actions": sorted(multicam_actions),
            "available_actions": sorted(multicam_actions & action_set),
            "angle_count": len(multicam_angles),
            "switch_count": 0,
            "sync_plan_ready": False,
            "sync_methods": [],
            "angle_bins_ready": False,
            "angle_bin_count": 0,
            "angle_gap_count": 0,
            "switcher_workbench_ready": False,
            "export_handoff_ready": False,
            "group_count": 0,
        }
    try:
        from app.nle_source_record import source_record_contract_evidence

        source_record_contract = source_record_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        source_record_contract = {
            "ok": False,
            "required_actions": sorted(source_record_actions),
            "available_actions": sorted(source_record_actions & action_set),
            "edit_decision_preview_ready": False,
        }
    try:
        from app.nle_project_bin import (
            build_project_bin_proxy_conflict_board,
            build_project_bin_proxy_health_board,
            build_project_bin_proxy_plan,
            project_bin_contract_evidence,
        )

        project_bin_contract = project_bin_contract_evidence(snapshot, action_ids=tuple(action_set))
        proxy_plan = build_project_bin_proxy_plan(snapshot)
        proxy_health = build_project_bin_proxy_health_board(snapshot)
        proxy_conflicts = build_project_bin_proxy_conflict_board(snapshot)
    except Exception:
        project_bin_contract = {
            "ok": False,
            "required_actions": sorted(project_bin_actions),
            "available_actions": sorted(project_bin_actions & action_set),
            "media_count": media_count,
            "bin_count": 0,
            "offline_count": 0,
            "relink_candidate_count": relink_candidates,
            "batch_plan_ready": False,
            "batch_operation_count": 0,
            "batch_operation_counts": {},
            "conform_report_ready": False,
            "conform_report_summary": {},
        }
        proxy_plan = {
            "ready": False,
            "proxy_ready": False,
            "summary": {},
            "commands": {},
            "readiness": {},
        }
        proxy_health = {
            "ready": False,
            "summary": {},
            "commands": {},
            "readiness": {},
        }
        proxy_conflicts = {
            "ready": False,
            "summary": {},
            "commands": {},
            "readiness": {},
        }
    long_stress = snapshot.get("long_project_stress") if isinstance(snapshot.get("long_project_stress"), Mapping) else {}
    long_stress_summary = long_stress.get("summary") if isinstance(long_stress.get("summary"), Mapping) else {}
    long_stress_ok = bool(long_stress.get("ok"))
    timeline_stress = snapshot.get("nle_timeline_stress") if isinstance(snapshot.get("nle_timeline_stress"), Mapping) else {}
    timeline_stress_summary = timeline_stress.get("summary") if isinstance(timeline_stress.get("summary"), Mapping) else {}
    timeline_stress_ok = bool(timeline_stress.get("ok") or timeline_stress.get("claim_ready"))
    try:
        from app.nle_timeline_stress import (
            build_nle_undo_health_matrix,
            build_nle_undo_recovery_playbook,
            build_nle_undo_review_board,
            build_nle_undo_stability_dashboard,
        )

        undo_health = build_nle_undo_health_matrix(timeline_stress)
        undo_review_board = build_nle_undo_review_board(timeline_stress)
        undo_recovery_playbook = build_nle_undo_recovery_playbook(timeline_stress)
        undo_stability_dashboard = build_nle_undo_stability_dashboard(timeline_stress)
    except Exception:
        undo_health = {"ready": False, "summary": {}, "blockers": []}
        undo_review_board = {"ready": False, "readiness": {}}
        undo_recovery_playbook = {"ready": False, "readiness": {}}
        undo_stability_dashboard = {"ready": False, "readiness": {}, "summary": {}}
    try:
        from app.nle_magnetic_storyline import (
            build_magnetic_storyline_status,
            magnetic_storyline_contract_evidence,
        )

        magnetic_status = build_magnetic_storyline_status(
            [
                type(
                    "_SnapshotTrack",
                    (),
                    {
                        "id": track.get("id"),
                        "locked": track.get("locked", False),
                        "clips": [
                            type("_SnapshotClip", (), dict(clip))()
                            for clip in list(track.get("clips") or [])
                            if isinstance(clip, Mapping)
                        ],
                    },
                )()
                for track in list(snapshot.get("video_tracks") or [])
                if isinstance(track, Mapping)
            ],
        )
        magnetic_contract = magnetic_storyline_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        magnetic_status = {"ready": False, "gap_count": 0, "overlap_count": 0, "track_count": 0}
        magnetic_contract = {
            "ok": False,
            "required_actions": sorted(magnetic_actions),
            "available_actions": sorted(magnetic_actions & action_set),
        }
    try:
        from app.nle_connected_clips import (
            build_connected_clip_status,
            connected_clip_contract_evidence,
        )

        connected_status = build_connected_clip_status(
            [
                type(
                    "_SnapshotTrack",
                    (),
                    {
                        "id": track.get("id"),
                        "locked": track.get("locked", False),
                        "clips": [
                            type("_SnapshotClip", (), dict(clip))()
                            for clip in list(track.get("clips") or [])
                            if isinstance(clip, Mapping)
                        ],
                    },
                )()
                for track in list(snapshot.get("video_tracks") or [])
                if isinstance(track, Mapping)
            ],
        )
        connected_contract = connected_clip_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        connected_status = {
            "ready": False,
            "connected_count": 0,
            "issue_count": 0,
            "role_colors": {"ready": False, "role_counts": {}, "clip_count": 0},
        }
        connected_contract = {
            "ok": False,
            "required_actions": sorted(connected_clip_actions),
            "available_actions": sorted(connected_clip_actions & action_set),
        }
    try:
        from app.nle_auditions import audition_contract_evidence, build_audition_status

        audition_status = build_audition_status(
            [
                type(
                    "_SnapshotTrack",
                    (),
                    {
                        "id": track.get("id"),
                        "locked": track.get("locked", False),
                        "clips": [
                            type("_SnapshotClip", (), dict(clip))()
                            for clip in list(track.get("clips") or [])
                            if isinstance(clip, Mapping)
                        ],
                    },
                )()
                for track in list(snapshot.get("video_tracks") or [])
                if isinstance(track, Mapping)
            ],
        )
        audition_contract = audition_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        audition_status = {"ready": False, "audition_count": 0, "take_count": 0, "issue_count": 0}
        audition_contract = {
            "ok": False,
            "required_actions": sorted(audition_actions),
            "available_actions": sorted(audition_actions & action_set),
        }
    try:
        from app.nle_role_lanes import build_role_lane_status, role_lane_contract_evidence

        role_lane_status = build_role_lane_status(
            _snapshot_video_tracks(snapshot),
        )
        role_lane_contract = role_lane_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        role_lane_status = {"ready": False, "lane_count": 0, "clip_count": 0, "lanes": []}
        role_lane_contract = {
            "ok": False,
            "required_actions": sorted(role_lane_actions),
            "available_actions": sorted(role_lane_actions & action_set),
        }
    try:
        from app.nle_visual_feedback import build_connected_anchor_overlay, build_role_lane_filter_model

        visual_tracks = _snapshot_video_tracks(snapshot)
        anchor_overlay = build_connected_anchor_overlay(visual_tracks)
        role_filter_model = build_role_lane_filter_model(visual_tracks)
        visual_feedback_contract_ready = visual_feedback_actions <= action_set
    except Exception:
        anchor_overlay = {"ready": False, "anchor_count": 0, "issue_count": 0}
        role_filter_model = {"ready": False, "filter_count": 0, "visible_clip_count": 0}
        visual_feedback_contract_ready = False
    try:
        from app.video_editor_nle_role_panel import RoleLaneFilterBar
        from app.video_editor_nle_role_workflow import refresh_nle_role_filter_bar

        role_filter_panel_ready = bool(RoleLaneFilterBar and refresh_nle_role_filter_bar)
    except Exception:
        role_filter_panel_ready = False
    try:
        from app.timeline_connected_anchor_overlay_widget import ConnectedAnchorOverlay

        cross_row_anchor_ui_ready = bool(ConnectedAnchorOverlay)
    except Exception:
        cross_row_anchor_ui_ready = False
    try:
        from app.nle_audition_visuals import build_audition_card_model

        sample_cards = build_audition_card_model({"takes": [{"id": "take_a", "active": True}], "active_take_id": "take_a"})
        audition_card_model_ready = bool(sample_cards.get("schema") == "tigerstudio.nle.audition_card_model.v1")
    except Exception:
        audition_card_model_ready = False
    try:
        from app.timeline_nle_visual_overlay import build_drag_preview_visual_cue

        snap_cue = build_drag_preview_visual_cue("snap")
        blocked_cue = build_drag_preview_visual_cue("blocked")
        magnetic_drag_visual_language_ready = bool(
            _int(snap_cue.get("field_lines"), 0) > 0 and bool(blocked_cue.get("hatch"))
        )
    except Exception:
        magnetic_drag_visual_language_ready = False
    real_corpus = snapshot.get("nle_real_project_corpus") if isinstance(snapshot.get("nle_real_project_corpus"), Mapping) else {}
    real_corpus_summary = real_corpus.get("summary") if isinstance(real_corpus.get("summary"), Mapping) else {}
    real_corpus_thresholds = real_corpus.get("thresholds") if isinstance(real_corpus.get("thresholds"), Mapping) else {}
    real_corpus_requires_validation = bool(real_corpus_thresholds.get("require_validation_evidence", True))
    real_corpus_min_projects = max(1, _int(real_corpus_thresholds.get("min_projects"), 3))
    real_corpus_validation_ready = (
        not real_corpus_requires_validation
        or (
            _int(real_corpus_summary.get("validation_ready_count"), 0) >= real_corpus_min_projects
            and _int(real_corpus_summary.get("validation_failed_required_check_count"), 0) == 0
        )
    )
    real_corpus_metric_ready = bool(real_corpus.get("claim_ready") or real_corpus.get("real_world_corpus"))
    real_corpus_ready = bool(real_corpus_metric_ready and real_corpus_validation_ready)
    real_corpus_intake_ready = "nle.real_corpus.intake_board" in action_set
    real_corpus_collection_kit_ready = "nle.real_corpus.collection_kit" in action_set
    real_corpus_gate_board_ready = "nle.real_corpus.gate_board" in action_set
    real_corpus_workbench_ready = "nle.real_corpus.workbench" in action_set
    real_corpus_validation_plan_ready = "nle.real_corpus.validation_plan" in action_set
    real_corpus_validation_packet_ready = "nle.real_corpus.validation_packet" in action_set
    try:
        from app.nle_polish_boards import (
            build_conform_apply_review_board,
            build_multicam_export_parity_board,
            build_nle_core_safety_matrix,
            build_proxy_apply_review_board,
            build_source_record_usability_board,
            build_storyline_gesture_polish_board,
            build_undo_long_session_plan,
        )

        core_safety = build_nle_core_safety_matrix(action_ids=tuple(action_set))
        source_usability = build_source_record_usability_board(action_ids=tuple(action_set))
        multicam_parity = build_multicam_export_parity_board(snapshot, action_ids=tuple(action_set))
        proxy_apply = build_proxy_apply_review_board(snapshot)
        conform_apply = build_conform_apply_review_board(snapshot)
        undo_long_session = build_undo_long_session_plan(action_ids=tuple(action_set))
        storyline_polish = build_storyline_gesture_polish_board(action_ids=tuple(action_set))
    except Exception:
        core_safety = {"ready": False, "readiness": {}}
        source_usability = {"ready": False, "readiness": {}}
        multicam_parity = {"ready": False, "readiness": {}}
        proxy_apply = {"ready": False, "readiness": {}}
        conform_apply = {"ready": False, "readiness": {}}
        undo_long_session = {"ready": False, "readiness": {}}
        storyline_polish = {"ready": False, "readiness": {}}

    rows = {
        "core_nle_actions": {
            "ok": bool((core_action_coverage.get("readiness") or {}).get("core_action_coverage_ready"))
            and core_nle_actions <= action_set,
            "evidence_level": evidence_level,
            "required_actions": sorted(core_nle_actions),
            "available_actions": sorted(core_nle_actions & action_set),
            "core_action_coverage_ready": bool((core_action_coverage.get("readiness") or {}).get("core_action_coverage_ready")),
            "registered_action_surface_ready": bool(
                (core_action_coverage.get("readiness") or {}).get("registered_action_surface_ready")
            ),
            "nle_group_matrix_ready": bool((core_action_coverage.get("readiness") or {}).get("nle_group_matrix_ready")),
            "core_safety_matrix_ready": bool((core_safety.get("readiness") or {}).get("core_safety_matrix_ready")),
            "core_action_coverage_summary": dict(core_action_coverage.get("summary") or {}),
            "core_action_group_count": _int((core_action_coverage.get("summary") or {}).get("group_count"), 0),
            "core_action_ready_group_count": _int((core_action_coverage.get("summary") or {}).get("ready_group_count"), 0),
        },
        "source_record_monitor_3_point": {
            "ok": bool(source_record_contract.get("ok")),
            "evidence_level": evidence_level,
            "workbench_contract": True,
            "required_actions": list(source_record_contract.get("required_actions") or sorted(source_record_actions)),
            "available_actions": list(source_record_contract.get("available_actions") or sorted(source_record_actions & action_set)),
            "edit_decision_preview_ready": bool(source_record_contract.get("edit_decision_preview_ready")),
            "patch_matrix_ready": bool(source_record_contract.get("patch_matrix_ready")),
            "monitor_layout_ready": bool(source_record_contract.get("monitor_layout_ready")),
            "apply_board_ready": bool(source_record_contract.get("apply_board_ready")),
            "keyboard_overlay_ready": bool(source_record_contract.get("keyboard_overlay_ready")),
            "usability_board_ready": bool((source_usability.get("readiness") or {}).get("source_record_usability_ready")),
            "review_before_apply_visible": bool((source_usability.get("readiness") or {}).get("review_before_apply_visible")),
        },
        "multicam": {
            "ok": bool(multicam_contract.get("ok")),
            "evidence_level": evidence_level,
            "angle_count": len(multicam_angles),
            "contract_angle_count": _int(multicam_contract.get("angle_count"), 0),
            "switch_count": _int(multicam_contract.get("switch_count"), 0),
            "group_count": _int(multicam_contract.get("group_count"), 0),
            "sync_plan_ready": bool(multicam_contract.get("sync_plan_ready")),
            "sync_methods": list(multicam_contract.get("sync_methods") or []),
            "angle_bins_ready": bool(multicam_contract.get("angle_bins_ready")),
            "angle_bin_count": _int(multicam_contract.get("angle_bin_count"), 0),
            "angle_gap_count": _int(multicam_contract.get("angle_gap_count"), 0),
            "switcher_workbench_ready": bool(multicam_contract.get("switcher_workbench_ready")),
            "switcher_tile_board_ready": bool(multicam_contract.get("switcher_tile_board_ready")),
            "switch_review_board_ready": bool(multicam_contract.get("switch_review_board_ready")),
            "live_switch_dashboard_ready": bool(multicam_contract.get("live_switch_dashboard_ready")),
            "sync_quality_board_ready": bool(multicam_contract.get("sync_quality_board_ready")),
            "waveform_sync_board_ready": bool(multicam_contract.get("waveform_sync_board_ready")),
            "export_parity_board_ready": bool((multicam_parity.get("readiness") or {}).get("multicam_export_parity_board_ready")),
            "export_handoff_ready": bool(multicam_contract.get("export_handoff_ready")),
            "video_clip_count": video_count,
            "required_actions": list(multicam_contract.get("required_actions") or sorted(multicam_actions)),
            "available_actions": list(multicam_contract.get("available_actions") or sorted(multicam_actions & action_set)),
        },
        "proxy_media_management": {
            "ok": media_count >= 12 and proxy_ready >= 6 and bool(proxy_plan.get("proxy_ready")) and bool(proxy_health.get("ready")) and proxy_actions <= action_set,
            "evidence_level": evidence_level,
            "media_pool_count": media_count,
            "proxy_ready_count": proxy_ready,
            "kind_counts": kind_counts,
            "required_actions": sorted(proxy_actions),
            "available_actions": sorted(proxy_actions & action_set),
            "proxy_plan_ready": bool(proxy_plan.get("proxy_ready")),
            "proxy_plan_summary": dict(proxy_plan.get("summary") or {}),
            "proxy_plan_commands": dict(proxy_plan.get("commands") or {}),
            "proxy_health_ready": bool(proxy_health.get("ready")),
            "proxy_health_summary": dict(proxy_health.get("summary") or {}),
            "proxy_health_commands": dict(proxy_health.get("commands") or {}),
            "proxy_review_ready": bool(project_bin_contract.get("proxy_review_ready")),
            "proxy_regeneration_board_ready": bool(project_bin_contract.get("proxy_regeneration_board_ready")),
            "proxy_conflict_board_ready": bool(project_bin_contract.get("proxy_conflict_board_ready")),
            "safe_background_regeneration_ready": bool(project_bin_contract.get("safe_background_regeneration_ready")),
            "proxy_conflict_summary": dict(proxy_conflicts.get("summary") or {}),
            "proxy_conflict_commands": dict(proxy_conflicts.get("commands") or {}),
            "proxy_apply_review_ready": bool((proxy_apply.get("readiness") or {}).get("proxy_apply_review_ready")),
            "stale_proxy_warning_ready": bool((proxy_apply.get("readiness") or {}).get("stale_proxy_warning_ready")),
            "search_filter_model_ready": bool(project_bin_contract.get("search_filter_model_ready")),
            "metadata_columns_ready": bool(project_bin_contract.get("metadata_columns_ready")),
        },
        "conform_relink_project_bin": {
            "ok": bool(project_bin_contract.get("ok")) and (kind_counts.get("video", 0) >= 6 or relink_candidates >= 2),
            "evidence_level": evidence_level,
            "media_pool_count": media_count,
            "relink_candidate_count": relink_candidates,
            "kind_counts": kind_counts,
            "project_bin_workbench": True,
            "project_bin_contract": dict(project_bin_contract),
            "batch_plan_ready": bool(project_bin_contract.get("batch_plan_ready")),
            "batch_operation_count": _int(project_bin_contract.get("batch_operation_count"), 0),
            "conform_report_ready": bool(project_bin_contract.get("conform_report_ready")),
            "conform_report_summary": dict(project_bin_contract.get("conform_report_summary") or {}),
            "review_board_ready": bool(project_bin_contract.get("review_board_ready")),
            "conform_apply_review_ready": bool((conform_apply.get("readiness") or {}).get("conform_apply_review_ready")),
            "batch_apply_review_required": bool((conform_apply.get("readiness") or {}).get("batch_apply_review_required")),
            "proxy_review_ready": bool(project_bin_contract.get("proxy_review_ready")),
            "offline_browser_ready": bool(project_bin_contract.get("offline_browser_ready")),
            "relink_candidate_board_ready": bool(project_bin_contract.get("relink_candidate_board_ready")),
            "proxy_regeneration_board_ready": bool(project_bin_contract.get("proxy_regeneration_board_ready")),
            "proxy_conflict_board_ready": bool(project_bin_contract.get("proxy_conflict_board_ready")),
            "search_filter_model_ready": bool(project_bin_contract.get("search_filter_model_ready")),
            "metadata_columns_ready": bool(project_bin_contract.get("metadata_columns_ready")),
        },
        "undo_edge_case_qa": {
            "ok": edit_actions <= action_set,
            "evidence_level": evidence_level,
            "required_actions": sorted(edit_actions),
            "available_actions": sorted(edit_actions & action_set),
            "timeline_fuzzer_ready": timeline_stress_ok,
            "timeline_fuzzer_summary": dict(timeline_stress_summary),
            "timeline_fuzzer_blockers": list(timeline_stress.get("blockers") or []),
            "undo_health_ready": bool(undo_health.get("ready")),
            "undo_health_summary": dict(undo_health.get("summary") or {}),
            "undo_health_blockers": list(undo_health.get("blockers") or []),
            "undo_review_board_ready": bool((undo_review_board.get("readiness") or {}).get("review_board_ready"))
            and "timeline.undo_review_board" in action_set,
            "undo_recovery_playbook_ready": bool((undo_recovery_playbook.get("readiness") or {}).get("recovery_playbook_ready"))
            and "timeline.undo_recovery_playbook" in action_set,
            "undo_stability_dashboard_ready": bool(
                (undo_stability_dashboard.get("readiness") or {}).get("stability_dashboard_ready")
            )
            and "timeline.undo_stability_dashboard" in action_set,
            "undo_long_session_plan_ready": bool(
                (undo_long_session.get("readiness") or {}).get("undo_long_session_plan_ready")
            ),
            "undo_stability_dashboard_summary": dict(undo_stability_dashboard.get("summary") or {}),
        },
        "final_cut_style_storyline": {
            "ok": (
                bool(magnetic_contract.get("ok"))
                and bool(connected_contract.get("ok"))
                and bool(role_lane_contract.get("ok"))
                and bool(visual_feedback_contract_ready)
                and bool(audition_contract.get("ok"))
            ),
            "evidence_level": evidence_level,
            "required_actions": sorted(
                set(magnetic_contract.get("required_actions") or sorted(magnetic_actions))
                | set(connected_contract.get("required_actions") or sorted(connected_clip_actions))
                | set(role_lane_contract.get("required_actions") or sorted(role_lane_actions))
                | set(visual_feedback_actions)
                | set(audition_contract.get("required_actions") or sorted(audition_actions))
            ),
            "available_actions": sorted(
                set(magnetic_contract.get("available_actions") or sorted(magnetic_actions & action_set))
                | set(connected_contract.get("available_actions") or sorted(connected_clip_actions & action_set))
                | set(role_lane_contract.get("available_actions") or sorted(role_lane_actions & action_set))
                | set(visual_feedback_actions & action_set)
                | set(audition_contract.get("available_actions") or sorted(audition_actions & action_set))
            ),
            "track_count": _int(magnetic_status.get("track_count"), 0),
            "gap_count": _int(magnetic_status.get("gap_count"), 0),
            "overlap_count": _int(magnetic_status.get("overlap_count"), 0),
            "ready": bool(magnetic_status.get("ready")),
            "magnetic_contract_ready": bool(magnetic_contract.get("ok")),
            "connected_clip_contract_ready": bool(connected_contract.get("ok")),
            "role_lane_contract_ready": bool(role_lane_contract.get("ok")),
            "visual_feedback_contract_ready": bool(visual_feedback_contract_ready),
            "storyline_gesture_polish_ready": bool(
                (storyline_polish.get("readiness") or {}).get("storyline_gesture_polish_ready")
            ),
            "audition_contract_ready": bool(audition_contract.get("ok")),
            "role_filter_panel_ready": bool(role_filter_panel_ready),
            "cross_row_anchor_ui_ready": bool(cross_row_anchor_ui_ready),
            "audition_card_model_ready": bool(audition_card_model_ready),
            "magnetic_drag_visual_language_ready": bool(magnetic_drag_visual_language_ready),
            "connected_count": _int(connected_status.get("connected_count"), 0),
            "connected_issue_count": _int(connected_status.get("issue_count"), 0),
            "role_counts": dict((connected_status.get("role_colors") or {}).get("role_counts") or {}),
            "role_lane_count": _int(role_lane_status.get("lane_count"), 0),
            "anchor_overlay_ready": bool(anchor_overlay.get("ready")),
            "anchor_count": _int(anchor_overlay.get("anchor_count"), 0),
            "role_filter_ready": bool(role_filter_model.get("ready")),
            "role_filter_count": _int(role_filter_model.get("filter_count"), 0),
            "audition_count": _int(audition_status.get("audition_count"), 0),
            "audition_take_count": _int(audition_status.get("take_count"), 0),
            "audition_issue_count": _int(audition_status.get("issue_count"), 0),
            "status": dict(magnetic_status),
            "connected_status": dict(connected_status),
            "role_lane_status": dict(role_lane_status),
            "anchor_overlay": dict(anchor_overlay),
            "role_filter_model": dict(role_filter_model),
            "audition_status": dict(audition_status),
        },
        "long_large_project_validation": {
            "ok": (duration_ms >= 30 * 60_000 and video_count >= 90 and audio_count >= 20) or long_stress_ok or real_corpus_ready,
            "evidence_level": evidence_level,
            "duration_ms": duration_ms,
            "video_clip_count": video_count,
            "audio_clip_count": audio_count,
            "long_project_stress_ok": long_stress_ok,
            "long_project_stress_summary": dict(long_stress_summary),
            "real_project_corpus_ready": real_corpus_ready,
            "real_project_corpus_intake_ready": real_corpus_intake_ready,
            "real_project_corpus_collection_kit_ready": real_corpus_collection_kit_ready,
            "real_project_corpus_gate_board_ready": real_corpus_gate_board_ready,
            "real_project_corpus_workbench_ready": real_corpus_workbench_ready,
            "real_project_corpus_validation_plan_ready": real_corpus_validation_plan_ready,
            "real_project_corpus_validation_packet_ready": real_corpus_validation_packet_ready,
            "real_project_corpus_summary": dict(real_corpus_summary),
            "real_project_corpus_blockers": list(real_corpus.get("blockers") or []),
            "real_project_corpus_metric_ready": real_corpus_metric_ready,
            "real_project_corpus_validation_ready": real_corpus_validation_ready,
        },
    }
    real_world_corpus = evidence_level == "real_project_corpus" or real_corpus_ready
    return {
        "schema": "tigerstudio.nle_evidence.v1",
        "evidence_level": evidence_level,
        "real_world_corpus": real_world_corpus,
        "rows": rows,
        "summary": {
            "checks": len(rows),
            "passing": sum(1 for row in rows.values() if bool(row.get("ok"))),
            "duration_ms": duration_ms,
            "video_clip_count": video_count,
            "audio_clip_count": audio_count,
            "media_pool_count": media_count,
            "registered_action_count": len(action_set),
            "long_project_stress_ok": long_stress_ok,
            "timeline_fuzzer_ready": timeline_stress_ok,
            "undo_health_ready": bool(undo_health.get("ready")),
            "real_project_corpus_ready": real_corpus_ready,
            "real_project_corpus_intake_ready": real_corpus_intake_ready,
            "real_project_corpus_gate_board_ready": real_corpus_gate_board_ready,
            "real_project_corpus_validation_packet_ready": real_corpus_validation_packet_ready,
        },
    }


def build_synthetic_nle_validation_snapshot(*, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Build a deterministic long-project contract corpus for QA.

    This is intentionally synthetic.  It raises implementation confidence for
    action contracts and data-model readiness, while the readiness report still
    blocks a full professional NLE claim until real footage projects are used.
    """

    duration_ms = 45 * 60_000
    media_pool: list[dict[str, Any]] = []
    for idx in range(36):
        kind = "video" if idx < 24 else "audio"
        proxy_state = "stale" if idx in {20, 21, 22, 23} else ("ready" if idx < 28 else "stale")
        media_pool.append(
            {
                "id": f"media_{idx + 1}",
                "path": f"qa_media/cam_{idx % 4 + 1:02d}_{idx + 1:03d}.{'mp4' if kind == 'video' else 'wav'}",
                "name": f"cam_{idx % 4 + 1:02d}_{idx + 1:03d}",
                "kind": kind,
                "proxy_state": proxy_state,
                "offline": False,
                "relink_candidate_count": 2 if idx in {3, 7, 15} else 0,
                "bin": "A-roll" if idx % 2 == 0 else "B-roll",
            }
        )

    video_tracks: list[dict[str, Any]] = []
    clip_id = 1
    for track_idx in range(4):
        clips: list[dict[str, Any]] = []
        for local_idx in range(30):
            start = local_idx * 90_000 + track_idx * 4_000
            end = min(duration_ms, start + 75_000)
            if end <= start:
                continue
            clips.append(
                {
                    "id": clip_id,
                    "index": local_idx,
                    "source_path": media_pool[(local_idx + track_idx) % 24]["path"],
                    "name": f"angle_{track_idx + 1}_{local_idx + 1}",
                    "camera_id": f"cam_{track_idx + 1}",
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "duration_ms": end - start,
                    "source_in_ms": 0,
                    "source_out_ms": end - start,
                    "waveform_sync_peak_ms": track_idx * 120,
                }
            )
            clip_id += 1
        video_tracks.append({"id": track_idx + 1, "index": track_idx, "locked": False, "muted": False, "clips": clips})

    audio_tracks: list[dict[str, Any]] = []
    audio_id = 1
    for track_idx in range(3):
        clips = []
        for local_idx in range(12):
            start = local_idx * 210_000 + track_idx * 18_000
            end = min(duration_ms, start + 180_000)
            if end <= start:
                continue
            clips.append(
                {
                    "id": audio_id,
                    "index": local_idx,
                    "source_path": media_pool[24 + ((local_idx + track_idx) % 12)]["path"],
                    "name": f"audio_{track_idx + 1}_{local_idx + 1}",
                    "offset_ms": start,
                    "end_ms": end,
                    "duration_ms": end - start,
                }
            )
            audio_id += 1
        audio_tracks.append({"id": track_idx + 1, "index": track_idx, "locked": False, "muted": False, "clips": clips})

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "source": "Tiger Studio synthetic NLE validation corpus",
        "project_path": "debugCapture/nle_synthetic_validation.tgp",
        "duration_ms": duration_ms,
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "media_pool": media_pool,
        "markers": [{"id": "m_intro", "ms": 0, "label": "Intro"}, {"id": "m_outro", "ms": duration_ms - 30_000, "label": "Outro"}],
        "selected_clips": [],
    }
    snapshot["summary"] = {
        "video_track_count": len(video_tracks),
        "audio_track_count": len(audio_tracks),
        "video_clip_count": sum(len(track["clips"]) for track in video_tracks),
        "audio_clip_count": sum(len(track["clips"]) for track in audio_tracks),
        "media_pool_count": len(media_pool),
        "marker_count": len(snapshot["markers"]),
        "selected_clip_count": 0,
    }
    snapshot["nle_evidence"] = build_nle_evidence_report(
        snapshot,
        action_ids=action_ids,
        evidence_level="synthetic_contract_corpus",
    )
    return snapshot
