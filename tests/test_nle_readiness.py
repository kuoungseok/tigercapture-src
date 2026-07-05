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
    assert payload["report"]["score"] >= 74
    assert payload["report"]["evidence_level"] == "synthetic_contract_corpus"
    assert payload["release_claim_gate_ok"] is False
    assert payload["report"]["professional_nle_claim_ok"] is False
    proxy = next(row for row in payload["report"]["rows"] if row["id"] == "proxy_media_management")
    assert proxy["score"] >= 78
    assert any("proxy_plan_ready=True" in item for item in proxy["evidence"])
    conform = next(row for row in payload["report"]["rows"] if row["id"] == "conform_relink_project_bin")
    assert conform["score"] >= 80
    assert any("conform_report_ready=True" in item for item in conform["evidence"])
    assert "real_world_long_project_corpus" in payload["report"]["blockers"]
    assert "multicam_full_ui_export_parity" not in payload["report"]["blockers"]
    assert "Professional NLE claim: not allowed" in payload["summary"]


def test_nle_readiness_qa_uses_real_corpus_without_allowing_professional_claim():
    from tools.qa_nle_readiness import run_nle_readiness_qa

    real_corpus = {
        "schema": "tigerstudio.nle.real_project_corpus.v1",
        "claim_ready": True,
        "real_world_corpus": True,
        "summary": {
            "valid_project_count": 3,
            "duration_ms": 2_400_000,
            "video_clips": 120,
            "audio_clips": 32,
            "missing_media_count": 0,
        },
        "blockers": [],
    }

    payload = run_nle_readiness_qa(real_project_corpus_report=real_corpus)

    assert payload["ok"] is True
    assert payload["report"]["real_world_corpus"] is True
    assert payload["report"]["evidence_level"] == "real_project_corpus"
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

    assert payload["report"]["score"] == 47
    assert payload["report"]["evidence_level"] == "project_snapshot"
    assert "multicam" in payload["report"]["blockers"]
