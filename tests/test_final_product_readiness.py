from __future__ import annotations

import json


def test_final_product_readiness_report_has_release_areas(tmp_path):
    from app.final_product_readiness import AREA_SPECS, build_final_product_readiness_report

    (tmp_path / "tools").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "tools" / "repair_project.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "recovery_dialog.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "crash_reporter.py").write_text("", encoding="utf-8")

    report = build_final_product_readiness_report(tmp_path)

    assert report["ok"] is True
    assert report["summary"]["areas"] == len(AREA_SPECS)
    assert {row["id"] for row in report["areas"]} == {area_id for area_id, _label in AREA_SPECS}
    assert "professional_runtime_parity" in {row["id"] for row in report["areas"]}
    assert report["summary"]["attention"] >= 1
    assert report["release_ready"] is False


def test_final_product_readiness_uses_existing_artifacts(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture" / "screenstudio_app_flow").mkdir(parents=True)
    (tmp_path / "debugCapture" / "screenstudio_gui_flow").mkdir(parents=True)
    (tmp_path / "debugCapture" / "timeline_visual_alignment_qa").mkdir(parents=True)
    (tmp_path / "debugCapture" / "screenstudio_app_flow" / "screenstudio_app_flow_report.json").write_text(
        json.dumps({"ok": True, "summary": {"passing": 5, "samples": 5}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "screenstudio_gui_flow" / "screenstudio_gui_flow_report.json").write_text(
        json.dumps({"ok": True, "summary": {"passing": 10, "checks": 10}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "preset_application_corpus_auto.json").write_text(
        json.dumps({"ok": True, "projects": [{"path": "demo.tgp"}]}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "timeline_fuzzer_qa.json").write_text(
        json.dumps({"ok": True, "summary": {"iterations": 400, "failures": 0}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "timeline_alignment_qa.json").write_text(
        json.dumps({"ok": True, "summary": {"max_abs_drift_px": 0}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "timeline_visual_alignment_qa" / "timeline_visual_alignment_report.json").write_text(
        json.dumps({"ok": True, "summary": {"max_abs_drift_px": 0}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "window_move_guard_qa.json").write_text(
        json.dumps({"ok": True, "summary": {"checks": 8, "passing": 8, "failures": 0}}),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "professional_runtime_next_qa.json").write_text(
        json.dumps({
            "ok": True,
            "checks": {
                "color_runtime": True,
                "preview_export_parity": True,
                "vfx_execution_plan": True,
                "local_ml_probe": True,
                "audio_stress": True,
            },
            "summary": {
                "color_delta": 8.5,
                "mask_coverage": 0.12,
                "vfx_nodes": 17,
                "local_ml_detections": 3,
                "audio_stress_tracks": 2000,
            },
        }),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "professional_pipeline_next_qa.json").write_text(
        json.dumps({
            "ok": True,
            "summary": {
                "color_score": 100,
                "audio_score": 100,
                "vfx_score": 100,
                "professional_deliver_jobs": 4,
            },
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    areas = {row["id"]: row for row in report["areas"]}

    assert areas["practical_editing_flow"]["score"] == 100
    assert areas["timeline_polish"]["score"] == 100
    assert areas["professional_runtime_parity"]["score"] == 100
    assert "vtuber_broadcast_readiness" in areas


def test_final_product_readiness_blocks_broadcast_sale_without_platform_evidence(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["vtuber_broadcast_readiness"]

    assert report["broadcast_commercial_ready"] is False
    assert report["release_ready"] is False
    assert area["release_blocking"] is True
    assert area["evidence"]["alpha_ready"] is True
    assert area["evidence"]["commercial_ready"] is False
    assert any("RTMP" in action or "Discord" in action for action in area["actions"])


def test_final_product_readiness_accepts_broadcast_platform_evidence(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["vtuber_broadcast_readiness"]

    assert report["broadcast_commercial_ready"] is True
    assert area["score"] == 100
    assert area["release_blocking"] is False


def test_final_product_readiness_blocks_screenstudio_claim_without_interaction_sidecars(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "screenstudio_real_recording_corpus_qa.json").write_text(
        json.dumps({
            "ok": True,
            "score": 53,
            "real_world_ready": False,
            "replacement_claim_ready": False,
            "replacement_claim_blockers": [
                "needs_20_more_cursor_sidecars",
                "needs_20_more_interaction_ready_sidecars",
            ],
            "summary": {
                "target_min": 20,
                "valid_files": 20,
                "video_probe_ok": 20,
                "probe_available": True,
                "cursor_sidecar_ready": 0,
                "click_ready": 0,
                "drag_ready": 0,
                "hotkey_ready": 0,
                "auto_zoom_ready": 0,
                "interaction_ready": 0,
            },
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["screenstudio_interaction_corpus"]

    assert report["release_ready"] is False
    assert report["screenstudio_replacement_claim_ready"] is False
    assert area["level"] == "blocked"
    assert area["release_blocking"] is True
    assert area["score"] < 70
    assert area["evidence"]["valid_files"] == 20
    assert area["evidence"]["cursor_sidecar_ready"] == 0
    assert any("Screen Studio replacement" in action for action in area["actions"])
    assert any("prepare_screenstudio_sidecar_intake.py" in action for action in area["actions"])
    assert any("record_screenstudio_cursor_sidecar.py" in action for action in area["actions"])
    assert area["evidence"]["sidecar_capture_tool"] == "tools/record_screenstudio_cursor_sidecar.py"


def test_final_product_readiness_accepts_interaction_ready_screenstudio_corpus(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "screenstudio_real_recording_corpus_qa.json").write_text(
        json.dumps({
            "ok": True,
            "score": 100,
            "real_world_ready": True,
            "replacement_claim_ready": True,
            "replacement_claim_blockers": [],
            "summary": {
                "target_min": 20,
                "valid_files": 20,
                "video_probe_ok": 20,
                "probe_available": True,
                "cursor_sidecar_ready": 20,
                "click_ready": 20,
                "drag_ready": 20,
                "hotkey_ready": 20,
                "auto_zoom_ready": 20,
                "interaction_ready": 20,
            },
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["screenstudio_interaction_corpus"]

    assert report["screenstudio_replacement_claim_ready"] is True
    assert area["score"] == 100
    assert area["release_blocking"] is False
    assert area["evidence"]["interaction_ready"] == 20


def test_final_product_readiness_surfaces_release_evidence_sprint_targets(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    debug = tmp_path / "debugCapture"
    sprint_dir = debug / "release_evidence_sprint"
    sprint_dir.mkdir(parents=True)
    screen_script = sprint_dir / "record_screenstudio_sidecars.ps1"
    ai_script = sprint_dir / "register_ai_real_cases.ps1"
    broadcast_script = sprint_dir / "register_broadcast_platform_evidence.ps1"
    playbook = sprint_dir / "README.md"
    screen_script.write_text("# screen evidence\n", encoding="utf-8")
    ai_script.write_text("# ai evidence\n", encoding="utf-8")
    broadcast_script.write_text("# broadcast evidence\n", encoding="utf-8")
    playbook.write_text("# sprint\n", encoding="utf-8")

    (debug / "screenstudio_real_recording_corpus_qa.json").write_text(
        json.dumps({
            "ok": True,
            "real_world_ready": False,
            "replacement_claim_ready": False,
            "summary": {
                "target_min": 20,
                "valid_files": 20,
                "cursor_sidecar_ready": 0,
                "click_ready": 0,
                "drag_ready": 0,
                "hotkey_ready": 0,
                "auto_zoom_ready": 0,
                "interaction_ready": 0,
            },
        }),
        encoding="utf-8",
    )
    (debug / "ai_edit_corpus_quality_qa.json").write_text(
        json.dumps({
            "ok": True,
            "score": 99,
            "safe_mvp_ready": True,
            "smart_edit_claim_ready": False,
            "claim_blockers": ["real_user_corpus_below_min"],
            "provider": {"direct_generation_ready": True},
            "summary": {"cases": 5, "real_cases": 0, "min_real_cases": 20},
        }),
        encoding="utf-8",
    )
    (debug / "release_evidence_sprint_qa.json").write_text(
        json.dumps({
            "kind": "release_evidence_sprint",
            "ok": True,
            "out_dir": str(sprint_dir),
            "scripts": {
                "screenstudio_sidecar_capture": str(screen_script),
                "ai_real_case_registration": str(ai_script),
                "broadcast_platform_registration": str(broadcast_script),
            },
            "playbook": str(playbook),
            "progress": {
                "overall_percent": 25,
                "ready": False,
                "blockers": ["needs_20_interaction_ready_cursor_sidecars", "needs_20_real_ai_edit_cases"],
                "screenstudio": {"target": 20, "interaction_ready": 0, "needed": 20},
                "ai": {"target": 20, "real_cases": 0, "needed": 20},
                "broadcast": {"target": 2, "ready": 0, "needed": 2},
            },
            "ai": {
                "selected_rows": [
                    {
                        "index": 1,
                        "case_id": "real_case_001",
                        "state": "needs_real_case",
                        "template_path": str(sprint_dir / "ai_edit_templates" / "real_case_001.template.json"),
                    }
                ]
            },
            "broadcast": {
                "selected_rows": [
                    {
                        "check_id": "private_rtmp_ingest",
                        "label": "Private/unlisted RTMP ingest test",
                        "ready": False,
                    }
                ]
            },
            "work_queue": [
                {
                    "kind": "screenstudio_interaction_evidence",
                    "slot_id": "screenstudio-real-01",
                    "summary": "screenstudio-real-01: Cursor sidecar",
                },
            ],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    areas = {row["id"]: row for row in report["areas"]}
    screen_sprint = areas["screenstudio_interaction_corpus"]["evidence"]["release_evidence_sprint"]
    ai_sprint = areas["ai_edit_claim_quality"]["evidence"]["release_evidence_sprint"]
    broadcast_sprint = areas["vtuber_broadcast_readiness"]["evidence"]["release_evidence_sprint"]

    assert screen_sprint["reported"] is True
    assert screen_sprint["overall_percent"] == 25
    assert screen_sprint["action_targets"]["screenstudio_sidecar_capture"]["exists"] is True
    assert [item["kind"] for item in screen_sprint["work_queue"]] == ["screenstudio_interaction_evidence"]
    assert ai_sprint["reported"] is True
    assert ai_sprint["action_targets"]["ai_real_case_registration"]["exists"] is True
    assert [item["kind"] for item in ai_sprint["work_queue"]] == ["ai_real_edit_case"]
    assert broadcast_sprint["reported"] is True
    assert broadcast_sprint["action_targets"]["broadcast_platform_registration"]["exists"] is True
    assert [item["kind"] for item in broadcast_sprint["work_queue"]] == ["broadcast_platform_evidence"]


def test_final_product_readiness_requires_preview_render_samples(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "preview_perf_report.json").write_text(
        json.dumps({
            "ok": True,
            "media_probe": [],
            "timeline_thumbnails": [],
            "native_gpu_candidates": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_gpu_performance"]

    assert area["score"] < 90
    assert area["evidence"]["render_samples"] == 0
    assert any("skip-render" in action for action in area["actions"])


def test_final_product_readiness_prefers_canonical_preview_perf_report(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    canonical = tmp_path / "debugCapture" / "preview_perf_report.json"
    canonical.write_text(
        json.dumps({
            "ok": True,
            "preview_render": [{
                "ok": True,
                "project": "canonical.tgp",
                "frame_summary": {"avg_ms": 10.0, "p95_ms": 20.0},
                "stage_summary": [],
            }],
            "native_gpu_candidates": [],
        }),
        encoding="utf-8",
    )
    (tmp_path / "debugCapture" / "preview_perf_report_experiment.json").write_text(
        json.dumps({
            "ok": True,
            "preview_render": [{
                "ok": True,
                "project": "experiment.tgp",
                "frame_summary": {"avg_ms": 80.0, "p95_ms": 120.0},
                "stage_summary": [{
                    "label": "preview.stage.decode",
                    "avg_ms": 60.0,
                    "p95_ms": 90.0,
                }],
            }],
            "native_gpu_candidates": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_gpu_performance"]

    assert area["score"] == 100
    assert area["evidence"]["report_path"].endswith("preview_perf_report.json")


def test_final_product_readiness_reads_nested_preview_stage_bottlenecks(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "preview_perf_report.json").write_text(
        json.dumps({
            "ok": True,
            "preview_render": [{
                "ok": True,
                "project": "actors.tgp",
                "sample_count": 8,
                "frame_summary": {"avg_ms": 30.0, "p95_ms": 45.0},
                "stage_summary": [{
                    "label": "preview.stage.spine_overlay",
                    "avg_ms": 40.0,
                    "p95_ms": 80.0,
                }],
            }],
            "native_gpu_candidates": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_gpu_performance"]

    assert area["score"] == 82
    assert area["evidence"]["render_samples"] == 1
    assert any("spine_overlay" in item for item in area["evidence"]["slow_stages"])


def test_final_product_readiness_separates_preview_advisory_stages(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "preview_perf_report.json").write_text(
        json.dumps({
            "ok": True,
            "preview_render": [{
                "ok": True,
                "project": "warmup.tgp",
                "sample_count": 4,
                "frame_summary": {"avg_ms": 10.0, "p95_ms": 20.0},
                "stage_summary": [{
                    "label": "preview.refresh.render",
                    "avg_ms": 400.0,
                    "p95_ms": 400.0,
                }],
            }],
            "native_gpu_candidates": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_gpu_performance"]

    assert area["score"] == 100
    assert not area["evidence"]["slow_stages"]
    assert any("refresh" in item for item in area["evidence"]["advisory_slow_stages"])


def test_final_product_readiness_gates_preview_on_playback_context(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "preview_perf_report.json").write_text(
        json.dumps({
            "ok": True,
            "preview_render": [{
                "ok": True,
                "project": "seek-heavy.tgp",
                "sample_count": 4,
                "frame_summary": {"avg_ms": 64.0, "p95_ms": 90.0},
                "playback_frame_summary": {"count": 12, "avg_ms": 7.0, "p95_ms": 12.0},
                "stage_summary": [{
                    "label": "preview.stage.decode",
                    "avg_ms": 50.0,
                    "p95_ms": 88.0,
                }],
                "stage_summary_by_context": {
                    "seek": [{
                        "label": "preview.stage.decode",
                        "avg_ms": 50.0,
                        "p95_ms": 88.0,
                    }],
                    "playback": [{
                        "label": "preview.stage.decode",
                        "avg_ms": 7.0,
                        "p95_ms": 12.0,
                    }],
                },
            }],
            "native_gpu_candidates": [{
                "label": "preview.stage.decode",
                "avg_ms": 50.0,
                "p95_ms": 88.0,
                "context": "seek",
            }],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_gpu_performance"]

    assert area["score"] == 100
    assert not area["evidence"]["slow_stages"]
    assert any("seek.preview.stage.decode" in item for item in area["evidence"]["advisory_slow_stages"])


def test_final_product_readiness_blocks_smart_ai_claim_when_provider_or_real_corpus_missing(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "ai_edit_corpus_quality_qa.json").write_text(
        json.dumps({
            "ok": True,
            "score": 82,
            "safe_mvp_ready": True,
            "smart_edit_claim_ready": False,
            "claim_blockers": ["provider_executor_not_wired", "real_user_corpus_below_min"],
            "provider": {
                "selected": "qwen_local",
                "effective": "rule_based",
                "executor_wired": False,
                "direct_generation_ready": False,
            },
            "summary": {
                "cases": 5,
                "fixture_cases": 5,
                "real_cases": 0,
                "min_real_cases": 20,
                "failures": 0,
                "missing_categories": [],
            },
            "failures": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["ai_edit_claim_quality"]

    assert report["smart_ai_edit_claim_ready"] is False
    assert report["commercial_claims_ready"] is False
    assert area["level"] == "attention"
    assert area["release_blocking"] is True
    assert area["evidence"]["safe_mvp_ready"] is True
    assert area["evidence"]["smart_edit_claim_ready"] is False
    assert any("executor" in action for action in area["actions"])
    assert any("prepare_ai_edit_corpus_intake.py" in action for action in area["actions"])
    assert any("register_ai_edit_corpus_case.py" in action for action in area["actions"])
    assert area["evidence"]["ai_case_registration_tool"] == "tools/register_ai_edit_corpus_case.py"


def test_final_product_readiness_blocks_scrub_claim_when_release_coverage_missing(tmp_path):
    from app.final_product_readiness import build_final_product_readiness_report

    (tmp_path / "debugCapture").mkdir()
    (tmp_path / "debugCapture" / "preview_scrub_readiness_qa.json").write_text(
        json.dumps({
            "ok": True,
            "score": 92,
            "current_corpus_scrub_ready": True,
            "release_scrub_claim_ready": False,
            "release_blockers": ["release_coverage_missing"],
            "summary": {
                "projects": 2,
                "ready_projects": 2,
                "warning_projects": 0,
                "blocked_projects": 0,
                "missing_release_coverage": ["actor_heavy", "hires_4k"],
            },
            "coverage": {
                "basic_video": True,
                "mask_filter_tracking": True,
                "nested_timeline": True,
                "actor_heavy": False,
                "audio_heavy": True,
                "long_project": True,
                "hires_4k": False,
            },
            "worst_projects": [],
            "top_seek_hotspots": [],
        }),
        encoding="utf-8",
    )

    report = build_final_product_readiness_report(tmp_path)
    area = {row["id"]: row for row in report["areas"]}["preview_scrub_claims"]

    assert report["preview_scrub_claim_ready"] is False
    assert report["commercial_claims_ready"] is False
    assert area["level"] == "attention"
    assert area["release_blocking"] is True
    assert area["evidence"]["current_corpus_scrub_ready"] is True
    assert area["evidence"]["release_scrub_claim_ready"] is False
    assert area["evidence"]["missing_release_coverage"] == ["actor_heavy", "hires_4k"]
    assert any("actor_heavy" in action and "hires_4k" in action for action in area["actions"])
