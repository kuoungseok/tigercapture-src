import json
from pathlib import Path


def test_simple_mode_project_patch_enables_screenstudio_defaults():
    from app.screenstudio_parity import screenstudio_simple_mode_project_patch

    patch = screenstudio_simple_mode_project_patch({"canvas_width": 1920, "canvas_height": 1080})

    assert patch["screenstudio_simple_mode"] is True
    assert patch["starter_template_id"] == "screen-recording-demo"
    assert patch["screenstudio_polish"]["cursor"]["renderer"] == "supersampled_vector"
    assert patch["screenstudio_export_defaults"]["format_id"] == "mp4"
    assert patch["screenstudio_export_defaults"]["quality_id"] == "high"
    assert patch["screenstudio_transcript_defaults"]["enabled"] is True
    assert "workbench" in patch["screenstudio_simple_mode_ui"]["hidden_by_default"]
    assert "transcript" in patch["screenstudio_simple_mode_ui"]["primary_actions"]


def test_product_grade_cursor_renderer_contract_is_complete():
    from app.screenstudio_parity import screenstudio_cursor_renderer_quality_report

    report = screenstudio_cursor_renderer_quality_report()

    assert report["ok"] is True
    assert report["score"] == 100
    assert report["supersample"] >= 2
    assert report["checks"]["hotspot_metadata"] is True
    assert report["checks"]["click_ripple"] is True
    assert report["checks"]["drag_release_accents"] is True
    assert report["checks"]["static_cursor_fade"] is True


def test_smart_cursor_fx_metadata_infers_blade_scissors():
    from app.screenstudio_polish import cursor_state_at, normalize_cursor_events

    events = normalize_cursor_events([
        {
            "t_ms": 100,
            "x_norm": 0.42,
            "y_norm": 0.55,
            "kind": "click",
            "hit_role": "blade_tool",
            "hit_label": "Blade",
        }
    ])

    assert events[0].cursor_style == "scissors"
    assert events[0].animation == "snip"
    assert events[0].to_dict()["cursor_style"] == "scissors"

    state = cursor_state_at(events, 180, click_ring_ms=520, hide_after_ms=0)

    assert state is not None
    assert state["cursor_style"] == "scissors"
    assert state["hit_role"] == "blade_tool"
    assert state["click"]["cursor_style"] == "scissors"
    assert state["click"]["animation"] == "snip"


def test_smart_cursor_fx_renders_scissors_differently_from_pointer():
    import numpy as np
    from types import SimpleNamespace

    from app.screenstudio_polish import apply_cursor_fx_rgb

    base = np.full((120, 180, 3), 24, dtype=np.uint8)
    common = {
        "t_ms": 0,
        "x_norm": 0.45,
        "y_norm": 0.46,
        "kind": "click",
        "visible": True,
    }
    pointer_owner = SimpleNamespace(
        cursor_events=[{**common, "cursor_style": "pointer"}],
        screenstudio_polish={"cursor": {"cursor_scale": 1.2, "click_ring_ms": 520, "loop_cursor": False}},
        source_duration_ms=1000,
    )
    scissors_owner = SimpleNamespace(
        cursor_events=[{**common, "hit_role": "blade_tool"}],
        screenstudio_polish={"cursor": {"cursor_scale": 1.2, "click_ring_ms": 520, "loop_cursor": False}},
        source_duration_ms=1000,
    )

    pointer = apply_cursor_fx_rgb(base, 80, owner=pointer_owner)
    scissors = apply_cursor_fx_rgb(base, 80, owner=scissors_owner)

    assert int(np.abs(pointer.astype(np.int16) - base.astype(np.int16)).sum()) > 0
    assert int(np.abs(scissors.astype(np.int16) - base.astype(np.int16)).sum()) > 0
    assert int(np.abs(scissors.astype(np.int16) - pointer.astype(np.int16)).sum()) > 1000


def test_transcript_subtitle_plan_creates_styled_subtitle_rows():
    from app.screenstudio_parity import screenstudio_transcript_subtitle_plan

    plan = screenstudio_transcript_subtitle_plan(
        {"starter_template_id": "screen-recording-demo"},
        [
            {"start_ms": 0, "end_ms": 1000, "text": "Open the project"},
            {"start_ms": 1200, "end_ms": 2400, "text": "Export it"},
        ],
        duration_ms=2600,
    )

    assert plan["ok"] is True
    assert plan["ready"] is True
    assert plan["backend_contract_ready"] is True
    assert plan["subtitle_row_count"] == 2
    assert plan["burn_subtitles_by_default"] is True
    assert plan["subtitle_rows"][0]["style"]["preset_id"].startswith("caption-")
    assert plan["subtitle_rows"][0]["show_box"] is True


def test_srt_import_plan_uses_screenstudio_caption_style():
    from app.screenstudio_parity import (
        screenstudio_parse_srt_text,
        screenstudio_subtitle_rows_from_srt_text,
    )

    text = (
        "1\n"
        "00:00:01,000 --> 00:00:02,250\n"
        "Open the editor\n\n"
        "2\n"
        "00:00:03.000 --> 00:00:04.500\n"
        "Export the clip\n"
    )

    parsed = screenstudio_parse_srt_text(text)
    plan = screenstudio_subtitle_rows_from_srt_text(
        text,
        {"starter_template_id": "screen-recording-demo"},
    )

    assert parsed[0]["start_ms"] == 1000
    assert parsed[1]["end_ms"] == 4500
    assert plan["ready"] is True
    assert plan["subtitle_row_count"] == 2
    assert plan["subtitle_rows"][0]["style"]["preset_id"] == "caption-ui-demo-soft-glass"


def test_recording_corpus_plan_tracks_real_corpus_gap_truthfully():
    from app.screenstudio_parity import screenstudio_recording_corpus_plan

    plan = screenstudio_recording_corpus_plan()

    assert plan["ok"] is True
    assert plan["contract_ready"] is True
    assert plan["fixture_samples"] >= 7
    assert plan["target_min"] == 20
    assert plan["target_recommended"] == 50
    assert len(plan["required_slots"]) >= 20
    assert plan["real_recordings"] >= 0
    assert isinstance(plan["real_corpus_ready"], bool)


def test_recording_corpus_manifest_registration_counts_real_video(tmp_path):
    from app.screenstudio_parity import (
        screenstudio_recording_corpus_plan,
        screenstudio_real_recording_corpus_report,
        screenstudio_register_real_recording,
    )

    video_path = tmp_path / "screen-recording.mp4"
    video_path.write_bytes(b"0" * (1024 * 1024 + 16))
    manifest_path = tmp_path / "manifest.json"

    report = screenstudio_register_real_recording(
        video_path,
        manifest_path=manifest_path,
        slot_id="screenstudio-real-01",
        metadata={"reason": "test"},
    )
    plan = screenstudio_recording_corpus_plan(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest_path,
    )

    assert report["registered"] is True
    assert report["recordings"] == 1
    assert plan["real_recordings"] == 1
    assert plan["recording_candidates"][0]["slot_id"] == "screenstudio-real-01"

    validation = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest_path,
        deep_probe=False,
    )
    assert validation["ok"] is True
    assert validation["summary"]["real_recordings"] == 1
    assert validation["summary"]["valid_files"] == 1
    assert validation["summary"]["target_min"] == 20
    assert validation["rows"][0]["basic_file_ok"] is True
    assert validation["rows"][0]["interaction_ready"] is False
    assert validation["summary"]["interaction_ready"] == 0
    assert validation["summary"]["click_ready"] == 0
    assert validation["summary"]["auto_zoom_ready"] == 0
    assert "missing_cursor_sidecar" in validation["rows"][0]["warnings"]


def test_recording_corpus_manifest_accepts_utf8_bom_without_dropping_rows(tmp_path):
    from app.screenstudio_parity import (
        screenstudio_recording_corpus_plan,
        screenstudio_real_recording_corpus_report,
        screenstudio_register_real_recording,
    )

    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"1" * (1024 * 1024 + 16))
    second.write_bytes(b"2" * (1024 * 1024 + 16))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "recordings": [
                    {
                        "path": str(first),
                        "size_bytes": first.stat().st_size,
                        "slot_id": "screenstudio-real-01",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8-sig",
    )

    plan = screenstudio_recording_corpus_plan(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
    )
    validation = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )
    registration = screenstudio_register_real_recording(
        second,
        manifest_path=manifest,
        slot_id="screenstudio-real-02",
    )
    repaired_payload = json.loads(manifest.read_text(encoding="utf-8-sig"))

    assert plan["real_recordings"] == 1
    assert validation["summary"]["valid_files"] == 1
    assert registration["registered"] is True
    assert registration["recordings"] == 2
    assert [row["slot_id"] for row in repaired_payload["recordings"]] == [
        "screenstudio-real-01",
        "screenstudio-real-02",
    ]


def test_screenstudio_remaining_parity_contracts_cover_all_open_todos():
    from app.screenstudio_parity import (
        screenstudio_advanced_strengths_separation_report,
        screenstudio_audio_subtitle_timing_report,
        screenstudio_export_handoff_polish_report,
        screenstudio_first_run_empty_project_report,
        screenstudio_golden_short_video_baseline_plan,
        screenstudio_manual_zoom_viewer_affordance_report,
        screenstudio_motion_tuning_report,
        screenstudio_real_project_corpus_run_report,
        screenstudio_vertical_social_export_plan,
    )

    reports = [
        screenstudio_first_run_empty_project_report(),
        screenstudio_motion_tuning_report(),
        screenstudio_manual_zoom_viewer_affordance_report(),
        screenstudio_vertical_social_export_plan(),
        screenstudio_export_handoff_polish_report(),
        screenstudio_audio_subtitle_timing_report(),
        screenstudio_golden_short_video_baseline_plan(),
        screenstudio_real_project_corpus_run_report({"summary": {"target_min": 20, "target_recommended": 50, "valid_files": 0, "interaction_ready": 0}}),
        screenstudio_advanced_strengths_separation_report(),
    ]

    assert all(report["ok"] for report in reports)
    assert reports[0]["empty_state"]["primary_action"] == "Import media"
    assert reports[2]["viewer_overlay"]["handles"]
    assert reports[3]["export_defaults"]["intent_id"] == "social_vertical"
    assert reports[4]["checks"]["four_k_sixty_validation"] is True
    assert reports[5]["checks"]["subtitle_rows_timed"] is True
    assert reports[6]["golden_samples"]
    assert reports[7]["real_world_ready"] is False
    assert reports[8]["checks"]["advanced_tools_not_primary"] is True


def test_screenstudio_parity_gap_report_summarizes_all_gap_contracts():
    from app.screenstudio_parity import screenstudio_parity_gap_report

    report = screenstudio_parity_gap_report()

    assert report["ok"] is True
    assert report["implementation_ok"] is True
    assert report["summary"]["areas"] >= 18
    assert report["summary"]["passing"] == report["summary"]["areas"]
    assert report["summary"]["first_run_empty_project"] is True
    assert report["summary"]["cursor_renderer"] is True
    assert report["summary"]["motion_tuning_contract"] is True
    assert report["summary"]["manual_zoom_viewer_contract"] is True
    assert report["summary"]["vertical_social_export"] is True
    assert report["summary"]["export_handoff_polish"] is True
    assert report["summary"]["transcript_subtitle_contract"] is True
    assert report["summary"]["audio_subtitle_timing_contract"] is True
    assert report["summary"]["golden_short_video_baseline"] is True
    assert report["summary"]["advanced_strengths_separated"] is True
    assert report["summary"]["real_recording_intake_board"] is True
    assert report["summary"]["adaptive_motion_tuning_patch"] is True
    assert report["summary"]["manual_zoom_command_model"] is True
    assert report["summary"]["export_result_parity_matrix"] is True
    assert report["summary"]["regression_hardening_plan"] is True
    assert report["project_settings_patch"]["screenstudio_simple_mode_profile"]["recommended_layout"] == "simple_screen_studio"
    assert report["productization"]["implementation_ok"] is True


def test_screenstudio_productization_next_report_exposes_actionable_work():
    from app.screenstudio_parity import (
        screenstudio_adaptive_motion_tuning_patch,
        screenstudio_export_result_parity_matrix,
        screenstudio_manual_zoom_viewer_command_model,
        screenstudio_productization_next_report,
        screenstudio_real_recording_intake_board,
        screenstudio_real_recording_slot_board,
        screenstudio_regression_hardening_plan,
    )

    fake_corpus = {
        "summary": {
            "target_min": 20,
            "target_recommended": 50,
            "valid_files": 2,
            "interaction_ready": 1,
            "click_ready": 1,
            "auto_zoom_ready": 1,
        },
        "rows": [
            {"slot_id": "screenstudio-real-01", "basic_file_ok": True, "duration_ms": 120_000},
            {"slot_id": "screenstudio-real-02", "basic_file_ok": True, "duration_ms": 240_000},
        ],
    }

    intake = screenstudio_real_recording_intake_board(fake_corpus)
    slot_board = screenstudio_real_recording_slot_board(fake_corpus)
    motion = screenstudio_adaptive_motion_tuning_patch(real_corpus_report=fake_corpus)
    command_model = screenstudio_manual_zoom_viewer_command_model()
    matrix = screenstudio_export_result_parity_matrix()
    regressions = screenstudio_regression_hardening_plan()
    report = screenstudio_productization_next_report(real_corpus_report=fake_corpus)

    assert intake["missing_for_minimum"] == 18
    assert slot_board["summary"]["slots"] == 20
    assert slot_board["summary"]["registered"] == 2
    assert slot_board["summary"]["needs_sidecar"] == 2
    assert intake["slot_board"]["summary"]["empty"] == 18
    assert intake["checklist"][0]["register_command"].startswith("python tools/register_screenstudio_real_recording.py")
    assert motion["project_settings_patch"]["screenstudio_motion_tuning"]["needs_real_corpus"] is True
    assert motion["project_settings_patch"]["screenstudio_polish"]["cursor"]["click_hold_ms"] >= 155
    assert any(command["id"] == "easing-popover" for command in command_model["commands"])
    assert command_model["keyboard"]["escape"] == "cancel edit"
    assert len(matrix["rows"]) >= 5
    assert all(row["parity_ok"] for row in matrix["rows"])
    assert any(row["target_id"] == "4k60" for row in matrix["rows"])
    assert any(row["id"] == "spine_zoom_crop" for row in regressions["watchlist"])
    assert report["implementation_ok"] is True
    assert report["real_world_ready"] is False
    assert report["summary"]["missing_for_minimum"] == 18
    assert report["summary"]["recording_slots_empty"] == 18


def test_screenstudio_slot_board_separates_click_drag_hotkey_quality():
    from app.screenstudio_parity import screenstudio_real_recording_slot_board

    fake_corpus = {
        "summary": {"target_min": 20},
        "rows": [{
            "slot_id": "screenstudio-real-01",
            "basic_file_ok": True,
            "cursor_sidecar_ok": True,
            "cursor_event_count": 8,
            "click_event_count": 2,
            "drag_event_count": 0,
            "hotkey_event_count": 0,
            "auto_zoom_count": 1,
            "duration_ms": 90_000,
        }],
    }

    slot_board = screenstudio_real_recording_slot_board(fake_corpus)
    first = slot_board["rows"][0]

    assert first["state"] == "needs_drag_hotkey"
    assert first["interaction_quality_score"] == 75
    assert first["missing_interaction_requirements"] == ["drag", "hotkey"]
    assert slot_board["summary"]["needs_drag_hotkey"] == 1
    assert slot_board["summary"]["ready"] == 0


def test_screenstudio_parity_gap_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_screenstudio_parity_gap

    out = tmp_path / "screenstudio_parity_gap_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_screenstudio_parity_gap.py", "--out", str(out)],
    )

    assert qa_screenstudio_parity_gap.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["implementation_ok"] is True
    assert payload["summary"]["areas"] >= 18
    assert payload["summary"]["real_recording_target_min"] == 20


def test_screenstudio_productization_next_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_screenstudio_productization_next

    out = tmp_path / "screenstudio_productization_next_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_screenstudio_productization_next.py", "--out", str(out)],
    )

    assert qa_screenstudio_productization_next.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["implementation_ok"] is True
    assert payload["summary"]["areas"] >= 6
    assert payload["summary"]["export_targets"] >= 5


def test_product_polish_next_report_and_dashboard_runner(tmp_path, monkeypatch):
    from app.product_polish import product_polish_readiness_report
    from app.qa_dashboard import QADashboardDialog
    from tools import qa_product_polish_next

    report = product_polish_readiness_report()
    command = QADashboardDialog._command_for_row({
        "kind": "product_polish_next",
        "path": str(tmp_path / "product_polish_next_qa.json"),
    })
    out = tmp_path / "product_polish_next_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_product_polish_next.py", "--out", str(out)],
    )

    assert report["implementation_ok"] is True
    assert report["summary"]["areas"] == 10
    assert report["summary"]["passing"] == 10
    assert command is not None
    assert "qa_product_polish_next.py" in " ".join(command)
    assert qa_product_polish_next.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["implementation_ok"] is True
    assert payload["summary"]["areas"] == 10


def test_screenstudio_render_result_smoke_qa_tool_writes_real_video(tmp_path, monkeypatch):
    from tools import qa_screenstudio_render_result_smoke

    out = tmp_path / "screenstudio_render_result_smoke_report.json"
    video = tmp_path / "screenstudio_default_smoke.mp4"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_screenstudio_render_result_smoke.py", "--out", str(out), "--video", str(video)],
    )

    assert qa_screenstudio_render_result_smoke.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert video.exists()
    assert payload["summary"]["frames"] >= 24
    assert payload["checks"]["frames_change"] is True


def test_real_project_product_flow_qa_uses_project_files(tmp_path, monkeypatch):
    from tools import qa_real_project_product_flow

    project = tmp_path / "tutorial_project.tgp"
    project.write_text(
        json.dumps(
            {
                "video_tracks": [
                    {
                        "clips": [
                            {
                                "source_path": str(tmp_path / "screen_capture.mp4"),
                                "duration_ms": 12_000,
                                "timeline_out_ms": 12_000,
                            }
                        ]
                    }
                ],
                "audio_tracks": [],
                "media_pool": [str(tmp_path / "screen_capture.mp4")],
                "project_settings": {"starter_template_id": "screen-recording-demo"},
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "real_project_product_flow_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_real_project_product_flow.py", "--out", str(out), "--root", str(tmp_path), "--limit", "1"],
    )

    assert qa_real_project_product_flow.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["summary"]["projects"] == 1
    assert payload["summary"]["render_frames"] >= 24
    assert payload["checks"]["preset_plans_export_baked"] is True


def test_screenstudio_real_recording_corpus_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_screenstudio_real_recording_corpus

    out = tmp_path / "screenstudio_real_recording_corpus_qa.json"
    manifest = tmp_path / "real_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "qa_screenstudio_real_recording_corpus.py",
            "--out",
            str(out),
            "--real-manifest",
            str(manifest),
            "--no-probe",
        ],
    )

    assert qa_screenstudio_real_recording_corpus.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["implementation_ok"] is True
    assert payload["summary"]["target_min"] == 20


def test_register_screenstudio_real_recording_cli_updates_manifest(tmp_path, monkeypatch, capsys):
    from tools import register_screenstudio_real_recording

    video = tmp_path / "recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_screenstudio_real_recording.py",
            "--source",
            str(video),
            "--slot-id",
            "screenstudio-real-03",
            "--manifest",
            str(manifest),
            "--label",
            "Browser docs",
        ],
    )

    assert register_screenstudio_real_recording.main() == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)

    assert stdout["registered"] is True
    assert payload["recordings"][0]["slot_id"] == "screenstudio-real-03"
    assert payload["recordings"][0]["label"] == "Browser docs"
    assert payload["recordings"][0]["sidecar_ready"] is False


def test_register_screenstudio_real_recording_can_require_sidecar(tmp_path, monkeypatch, capsys):
    from tools import register_screenstudio_real_recording

    video = tmp_path / "recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_screenstudio_real_recording.py",
            "--source",
            str(video),
            "--slot-id",
            "screenstudio-real-04",
            "--manifest",
            str(manifest),
            "--require-sidecar",
        ],
    )

    assert register_screenstudio_real_recording.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["registered"] is False
    assert stdout["warning"] == "cursor_sidecar_required"
    assert not manifest.exists()


def test_register_screenstudio_real_recording_records_sidecar_metadata(tmp_path, monkeypatch, capsys):
    from tools import register_screenstudio_real_recording
    from app.screenstudio_parity import screenstudio_real_recording_corpus_report

    video = tmp_path / "recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    Path(str(video) + ".cursor.json").write_text(
        json.dumps(
            {
                "events": [
                    {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.2, "kind": "move"},
                    {"t_ms": 500, "x_norm": 0.2, "y_norm": 0.2, "kind": "click"},
                    {"t_ms": 900, "x_norm": 0.4, "y_norm": 0.4, "kind": "drag"},
                    {"t_ms": 1300, "x_norm": 0.5, "y_norm": 0.5, "kind": "release"},
                    {"t_ms": 1800, "x_norm": 0.6, "y_norm": 0.5, "kind": "hotkey", "label": "Ctrl+K"},
                    {"t_ms": 2600, "x_norm": 0.75, "y_norm": 0.65, "kind": "move"},
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_screenstudio_real_recording.py",
            "--source",
            str(video),
            "--slot-id",
            "screenstudio-real-05",
            "--manifest",
            str(manifest),
            "--require-sidecar",
        ],
    )

    assert register_screenstudio_real_recording.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    validation = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert stdout["registered"] is True
    assert stdout["sidecar_ready"] is True
    assert stdout["cursor_event_count"] == 6
    assert stdout["auto_zoom_count"] >= 1
    assert payload["recordings"][0]["sidecar_ready"] is True
    assert payload["recordings"][0]["cursor_counts"]["click"] == 1
    assert validation["summary"]["cursor_sidecar_ready"] == 1
    assert validation["summary"]["interaction_ready"] == 1
    assert validation["replacement_claim_ready"] is False
    assert "needs_19_more_cursor_sidecars" in validation["replacement_claim_blockers"]


def test_screenstudio_sidecar_intake_writes_safe_templates_without_faking_readiness(tmp_path):
    from app.screenstudio_parity import screenstudio_register_real_recording, screenstudio_real_recording_corpus_report
    from app.screenstudio_sidecar_intake import build_screenstudio_sidecar_intake_report

    video = tmp_path / "recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    manifest = tmp_path / "manifest.json"
    screenstudio_register_real_recording(
        video,
        manifest_path=manifest,
        slot_id="screenstudio-real-01",
        metadata={"reason": "test"},
    )
    corpus = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )
    report = build_screenstudio_sidecar_intake_report(
        real_corpus_report=corpus,
        template_dir=tmp_path / "templates",
        write_templates=True,
    )
    template_path = Path(report["rows"][0]["template_path"])
    template = json.loads(template_path.read_text(encoding="utf-8"))
    unchanged = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert report["summary"]["needs_sidecar"] == 1
    assert report["summary"]["needs_click"] == 1
    assert report["summary"]["templates_written"] == 1
    assert template_path.name.endswith(".cursor.template.json")
    assert template["events"] == []
    assert template["example_events"]
    assert template["counts_for_qa"] is False
    assert "record_screenstudio_cursor_sidecar.py" in template["sidecar_capture_command"]
    assert "--from-template" in template["sidecar_capture_command"]
    assert "record_screenstudio_cursor_sidecar.py" in report["rows"][0]["sidecar_capture_command"]
    assert "--from-template" in report["rows"][0]["sidecar_capture_command"]
    assert template["target_sidecar_path"].endswith(".mp4.cursor.json")
    assert not Path(template["target_sidecar_path"]).exists()
    assert unchanged["summary"]["cursor_sidecar_ready"] == 0
    assert unchanged["summary"]["interaction_ready"] == 0


def test_prepare_screenstudio_sidecar_intake_cli_writes_report_and_template(tmp_path, monkeypatch, capsys):
    from app.screenstudio_parity import screenstudio_register_real_recording
    from tools import prepare_screenstudio_sidecar_intake

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "intake.json"
    template_dir = tmp_path / "templates"
    screenstudio_register_real_recording(video, manifest_path=manifest, slot_id="screenstudio-real-02")
    monkeypatch.setattr(
        "sys.argv",
        [
            "prepare_screenstudio_sidecar_intake.py",
            "--real-manifest",
            str(manifest),
            "--out",
            str(out),
            "--template-dir",
            str(template_dir),
            "--write-templates",
        ],
    )

    assert prepare_screenstudio_sidecar_intake.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    printed = capsys.readouterr().out

    assert payload["kind"] == "screenstudio_sidecar_intake"
    assert payload["summary"]["templates_written"] == 1
    assert Path(payload["rows"][0]["template_path"]).is_file()
    assert "screenstudio_sidecar_intake" in printed


def test_record_screenstudio_cursor_sidecar_cli_writes_ready_sidecar_and_registers(tmp_path, monkeypatch, capsys):
    from app.screenstudio_parity import screenstudio_real_recording_corpus_report
    from app.screenstudio_polish import screenstudio_sidecar_report
    from tools import record_screenstudio_cursor_sidecar

    video = tmp_path / "recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    events_path = tmp_path / "events.json"
    events_path.write_text(
        json.dumps(
            {
                "events": [
                    {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.2, "kind": "move"},
                    {"t_ms": 420, "x_norm": 0.2, "y_norm": 0.2, "kind": "click"},
                    {"t_ms": 800, "x_norm": 0.38, "y_norm": 0.42, "kind": "drag"},
                    {"t_ms": 1140, "x_norm": 0.52, "y_norm": 0.5, "kind": "release"},
                    {"t_ms": 1660, "x_norm": 0.62, "y_norm": 0.44, "kind": "hotkey", "label": "Ctrl+K"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_screenstudio_cursor_sidecar.py",
            "--video",
            str(video),
            "--from-events",
            str(events_path),
            "--duration-ms",
            "2400",
            "--register",
            "--manifest",
            str(manifest),
            "--slot-id",
            "screenstudio-real-03",
        ],
    )

    assert record_screenstudio_cursor_sidecar.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    sidecar_path = Path(stdout["sidecar_path"])
    sidecar_payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar_report = screenstudio_sidecar_report(video, duration_ms=2400)
    corpus = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert sidecar_path.name.endswith(".mp4.cursor.json")
    assert sidecar_payload["counts_for_qa"] is True
    assert stdout["registration"]["registered"] is True
    assert stdout["registration"]["sidecar_ready"] is True
    assert sidecar_report["ok"] is True
    assert sidecar_report["counts"]["click"] == 1
    assert corpus["summary"]["cursor_sidecar_ready"] == 1
    assert corpus["summary"]["interaction_ready"] == 1


def test_record_screenstudio_cursor_sidecar_cli_uses_filled_template(tmp_path, monkeypatch, capsys):
    from app.screenstudio_parity import screenstudio_register_real_recording, screenstudio_real_recording_corpus_report
    from app.screenstudio_sidecar_intake import build_screenstudio_sidecar_intake_report
    from tools import record_screenstudio_cursor_sidecar

    video = tmp_path / "template-recording.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    manifest = tmp_path / "manifest.json"
    screenstudio_register_real_recording(video, manifest_path=manifest, slot_id="screenstudio-real-04")
    corpus = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )
    intake = build_screenstudio_sidecar_intake_report(
        real_corpus_report=corpus,
        template_dir=tmp_path / "templates",
        write_templates=True,
    )
    template_path = Path(intake["rows"][0]["template_path"])
    template = json.loads(template_path.read_text(encoding="utf-8"))
    template["events"] = [
        {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.2, "kind": "move"},
        {"t_ms": 320, "x_norm": 0.22, "y_norm": 0.24, "kind": "click"},
        {"t_ms": 720, "x_norm": 0.40, "y_norm": 0.42, "kind": "drag"},
        {"t_ms": 1040, "x_norm": 0.52, "y_norm": 0.52, "kind": "release"},
        {"t_ms": 1500, "x_norm": 0.70, "y_norm": 0.40, "kind": "hotkey", "label": "Ctrl+K"},
    ]
    template_path.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_screenstudio_cursor_sidecar.py",
            "--from-template",
            str(template_path),
            "--register",
            "--manifest",
            str(manifest),
        ],
    )

    assert record_screenstudio_cursor_sidecar.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    refreshed = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert Path(stdout["sidecar_path"]).is_file()
    assert stdout["counts_for_qa"] is True
    assert stdout["registration"]["sidecar_ready"] is True
    assert refreshed["summary"]["cursor_sidecar_ready"] == 1
    assert refreshed["summary"]["interaction_ready"] == 1


def test_record_screenstudio_cursor_sidecar_cli_rejects_empty_template(tmp_path, monkeypatch, capsys):
    from app.screenstudio_sidecar_intake import sidecar_template_for_recording
    from tools import record_screenstudio_cursor_sidecar

    video = tmp_path / "empty-template.mp4"
    video.write_bytes(b"0" * (1024 * 1024 + 8))
    template_path = tmp_path / "empty.cursor.template.json"
    template_path.write_text(
        json.dumps(sidecar_template_for_recording({"path": str(video)}, template_path=template_path), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "record_screenstudio_cursor_sidecar.py",
            "--from-template",
            str(template_path),
        ],
    )

    assert record_screenstudio_cursor_sidecar.main() == 1
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["reason"] == "template_events_empty"
    assert not Path(str(video) + ".cursor.json").exists()


def test_promote_screenstudio_sidecar_templates_cli_batches_filled_templates(tmp_path, monkeypatch, capsys):
    from app.screenstudio_parity import screenstudio_register_real_recording, screenstudio_real_recording_corpus_report
    from app.screenstudio_sidecar_intake import build_screenstudio_sidecar_intake_report
    from tools import promote_screenstudio_sidecar_templates

    manifest = tmp_path / "manifest.json"
    videos = [tmp_path / "recording-a.mp4", tmp_path / "recording-b.mp4"]
    for idx, video in enumerate(videos, start=1):
        video.write_bytes(b"0" * (1024 * 1024 + idx))
        screenstudio_register_real_recording(video, manifest_path=manifest, slot_id=f"screenstudio-real-{idx:02d}")
    corpus = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )
    intake = build_screenstudio_sidecar_intake_report(
        real_corpus_report=corpus,
        template_dir=tmp_path / "templates",
        write_templates=True,
    )
    filled_template = Path(intake["rows"][0]["template_path"])
    template = json.loads(filled_template.read_text(encoding="utf-8"))
    template["events"] = [
        {"t_ms": 0, "x_norm": 0.2, "y_norm": 0.2, "kind": "move"},
        {"t_ms": 300, "x_norm": 0.22, "y_norm": 0.22, "kind": "click"},
        {"t_ms": 700, "x_norm": 0.40, "y_norm": 0.42, "kind": "drag"},
        {"t_ms": 980, "x_norm": 0.55, "y_norm": 0.50, "kind": "release"},
        {"t_ms": 1300, "x_norm": 0.65, "y_norm": 0.30, "kind": "hotkey", "label": "Ctrl+K"},
    ]
    filled_template.write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "promote_screenstudio_sidecar_templates.py",
            "--template-dir",
            str(tmp_path / "templates"),
            "--register",
            "--manifest",
            str(manifest),
        ],
    )

    assert promote_screenstudio_sidecar_templates.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    refreshed = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert stdout["summary"]["templates"] == 2
    assert stdout["summary"]["written"] == 1
    assert stdout["summary"]["registered"] == 1
    assert stdout["summary"]["skipped_empty"] == 1
    assert refreshed["summary"]["interaction_ready"] == 1


def test_register_screenstudio_real_recording_cli_scans_roots_and_assigns_slots(tmp_path, monkeypatch, capsys):
    from tools import register_screenstudio_real_recording
    from app.screenstudio_parity import screenstudio_real_recording_corpus_report

    scan_root = tmp_path / "recordings"
    scan_root.mkdir()
    for idx in range(3):
        (scan_root / f"recording-{idx}.mp4").write_bytes(b"0" * (1024 * 1024 + 32 + idx))
    (scan_root / "tiny.mp4").write_bytes(b"tiny")
    (scan_root / "ignore.txt").write_text("not video", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "register_screenstudio_real_recording.py",
            "--scan-root",
            str(scan_root),
            "--manifest",
            str(manifest),
            "--limit",
            "2",
            "--label",
            "Batch",
        ],
    )

    assert register_screenstudio_real_recording.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    validation = screenstudio_real_recording_corpus_report(
        manifest_path=None,
        real_roots=[tmp_path / "empty"],
        real_manifest_path=manifest,
        deep_probe=False,
    )

    assert stdout["registered"] == 2
    assert stdout["scanned"] == 3
    assert stdout["recordings"] == 2
    assert stdout["missing_for_minimum"] == 18
    assert [row["slot_id"] for row in payload["recordings"]] == [
        "screenstudio-real-01",
        "screenstudio-real-02",
    ]
    assert all(row["label"] == "Batch" for row in payload["recordings"])
    assert validation["summary"]["valid_files"] == 2


def test_repair_screenstudio_real_recording_manifest_slots(tmp_path, monkeypatch, capsys):
    from app.screenstudio_parity import screenstudio_repair_real_recording_manifest_slots
    from tools import register_screenstudio_real_recording

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "recordings": [
                    {"path": "a.mp4", "slot_id": "screenstudio-real-01"},
                    {"path": "b.mp4", "slot_id": "screenstudio-real-01"},
                    {"path": "c.mp4", "slot_id": ""},
                ],
            }
        ),
        encoding="utf-8",
    )

    dry = screenstudio_repair_real_recording_manifest_slots(manifest, dry_run=True)
    unchanged = json.loads(manifest.read_text(encoding="utf-8"))

    assert dry["changed"] == 2
    assert dry["duplicate_slots_before"] == ["screenstudio-real-01"]
    assert unchanged["recordings"][1]["slot_id"] == "screenstudio-real-01"

    monkeypatch.setattr(
        "sys.argv",
        [
            "register_screenstudio_real_recording.py",
            "--manifest",
            str(manifest),
            "--repair-slots",
        ],
    )

    assert register_screenstudio_real_recording.main() == 0
    stdout = json.loads(capsys.readouterr().out)
    repaired = json.loads(manifest.read_text(encoding="utf-8"))
    slots = [row["slot_id"] for row in repaired["recordings"]]

    assert stdout["changed"] == 2
    assert slots == ["screenstudio-real-01", "screenstudio-real-02", "screenstudio-real-03"]
