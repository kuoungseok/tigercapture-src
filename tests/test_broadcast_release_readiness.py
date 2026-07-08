import json


def test_broadcast_release_readiness_is_alpha_ready_but_blocks_sale_without_e2e(tmp_path):
    from app.broadcast_release_readiness import build_broadcast_release_readiness_report

    report = build_broadcast_release_readiness_report(tmp_path)
    areas = {row["id"]: row for row in report["areas"]}

    assert report["schema"] == "tigerstudio.broadcast.release_readiness.v1"
    assert report["alpha_ready"] is True
    assert report["commercial_ready"] is False
    assert areas["obs_free_video_call"]["score"] == 100
    assert areas["capture_backends"]["score"] >= 90
    assert areas["real_platform_evidence"]["sale_blocking"] is True
    assert any("Register RTMP" in action for action in report["next_actions"])
    assert "Commercial broadcast claims are blocked" in areas["real_platform_evidence"]["summary"]
    assert areas["real_platform_evidence"]["evidence"]["operator_focus"]["id"] == "private_rtmp_ingest"


def test_broadcast_release_readiness_accepts_real_platform_evidence(tmp_path):
    from app.broadcast_release_readiness import build_broadcast_release_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json").write_text(
        json.dumps(
            {
                "ok": True,
                "real_platform_evidence": True,
                "summary": {"passed": 5, "required": 5},
                "checks": [
                    {"id": "record_file_local", "kind": "local_runtime", "ok": True, "required_for_sale": True},
                    {"id": "live2d_record_file_local", "kind": "local_runtime", "ok": True, "required_for_sale": True},
                    {"id": "capture_composite_local", "kind": "local_runtime", "ok": True, "required_for_sale": True},
                    {"id": "private_rtmp_ingest", "kind": "real_platform", "ok": True, "required_for_sale": True},
                    {"id": "youtube_unlisted_viewer_playback", "kind": "real_platform", "ok": True, "required_for_sale": True},
                    {"id": "discord_window_share", "kind": "manual_platform", "ok": False, "required_for_sale": False},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_broadcast_release_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["real_platform_evidence"]

    assert report["commercial_ready"] is True
    assert report["sale_ready"] is True
    assert area["score"] == 100
    assert report["sale_blockers"] == []


def test_format_broadcast_release_readiness_summary():
    from app.broadcast_release_readiness import (
        build_broadcast_release_readiness_report,
        format_broadcast_release_readiness_summary,
    )

    report = build_broadcast_release_readiness_report(".")
    summary = format_broadcast_release_readiness_summary(report)

    assert "Broadcast readiness" in summary
    assert "/100" in summary
