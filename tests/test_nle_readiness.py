from __future__ import annotations


def test_nle_readiness_report_blocks_full_professional_claim():
    from app.nle_readiness import build_nle_readiness_report, format_nle_readiness_summary

    snapshot = {
        "duration_ms": 90_000,
        "media_pool": [{"id": "media_1", "path": "clip.mp4", "kind": "video"}],
        "video_tracks": [{"id": 1, "clips": [{"id": 10, "timeline_in_ms": 0, "timeline_out_ms": 90_000}]}],
        "audio_tracks": [],
        "summary": {"video_clip_count": 1, "audio_clip_count": 0},
    }
    report = build_nle_readiness_report(snapshot, action_count=88)
    summary = format_nle_readiness_summary(report)

    assert report["schema"] == "tigerstudio.nle_readiness.v1"
    assert report["score"] >= 50
    assert report["professional_nle_claim_ok"] is False
    assert "multicam" in report["blockers"]
    assert any(row["id"] == "source_record_monitor_3_point" and row["status"] == "partial" for row in report["rows"])
    assert "Professional NLE claim: not allowed" in summary


def test_nle_readiness_qa_payload_is_json_ready():
    from tools.qa_nle_readiness import run_nle_readiness_qa

    payload = run_nle_readiness_qa()

    assert payload["kind"] == "nle_readiness"
    assert payload["ok"] is True
    assert payload["report"]["score"] >= 91
    assert payload["report"]["score_breakdown"]["core_nle_actions"]["score"] >= 90
    assert payload["report"]["score_breakdown"]["long_large_project_validation"]["score"] >= 86
    assert payload["report"]["evidence_level"] == "synthetic_contract_corpus"
    assert payload["release_claim_gate_ok"] is False
    assert payload["report"]["professional_nle_claim_ok"] is False
    core = next(row for row in payload["report"]["rows"] if row["id"] == "core_nle_actions")
    assert core["score"] >= 90
    assert any("core_action_coverage_ready=True" in item for item in core["evidence"])
    assert any("core_safety_matrix_ready=True" in item for item in core["evidence"])
    proxy = next(row for row in payload["report"]["rows"] if row["id"] == "proxy_media_management")
    assert proxy["score"] >= 91
    assert any("proxy_plan_ready=True" in item for item in proxy["evidence"])
    assert any("proxy_review_ready=True" in item for item in proxy["evidence"])
    assert any("proxy_regeneration_board_ready=True" in item for item in proxy["evidence"])
    assert any("proxy_conflict_board_ready=True" in item for item in proxy["evidence"])
    assert any("safe_background_regeneration_ready=True" in item for item in proxy["evidence"])
    assert any("proxy_apply_review_ready=True" in item for item in proxy["evidence"])
    assert any("search_filter_model_ready=True" in item for item in proxy["evidence"])
    assert any("metadata_columns_ready=True" in item for item in proxy["evidence"])
    conform = next(row for row in payload["report"]["rows"] if row["id"] == "conform_relink_project_bin")
    assert conform["score"] >= 91
    assert any("conform_report_ready=True" in item for item in conform["evidence"])
    assert any("review_board_ready=True" in item for item in conform["evidence"])
    assert any("conform_apply_review_ready=True" in item for item in conform["evidence"])
    assert any("offline_browser_ready=True" in item for item in conform["evidence"])
    assert any("relink_candidate_board_ready=True" in item for item in conform["evidence"])
    assert any("search_filter_model_ready=True" in item for item in conform["evidence"])
    assert any("metadata_columns_ready=True" in item for item in conform["evidence"])
    source_record = next(row for row in payload["report"]["rows"] if row["id"] == "source_record_monitor_3_point")
    assert source_record["score"] >= 91
    assert any("monitor_layout_ready=True" in item for item in source_record["evidence"])
    assert any("apply_board_ready=True" in item for item in source_record["evidence"])
    assert any("keyboard_overlay_ready=True" in item for item in source_record["evidence"])
    assert any("usability_board_ready=True" in item for item in source_record["evidence"])
    multicam = next(row for row in payload["report"]["rows"] if row["id"] == "multicam")
    assert multicam["score"] >= 92
    assert any("switcher_tile_board_ready=True" in item for item in multicam["evidence"])
    assert any("switch_review_board_ready=True" in item for item in multicam["evidence"])
    assert any("live_switch_dashboard_ready=True" in item for item in multicam["evidence"])
    assert any("sync_quality_board_ready=True" in item for item in multicam["evidence"])
    assert any("waveform_sync_board_ready=True" in item for item in multicam["evidence"])
    assert any("export_parity_board_ready=True" in item for item in multicam["evidence"])
    undo = next(row for row in payload["report"]["rows"] if row["id"] == "undo_edge_case_qa")
    assert undo["score"] >= 91
    assert any("undo_review_board_ready=True" in item for item in undo["evidence"])
    assert any("undo_recovery_playbook_ready=True" in item for item in undo["evidence"])
    assert any("undo_stability_dashboard_ready=True" in item for item in undo["evidence"])
    assert any("undo_long_session_plan_ready=True" in item for item in undo["evidence"])
    storyline = next(row for row in payload["report"]["rows"] if row["id"] == "final_cut_style_storyline")
    assert storyline["score"] >= 93
    assert any("role_filter_panel_ready=True" in item for item in storyline["evidence"])
    assert any("cross_row_anchor_ui_ready=True" in item for item in storyline["evidence"])
    assert any("audition_card_model_ready=True" in item for item in storyline["evidence"])
    assert any("magnetic_drag_visual_language_ready=True" in item for item in storyline["evidence"])
    assert any("storyline_gesture_polish_ready=True" in item for item in storyline["evidence"])
    long_project = next(row for row in payload["report"]["rows"] if row["id"] == "long_large_project_validation")
    assert long_project["score"] >= 86
    assert any("real_project_corpus_intake_ready=True" in item for item in long_project["evidence"])
    assert any("real_project_corpus_collection_kit_ready=True" in item for item in long_project["evidence"])
    assert any("real_project_corpus_gate_board_ready=True" in item for item in long_project["evidence"])
    assert any("real_project_corpus_workbench_ready=True" in item for item in long_project["evidence"])
    assert any("real_project_corpus_validation_plan_ready=True" in item for item in long_project["evidence"])
    assert any("real_project_corpus_validation_packet_ready=True" in item for item in long_project["evidence"])
    assert "real_world_long_project_corpus" in payload["report"]["blockers"]
    assert "multicam_full_ui_export_parity" not in payload["report"]["blockers"]
    assert "Professional NLE claim: not allowed" in payload["summary"]


def test_nle_readiness_scoring_helpers_keep_current_contract():
    from app.nle_readiness_scoring import score_ladder, score_multicam, score_undo_edge_case_qa

    assert score_ladder((False, 99), (True, 42), default=1) == 42
    assert score_multicam(
        multicam_workbench_ready=True,
        multicam_angle_bins_ready=True,
        multicam_tile_board_ready=True,
        multicam_review_board_ready=True,
        multicam_live_dashboard_ready=True,
        multicam_sync_quality_board_ready=True,
        multicam_waveform_sync_board_ready=True,
        multicam_export_parity_board_ready=True,
        multicam_export_handoff_ready=True,
        evidence_ok=True,
    ) == 92
    assert score_undo_edge_case_qa(
        timeline_fuzzer_ready=True,
        undo_health_ready=True,
        undo_review_board_ready=True,
        undo_recovery_playbook_ready=True,
        undo_stability_dashboard_ready=True,
        undo_long_session_plan_ready=True,
        evidence_ok=True,
    ) == 91


def test_nle_target_gap_board_keeps_real_corpus_as_hard_blocker():
    from app.nle_target_gap import build_nle_target_gap_board
    from tools.qa_nle_readiness import run_nle_readiness_qa

    payload = run_nle_readiness_qa()
    board = build_nle_target_gap_board(
        payload["report"],
        target_score=95,
        real_corpus_report={
            "summary": {
                "valid_project_count": 0,
                "preflight_ready_count": 0,
                "preflight_blocked_count": 0,
                "validation_ready_count": 0,
                "duration_ms": 0,
                "video_clips": 0,
                "audio_clips": 0,
                "missing_media_count": 0,
            },
            "thresholds": {
                "min_projects": 3,
                "min_duration_ms": 30 * 60_000,
                "min_total_video_clips": 90,
                "min_total_audio_clips": 20,
                "require_validation_evidence": True,
            },
        },
    )

    assert board["schema"] == "tigerstudio.nle.target_gap.v1"
    assert board["ready"] is True
    assert board["target_score"] == 95
    assert board["current_score"] < 95
    assert board["readiness"]["real_corpus_required_for_claim"] is True
    assert "real_world_long_project_corpus" in board["hard_blockers"]
    real_corpus = next(section for section in board["sections"] if section["id"] == "real_corpus")
    assert real_corpus["remaining"]["projects"] == 3
    assert real_corpus["remaining"]["preflight_projects"] == 3
    assert real_corpus["remaining"]["validation_projects"] == 3
    assert any(row["id"] == "preflight_ready_count" for row in real_corpus["rows"])


def test_nle_target_gap_qa_payload_is_json_ready(tmp_path):
    import json

    from tools.qa_nle_readiness import run_nle_readiness_qa
    from tools.qa_nle_target_gap import run_nle_target_gap_qa

    readiness = run_nle_readiness_qa()
    readiness_path = tmp_path / "nle_readiness_qa.json"
    real_corpus_path = tmp_path / "nle_real_project_corpus_qa.json"
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    real_corpus_path.write_text(
        json.dumps(
            {
                "summary": {
                    "valid_project_count": 0,
                    "preflight_ready_count": 0,
                    "preflight_blocked_count": 0,
                    "validation_ready_count": 0,
                    "duration_ms": 0,
                    "video_clips": 0,
                    "audio_clips": 0,
                    "missing_media_count": 0,
                },
                "thresholds": {"min_projects": 3, "require_validation_evidence": True},
            }
        ),
        encoding="utf-8",
    )

    payload = run_nle_target_gap_qa(
        target_score=95,
        readiness_path=readiness_path,
        real_corpus_path=real_corpus_path,
    )

    assert payload["kind"] == "nle_target_gap"
    assert payload["ok"] is True
    assert payload["target_score"] == 95
    assert payload["current_score"] == readiness["report"]["score"]
    assert payload["score_gap"] == max(0, 95 - readiness["report"]["score"])
    assert payload["professional_claim_blocked"] is True


def test_nle_readiness_qa_uses_real_corpus_without_allowing_professional_claim():
    from tools.qa_nle_readiness import run_nle_readiness_qa

    real_corpus = {
        "schema": "tigerstudio.nle.real_project_corpus.v1",
        "claim_ready": True,
        "real_world_corpus": True,
        "summary": {
            "valid_project_count": 3,
            "preflight_ready_count": 3,
            "preflight_blocked_count": 0,
            "validation_ready_count": 3,
            "validation_failed_required_check_count": 0,
            "duration_ms": 2_400_000,
            "video_clips": 120,
            "audio_clips": 32,
            "missing_media_count": 0,
        },
        "thresholds": {"min_projects": 3, "require_validation_evidence": True},
        "blockers": [],
    }

    payload = run_nle_readiness_qa(real_project_corpus_report=real_corpus)

    assert payload["ok"] is True
    assert payload["report"]["real_world_corpus"] is True
    assert payload["report"]["evidence_level"] == "real_project_corpus"
    assert payload["report"]["score"] >= 95
    assert any(
        "real_world_score_unlock=True" in item
        for row in payload["report"]["rows"]
        for item in row["evidence"]
    )
    assert "real_world_long_project_corpus" not in payload["report"]["blockers"]
    assert payload["report"]["professional_nle_claim_ok"] is False


def test_nle_readiness_qa_uses_timeline_fuzzer_evidence():
    from tools.qa_nle_readiness import run_nle_readiness_qa

    fuzzer = {
        "ok": True,
        "summary": {
            "iterations": 400,
            "failures": 0,
            "operations": {"blade": 50, "move": 50, "ripple": 50, "roll": 50, "slip": 50, "slide": 50, "undo": 100},
            "undo_depth": 20,
            "video_tracks": 2,
            "audio_tracks": 1,
            "actor_tracks": 2,
        },
        "failures": [],
    }

    payload = run_nle_readiness_qa(timeline_fuzzer_report=fuzzer)
    undo = next(row for row in payload["report"]["rows"] if row["id"] == "undo_edge_case_qa")

    assert payload["ok"] is True
    assert undo["score"] >= 78
    assert any("timeline_fuzzer_ready=True" in item for item in undo["evidence"])


def test_nle_readiness_without_evidence_stays_conservative():
    from tools.qa_nle_readiness import run_nle_readiness_qa

    payload = run_nle_readiness_qa(synthetic_contract_corpus=False)

    assert payload["report"]["score"] <= 50
    assert payload["report"]["evidence_level"] == "project_snapshot"
    assert "multicam" in payload["report"]["blockers"]
    assert payload["report"]["professional_nle_claim_ok"] is False
