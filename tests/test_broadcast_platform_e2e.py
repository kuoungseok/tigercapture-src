def test_broadcast_platform_e2e_report_tracks_local_and_manual_checks(tmp_path):
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
        live2d_record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_live2d_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
            "avatar_target_kind": "live2d_actor_clip",
            "performance_source_direct_output": False,
        },
    )
    checks = {row["id"]: row for row in report["checks"]}

    assert report["schema"] == "tigerstudio.broadcast.platform_e2e.v1"
    assert report["ok"] is True
    assert report["real_platform_evidence"] is False
    assert checks["record_file_local"]["ok"] is True
    assert checks["live2d_record_file_local"]["ok"] is True
    assert checks["live2d_record_file_local"]["evidence"]["avatar_target_kind"] == "live2d_actor_clip"
    assert checks["live2d_record_file_local"]["evidence"]["performance_source_direct_output"] is False
    assert checks["capture_composite_local"]["ok"] is True
    assert checks["private_rtmp_ingest"]["kind"] == "manual_platform"
    assert "register_broadcast_platform_evidence.py" in checks["private_rtmp_ingest"]["registration"]["command_template"]
    assert checks["private_rtmp_ingest"]["registration"]["redaction_required"] is True
    assert any("private/unlisted" in step for step in checks["private_rtmp_ingest"]["operator_steps"])
    assert any("Performance Source" in step for step in checks["discord_window_share"]["operator_steps"])
    assert report["summary"]["local_runtime_passed"] == 3
    assert report["summary"]["manual_platform_pending"] == 2


def test_broadcast_platform_e2e_can_skip_record_smoke(tmp_path):
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(tmp_path, run_record_smoke=False)
    checks = {row["id"]: row for row in report["checks"]}

    assert report["ok"] is False
    assert checks["record_file_local"]["evidence"]["skipped"] is True
    assert checks["live2d_record_file_local"]["evidence"]["skipped"] is True
    assert checks["capture_composite_local"]["ok"] is True


def test_register_manual_platform_evidence_requires_redaction_confirmation(tmp_path):
    import pytest

    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report, register_manual_platform_evidence

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(__import__("json").dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="confirm_redacted"):
        register_manual_platform_evidence(
            tmp_path,
            check_id="private_rtmp_ingest",
            platform="YouTube",
            notes="unlisted ingest reached excellent status",
        )


def test_register_manual_platform_evidence_can_unlock_platform_rows(tmp_path):
    import json

    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report, register_manual_platform_evidence
    from app.broadcast_release_readiness import build_broadcast_release_readiness_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
        live2d_record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_live2d_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")

    register_manual_platform_evidence(
        tmp_path,
        check_id="private_rtmp_ingest",
        platform="YouTube",
        notes="Unlisted ingest reached excellent status; stream key redacted.",
        confirm_redacted=True,
    )
    result = register_manual_platform_evidence(
        tmp_path,
        check_id="discord_window_share",
        platform="Discord",
        notes="Program Output window shared; Performance Source not visible.",
        confirm_redacted=True,
    )
    readiness = build_broadcast_release_readiness_report(tmp_path)

    assert result["report"]["real_platform_evidence"] is True
    assert result["report"]["summary"]["passed"] == 5
    assert readiness["commercial_ready"] is True


def test_broadcast_platform_e2e_preserves_registered_real_platform_rows(tmp_path):
    import json

    from app.broadcast_platform_e2e import (
        build_broadcast_platform_e2e_report,
        preserve_registered_platform_evidence,
        register_manual_platform_evidence,
    )

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
        live2d_record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_live2d_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")
    registered = register_manual_platform_evidence(
        tmp_path,
        check_id="private_rtmp_ingest",
        platform="YouTube",
        notes="Unlisted ingest reached excellent status; stream key redacted.",
        confirm_redacted=True,
    )["report"]

    fresh = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
        live2d_record_smoke_runner=lambda root: {
            "ok": True,
            "output_path": str(root / "debugCapture" / "broadcast_live2d_record_smoke.mp4"),
            "bytes": 4096,
            "frames_written": 12,
        },
    )
    preserved = preserve_registered_platform_evidence(fresh, registered)
    checks = {row["id"]: row for row in preserved["checks"]}

    assert checks["private_rtmp_ingest"]["kind"] == "real_platform"
    assert checks["private_rtmp_ingest"]["ok"] is True
    assert checks["private_rtmp_ingest"]["evidence"]["redacted"] is True
    assert checks["discord_window_share"]["kind"] == "manual_platform"


def test_broadcast_platform_evidence_checklist_guides_remaining_manual_work(tmp_path):
    import json

    from app.broadcast_platform_e2e import (
        build_broadcast_platform_e2e_report,
        build_broadcast_platform_evidence_checklist,
        register_manual_platform_evidence,
    )

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")

    checklist = build_broadcast_platform_evidence_checklist(tmp_path)

    assert checklist["schema"] == "tigerstudio.broadcast.platform_evidence_checklist.v1"
    assert checklist["artifact_present"] is True
    assert checklist["summary"]["passed"] == 3
    assert checklist["summary"]["required"] == 5
    assert checklist["summary"]["manual_platform_pending"] == 2
    assert checklist["sale_ready"] is False
    assert checklist["operator_focus"]["id"] == "private_rtmp_ingest"
    assert "private/unlisted" in " ".join(checklist["operator_focus"]["operator_steps"])
    assert "register_broadcast_platform_evidence.py" in checklist["operator_focus"]["registration"]["command_template"]
    assert "3/5 passed" in checklist["status_text"]

    register_manual_platform_evidence(
        tmp_path,
        check_id="private_rtmp_ingest",
        platform="YouTube",
        notes="Private ingest reached excellent status; stream key redacted.",
        confirm_redacted=True,
    )
    register_manual_platform_evidence(
        tmp_path,
        check_id="discord_window_share",
        platform="Discord",
        notes="Program Output window shared; Performance Source not visible.",
        confirm_redacted=True,
    )

    ready = build_broadcast_platform_evidence_checklist(tmp_path)

    assert ready["sale_ready"] is True
    assert ready["summary"]["passed"] == 5
    assert ready["operator_focus"] == {}
