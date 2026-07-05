from __future__ import annotations

import json
from pathlib import Path


def test_crash_reporter_writes_recent_actions_and_emergency_autosave(tmp_path):
    from app import crash_reporter

    autosave_path = tmp_path / "crash_autosave.tgp"

    def _autosave(reason: str):
        autosave_path.write_text(reason, encoding="utf-8")
        return autosave_path

    crash_reporter.configure_crash_reporting(tmp_path)
    crash_reporter.set_emergency_autosave_callback(_autosave)
    crash_reporter.record_action("qa.before_crash", clip_id=7)
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        crash_reporter.write_crash_report(type(exc), exc, exc.__traceback__)
    finally:
        crash_reporter.set_emergency_autosave_callback(None)

    payload = json.loads((tmp_path / "crash_report_latest.json").read_text(encoding="utf-8"))
    assert payload["exception"]["type"] == "RuntimeError"
    assert payload["emergency_autosave"]["path"] == str(autosave_path)
    assert any(row["event"] == "qa.before_crash" for row in payload["recent_actions"])
    assert "actor_context" in payload
    assert autosave_path.read_text(encoding="utf-8") == "crash"


def test_crash_report_user_summary_recommends_autosave(tmp_path):
    from app.crash_report_dialog import crash_report_user_summary

    autosave = tmp_path / "emergency.tgp"
    autosave.write_text("{}", encoding="utf-8")
    report = {
        "exception": {"type": "RuntimeError", "message": "node graph failed"},
        "emergency_autosave": {"path": str(autosave)},
        "recent_actions": [{"event": "node.edit"}],
        "actor_context": {"actor_related": True},
    }

    summary = crash_report_user_summary(report, tmp_path / "crash_report_latest.json")

    assert summary["autosave_ready"] is True
    assert "Open Emergency Autosave" in summary["recommended_actions"]
    assert "Review Live2D/Spine" in " ".join(summary["recommended_actions"])
    assert "node graph failed" in summary["plain_text"]


def test_crash_reporter_seen_and_repro_bundle(tmp_path):
    from app import crash_reporter

    report_path = tmp_path / "crash_report_latest.json"
    report_path.write_text(
        json.dumps({
            "exception": {"type": "ValueError", "message": "bad"},
            "emergency_autosave": {"path": str(tmp_path / "auto.tgp")},
            "recent_actions": [
                {"event": "timeline.drop_spine", "data": {"start_ms": 1200, "path": "a.skel"}},
                {"event": "node_graph.connection_created", "data": {"source": "A"}},
            ],
            "traceback": "trace",
        }),
        encoding="utf-8",
    )

    assert crash_reporter.has_unseen_crash_report(report_path)
    out = crash_reporter.export_repro_bundle(report_path, tmp_path / "repro.json")
    assert out is not None and out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert any("Drop Spine" in step for step in payload["steps"])
    crash_reporter.mark_crash_report_seen(report_path)
    assert not crash_reporter.has_unseen_crash_report(report_path)


def test_crash_reporter_ignores_malformed_and_stale_reports(tmp_path, monkeypatch):
    import time
    from app import crash_reporter

    report_path = tmp_path / "crash_report_latest.json"
    report_path.write_text("{", encoding="utf-8")
    assert not crash_reporter.has_unseen_crash_report(report_path)

    report_path.write_text(
        json.dumps({"exception": {"type": "RuntimeError", "message": "old"}}),
        encoding="utf-8",
    )
    old = time.time() - 9 * 24 * 3600
    import os

    os.utime(report_path, (old, old))
    monkeypatch.setenv("TIGERCAPTURE_CRASH_REPORT_MAX_AGE_HOURS", "168")
    assert not crash_reporter.has_unseen_crash_report(report_path)

    monkeypatch.setenv("TIGERCAPTURE_CRASH_REPORT_MAX_AGE_HOURS", "0")
    assert crash_reporter.has_unseen_crash_report(report_path)


def test_crash_reporter_extracts_actor_loading_context():
    from app.crash_reporter import actor_context_from_actions, repro_steps_from_report

    actions = [
        {"at": "now", "event": "actor.open_live2d_editor", "data": {"model_path": "hero.model3.json"}},
        {"at": "now", "event": "actor.load_live2d.stage", "data": {"stage": "first_frame", "path": "hero.model3.json", "status": "loading"}},
    ]
    context = actor_context_from_actions(actions)
    steps = repro_steps_from_report({"recent_actions": actions})

    assert context["actor_related"] is True
    assert context["latest_load"]["data"]["stage"] == "first_frame"
    assert any("Live2D load stage first_frame" in step for step in steps)


def test_timeline_alignment_qa_passes_shared_origin():
    from tools.qa_timeline_alignment import run_alignment_qa

    report = run_alignment_qa(px_per_sec=91.0, samples_ms=[0, 1000, 2345])

    assert report["ok"]
    assert report["summary"]["max_abs_drift_px"] == 0


def test_actor_lane_workflow_qa_checks_double_click_and_hit_test():
    from tools.qa_actor_lane_workflow import run_actor_lane_workflow_qa

    report = run_actor_lane_workflow_qa(px_per_sec=80.0)

    assert report["ok"]
    assert {row["kind"] for row in report["rows"]} == {"live2d", "spine"}


def test_timeline_visual_alignment_qa_writes_screenshot(tmp_path):
    from tools.qa_timeline_visual_alignment import run_timeline_visual_alignment_qa

    report = run_timeline_visual_alignment_qa(out_dir=tmp_path)

    assert report["ok"]
    assert report["summary"]["max_abs_drift_px"] == 0
    assert (tmp_path / "timeline_visual_alignment.png").exists()


def test_timeline_drag_feedback_qa_writes_snap_and_blocked_screenshots(tmp_path):
    from tools.qa_timeline_drag_feedback import run_timeline_drag_feedback_qa

    report = run_timeline_drag_feedback_qa(out_dir=tmp_path)

    assert report["ok"], report["cases"]
    assert {row["mode"] for row in report["cases"]} == {"snap", "blocked"}
    assert (tmp_path / "timeline_drag_snap.png").exists()
    assert (tmp_path / "timeline_drag_blocked.png").exists()


def test_timeline_edit_gestures_qa_checks_release_results(tmp_path):
    from tools.qa_timeline_edit_gestures import run_timeline_edit_gestures_qa

    report = run_timeline_edit_gestures_qa(out_dir=tmp_path)

    assert report["ok"], report["cases"]
    assert {row["mode"] for row in report["cases"]} == {"trim", "ripple", "roll", "slip", "slide"}
    assert all(row["commits"] == 1 for row in report["cases"])
    assert (tmp_path / "timeline_edit_gestures_report.json").exists()


def test_timeline_hover_affordance_qa_keeps_tooltips_and_cursors_synced(tmp_path):
    from tools.qa_timeline_hover_affordance import run_timeline_hover_affordance_qa

    report = run_timeline_hover_affordance_qa(out_dir=tmp_path)

    assert report["ok"], report["cases"]
    assert {row["name"] for row in report["cases"]} == {
        "move_repeat",
        "trim_gap_edge",
        "roll_shared_edge",
        "slip_body",
        "slide_body",
    }
    assert all(row["checks"]["tooltip_synced"] for row in report["cases"])
    assert (tmp_path / "timeline_hover_affordance_report.json").exists()


def test_timeline_preset_visibility_qa_keeps_short_clip_markers_visible(tmp_path):
    from tools.qa_timeline_preset_visibility import run_timeline_preset_visibility_qa

    report = run_timeline_preset_visibility_qa(out_dir=tmp_path)

    assert report["ok"], report["summary"]
    assert report["summary"]["wide_pixels"] >= 80
    assert report["summary"]["narrow_pixels"] >= 8
    assert (tmp_path / "timeline_preset_visibility_report.json").exists()


def test_node_graph_fuzzer_passes_deterministic_smoke():
    from tools.qa_node_graph_fuzzer import run_node_graph_fuzzer

    report = run_node_graph_fuzzer(iterations=80, seed=7)

    assert report["ok"], report["failures"]
    assert report["summary"]["iterations"] == 80


def test_node_graph_ui_fuzzer_passes_widget_smoke():
    from tools.qa_node_graph_ui_fuzzer import run_node_graph_ui_fuzzer

    report = run_node_graph_ui_fuzzer(iterations=40, seed=9)

    assert report["ok"], report["failures"]


def test_visual_baseline_manager_approves_snapshot(tmp_path):
    from tools.qa_visual_baseline_manager import approve_latest_visual_baseline

    shot = tmp_path / "ui.png"
    shot.write_bytes(b"png")
    snapshot = tmp_path / "current_snapshot.json"
    snapshot.write_text(
        json.dumps({"screenshots": {"ui.png": "abc"}, "metrics": [], "screenshot_count": 1}),
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"

    report = approve_latest_visual_baseline(snapshot_path=snapshot, baseline_path=baseline)

    assert report["ok"]
    assert baseline.exists()
    assert (baseline.parent / "approved" / "ui.png").exists()


def test_health_center_report_has_sections():
    from app.health_center_dialog import build_health_center_report

    report = build_health_center_report(None)

    assert report["summary"]["sections"] >= 5


def test_long_project_stress_qa_generates_recovery_fixture():
    from tools.qa_long_project_stress import run_long_project_stress_qa

    report = run_long_project_stress_qa()

    assert report["ok"], report["failures"]
    assert report["summary"]["duration_ms"] >= 300_000
    assert report["summary"]["recovery_level"] == "open_safe"


def test_micro_interactions_qa_smoke():
    from tools.qa_micro_interactions import run_micro_interactions_qa

    report = run_micro_interactions_qa()

    assert report["ok"], report["failures"]
    assert report["summary"]["icons"] >= 12


def test_screenstudio_auto_polish_qa_smoke():
    from tools.qa_screenstudio_auto_polish import run_screenstudio_auto_polish_qa

    report = run_screenstudio_auto_polish_qa()

    assert report["ok"], report["failures"]
    assert report["summary"]["samples"] >= 6
    assert report["summary"]["zoom_candidates"] >= 10
    assert report["summary"]["dwell_candidates"] >= 1
    assert report["summary"]["cursor_loop_ready"] >= 6
    assert report["summary"]["visual_parity"] >= 6
    assert report["summary"]["real_mp4_samples"] >= 6
    assert any(
        sample.get("id") == "long_walkthrough" and int(sample.get("auto_zoom_count", 0) or 0) >= 6
        for sample in report["samples"]
    )


def test_screenstudio_naturalness_qa_smoke():
    from tools.qa_screenstudio_naturalness import run_screenstudio_naturalness_qa

    report = run_screenstudio_naturalness_qa()

    assert report["ok"], report["failures"]
    assert report["summary"]["samples"] >= 6
    assert report["summary"]["avg_score"] >= 90
    assert report["summary"]["loopback_ok"] >= 6
    assert report["summary"]["rhythm_ok"] >= 7
    assert report["summary"]["export_intents"] >= 4
    assert report["summary"]["long_samples"] >= 1
    assert report["summary"]["long_rhythm_ok"] >= 1
    assert report["summary"]["long_coverage_ok"] >= 1


def test_screenstudio_export_handoff_qa_smoke(tmp_path):
    from tools.qa_screenstudio_export_handoff import run_screenstudio_export_handoff_qa

    report = run_screenstudio_export_handoff_qa(out_dir=tmp_path)

    assert report["ok"], report["failures"]
    assert report["summary"]["scenarios"] >= 5
    assert report["summary"]["clipboard_ready"] >= 4
    assert report["summary"]["share_package_ready"] >= 5
    assert report["summary"]["share_link_ready"] >= 1
    assert report["summary"]["manifests"] >= 5
    assert report["summary"]["completion_ready"] >= 5
    assert report["summary"]["default_result_ready"] == 1
    assert report["summary"]["default_auto_zoom_added"] >= 1
    assert report["summary"]["default_beauty_ready"] == 1
    assert report["summary"]["default_beauty_score"] == 100
    assert report["summary"]["default_golden_video_ready"] == 1


def test_screenstudio_visual_polish_qa_writes_before_after(tmp_path):
    from tools.qa_screenstudio_visual_polish import run_screenstudio_visual_polish_qa

    report = run_screenstudio_visual_polish_qa(out_dir=tmp_path)

    assert report["ok"], report["failures"]
    assert report["summary"]["samples"] >= 5
    assert report["summary"]["visual_samples"] >= 5
    assert report["summary"]["avg_changed_ratio"] > 0.18
    assert report["summary"]["cursor_focus"] >= 5
    assert report["summary"]["avg_cursor_focus_delta"] >= 9.0
    assert (tmp_path / "screenstudio_visual_contact_sheet.png").exists()
    for sample in report["samples"]:
        assert sample["cursor_focus"]["ok"], sample["cursor_focus"]
        images = sample["images"]
        assert Path(images["before"]).exists()
        assert Path(images["after"]).exists()
        assert Path(images["contact"]).exists()


def test_screenstudio_app_flow_qa_checks_import_timeline_export(tmp_path):
    from tools.qa_screenstudio_app_flow import run_screenstudio_app_flow_qa

    report = run_screenstudio_app_flow_qa(out_dir=tmp_path)

    assert report["ok"], report["failures"]
    assert report["summary"]["samples"] >= 5
    assert report["summary"]["events"] >= 20
    assert report["summary"]["auto_zoom_added"] >= 8
    assert report["summary"]["track_zoom_export"] == 0
    assert report["summary"]["avg_changed_ratio"] > 0.18
    assert (tmp_path / "screenstudio_app_flow_contact_sheet.png").exists()


def test_screenstudio_gui_flow_qa_checks_launcher_editor_dashboard(tmp_path):
    from tools.qa_screenstudio_gui_flow import run_screenstudio_gui_flow_qa

    report = run_screenstudio_gui_flow_qa(out_dir=tmp_path)

    assert report["ok"], report["failures"]
    assert report["summary"]["checks"] >= 20
    assert report["summary"]["screenshots"] >= 5
    assert report["checks"]["launcher_is_compact"]
    assert report["checks"]["launcher_quick_start_cards"]
    assert report["checks"]["launcher_no_template_first_cards"]
    assert report["checks"]["launcher_editor_signal_uses_workspace_payload"]
    assert report["checks"]["launcher_video_capture_signal"]
    assert report["checks"]["dashboard_has_capcut_creator_flow"]
    assert report["checks"]["dashboard_has_local_ml_backend"]
    assert report["checks"]["new_project_screenstudio_default"]
    assert report["checks"]["editor_auto_polish_button"]
    assert report["checks"]["dashboard_has_screenstudio_gui_flow"]
    assert report["checks"]["dashboard_can_run_gui_flow"]
    assert (tmp_path / "screenstudio_gui_flow_contact_sheet.png").exists()


def test_visual_baseline_audit_with_fake_baseline(tmp_path):
    from tools.qa_visual_baseline_audit import run_visual_baseline_audit

    baseline_dir = tmp_path / "visual_baseline"
    approved = baseline_dir / "approved"
    approved.mkdir(parents=True)
    for name in ("ui_1366x768.png", "ui_1920x1080.png", "ui_2560x1080.png"):
        (approved / name).write_bytes(b"png")
    (approved / "baseline_manifest.json").write_text(
        json.dumps({"screenshot_count": 3}),
        encoding="utf-8",
    )
    baseline = baseline_dir / "baseline.json"
    baseline.write_text(
        json.dumps({
            "screenshots": {
                "ui_1366x768.png": "a",
                "ui_1920x1080.png": "b",
                "ui_2560x1080.png": "c",
            },
            "metrics": [
                {"size": [1366, 768], "ok": True},
                {"size": [1920, 1080], "ok": True},
                {"size": [2560, 1080], "ok": True},
            ],
        }),
        encoding="utf-8",
    )
    regression = tmp_path / "visual_regression_report.json"
    regression.write_text(json.dumps({"ok": True}), encoding="utf-8")
    gui_flow = tmp_path / "screenstudio_gui_flow_report.json"
    gui_flow.write_text(json.dumps({"ok": True}), encoding="utf-8")
    export_handoff = tmp_path / "screenstudio_export_handoff_qa.json"
    export_handoff.write_text(
        json.dumps({
            "ok": True,
            "summary": {
                "default_result_ready": 1,
                "default_beauty_ready": 1,
                "default_beauty_score": 100,
                "default_golden_video_ready": 1,
            },
        }),
        encoding="utf-8",
    )

    report = run_visual_baseline_audit(
        baseline_path=baseline,
        regression_report_path=regression,
        gui_flow_report_path=gui_flow,
        export_handoff_report_path=export_handoff,
    )

    assert report["ok"], report["failures"]


def test_ui_visual_baseline_refresh_with_fake_reports(tmp_path, monkeypatch):
    import tools.qa_ui_visual_baseline_refresh as refresh

    root = tmp_path
    (root / "debugCapture" / "visual_regression").mkdir(parents=True)
    latest = root / "debugCapture" / "visual_regression" / "visual_regression_report.json"
    latest.write_text(json.dumps({"ok": True, "summary": {"captures": 1}}), encoding="utf-8")
    audit = root / "debugCapture" / "visual_baseline_audit.json"
    audit.write_text(json.dumps({"ok": True}), encoding="utf-8")
    approved = root / "debugCapture" / "visual_baseline" / "approved"
    approved.mkdir(parents=True)
    (approved / "ui.png").write_bytes(b"png")
    monkeypatch.setattr(refresh, "ROOT", root)

    report = refresh.run_ui_visual_baseline_refresh(baseline_audit_path=audit)

    assert report["ok"]
    assert report["summary"]["approved_screenshots"] == 1


def test_actor_mass_compat_qa_with_fake_status(tmp_path):
    from tools.qa_actor_mass_compat import run_actor_mass_compat_qa

    status = tmp_path / "actor_corpus_status.json"
    status.write_text(
        json.dumps({
            "ok": True,
            "coverage": {
                "total": 60,
                "spine": 20,
                "live2d": 8,
                "stress": 6,
                "quarantined": 1,
                "golden": {"pass": 24},
            },
            "golden_baselines": {"baseline_count": 24},
            "issues": [],
        }),
        encoding="utf-8",
    )
    manifest = tmp_path / "actor_corpus_manifest.json"
    manifest.write_text(
        json.dumps({
            "coverage_targets": {
                "min_total": 50,
                "min_spine": 10,
                "min_live2d": 5,
                "min_stress": 5,
            }
        }),
        encoding="utf-8",
    )

    report = run_actor_mass_compat_qa(status_path=status, manifest_path=manifest)

    assert report["ok"], report["failures"]
