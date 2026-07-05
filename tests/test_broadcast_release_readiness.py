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
    assert any("YouTube" in action or "Twitch" in action for action in report["next_actions"])


def test_broadcast_release_readiness_accepts_real_platform_evidence(tmp_path):
    from app.broadcast_release_readiness import build_broadcast_release_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json").write_text(
        json.dumps(
            {
                "ok": True,
                "real_platform_evidence": True,
                "summary": {"passed": 4, "required": 4},
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
