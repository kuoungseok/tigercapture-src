from __future__ import annotations


def test_nle_timeline_stress_report_blocks_without_fuzzer_file(tmp_path):
    from app.nle_timeline_stress import build_nle_timeline_stress_report

    report = build_nle_timeline_stress_report(report_path=tmp_path / "missing.json")

    assert report["schema"] == "tigerstudio.nle.timeline_stress.v1"
    assert report["claim_ready"] is False
    assert "report_exists" in report["blockers"]
    assert "iterations" in report["blockers"]


def test_nle_timeline_stress_report_accepts_complete_fuzzer_payload():
    from app.nle_timeline_stress import build_nle_timeline_stress_report, build_nle_undo_health_matrix

    report = build_nle_timeline_stress_report(
        {
            "ok": True,
            "summary": {
                "iterations": 400,
                "failures": 0,
                "operations": {
                    "blade": 51,
                    "move": 62,
                    "ripple": 48,
                    "roll": 43,
                    "slip": 58,
                    "slide": 66,
                    "undo": 72,
                },
                "undo_depth": 19,
                "video_tracks": 2,
                "audio_tracks": 1,
                "actor_tracks": 2,
            },
            "failures": [],
        }
    )

    assert report["claim_ready"] is True
    assert report["summary"]["iterations"] == 400
    assert report["summary"]["missing_operations"] == []

    health = build_nle_undo_health_matrix(report)
    assert health["kind"] == "nle_undo_health_matrix"
    assert health["ready"] is True
    assert health["summary"]["covered_operation_count"] == 7
    assert health["commands"]["show_operation_matrix_enabled"] is True
