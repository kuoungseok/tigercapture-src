from __future__ import annotations

import json
import os
from pathlib import Path
import struct


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _FakePixmap:
    def save(self, path: str) -> bool:
        from PIL import Image

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (24, 16), (92, 70, 255)).save(target)
        return True


def _write_vrm0(path: Path) -> Path:
    gltf = {
        "asset": {"version": "2.0"},
        "extensionsUsed": ["VRM"],
        "extensions": {
            "VRM": {
                "meta": {"title": "Action Test", "author": "unit-test"},
                "humanoid": {"humanBones": [{"bone": "hips", "node": 0}]},
            }
        },
        "nodes": [{"name": "hips"}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    chunk = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(chunk) % 4:
        chunk += b" "
    path.write_bytes(
        b"glTF"
        + struct.pack("<II", 2, 12 + 8 + len(chunk))
        + struct.pack("<I4s", len(chunk), b"JSON")
        + chunk
    )
    return path


class _ActionOwner:
    def __init__(self) -> None:
        from app.audio_tracks import AudioClip, AudioTrack
        from app.timeline_model import VideoClip, VideoTrack

        self._tracks = [
            VideoTrack(
                id=1,
                clips=[
                    VideoClip(
                        id=10,
                        source_duration_ms=5000,
                        timeline_in_ms=0,
                        source_in_ms=0,
                        source_out_ms=5000,
                    )
                ],
            )
        ]
        self._audio_tracks = [
            AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=3000, offset_ms=500)])
        ]
        self._timeline_markers = []
        self._selected_clips = [(1, 10)]
        self._project_settings = {}
        self.marker_sync_count = 0
        self.refresh_count = 0
        self.width_refresh_count = 0
        self.ensure_visible_count = 0
        self.undo_count = 0
        self.redo_count = 0
        self.staged_render_payloads: list[dict] = []
        self.opened_hosts: list[object] = []
        self._render_queue_section_host = object()
        self._px_per_sec = 40.0
        self._action_timeline_width = 1000
        self.changes: list[str] = []

    def _sync_markers_to_ruler(self) -> None:
        self.marker_sync_count += 1

    def _register_change(self, label: str = "") -> None:
        self.changes.append(label)

    def _refresh_player_tracks(self) -> None:
        self.refresh_count += 1

    def _update_tracks_host_width(self) -> None:
        self.width_refresh_count += 1

    def _zoom_fit(self) -> None:
        self._px_per_sec = 190.0

    def _ensure_playhead_visible(self) -> None:
        self.ensure_visible_count += 1

    def _on_undo(self) -> None:
        self.undo_count += 1

    def _on_redo(self) -> None:
        self.redo_count += 1

    def _stage_ai_script_render_jobs(self, payload: dict | None = None) -> dict:
        row_count = len((payload or {}).get("render_queue_jobs") or [])
        self.staged_render_payloads.append(dict(payload or {}))
        return {"ok": True, "added": row_count, "skipped": 0, "job_ids": [f"job-{i + 1}" for i in range(row_count)], "warnings": []}

    def _set_collapsible_host_open(self, host, open_state: bool) -> None:
        if open_state:
            self.opened_hosts.append(host)

    def grab(self) -> _FakePixmap:
        return _FakePixmap()


def test_action_registry_exposes_safe_initial_specs():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(_ActionOwner())
    specs = registry.specs()
    ids = {row["id"] for row in specs}

    assert {
        "app.status",
        "project.snapshot",
        "timeline.summary",
        "timeline.nle_status",
        "timeline.professional_nle_readiness",
        "timeline.nle_target_gap",
        "timeline.nle_evidence",
        "nle.real_corpus.status",
        "nle.real_corpus.discover",
        "nle.real_corpus.intake_board",
        "nle.real_corpus.collection_kit",
        "nle.real_corpus.gate_board",
        "nle.real_corpus.workbench",
        "nle.real_corpus.validation_plan",
        "nle.real_corpus.validation_packet",
        "nle.real_corpus.validation_preflight",
        "nle.real_corpus.validation_report",
        "nle.real_corpus.validation_evidence.register",
        "timeline.nle_fuzzer.status",
        "timeline.core_action_coverage",
        "timeline.nle_core_safety_matrix",
        "timeline.undo_health",
        "timeline.undo_review_board",
        "timeline.undo_recovery_playbook",
        "timeline.undo_stability_dashboard",
        "timeline.undo_long_session_plan",
        "timeline.magnetic_storyline.status",
        "timeline.magnetic_storyline.apply",
        "timeline.magnetic_storyline.drag_preview",
        "timeline.storyline_gesture_polish_board",
        "timeline.connected_clips.status",
        "timeline.connected_clips.connect",
        "timeline.connected_clips.anchor_overlay",
        "timeline.role_colors.status",
        "timeline.role_lanes.status",
        "timeline.role_lanes.focus",
        "timeline.role_lanes.filter_model",
        "timeline.clip_role.set",
        "timeline.auditions.status",
        "timeline.audition.compare",
        "timeline.audition.add_take",
        "timeline.audition.switch_take",
        "timeline.audition.rename_take",
        "timeline.audition.remove_take",
        "timeline.multicam.summary",
        "timeline.multicam.create_group",
        "timeline.multicam.sync_plan",
        "timeline.multicam.switch_plan",
        "timeline.multicam.angle_bins",
        "timeline.multicam.set_active_angle",
        "timeline.multicam.switcher_workbench",
        "timeline.multicam.tile_board",
        "timeline.multicam.review_board",
        "timeline.multicam.sync_quality_board",
        "timeline.multicam.waveform_sync_board",
        "timeline.multicam.export_parity_board",
        "timeline.multicam.export_handoff",
        "creative_layer.readiness",
        "timeline.edit_points",
        "timeline.jump_edit_point",
        "timeline.range",
        "source_monitor.state",
        "source_monitor.load_media",
        "source_monitor.set_in",
        "source_monitor.set_out",
        "source_monitor.clear",
        "record_monitor.state",
        "record_monitor.set_in",
        "record_monitor.set_out",
        "record_monitor.clear",
        "source_record.workbench",
        "source_record.edit_decision_preview",
        "source_record.patch_matrix",
        "source_record.monitor_layout",
        "source_record.apply_board",
        "source_record.keyboard_overlay",
        "source_record.usability_board",
        "timeline.set_in",
        "timeline.set_out",
        "timeline.clear_in_out",
        "timeline.set_in_out_from_selection",
        "timeline.jump_in_out",
        "timeline.track_targets",
        "timeline.track_target.set",
        "timeline.track_target.clear",
        "timeline.range_delete",
        "timeline.lift",
        "timeline.extract",
        "timeline.play",
        "timeline.pause",
        "timeline.stop",
        "timeline.step_frames",
        "timeline.set_shuttle_rate",
        "timeline.play_range",
        "timeline.play_clip_range",
        "media.summary",
        "project_bin.workbench",
        "project_bin.batch_plan",
        "project_bin.conform_report",
        "project_bin.review_board",
        "project_bin.offline_browser",
        "project_bin.relink_candidate_board",
        "project_bin.proxy_regeneration_board",
        "project_bin.proxy_conflict_board",
        "project_bin.proxy_apply_review_board",
        "project_bin.conform_apply_review_board",
        "project_bin.search_filter_model",
        "project_bin.proxy_plan",
        "project_bin.proxy_health",
        "timeline.multicam.live_switch_dashboard",
        "vtuber.vseeface_input_sources",
        "vtuber.vseeface_bridge_status",
        "vtuber.vseeface_action_preview",
        "vtuber.vseeface_start_probe_plan",
        "vtuber.vseeface_start_probe_execution_gate",
        "vtuber.vseeface_start_probe_executor_dry_run",
        "vtuber.vseeface_start_probe_execute",
        "vtuber.vseeface_sidecar_settings_preview",
        "vtuber.vseeface_sidecar_apply_plan",
        "vtuber.vseeface_sidecar_execution_gate",
        "vtuber.vseeface_sidecar_executor_dry_run",
        "vtuber.vseeface_sidecar_workflow",
        "vtuber.vseeface_install_plan",
        "vtuber.vseeface_install_execution_gate",
        "vtuber.vseeface_install_executor_dry_run",
        "vtuber.vseeface_install_execute",
        "vtuber.vseeface_connect_installed_sidecar",
        "vtuber.vseeface_select_exe",
        "vtuber.vseeface_select_vrm0_avatar",
        "vtuber.vseeface_select_capture_backend",
        "vtuber.vseeface_select_framing",
        "vtuber.vseeface_select_input_source",
        "vtuber.studio.open",
        "vtuber.avatar_target.summary",
        "vtuber.avatar_target.select",
        "broadcast.live_target.summary",
        "broadcast.live_target.select",
        "broadcast.live_target.troubleshoot",
        "broadcast.release_readiness",
        "broadcast.platform_evidence_checklist",
        "broadcast.youtube_evidence_quickstart",
        "broadcast.evidence_readiness.refresh",
        "broadcast.platform_evidence.preflight",
        "broadcast.platform_evidence.register",
        "broadcast.virtual_camera.plan",
        "broadcast.virtual_camera.obs_bridge_plan",
        "broadcast.virtual_camera.obs_bridge_gate",
        "broadcast.virtual_camera.obs_bridge_dry_run",
        "broadcast.virtual_camera.obs_bridge_execute",
        "vtuber.vrm.bridge_status",
        "vtuber.vrm.pose_stream_preview",
        "vtuber.performance_source.summary",
        "vtuber.performance_source.mark_media",
        "vtuber.performance_source.add_clip",
        "vtuber.program_output_contract",
        "actor.live2d.apply_performance_source",
        "selected.clip",
        "preset.catalog",
        "timeline.fit",
        "timeline.snap.get",
        "timeline.snap.set",
        "timeline.snap.toggle",
        "timeline.edge_issues",
        "timeline.gaps",
        "timeline.close_gap",
        "timeline.close_all_gaps",
        "history.undo",
        "history.redo",
        "timeline.marker.add",
        "timeline.marker.list",
        "timeline.marker.remove",
        "timeline.marker.move",
        "timeline.marker.jump",
        "timeline.split",
        "timeline.trim_to_playhead",
        "timeline.cleanup_edges",
        "clip.delete",
        "clip.set_speed",
        "clip.copy",
        "clip.cut_to_clipboard",
        "clip.paste",
        "clip.nudge_frames",
        "timeline.insert_clipboard",
        "timeline.overwrite_clipboard",
        "timeline.three_point_insert",
        "timeline.three_point_overwrite",
        "clip.select",
        "selection.move",
        "selection.nudge",
        "selection.nudge_frames",
        "timeline.nudge_frames",
        "selection.align_to_playhead",
        "selection.align_to_marker",
        "selection.snap_to_nearest",
        "selection.ripple_delete",
        "audio.extract_from_video",
        "audio.track.set_mix",
        "audio.track.set_volume",
        "audio.track.set_pan",
        "audio.track.mute",
        "audio.track.solo",
        "audio.track.set_type",
        "audio.track.insert.set",
        "audio.track.send.set_level",
        "audio.track.route_to_bus",
        "audio.track.meter.state",
        "audio.automation.state",
        "audio.automation.write",
        "audio.automation.clear",
        "audio.mixer.snapshot.save",
        "audio.mixer.snapshot.apply",
        "audio.mixer.snapshot.compare",
        "audio.mixer.state",
        "audio.sound_editor.jog_shuttle.state",
        "audio.sound_editor.jog_shuttle.set",
        "audio.sound_editor.advanced_lab.state",
        "audio.sound_editor.advanced_lab.set",
        "audio.sound_editor.apply_effects",
        "audio.sound_editor.apply_ai_preset",
        "audio.loudness_report",
        "audio.separate_stems",
        "audio.export_clip",
        "track.select",
        "track.lock",
        "track.mute",
        "track.rename",
        "timeline.select_all",
        "track.remove",
        "transition.apply",
        "transition.clear",
        "render.queue.stage",
        "ui.focus_surface",
        "nle.real_corpus.discover",
        "nle.real_corpus.intake_board",
        "nle.real_corpus.register",
    } <= ids
    assert all("." in row["id"] for row in specs)
    assert all("params_schema" in row for row in specs)
    assert next(row for row in specs if row["id"] == "timeline.marker.add")["mutates"] is True
    assert next(row for row in specs if row["id"] == "vtuber.vseeface_select_input_source")["mutates"] is True
    assert next(row for row in specs if row["id"] == "vtuber.vrm.bridge_status")["mutates"] is False
    assert next(row for row in specs if row["id"] == "render.queue.stage")["mutates"] is True
    assert next(row for row in specs if row["id"] == "ui.focus_surface")["mutates"] is False


def test_action_registry_read_only_actions_are_json_ready(tmp_path):
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(_ActionOwner())
    status = registry.execute("app.status").to_dict()
    snapshot = registry.execute("project.snapshot").to_dict()
    timeline = registry.execute("timeline.summary").to_dict()
    nle = registry.execute("timeline.nle_status").to_dict()
    readiness = registry.execute("timeline.professional_nle_readiness").to_dict()
    target_gap = registry.execute("timeline.nle_target_gap", {"target_score": 95}).to_dict()
    evidence = registry.execute("timeline.nle_evidence").to_dict()
    real_corpus = registry.execute("nle.real_corpus.status", {"manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_board = registry.execute("nle.real_corpus.intake_board", {"search_roots": [str(tmp_path)], "manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_kit = registry.execute("nle.real_corpus.collection_kit", {"search_roots": [str(tmp_path)], "manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_gate = registry.execute("nle.real_corpus.gate_board", {"search_roots": [str(tmp_path)], "manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_workbench = registry.execute("nle.real_corpus.workbench", {"search_roots": [str(tmp_path)], "manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_validation = registry.execute("nle.real_corpus.validation_plan", {"manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_packet = registry.execute("nle.real_corpus.validation_packet", {"manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_preflight = registry.execute("nle.real_corpus.validation_preflight", {"manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    real_corpus_validation_report = registry.execute("nle.real_corpus.validation_report", {"manifest_path": str(tmp_path / "missing_manifest.json")}).to_dict()
    fuzzer = registry.execute("timeline.nle_fuzzer.status", {"report_path": str(tmp_path / "missing_fuzzer.json")}).to_dict()
    core_coverage = registry.execute("timeline.core_action_coverage").to_dict()
    core_safety = registry.execute("timeline.nle_core_safety_matrix").to_dict()
    undo_health = registry.execute("timeline.undo_health", {"report_path": str(tmp_path / "missing_fuzzer.json")}).to_dict()
    undo_review = registry.execute("timeline.undo_review_board", {"report_path": str(tmp_path / "missing_fuzzer.json")}).to_dict()
    undo_recovery = registry.execute("timeline.undo_recovery_playbook", {"report_path": str(tmp_path / "missing_fuzzer.json")}).to_dict()
    undo_dashboard = registry.execute("timeline.undo_stability_dashboard", {"report_path": str(tmp_path / "missing_fuzzer.json")}).to_dict()
    undo_long_session = registry.execute("timeline.undo_long_session_plan").to_dict()
    storyline_gesture = registry.execute("timeline.storyline_gesture_polish_board").to_dict()
    creative = registry.execute("creative_layer.readiness").to_dict()
    selected = registry.execute("selected.clip").to_dict()
    presets = registry.execute("preset.catalog", {"limit": 5}).to_dict()

    assert status["ok"] is True
    assert status["result"]["action_system"]["arbitrary_python"] is False
    assert snapshot["result"]["summary"]["video_clip_count"] == 1
    assert timeline["result"]["tracks"][0]["clip_count"] == 1
    assert nle["ok"] is True
    assert nle["result"]["selection"]["selected_count"] >= 1
    assert "track_targets" in nle["result"]
    assert "source_monitor" in nle["result"]
    assert "record_monitor" in nle["result"]
    assert "clipboard" in nle["result"]
    assert readiness["ok"] is True
    assert readiness["result"]["professional_nle_claim_ok"] is False
    assert "source_record_monitor_3_point" in {row["id"] for row in readiness["result"]["rows"]}
    assert target_gap["ok"] is True
    assert target_gap["result"]["schema"] == "tigerstudio.nle.target_gap.v1"
    assert target_gap["result"]["target_score"] == 95
    assert target_gap["result"]["professional_claim_blocked"] is True
    assert evidence["ok"] is True
    assert evidence["result"]["schema"] == "tigerstudio.nle_evidence.v1"
    assert real_corpus["ok"] is True
    assert real_corpus["result"]["schema"] == "tigerstudio.nle.real_project_corpus.v1"
    assert real_corpus["result"]["claim_ready"] is False
    assert real_corpus_board["ok"] is True
    assert real_corpus_board["result"]["schema"] == "tigerstudio.nle.real_project_corpus.intake_board.v1"
    assert real_corpus_board["result"]["commands"]["discover_enabled"] is True
    assert real_corpus_kit["ok"] is True
    assert real_corpus_kit["result"]["schema"] == "tigerstudio.nle.real_project_corpus.collection_kit.v1"
    assert real_corpus_kit["result"]["readiness"]["collection_kit_ready"] is True
    assert real_corpus_kit["result"]["readiness"]["requires_user_projects"] is True
    assert real_corpus_kit["result"]["commands"]["open_validation_plan_enabled"] is True
    assert real_corpus_kit["result"]["commands"]["open_validation_report_enabled"] is True
    assert "register_validation_evidence" in {row["id"] for row in real_corpus_kit["result"]["steps"]}
    assert real_corpus_gate["ok"] is True
    assert real_corpus_gate["result"]["schema"] == "tigerstudio.nle.real_project_corpus.gate_board.v1"
    assert real_corpus_gate["result"]["professional_nle_claim_blocked"] is True
    assert real_corpus_workbench["ok"] is True
    assert real_corpus_workbench["result"]["schema"] == "tigerstudio.nle.real_project_corpus.workbench.v1"
    assert real_corpus_workbench["result"]["primary_step"]["id"] == "find_projects"
    assert real_corpus_validation["ok"] is True
    assert real_corpus_validation["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_plan.v1"
    assert real_corpus_validation["result"]["readiness"]["validation_plan_ready"] is True
    assert real_corpus_packet["ok"] is True
    assert real_corpus_packet["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_packet.v1"
    assert real_corpus_packet["result"]["ready"] is False
    assert real_corpus_preflight["ok"] is True
    assert real_corpus_preflight["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_preflight.v1"
    assert real_corpus_preflight["result"]["ready"] is False
    assert real_corpus_validation_report["ok"] is True
    assert real_corpus_validation_report["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_report.v1"
    assert real_corpus_validation_report["result"]["commands"]["register_validation_evidence_enabled"] is True
    assert fuzzer["ok"] is True
    assert fuzzer["result"]["schema"] == "tigerstudio.nle.timeline_stress.v1"
    assert fuzzer["result"]["claim_ready"] is False
    assert core_coverage["ok"] is True
    assert core_coverage["result"]["kind"] == "core_nle_action_coverage"
    assert core_coverage["result"]["readiness"]["core_action_coverage_ready"] is True
    assert core_safety["ok"] is True
    assert core_safety["result"]["kind"] == "core_safety_matrix"
    assert core_safety["result"]["readiness"]["core_safety_matrix_ready"] is True
    assert undo_health["ok"] is True
    assert undo_health["result"]["kind"] == "nle_undo_health_matrix"
    assert undo_health["result"]["ready"] is False
    assert undo_review["ok"] is True
    assert undo_review["result"]["kind"] == "nle_undo_review_board"
    assert {row["id"] for row in undo_review["result"]["sections"]} >= {"operations", "risks", "blockers"}
    assert undo_recovery["ok"] is True
    assert undo_recovery["result"]["kind"] == "nle_undo_recovery_playbook"
    assert undo_recovery["result"]["readiness"]["recovery_playbook_ready"] is True
    assert undo_dashboard["ok"] is True
    assert undo_dashboard["result"]["kind"] == "nle_undo_stability_dashboard"
    assert undo_dashboard["result"]["readiness"]["stability_dashboard_ready"] is True
    assert {row["id"] for row in undo_dashboard["result"]["sections"]} >= {"risk_cards", "operations", "recovery_steps"}
    assert undo_long_session["ok"] is True
    assert undo_long_session["result"]["kind"] == "undo_long_session_plan"
    assert undo_long_session["result"]["readiness"]["undo_long_session_plan_ready"] is True
    assert storyline_gesture["ok"] is True
    assert storyline_gesture["result"]["kind"] == "storyline_gesture_polish_board"
    assert storyline_gesture["result"]["readiness"]["storyline_gesture_polish_ready"] is True
    assert creative["ok"] is True
    assert creative["result"]["full_creative_suite_claim_ok"] is False
    assert "transition_workflow" in {row["id"] for row in creative["result"]["rows"]}
    assert selected["result"]["selected"]["id"] == 10
    assert presets["result"]["returned"] <= 5
    assert presets["result"]["total"] >= presets["result"]["returned"]


def test_nle_real_corpus_register_action_previews_and_writes_manifest(tmp_path):
    from app.actions import build_default_action_registry

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video = media_dir / "source.mp4"
    audio = media_dir / "source.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    project = tmp_path / "user_project_action.tgp"
    project.write_text(
        json.dumps(
            {
                "name": "User Project Action",
                "duration_ms": 600_000,
                "media_pool": [
                    {"id": "v", "path": str(video), "kind": "video", "proxy_state": "ready"},
                    {"id": "a", "path": str(audio), "kind": "audio", "proxy_state": "ready"},
                ],
                "video_tracks": [{
                    "id": 1,
                    "clips": [
                        {
                            "id": f"v{index}",
                            "source_path": str(video),
                            "timeline_in_ms": index * 20_000,
                            "duration_ms": 20_000,
                        }
                        for index in range(30)
                    ],
                }],
                "audio_tracks": [{
                    "id": 2,
                    "clips": [
                        {
                            "id": f"a{index}",
                            "source_path": str(audio),
                            "timeline_in_ms": index * 75_000,
                            "duration_ms": 75_000,
                        }
                        for index in range(8)
                    ],
                }],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    registry = build_default_action_registry(_ActionOwner())

    preview = registry.execute(
        "nle.real_corpus.register",
        {"project_path": str(project), "manifest_path": str(manifest), "label": "Action Corpus"},
        dry_run=True,
    ).to_dict()
    assert preview["ok"] is True
    assert preview["dry_run"] is True
    assert preview["changed"] is False
    assert preview["result"]["would_register"] is True

    registered = registry.execute(
        "nle.real_corpus.register",
        {"project_path": str(project), "manifest_path": str(manifest), "label": "Action Corpus"},
    ).to_dict()

    assert registered["ok"] is True
    assert registered["changed"] is True
    assert registered["result"]["ok"] is True
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["projects"][0]["label"] == "Action Corpus"
    checks = [
        {"id": "open_reopen", "status": "pass"},
        {"id": "scrub_sampling", "status": "pass"},
        {"id": "proxy_relink_health", "status": "pass"},
        {"id": "undo_recovery", "status": "pass"},
        {"id": "short_export", "status": "pass"},
    ]
    validation_preview = registry.execute(
        "nle.real_corpus.validation_evidence.register",
        {"project_path": str(project), "manifest_path": str(manifest), "checks": checks},
        dry_run=True,
    ).to_dict()
    assert validation_preview["ok"] is True
    assert validation_preview["dry_run"] is True
    assert validation_preview["changed"] is False
    assert validation_preview["result"]["would_write"]["summary"]["all_required_passed"] is True

    validation_registered = registry.execute(
        "nle.real_corpus.validation_evidence.register",
        {"project_path": str(project), "manifest_path": str(manifest), "checks": checks, "operator": "qa"},
    ).to_dict()
    validation_report = registry.execute(
        "nle.real_corpus.validation_report",
        {"manifest_path": str(manifest)},
    ).to_dict()

    assert validation_registered["ok"] is True
    assert validation_registered["changed"] is True
    assert validation_registered["result"]["validation_evidence"]["status"] == "passed"
    assert validation_report["ok"] is True
    assert validation_report["result"]["summary"]["validation_ready_count"] == 1


def test_nle_real_corpus_discover_action_finds_project_candidates(tmp_path):
    from app.actions import build_default_action_registry

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    video = media_dir / "source.mp4"
    audio = media_dir / "source.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    project = tmp_path / "user_project_discover_action.tgp"
    project.write_text(
        json.dumps(
            {
                "name": "User Project Discover Action",
                "duration_ms": 600_000,
                "media_pool": [
                    {"id": "v", "path": str(video), "kind": "video", "proxy_state": "ready"},
                    {"id": "a", "path": str(audio), "kind": "audio", "proxy_state": "ready"},
                ],
                "video_tracks": [{
                    "id": 1,
                    "clips": [
                        {
                            "id": f"v{index}",
                            "source_path": str(video),
                            "timeline_in_ms": index * 20_000,
                            "duration_ms": 20_000,
                        }
                        for index in range(30)
                    ],
                }],
                "audio_tracks": [{
                    "id": 2,
                    "clips": [
                        {
                            "id": f"a{index}",
                            "source_path": str(audio),
                            "timeline_in_ms": index * 75_000,
                            "duration_ms": 75_000,
                        }
                        for index in range(8)
                    ],
                }],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    registry = build_default_action_registry(_ActionOwner())

    discovery = registry.execute(
        "nle.real_corpus.discover",
        {
            "search_roots": [str(tmp_path)],
            "manifest_path": str(tmp_path / "manifest.json"),
            "max_results": 5,
        },
    ).to_dict()

    assert discovery["ok"] is True
    assert discovery["result"]["schema"] == "tigerstudio.nle.real_project_corpus.discovery.v1"
    assert discovery["result"]["candidate_count"] == 1
    assert discovery["result"]["candidates"][0]["would_register"] is True

    board = registry.execute(
        "nle.real_corpus.intake_board",
        {
            "search_roots": [str(tmp_path)],
            "manifest_path": str(tmp_path / "manifest.json"),
            "max_results": 5,
        },
    ).to_dict()

    assert board["ok"] is True
    assert board["result"]["registerable_count"] == 1
    assert {section["id"] for section in board["result"]["sections"]} >= {
        "claim_gate",
        "registerable_projects",
        "rejected_candidates",
        "registered_projects",
    }
    registerable = next(section for section in board["result"]["sections"] if section["id"] == "registerable_projects")
    assert registerable["rows"][0]["primary_action"]["id"] == "nle.real_corpus.register"

    gate = registry.execute(
        "nle.real_corpus.gate_board",
        {
            "search_roots": [str(tmp_path)],
            "manifest_path": str(tmp_path / "manifest.json"),
            "max_results": 5,
        },
    ).to_dict()

    assert gate["ok"] is True
    assert gate["result"]["schema"] == "tigerstudio.nle.real_project_corpus.gate_board.v1"
    assert gate["result"]["professional_nle_claim_blocked"] is True
    assert {section["id"] for section in gate["result"]["sections"]} >= {
        "claim_gate",
        "blocked_requirements",
        "registerable_projects",
        "workflow",
    }
    workbench = registry.execute(
        "nle.real_corpus.workbench",
        {
            "search_roots": [str(tmp_path)],
            "manifest_path": str(tmp_path / "manifest.json"),
            "max_results": 5,
        },
    ).to_dict()

    assert workbench["ok"] is True
    assert workbench["result"]["schema"] == "tigerstudio.nle.real_project_corpus.workbench.v1"
    assert workbench["result"]["primary_step"]["id"] == "register_candidates"

    registered = registry.execute(
        "nle.real_corpus.register",
        {"project_path": str(project), "manifest_path": str(tmp_path / "manifest.json")},
    ).to_dict()
    packet = registry.execute(
        "nle.real_corpus.validation_packet",
        {"project_path": str(project), "manifest_path": str(tmp_path / "manifest.json")},
    ).to_dict()
    preflight = registry.execute(
        "nle.real_corpus.validation_preflight",
        {"project_path": str(project), "manifest_path": str(tmp_path / "manifest.json")},
    ).to_dict()

    assert registered["ok"] is True
    assert packet["ok"] is True
    assert packet["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_packet.v1"
    assert packet["result"]["action_template"]["id"] == "nle.real_corpus.validation_evidence.register"
    assert packet["result"]["readiness"]["validation_packet_ready"] is True
    assert preflight["ok"] is True
    assert preflight["result"]["schema"] == "tigerstudio.nle.real_project_corpus.validation_preflight.v1"
    assert preflight["result"]["readiness"]["machine_preflight_passed"] is True
    assert {row["status"] for row in preflight["result"]["suggested_validation_checks"]} == {"pending"}


def test_magnetic_storyline_action_closes_gaps_and_moves_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_path="a.mp4", source_duration_ms=1000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_path="b.mp4", source_duration_ms=1000, timeline_in_ms=1800, source_in_ms=0, source_out_ms=1000, linked_audio_id=21),
                VideoClip(id=12, source_path="c.mp4", source_duration_ms=1000, timeline_in_ms=3400, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=21, duration_ms=1000, offset_ms=1800)])]
    registry = build_default_action_registry(owner)

    dry = registry.execute("timeline.magnetic_storyline.apply", {"track_id": 1}, dry_run=True).to_dict()
    assert dry["ok"] is True
    assert dry["changed"] is False
    assert dry["result"]["plan"]["move_count"] == 2
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1800, 3400]

    result = registry.execute("timeline.magnetic_storyline.apply", {"track_id": 1}).to_dict()
    status = registry.execute("timeline.magnetic_storyline.status", {"track_id": 1}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 2000]
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000
    assert result["result"]["moved_linked_audio"][0]["audio_clip_id"] == 21
    assert status["result"]["gap_count"] == 0


def test_connected_clip_and_role_color_actions_mutate_timeline_metadata():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_path="primary.mp4", source_duration_ms=4000, timeline_in_ms=0, source_in_ms=0, source_out_ms=4000),
            ],
        ),
        VideoTrack(
            id=2,
            clips=[
                VideoClip(id=20, source_path="broll.mp4", source_duration_ms=1000, timeline_in_ms=1200, source_in_ms=0, source_out_ms=1000),
            ],
        ),
    ]
    registry = build_default_action_registry(owner)

    dry = registry.execute(
        "timeline.connected_clips.connect",
        {"child_track_id": 2, "child_clip_id": 20, "role": "b-roll"},
        dry_run=True,
    ).to_dict()
    assert dry["ok"] is True
    assert dry["changed"] is False
    assert owner._tracks[1].clips[0].connected_parent_clip_id is None

    connected = registry.execute(
        "timeline.connected_clips.connect",
        {"child_track_id": 2, "child_clip_id": 20, "role": "b-roll"},
    ).to_dict()
    assert connected["ok"] is True
    assert connected["changed"] is True
    child = owner._tracks[1].clips[0]
    assert child.connected_parent_track_id == 1
    assert child.connected_parent_clip_id == 10
    assert child.connected_offset_ms == 1200
    assert child.clip_role == "b_roll"

    role = registry.execute(
        "timeline.clip_role.set",
        {"track_id": 2, "clip_id": 20, "role": "overlay", "role_color": "#123456"},
    ).to_dict()
    status = registry.execute("timeline.connected_clips.status").to_dict()
    colors = registry.execute("timeline.role_colors.status").to_dict()

    assert role["ok"] is True
    assert child.clip_role == "overlay"
    assert child.role_color == "#123456"
    assert status["result"]["connected_count"] == 1
    assert status["result"]["issue_count"] == 0
    assert colors["result"]["role_counts"]["overlay"] == 1


def test_role_lane_actions_group_and_focus_roles():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    class _Row:
        def __init__(self) -> None:
            self.focused_role = None

        def set_focused_clip_role(self, role: str) -> None:
            self.focused_role = role

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_path="primary.mp4", source_duration_ms=2000, timeline_in_ms=0, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=11, source_path="overlay.mp4", source_duration_ms=1000, timeline_in_ms=400, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._tracks[0].clips[1].clip_role = "overlay"
    owner._track_rows = {1: _Row()}
    registry = build_default_action_registry(owner)

    status = registry.execute("timeline.role_lanes.status").to_dict()
    dry = registry.execute("timeline.role_lanes.focus", {"role": "overlay"}, dry_run=True).to_dict()
    focused = registry.execute("timeline.role_lanes.focus", {"role": "overlay"}).to_dict()
    after = registry.execute("timeline.role_lanes.status").to_dict()

    assert status["ok"] is True
    assert {row["role"] for row in status["result"]["lanes"]} >= {"primary", "overlay"}
    assert dry["changed"] is False
    assert getattr(owner, "_nle_role_lane_focus", "") == "overlay"
    assert owner._track_rows[1].focused_role == "overlay"
    assert focused["ok"] is True
    assert focused["changed"] is True
    assert after["result"]["focused_role"] == "overlay"


def test_audition_actions_add_and_switch_active_take():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_path="host.mp4", source_duration_ms=4000, timeline_in_ms=0, source_in_ms=0, source_out_ms=4000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    dry = registry.execute(
        "timeline.audition.add_take",
        {
            "host_track_id": 1,
            "host_clip_id": 10,
            "take_id": "take_alt",
            "label": "Alt",
            "source_path": "alt.mp4",
            "source_duration_ms": 1200,
            "source_in_ms": 100,
            "source_out_ms": 1100,
        },
        dry_run=True,
    ).to_dict()
    assert dry["ok"] is True
    assert dry["changed"] is False
    assert owner._tracks[0].clips[0].audition_takes == []

    added = registry.execute(
        "timeline.audition.add_take",
        {
            "host_track_id": 1,
            "host_clip_id": 10,
            "take_id": "take_alt",
            "label": "Alt",
            "source_path": "alt.mp4",
            "source_duration_ms": 1200,
            "source_in_ms": 100,
            "source_out_ms": 1100,
        },
    ).to_dict()
    host = owner._tracks[0].clips[0]
    assert added["ok"] is True
    assert added["changed"] is True
    assert host.audition_group_id == 10
    assert host.audition_active_take_id == "take_original"
    assert {row["id"] for row in host.audition_takes} == {"take_original", "take_alt"}
    assert str(host.source_path) == "host.mp4"

    switched = registry.execute(
        "timeline.audition.switch_take",
        {"track_id": 1, "clip_id": 10, "take_id": "take_alt"},
    ).to_dict()
    status = registry.execute("timeline.auditions.status").to_dict()
    compare = registry.execute("timeline.audition.compare", {"track_id": 1, "clip_id": 10}).to_dict()
    renamed = registry.execute(
        "timeline.audition.rename_take",
        {"track_id": 1, "clip_id": 10, "take_id": "take_alt", "label": "Better Alt"},
    ).to_dict()
    removed = registry.execute(
        "timeline.audition.remove_take",
        {"track_id": 1, "clip_id": 10, "take_id": "take_original"},
    ).to_dict()

    assert switched["ok"] is True
    assert switched["changed"] is True
    assert host.audition_active_take_id == "take_alt"
    assert str(host.source_path) == "alt.mp4"
    assert host.source_in_ms == 100
    assert host.source_out_ms == 1100
    assert status["result"]["audition_count"] == 1
    assert status["result"]["take_count"] == 2
    assert compare["result"]["schema"] == "tigerstudio.nle.audition_compare.v1"
    assert compare["result"]["take_count"] == 2
    assert renamed["ok"] is True
    assert removed["ok"] is True
    assert host.audition_active_take_id == "take_alt"
    assert {row["id"] for row in host.audition_takes} == {"take_alt"}
    assert host.audition_takes[0]["label"] == "Better Alt"


def test_ui_focus_surface_action_is_safe_without_live_docks():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "ui.focus_surface",
        {"surface": "node_graph", "kind": "video", "track_id": 1, "clip_id": 10, "inspector_tab": "fx"},
    ).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["surface"] == "node_graph"
    assert result["result"]["track_id"] == 1


def test_render_queue_stage_action_routes_to_live_queue_hook():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "render.queue.stage",
        {
            "jobs": [
                {
                    "label": "Catalog Export",
                    "out_path": "debugCapture/render/catalog_export.mp4",
                    "in_ms": 0,
                    "out_ms": 4000,
                    "format_id": "mp4",
                    "quality_id": "high",
                }
            ]
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["changed"] is True
    assert result["result"]["requested"] == 1
    assert result["result"]["added"] == 1
    assert owner.staged_render_payloads[0]["render_queue_jobs"][0]["label"] == "Catalog Export"
    assert owner.opened_hosts == [owner._render_queue_section_host]
    assert owner._selected_clips == [(1, 10)]


def test_vseeface_input_source_actions_list_and_persist_project_clip(tmp_path):
    from app.actions import build_default_action_registry

    class _MediaPool:
        def __init__(self, paths):
            self._paths = list(paths)

        def items(self):
            return list(self._paths)

    owner = _ActionOwner()
    face_video = tmp_path / "face.mp4"
    track_video = tmp_path / "track_face.mov"
    face_video.write_bytes(b"face")
    track_video.write_bytes(b"track")
    owner._media_pool = _MediaPool([str(face_video)])
    owner._tracks[0].clips[0].source_path = track_video
    registry = build_default_action_registry(owner)

    listed = registry.execute(
        "vtuber.vseeface_input_sources",
        {"camera_devices": [{"id": "webcam0", "name": "USB Camera", "index": 0}]},
    ).to_dict()

    option_ids = [row["id"] for row in listed["result"]["input_sources"]["options"]]
    assert option_ids == ["camera:webcam0", "media_pool:media_1", "timeline:1:10"]

    dry = registry.execute(
        "vtuber.vseeface_select_input_source",
        {"source_id": "timeline:1:10"},
        dry_run=True,
    ).to_dict()

    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert "vseeface_bridge" not in owner._project_settings
    assert dry["result"]["input"]["video_path"] == str(track_video)

    applied = registry.execute(
        "vtuber.vseeface_select_input_source",
        {"source_id": "timeline:1:10"},
    ).to_dict()

    saved = owner._project_settings["vseeface_bridge"]["input"]
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert saved["source_kind"] == "timeline_video_clip"
    assert saved["track_id"] == 1
    assert saved["clip_id"] == 10
    assert saved["video_path"] == str(track_video)
    assert owner.changes[-1] == "Select VSeeFace tracking input"


def test_performance_source_actions_mark_media_add_track_and_preserve_program_output(tmp_path):
    from app.actions import build_default_action_registry
    from app.vtuber.performance_source import PROGRAM_BACKGROUND_CHROMA, is_performance_source_track

    class _MediaPool:
        def __init__(self) -> None:
            self.paths: list[str] = []
            self.flags: dict[str, bool] = {}

        def add_path(self, path):
            text = str(Path(path).resolve())
            if text not in self.paths:
                self.paths.append(text)
                return True
            return False

        def set_performance_source_path(self, path, enabled):
            text = str(Path(path).resolve())
            before = bool(self.flags.get(text, False))
            self.flags[text] = bool(enabled)
            return before != bool(enabled)

        def performance_source_paths(self):
            return [path for path in self.paths if self.flags.get(path)]

    owner = _ActionOwner()
    owner._tracks = []
    owner._media_pool = _MediaPool()
    face_video = tmp_path / "face_input.mp4"
    face_video.write_bytes(b"face")
    registry = build_default_action_registry(owner)

    mark = registry.execute(
        "vtuber.performance_source.mark_media",
        {"path": str(face_video), "enabled": True},
    ).to_dict()
    added = registry.execute(
        "vtuber.performance_source.add_clip",
        {"path": str(face_video), "start_ms": 1_000, "duration_ms": 5_000},
    ).to_dict()
    summary = registry.execute("vtuber.performance_source.summary", {"time_ms": 2_000}).to_dict()
    contract = registry.execute("vtuber.program_output_contract", {"time_ms": 2_000}).to_dict()

    assert mark["ok"] is True
    assert mark["result"]["enabled"] is True
    assert added["ok"] is True
    assert added["result"]["track_id"] == owner._tracks[0].id
    assert is_performance_source_track(owner._tracks[0])
    assert owner._tracks[0].clips[0].source_path == face_video.resolve()
    assert summary["result"]["performance_track_count"] == 1
    assert summary["result"]["ui_contract"]["timeline"]["dedicated_track"] is True
    assert summary["result"]["ui_contract"]["media_pool"]["program_output"] is False
    assert summary["result"]["program_output_contract"]["performance_source"]["active"] is True
    assert contract["result"]["program_background"]["kind"] == PROGRAM_BACKGROUND_CHROMA
    assert contract["result"]["performance_source"]["source_path"] == str(face_video.resolve())
    assert contract["result"]["performance_source"]["program_output"] is False


def test_live2d_performance_source_action_uses_active_perf_source_and_framing(tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    from app.timeline_model import VideoClip, VideoTrack
    from app.vtuber.performance_source import mark_performance_source_object

    owner = _ActionOwner()
    face_video = tmp_path / "face.mp4"
    face_video.write_bytes(b"face")
    perf_clip = VideoClip(
        id=91,
        source_path=face_video.resolve(),
        source_duration_ms=2000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=2000,
    )
    perf_track = VideoTrack(id=9, clips=[perf_clip])
    mark_performance_source_object(perf_track)
    mark_performance_source_object(perf_clip)
    owner._tracks = [perf_track]
    live_clip = Live2DActorClip(
        model_path="avatar.model3.json",
        start_ms=0,
        duration_ms=1000,
        pos_x=0.5,
        pos_y=0.55,
        scale=1.0,
    )
    owner._live2d_actor_tracks = [Live2DActorTrack(id=3, clips=[live_clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "actor.live2d.apply_performance_source",
        {
            "track_id": 3,
            "clip_index": 0,
            "time_ms": 500,
            "analyze_video": False,
            "mocap_frames": [
                {"time_ms": 0, "x_norm": 0.44, "y_norm": 0.50, "w_norm": 0.18, "h_norm": 0.24},
                {"time_ms": 200, "x_norm": 0.62, "y_norm": 0.45, "w_norm": 0.22, "h_norm": 0.27},
            ],
            "framing_payload": {
                "schema": "tigerstudio.vtuber.source_framing_control.v1",
                "time_ms": 0,
                "preset": "bust_up",
                "final": {
                    "model_view": {
                        "zoom": 6.64,
                        "pan_x": 0.117,
                        "pan_y": -1.70,
                        "pan_z": 0.0,
                        "camera_z": 3.25,
                        "lower_occlusion_y": 0.68,
                    },
                    "track_rotation": [-5.08, 180.0, 0.0],
                },
            },
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["program_output"] is False
    assert result["result"]["source_path"] == str(face_video.resolve())
    assert live_clip.mocap_source_path == str(face_video.resolve())
    assert live_clip.mocap_parameter_keyframes["ParamAngleX"]
    assert live_clip.performance_source_framing_payload
    assert live_clip.performance_source_model_view["lower_occlusion_y"] == 0.68
    assert live_clip.kf_pos_x
    assert owner.changes[-1] == "Apply Live2D Performance Source"


def test_live2d_performance_source_action_keeps_face_only_actor_transform_locked(tmp_path):
    from app.actions import build_default_action_registry
    from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
    from app.timeline_model import VideoClip, VideoTrack
    from app.vtuber.performance_source import mark_performance_source_object

    owner = _ActionOwner()
    face_video = tmp_path / "closeup_face.mp4"
    face_video.write_bytes(b"face")
    perf_clip = VideoClip(
        id=92,
        source_path=face_video.resolve(),
        source_duration_ms=2000,
        timeline_in_ms=0,
        source_in_ms=0,
        source_out_ms=2000,
    )
    perf_track = VideoTrack(id=10, clips=[perf_clip])
    mark_performance_source_object(perf_track)
    mark_performance_source_object(perf_clip)
    owner._tracks = [perf_track]
    live_clip = Live2DActorClip(
        model_path="avatar.model3.json",
        start_ms=0,
        duration_ms=1000,
        pos_x=0.5,
        pos_y=0.55,
        scale=1.0,
    )
    owner._live2d_actor_tracks = [Live2DActorTrack(id=4, clips=[live_clip])]
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "actor.live2d.apply_performance_source",
        {
            "track_id": 4,
            "clip_index": 0,
            "time_ms": 500,
            "analyze_video": False,
            "mocap_frames": [
                {"time_ms": 0, "x_norm": 0.34, "y_norm": 0.50, "w_norm": 0.36, "h_norm": 0.44},
                {"time_ms": 200, "x_norm": 0.66, "y_norm": 0.48, "w_norm": 0.35, "h_norm": 0.43},
            ],
            "framing_payload": {
                "schema": "tigerstudio.vtuber.source_framing_control.v1",
                "time_ms": 0,
                "preset": "bust_up",
                "final": {
                    "model_view": {
                        "zoom": 10.0,
                        "pan_x": 0.75,
                        "pan_y": -0.50,
                        "lower_occlusion_y": 0.68,
                    },
                    "track_rotation": [-5.0, 180.0, 0.0],
                },
            },
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["subject_type"] == "face_only"
    assert result["result"]["program_output"] is False
    assert result["result"]["active_performance_source"]["program_output"] is False
    assert result["result"]["mocap"]["actor_transform_locked"] is True
    assert result["result"]["framing"]["mapping"]["movement_constraints"]["actor_transform_locked"] is True
    assert result["result"]["parameter_aliases"]["alias_count"] > 0
    assert live_clip.mocap_subject_type == "face_only"
    assert live_clip.performance_source_subject_type == "face_only"
    assert live_clip.mocap_parameter_aliases["ParamAngleX"]
    assert {row.value for row in live_clip.kf_pos_x} == {0.5}
    assert {row.value for row in live_clip.kf_pos_y} == {0.55}
    assert {row.value for row in live_clip.kf_scale} == {1.0}


def test_vseeface_status_and_action_preview_actions_are_json_ready(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    face_video = tmp_path / "face.mp4"
    face_video.write_bytes(b"face")
    owner._tracks[0].clips[0].source_path = face_video
    owner._project_settings = {
        "vseeface_bridge": {
            "input": {
                "source_kind": "timeline_video_clip",
                "track_id": 1,
                "clip_id": 10,
            }
        }
    }
    registry = build_default_action_registry(owner)

    status = registry.execute(
        "vtuber.vseeface_bridge_status",
        {
            "camera_devices": [{"id": "webcam0", "name": "USB Camera", "index": 0}],
            "input_diagnostics": {
                "inputs": {
                    "camera:webcam0": {
                        "status": "ready",
                    }
                }
            },
            "width": 1280,
            "height": 720,
            "fps": 60,
        },
    ).to_dict()
    preview = registry.execute("vtuber.vseeface_action_preview").to_dict()

    assert status["ok"] is True
    assert status["result"]["status"]["state"] == "blocked"
    assert status["result"]["view"]["show_debug"] is False
    assert status["result"]["input_sources"]["selected_id"] == "timeline:1:10"
    assert status["result"]["input_sources"]["options"][0]["status"] == "ready"
    assert status["result"]["status"]["scene"]["canvas"]["width"] == 1280
    assert status["result"]["status"]["scene"]["canvas"]["fps"] == 60.0
    assert status["result"]["status"]["scene"]["sources"][1]["settings"]["input"]["video_path"] == str(face_video)
    assert preview["ok"] is True
    assert preview["result"]["preview"]["action_id"] in {"select_vseeface_exe", "connect_installed_vseeface_sidecar", "install_vseeface_sidecar"}
    assert preview["result"]["preview"]["steps"][0]["kind"] == "ui"


def test_vseeface_exe_and_vrm0_selection_actions_persist_project_settings(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")

    dry_exe = registry.execute("vtuber.vseeface_select_exe", {"path": str(exe)}, dry_run=True).to_dict()
    applied_exe = registry.execute("vtuber.vseeface_select_exe", {"path": str(exe)}).to_dict()
    dry_vrm = registry.execute("vtuber.vseeface_select_vrm0_avatar", {"path": str(vrm)}, dry_run=True).to_dict()
    applied_vrm = registry.execute("vtuber.vseeface_select_vrm0_avatar", {"path": str(vrm)}).to_dict()
    status = registry.execute("vtuber.vseeface_bridge_status").to_dict()

    assert dry_exe["ok"] is True
    assert dry_exe["dry_run"] is True
    assert applied_exe["ok"] is True
    assert applied_exe["changed"] is True
    assert dry_vrm["ok"] is True
    assert dry_vrm["result"]["vrm"]["vseeface_compatible"] is True
    assert applied_vrm["ok"] is True
    assert owner._project_settings["vseeface_bridge"]["vseeface_exe"] == str(exe)
    assert owner._project_settings["vseeface_bridge"]["avatar_vrm"] == str(vrm)
    assert owner._project_settings["vtuber_studio"]["avatar_target_id"] == "vrm:vseeface_bridge"
    assert applied_vrm["result"]["selected_avatar_target_id"] == "vrm:vseeface_bridge"
    assert owner.changes[-2:] == ["Select VSeeFace executable", "Select VSeeFace VRM0 avatar"]
    assert status["result"]["status"]["state"] == "needs_probe"
    assert status["result"]["status"]["setup_flow"]["steps"][0]["state"] == "done"
    assert status["result"]["status"]["setup_flow"]["steps"][1]["state"] == "done"


def test_vtuber_avatar_target_and_vrm_pose_stream_actions_share_studio(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    owner._project_settings = {
        "vseeface_bridge": {
            "vseeface_exe": str(exe),
            "avatar_vrm": str(vrm),
        }
    }
    opened = {"count": 0}

    def _open_studio():
        opened["count"] += 1

    owner._open_vtuber_broadcast_studio = _open_studio
    registry = build_default_action_registry(owner)

    summary = registry.execute("vtuber.avatar_target.summary").to_dict()
    selected = registry.execute("vtuber.avatar_target.select", {"target_id": "vrm:vseeface_bridge"}).to_dict()
    bridge = registry.execute("vtuber.vrm.bridge_status").to_dict()
    pose = registry.execute("vtuber.vrm.pose_stream_preview").to_dict()
    opened_result = registry.execute("vtuber.studio.open", {"avatar_target_id": "vrm:vseeface_bridge"}).to_dict()

    assert summary["result"]["selected"]["kind"] == "vrm_vseeface_bridge"
    assert selected["result"]["selected_id"] == "vrm:vseeface_bridge"
    assert owner._project_settings["vtuber_studio"]["avatar_target_id"] == "vrm:vseeface_bridge"
    assert bridge["result"]["avatar_target"]["kind"] == "vrm_vseeface_bridge"
    assert bridge["result"]["bridge"]["preflight"]["vrm"]["vseeface_compatible"] is True
    assert pose["result"]["pose_stream"]["direct_key_baking"] is False
    assert pose["result"]["pose_stream"]["capture_required_for_pose"] is False
    assert "OpenSeeFace" in pose["result"]["pose_stream"]["route"]
    assert opened_result["result"]["window"] == "VTuberBroadcastStudioWindow"
    assert opened_result["result"]["shared_studio"] is True
    assert opened["count"] == 1


def test_broadcast_live_target_actions_redact_stream_key():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    selected = registry.execute(
        "broadcast.live_target.select",
        {
            "target_id": "youtube_live",
            "stream_key": "secret-live-key",
            "video_bitrate_kbps": 4500,
            "include_audio": True,
            "audio_source_kind": "silence",
        },
    ).to_dict()
    summary = registry.execute(
        "broadcast.live_target.summary",
        {
            "target_id": "youtube_live",
            "stream_key": "secret-live-key",
            "width": 1280,
            "height": 720,
            "fps": 60,
        },
    ).to_dict()
    troubleshooting = registry.execute(
        "broadcast.live_target.troubleshoot",
        {
            "target_id": "youtube_live",
            "platform_error_kind": "platform_auth",
            "platform_error_message": "Platform rejected the stream.",
            "stderr_tail": "Server returned 403 Forbidden",
        },
    ).to_dict()

    saved = owner._project_settings["broadcast_output"]["live_target"]
    assert selected["result"]["selected_id"] == "youtube_live"
    assert "stream_key" not in saved
    assert saved["stream_key_storage"] == "session"
    assert saved["include_audio"] is True
    assert saved["audio_input"]["kind"] == "silence"
    assert summary["result"]["preflight"]["ok"] is True
    assert "secret-live-key" not in " ".join(str(part) for part in summary["result"]["preflight"]["command"])
    assert troubleshooting["result"]["troubleshooting"]["primary_action"] == "refresh_stream_key"
    assert any("YouTube" in step for step in troubleshooting["result"]["troubleshooting"]["checks"])


def test_broadcast_virtual_camera_actions_return_obs_bridge_plan():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry()
    installed = {
        "obs_virtual_camera": {
            "available": True,
            "executable": "C:/OBS/obs64.exe",
        }
    }

    plan = registry.execute(
        "broadcast.virtual_camera.plan",
        {
            "discover": False,
            "preferred_backend": "obs_virtual_camera",
            "installed_backends": installed,
            "program_window_title": "Tiger Studio Program Output",
        },
    ).to_dict()
    bridge = registry.execute(
        "broadcast.virtual_camera.obs_bridge_plan",
        {
            "discover": False,
            "installed_backends": installed,
            "program_window_title": "Tiger Studio Program Output",
            "scene_name": "Tiger Studio Program Output",
            "source_name": "Tiger Studio Program Output",
        },
    ).to_dict()
    gate = registry.execute(
        "broadcast.virtual_camera.obs_bridge_gate",
        {
            "discover": False,
            "confirm": True,
            "websocket_enabled": True,
            "obsws_available": True,
            "installed_backends": installed,
        },
    ).to_dict()
    dry_run = registry.execute(
        "broadcast.virtual_camera.obs_bridge_dry_run",
        {
            "discover": False,
            "confirm": True,
            "websocket_enabled": True,
            "obsws_available": True,
            "installed_backends": installed,
        },
    ).to_dict()

    assert plan["result"]["selected_backend"] == "obs_virtual_camera"
    assert plan["result"]["plan"]["obs_bridge"]["obs_scene"]["source_kind"] == "window_capture"
    assert bridge["result"]["available"] is True
    assert bridge["result"]["plan"]["program_output"]["must_exclude_performance_source"] is True
    assert bridge["result"]["plan"]["automation"]["direct_driver_install"] is False
    assert gate["result"]["can_execute"] is True
    assert dry_run["result"]["dry_run"]["can_execute_now"] is True
    assert dry_run["result"]["operations"][-1]["id"] == "start_virtual_camera"


def test_broadcast_release_readiness_action_reports_alpha_and_sale_state(tmp_path):
    from app.actions import build_default_action_registry

    registry = build_default_action_registry()
    result = registry.execute("broadcast.release_readiness", {"root": str(tmp_path)}).to_dict()

    assert result["result"]["schema"] == "tigerstudio.broadcast.release_readiness.v1"
    assert result["result"]["alpha_ready"] is True
    assert result["result"]["commercial_ready"] is False
    assert "Broadcast readiness" in result["result"]["summary_text"]


def test_broadcast_platform_evidence_checklist_action_reports_next_manual_step(tmp_path):
    import json

    from app.actions import build_default_action_registry
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")
    registry = build_default_action_registry()

    result = registry.execute("broadcast.platform_evidence_checklist", {"root": str(tmp_path)}).to_dict()

    assert result["result"]["schema"] == "tigerstudio.broadcast.platform_evidence_checklist.v1"
    assert result["result"]["summary"]["passed"] == 3
    assert result["result"]["operator_focus"]["id"] == "private_rtmp_ingest"
    assert result["result"]["sale_ready"] is False


def test_broadcast_youtube_evidence_quickstart_action_explains_required_checks(tmp_path):
    import json

    from app.actions import build_default_action_registry
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")
    registry = build_default_action_registry()

    result = registry.execute("broadcast.youtube_evidence_quickstart", {"root": str(tmp_path)}).to_dict()

    assert result["ok"] is True
    assert result["result"]["schema"] == "tigerstudio.broadcast.youtube_evidence_quickstart.v1"
    assert result["result"]["live_target_id"] == "youtube_live"
    assert result["result"]["next_required_check_id"] == "private_rtmp_ingest"
    assert [row["check_id"] for row in result["result"]["required_evidence"]] == [
        "private_rtmp_ingest",
        "youtube_unlisted_viewer_playback",
    ]
    assert result["result"]["optional_evidence"][0]["required_for_sale"] is False
    assert "stream keys" in result["result"]["do_not_include"]
    assert "YouTube watch/preview URLs" in result["result"]["do_not_include"]


def test_broadcast_evidence_readiness_refresh_action_writes_artifacts(tmp_path):
    import json

    from app.actions import build_default_action_registry
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")
    registry = build_default_action_registry()

    result = registry.execute("broadcast.evidence_readiness.refresh", {"root": str(tmp_path)}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["schema"] == "tigerstudio.broadcast.evidence_readiness_refresh.v1"
    assert result["result"]["broadcast_commercial_ready"] is False
    assert result["result"]["final_release_ready"] is False
    assert (tmp_path / "debugCapture" / "broadcast_release_readiness_qa.json").exists()
    assert (tmp_path / "debugCapture" / "final_product_readiness_qa.json").exists()


def test_broadcast_platform_evidence_preflight_action_blocks_private_urls():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry()
    blocked = registry.execute(
        "broadcast.platform_evidence.preflight",
        {
            "check_id": "youtube_unlisted_viewer_playback",
            "platform": "YouTube",
            "notes": "Preview worked: https://www.youtube.com/watch?v=PRIVATE",
            "confirm_redacted": True,
        },
    ).to_dict()
    clean = registry.execute(
        "broadcast.platform_evidence.preflight",
        {
            "check_id": "youtube_unlisted_viewer_playback",
            "platform": "YouTube",
            "notes": "Private YouTube preview played Program Output; URL, account, and chat redacted.",
            "confirm_redacted": True,
        },
    ).to_dict()

    assert blocked["ok"] is True
    assert blocked["changed"] is False
    assert blocked["result"]["schema"] == "tigerstudio.broadcast.platform_evidence_preflight.v1"
    assert blocked["result"]["can_register"] is False
    assert "Remove YouTube watch/preview links" in blocked["result"]["warning"]
    assert clean["result"]["can_register"] is True
    assert clean["result"]["warning"] == ""


def test_broadcast_platform_evidence_register_action_requires_redaction_and_updates_report(tmp_path):
    import json

    from app.actions import build_default_action_registry
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report

    report = build_broadcast_platform_e2e_report(
        tmp_path,
        record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
        live2d_record_smoke_runner=lambda _root: {"ok": True, "bytes": 4096, "frames_written": 12},
    )
    artifact = tmp_path / "debugCapture" / "broadcast_platform_e2e_qa.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(report), encoding="utf-8")
    registry = build_default_action_registry()

    blocked = registry.execute(
        "broadcast.platform_evidence.register",
        {
            "root": str(tmp_path),
            "check_id": "private_rtmp_ingest",
            "platform": "YouTube",
            "notes": "Private ingest reached excellent status.",
            "confirm_redacted": False,
        },
    ).to_dict()
    secret_blocked = registry.execute(
        "broadcast.platform_evidence.register",
        {
            "root": str(tmp_path),
            "check_id": "private_rtmp_ingest",
            "platform": "YouTube",
            "notes": "token=SECRET",
            "confirm_redacted": True,
        },
    ).to_dict()
    registered = registry.execute(
        "broadcast.platform_evidence.register",
        {
            "root": str(tmp_path),
            "check_id": "private_rtmp_ingest",
            "platform": "YouTube",
            "notes": "Private ingest reached excellent status; stream key redacted.",
            "confirm_redacted": True,
        },
    ).to_dict()
    checklist = registry.execute("broadcast.platform_evidence_checklist", {"root": str(tmp_path)}).to_dict()

    assert blocked["ok"] is False
    assert "confirm_redacted" in blocked["error"]
    assert secret_blocked["ok"] is False
    assert "unredacted secret" in secret_blocked["error"]
    assert registered["ok"] is True
    assert registered["changed"] is True
    assert registered["result"]["registered"] is True
    assert registered["result"]["check_id"] == "private_rtmp_ingest"
    assert checklist["result"]["summary"]["passed"] == 4
    assert checklist["result"]["operator_focus"]["id"] == "youtube_unlisted_viewer_playback"


def test_vseeface_capture_backend_action_persists_capture_settings():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    dry = registry.execute(
        "vtuber.vseeface_select_capture_backend",
        {
            "method": "virtual_camera",
            "virtual_camera_name": "VSeeFaceCamera",
        },
        dry_run=True,
    ).to_dict()
    applied = registry.execute(
        "vtuber.vseeface_select_capture_backend",
        {
            "method": "virtual_camera",
            "virtual_camera_name": "VSeeFaceCamera",
        },
    ).to_dict()
    status = registry.execute("vtuber.vseeface_bridge_status").to_dict()

    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["result"]["capture"]["method"] == "virtual_camera"
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert owner._project_settings["vseeface_bridge"]["capture"]["method"] == "virtual_camera"
    assert owner._project_settings["vseeface_bridge"]["capture"]["virtual_camera_name"] == "VSeeFaceCamera"
    assert owner.changes[-1] == "Select VSeeFace capture backend"
    assert status["result"]["status"]["scene"]["sources"][1]["settings"]["capture_method"] == "virtual_camera"


def test_vseeface_framing_action_persists_camera_preset():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    dry = registry.execute("vtuber.vseeface_select_framing", {"framing_preset": "half_body"}, dry_run=True).to_dict()
    applied = registry.execute("vtuber.vseeface_select_framing", {"framing_preset": "half_body"}).to_dict()
    status = registry.execute("vtuber.vseeface_bridge_status").to_dict()

    assert dry["ok"] is True
    assert dry["result"]["camera"]["composition"] == "head_to_waist"
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert owner._project_settings["vseeface_bridge"]["capture"]["framing_preset"] == "half_body"
    assert status["result"]["status"]["scene"]["sources"][1]["settings"]["framing_preset"] == "half_body"
    assert status["result"]["status"]["scene"]["sources"][1]["settings"]["camera"]["composition"] == "head_to_waist"


def test_vseeface_sidecar_settings_preview_action_is_read_only(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    owner._project_settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm),
            "capture": {"method": "virtual_camera"},
            "input": {"openseeface_port": 39542},
        }
    }
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "vtuber.vseeface_sidecar_settings_preview",
        {"settings_path": str(tmp_path / "settings.ini")},
    ).to_dict()

    preview = result["result"]["preview"]
    assert result["ok"] is True
    assert result["changed"] is False
    assert preview["read_only"] is True
    assert preview["would_write"] is False
    assert preview["settings_path"] == str(tmp_path / "settings.ini")
    assert preview["values"]["AvatarFile"] == str(vrm)
    assert preview["values"]["Port"] == "39542"
    assert not (tmp_path / "settings.ini").exists()


def test_vseeface_sidecar_apply_plan_action_does_not_write_settings(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    settings = tmp_path / "settings.ini"
    owner._project_settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm),
            "capture": {"method": "window_capture"},
            "input": {"openseeface_host": "127.0.0.1", "openseeface_port": 39542},
        }
    }
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "vtuber.vseeface_sidecar_apply_plan",
        {"settings_path": str(settings), "out_path": str(tmp_path / "report.json")},
    ).to_dict()

    plan = result["result"]["plan"]
    args = plan["steps"][0]["args"]
    assert result["ok"] is True
    assert result["changed"] is False
    assert plan["ok"] is True
    assert plan["auto_run"] is False
    assert plan["preview_only"] is True
    assert plan["would_write_when_executed"] is True
    assert "tools\\configure_vseeface_sidecar.py" in args
    assert "--disable-virtual-camera" in args
    assert str(settings) in args
    assert not settings.exists()


def test_vseeface_sidecar_execution_gate_action_is_read_only(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    settings = tmp_path / "settings.ini"
    owner._project_settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm),
            "capture": {"method": "virtual_camera"},
            "input": {"openseeface_port": 39542},
        }
    }
    registry = build_default_action_registry(owner)

    gated = registry.execute(
        "vtuber.vseeface_sidecar_execution_gate",
        {"settings_path": str(settings)},
    ).to_dict()
    confirmed = registry.execute(
        "vtuber.vseeface_sidecar_execution_gate",
        {"settings_path": str(settings), "confirm": True},
    ).to_dict()

    assert gated["ok"] is True
    assert gated["changed"] is False
    assert gated["result"]["gate"]["execute_allowed"] is False
    assert gated["result"]["gate"]["steps"][0]["state"] == "requires_user_confirmation"
    assert confirmed["result"]["gate"]["execute_allowed"] is True
    assert confirmed["result"]["gate"]["steps"][0]["state"] == "ready"
    assert not settings.exists()


def test_vseeface_sidecar_executor_dry_run_action_never_executes(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    settings = tmp_path / "settings.ini"
    owner._project_settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm),
            "capture": {"method": "virtual_camera"},
            "input": {"openseeface_port": 39542},
        }
    }
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "vtuber.vseeface_sidecar_executor_dry_run",
        {"settings_path": str(settings), "confirm": True},
    ).to_dict()

    executor = result["result"]["executor"]
    assert result["ok"] is True
    assert result["changed"] is False
    assert executor["ok"] is True
    assert executor["dry_run"] is True
    assert executor["executed"] is False
    assert executor["steps"][0]["would_run"] is True
    assert not settings.exists()


def test_vseeface_sidecar_workflow_action_returns_ui_view(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    settings = tmp_path / "settings.ini"
    owner._project_settings = {
        "vseeface_bridge": {
            "avatar_vrm": str(vrm),
            "capture": {"method": "virtual_camera"},
            "input": {"openseeface_port": 39542},
        }
    }
    registry = build_default_action_registry(owner)

    result = registry.execute(
        "vtuber.vseeface_sidecar_workflow",
        {"settings_path": str(settings)},
    ).to_dict()
    confirmed = registry.execute(
        "vtuber.vseeface_sidecar_workflow",
        {"settings_path": str(settings), "confirm": True},
    ).to_dict()

    workflow = result["result"]["workflow"]
    view = result["result"]["view"]
    assert result["ok"] is True
    assert result["changed"] is False
    assert workflow["state"] == "confirmation_required"
    assert view["tone"] == "warning"
    assert view["progress"] == 0.75
    assert view["steps"][2]["state"] == "current"
    assert view["next_action"]["registry_action"] == "vtuber.vseeface_sidecar_workflow"
    assert view["actions"][3]["registry_action"] == "vtuber.vseeface_sidecar_executor_dry_run"
    assert confirmed["result"]["workflow"]["state"] == "ready_to_execute"
    assert confirmed["result"]["view"]["would_run"] is True
    assert confirmed["result"]["view"]["progress"] == 1.0
    assert not settings.exists()


def test_vseeface_setup_actions_expose_registry_action_names(tmp_path):
    from app.vtuber.vseeface_bridge import VSeeFaceBridgeConfig, build_vseeface_bridge_status

    status = build_vseeface_bridge_status(VSeeFaceBridgeConfig())

    assert status["view"]["primary_action"]["id"] in {"select_vseeface_exe", "connect_installed_vseeface_sidecar", "install_vseeface_sidecar"}
    assert status["view"]["primary_action"]["registry_action"] in {
        "vtuber.vseeface_select_exe",
        "vtuber.vseeface_connect_installed_sidecar",
        "vtuber.vseeface_install_plan",
    }
    assert status["view"]["primary_action"]["form"]["params"][0]["kind"] in {"file", "directory"}
    capture_action = next(action for action in status["view"]["secondary_actions"] if action["id"] == "select_capture_backend")
    assert capture_action["registry_action"] == "vtuber.vseeface_select_capture_backend"
    assert capture_action["form"]["params"][0]["options"][1]["value"] == "virtual_camera"
    framing_action = next(action for action in status["view"]["secondary_actions"] if action["id"] == "select_broadcast_framing")
    assert framing_action["registry_action"] == "vtuber.vseeface_select_framing"
    assert framing_action["form"]["params"][0]["options"][0]["value"] == "bust_up"
    input_action = next(action for action in status["view"]["secondary_actions"] if action["id"] == "select_tracking_input_source")
    assert input_action["registry_action"] == "vtuber.vseeface_select_input_source"
    assert input_action["form"]["params"][0]["source"] == "status.input_sources.options"


def test_vseeface_install_plan_actions_are_json_ready(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    zip_path = tmp_path / "VSeeFace-test.zip"
    zip_path.write_bytes(b"zip")

    plan = registry.execute(
        "vtuber.vseeface_install_plan",
        {
            "source_zip": str(zip_path),
            "install_dir": str(tmp_path / "install"),
            "out_path": str(tmp_path / "install_report.json"),
        },
    ).to_dict()
    gate = registry.execute(
        "vtuber.vseeface_install_execution_gate",
        {
            "source_zip": str(zip_path),
            "install_dir": str(tmp_path / "install"),
            "confirm": True,
        },
    ).to_dict()
    dry = registry.execute(
        "vtuber.vseeface_install_executor_dry_run",
        {
            "source_zip": str(zip_path),
            "install_dir": str(tmp_path / "install"),
            "confirm": True,
        },
    ).to_dict()

    install_plan = plan["result"]["plan"]
    assert install_plan["auto_run"] is False
    assert install_plan["steps"][0]["args"][0] == "tools\\install_vseeface_sidecar.py"
    assert gate["result"]["gate"]["execute_allowed"] is True
    assert dry["result"]["executor"]["executed"] is False
    assert dry["result"]["executor"]["steps"][0]["would_run"] is True


def test_vseeface_start_probe_actions_are_gated_and_json_ready(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")
    vrm = _write_vrm0(tmp_path / "avatar.vrm")
    owner._project_settings = {
        "vseeface_bridge": {
            "vseeface_exe": str(exe),
            "avatar_vrm": str(vrm),
        }
    }
    registry = build_default_action_registry(owner)

    plan = registry.execute("vtuber.vseeface_start_probe_plan").to_dict()
    gate = registry.execute("vtuber.vseeface_start_probe_execution_gate", {"confirm": True}).to_dict()
    dry = registry.execute("vtuber.vseeface_start_probe_executor_dry_run", {"confirm": True}).to_dict()
    blocked = registry.execute("vtuber.vseeface_start_probe_execute", {"confirm": False}).to_dict()

    steps = plan["result"]["plan"]["steps"]
    assert plan["result"]["plan"]["would_launch_external_process"] is True
    assert steps[1]["id"] == "launch_and_verify_capture"
    assert "--launch-vseeface" in steps[1]["args"]
    assert any(step["id"] == "vseeface_live_check" for step in steps)
    assert gate["result"]["gate"]["execute_allowed"] is True
    assert dry["result"]["executor"]["executed"] is False
    assert blocked["result"]["executor"]["executed"] is False
    assert "execution_gate_blocked" in blocked["result"]["executor"]["errors"]


def test_vseeface_install_execute_blocks_without_confirmation(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    zip_path = tmp_path / "VSeeFace-test.zip"
    zip_path.write_bytes(b"zip")

    result = registry.execute(
        "vtuber.vseeface_install_execute",
        {
            "source_zip": str(zip_path),
            "install_dir": str(tmp_path / "install"),
            "confirm": False,
        },
    ).to_dict()

    executor = result["result"]["executor"]
    assert executor["execute_requested"] is True
    assert executor["executed"] is False
    assert "execution_gate_blocked" in executor["errors"]
    assert not (tmp_path / "install" / "VSeeFace").exists()


def test_vseeface_connect_installed_sidecar_action_persists_path(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    exe = tmp_path / "VSeeFace.exe"
    exe.write_bytes(b"MZ")

    dry = registry.execute("vtuber.vseeface_connect_installed_sidecar", {"path": str(exe)}, dry_run=True).to_dict()
    applied = registry.execute("vtuber.vseeface_connect_installed_sidecar", {"path": str(exe)}).to_dict()

    assert dry["result"]["exists"] is True
    assert applied["result"]["connected"] is True
    assert owner._project_settings["vseeface_bridge"]["vseeface_exe"] == str(exe)


def test_marker_action_supports_dry_run_and_apply():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    dry = registry.execute(
        "timeline.marker.add",
        {"ms": 1234, "label": "Dry marker"},
        dry_run=True,
    ).to_dict()

    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert owner._timeline_markers == []

    applied = registry.execute("timeline.marker.add", {"ms": 1234, "label": "Action marker"}).to_dict()

    assert applied["ok"] is True
    assert applied["changed"] is True
    assert owner._timeline_markers[0]["label"] == "Action marker"
    assert owner._timeline_markers[0]["source"] == "python_action"
    assert owner.marker_sync_count == 1
    assert owner.changes == ["Add marker"]

    listed = registry.execute("timeline.marker.list").to_dict()
    assert listed["ok"] is True
    assert listed["result"]["marker_count"] == 1
    assert listed["result"]["markers"][0]["label"] == "Action marker"

    marker_id = applied["result"]["marker"]["id"]
    dry_remove = registry.execute("timeline.marker.remove", {"id": marker_id}, dry_run=True).to_dict()
    assert dry_remove["ok"] is True
    assert dry_remove["changed"] is False
    assert len(owner._timeline_markers) == 1

    removed = registry.execute("timeline.marker.remove", {"id": marker_id}).to_dict()
    assert removed["ok"] is True
    assert removed["changed"] is True
    assert removed["result"]["removed"]["label"] == "Action marker"
    assert owner._timeline_markers == []
    assert owner.marker_sync_count == 2


def test_marker_move_and_jump_actions_apply_to_timeline_state():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    registry.execute("timeline.marker.add", {"id": "m1", "ms": 1000, "label": "Intro"}).to_dict()
    registry.execute("timeline.marker.add", {"id": "m2", "ms": 3000, "label": "Beat"}).to_dict()
    moved = registry.execute("timeline.marker.move", {"id": "m1", "new_ms": 2000}).to_dict()

    assert moved["ok"] is True
    assert moved["changed"] is True
    assert moved["result"]["old_marker"]["ms"] == 1000
    assert moved["result"]["marker"]["ms"] == 2000
    assert [row["ms"] for row in owner._timeline_markers] == [2000, 3000]
    assert owner.marker_sync_count == 3
    assert owner.changes[-1] == "Move marker"

    registry.execute("timeline.set_playhead", {"ms": 2500}).to_dict()
    next_marker = registry.execute("timeline.marker.jump", {"direction": "next"}).to_dict()
    previous_marker = registry.execute("timeline.marker.jump", {"direction": "previous"}).to_dict()

    assert next_marker["ok"] is True
    assert next_marker["changed"] is True
    assert next_marker["result"]["ms"] == 3000
    assert owner._action_playhead_ms == 2000
    assert previous_marker["result"]["ms"] == 2000


def test_low_risk_track_and_playhead_actions():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    audio = registry.execute("track.add", {"kind": "audio", "name": "Dialogue"}).to_dict()
    zoom = registry.execute("timeline.set_zoom", {"px_per_sec": 180}).to_dict()
    fit = registry.execute("timeline.fit").to_dict()
    playhead = registry.execute("timeline.set_playhead", {"ms": 2400}).to_dict()
    undo = registry.execute("history.undo").to_dict()
    redo = registry.execute("history.redo").to_dict()

    assert audio["ok"] is True
    assert audio["changed"] is True
    assert owner._audio_tracks[-1].label == "Dialogue"
    assert zoom["ok"] is True
    assert zoom["result"]["px_per_sec"] == 180.0
    assert fit["ok"] is True
    assert fit["result"]["px_per_sec"] == 190.0
    assert owner.ensure_visible_count == 1
    assert playhead["ok"] is True
    assert owner._action_playhead_ms == 2400
    assert undo["ok"] is True
    assert redo["ok"] is True
    assert owner.undo_count == 1
    assert owner.redo_count == 1


def test_audio_extract_from_video_action_creates_linked_audio_track(tmp_path, monkeypatch):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"not a real video; probe is patched")
    video = owner._tracks[0].clips[0]
    video.source_path = media
    video.source_duration_ms = 5000
    video.timeline_in_ms = 1500
    video.source_in_ms = 250
    video.source_out_ms = 3250
    owner._selected_clips = [(1, 10)]
    owner._audio_tracks = []
    owner._next_track_id = 7
    inserted: list[int] = []
    waveforms: list[int] = []
    mixer_added: list[int] = []

    class _Mixer:
        def add_track(self, track):
            mixer_added.append(track.id)

        def update_track(self, track):
            pass

    owner._audio_mixer = _Mixer()
    owner._insert_audio_track_widget = lambda track: inserted.append(track.id)
    owner._start_waveform_extraction = lambda clip: waveforms.append(clip.id)
    monkeypatch.setattr("app.audio_tracks.probe_audio_duration_ms", lambda _path: 5000)

    registry = build_default_action_registry(owner)
    result = registry.execute("audio.extract_from_video").to_dict()

    assert result["ok"] is True
    assert result["changed"] is True
    assert result["result"]["video_track_id"] == 1
    assert result["result"]["video_clip_id"] == 10
    assert result["result"]["audio_track_id"] == 7
    assert result["result"]["created_track"] is True
    assert result["result"]["linked"] is True
    assert owner._next_track_id == 8
    assert inserted == [7]
    assert mixer_added == [7]
    assert len(owner._audio_tracks) == 1
    audio_clip = owner._audio_tracks[0].clips[0]
    assert audio_clip.source_path == media.resolve()
    assert audio_clip.offset_ms == 1500
    assert audio_clip.duration_ms == 5000
    assert audio_clip.trim_start_ms == 250
    assert audio_clip.trim_end_ms == 3250
    assert waveforms == [audio_clip.id]
    assert video.linked_audio_id == audio_clip.id
    assert owner.changes[-1] == "Action extract audio from video"


def test_timeline_snap_settings_actions_round_trip():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    default = registry.execute("timeline.snap.get").to_dict()
    changed = registry.execute(
        "timeline.snap.set",
        {"enabled": False, "snap_ms": 90, "include_markers": False},
    ).to_dict()
    toggled = registry.execute("timeline.snap.toggle").to_dict()

    assert default["ok"] is True
    assert default["changed"] is False
    assert default["result"]["enabled"] is True
    assert changed["ok"] is True
    assert changed["changed"] is True
    assert changed["result"]["settings"]["enabled"] is False
    assert changed["result"]["settings"]["snap_ms"] == 90
    assert changed["result"]["settings"]["include_markers"] is False
    assert toggled["ok"] is True
    assert toggled["result"]["settings"]["enabled"] is True


def test_timeline_transport_actions_play_pause_stop_step_and_shuttle():
    from app.actions import build_default_action_registry

    class _TransportPlayer:
        def __init__(self) -> None:
            self.pos = 1000
            self.rate = 1.0
            self.calls: list[str] = []

        def position(self) -> int:
            return self.pos

        def duration(self) -> int:
            return 5000

        def set_position(self, ms: int) -> None:
            self.pos = int(ms)
            self.calls.append(f"set:{self.pos}")

        def play(self) -> None:
            self.calls.append("play")

        def pause(self) -> None:
            self.calls.append("pause")

        def stop(self) -> None:
            self.calls.append("stop")

        def set_shuttle_rate(self, rate: float) -> None:
            self.rate = float(rate)
            self.calls.append(f"rate:{self.rate:g}")

    owner = _ActionOwner()
    owner._player = _TransportPlayer()
    registry = build_default_action_registry(owner)

    dry_step = registry.execute("timeline.step_frames", {"frames": 3, "fps": 30}, dry_run=True).to_dict()
    assert dry_step["ok"] is True
    assert dry_step["result"]["target_ms"] == 1100
    assert owner._player.pos == 1000
    assert owner._player.calls == []

    step = registry.execute("timeline.step_frames", {"frames": 3, "fps": 30}).to_dict()
    play = registry.execute("timeline.play", {}).to_dict()
    pause = registry.execute("timeline.pause", {}).to_dict()
    stop = registry.execute("timeline.stop", {}).to_dict()
    shuttle = registry.execute("timeline.set_shuttle_rate", {"rate": 2.0}).to_dict()
    shuttle_pause = registry.execute("timeline.set_shuttle_rate", {"rate": 0.0}).to_dict()

    assert step["ok"] is True
    assert step["result"]["target_ms"] == 1100
    assert owner._player.pos == 1100
    assert play["ok"] is True
    assert pause["ok"] is True
    assert stop["ok"] is True
    assert shuttle["result"]["rate"] == 2.0
    assert shuttle_pause["result"]["rate"] == 0.0
    assert owner._player.calls == [
        "pause",
        "set:1100",
        "play",
        "pause",
        "stop",
        "rate:2",
        "play",
        "rate:0",
        "pause",
    ]


def test_timeline_in_out_actions_set_clear_and_dry_run():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    initial = registry.execute("timeline.range").to_dict()
    dry = registry.execute("timeline.set_in", {"ms": 1200}, dry_run=True).to_dict()

    assert initial["result"]["valid"] is False
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert not hasattr(owner, "_global_in_ms")

    set_in = registry.execute("timeline.set_in", {"ms": 1500}).to_dict()
    set_out = registry.execute("timeline.set_out", {"ms": 2600}).to_dict()
    current = registry.execute("timeline.range").to_dict()
    cleared = registry.execute("timeline.clear_in_out", {}).to_dict()

    assert set_in["ok"] is True
    assert set_in["result"]["after"]["in_ms"] == 1500
    assert set_out["ok"] is True
    assert current["result"]["valid"] is True
    assert current["result"]["duration_ms"] == 1100
    assert cleared["ok"] is True
    assert cleared["result"]["after"]["has_in"] is False
    assert cleared["result"]["after"]["has_out"] is False


def test_timeline_in_out_from_selection_and_jump_actions():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._selected_clips = [(1, 10), (1, 11)]
    owner._action_playhead_ms = 0
    registry = build_default_action_registry(owner)

    marked = registry.execute("timeline.set_in_out_from_selection").to_dict()
    dry_jump = registry.execute("timeline.jump_in_out", {"edge": "out"}, dry_run=True).to_dict()

    assert marked["ok"] is True
    assert marked["result"]["after"]["in_ms"] == 1000
    assert marked["result"]["after"]["out_ms"] == 3500
    assert dry_jump["ok"] is True
    assert dry_jump["result"]["target_ms"] == 3500
    assert owner._action_playhead_ms == 0
    jumped = registry.execute("timeline.jump_in_out", {"edge": "out"}).to_dict()
    assert jumped["ok"] is True
    assert jumped["changed"] is True
    assert owner._action_playhead_ms == 3500


def test_track_targets_and_range_lift_extract_use_in_out_range():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        ),
        VideoTrack(
            id=2,
            clips=[VideoClip(id=40, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=3000)],
        ),
    ]
    registry = build_default_action_registry(owner)

    targets0 = registry.execute("timeline.track_targets").to_dict()
    target = registry.execute("timeline.track_target.set", {"track_id": 1, "exclusive": True}).to_dict()
    registry.execute("timeline.set_in", {"ms": 1500}).to_dict()
    registry.execute("timeline.set_out", {"ms": 2500}).to_dict()
    dry_lift = registry.execute("timeline.lift", dry_run=True).to_dict()
    blocked = registry.execute("timeline.lift").to_dict()
    lifted = registry.execute("timeline.lift", confirm_destructive=True).to_dict()

    assert targets0["ok"] is True
    assert targets0["changed"] is False
    assert target["ok"] is True
    assert target["result"]["after"]["video"] == [1]
    assert dry_lift["ok"] is True
    assert dry_lift["dry_run"] is True
    assert dry_lift["changed"] is False
    assert dry_lift["result"]["target_track_ids"] == [1]
    assert dry_lift["result"]["deleted_clip_count"] == 1
    assert owner._tracks[0].clips[1].timeline_in_ms == 1000
    assert blocked["ok"] is False
    assert "confirm_destructive" in blocked["error"]
    assert lifted["ok"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 2500, 3000]
    assert [clip.timeline_in_ms for clip in owner._tracks[1].clips] == [1000]

    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    extracted = registry.execute("timeline.extract", confirm_destructive=True).to_dict()
    assert extracted["ok"] is True
    assert extracted["changed"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500, 2000]


def test_timeline_play_clip_range_uses_selected_clip_and_restores():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    class _FakePlayer:
        def __init__(self) -> None:
            self.pos = 1200
            self.play_until_calls: list[tuple[int, int | None]] = []

        def position(self) -> int:
            return self.pos

        def set_position(self, ms: int) -> None:
            self.pos = int(ms)

        def play_until(self, end_ms: int, *, return_to_ms: int | None = None) -> None:
            self.play_until_calls.append((int(end_ms), None if return_to_ms is None else int(return_to_ms)))

    owner = _ActionOwner()
    owner._player = _FakePlayer()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=1000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=1000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._selected_clips = [(1, 11)]
    registry = build_default_action_registry(owner)

    dry = registry.execute("timeline.play_clip_range", {}, dry_run=True).to_dict()

    assert dry["ok"] is True
    assert dry["result"]["audition"]["start_ms"] == 1200
    assert dry["result"]["audition"]["end_ms"] == 2000
    assert owner._player.play_until_calls == []

    played = registry.execute("timeline.play_clip_range", {}).to_dict()

    assert played["ok"] is True
    assert played["result"]["audition"]["source"] == "selection"
    assert played["result"]["playback"]["mode"] == "play_until"
    assert owner._player.play_until_calls == [(2000, 1200)]
    assert owner._player.pos == 1200


def test_timeline_edit_point_actions_list_and_jump():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=1000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=1000, timeline_in_ms=1500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=500, offset_ms=750)])]
    owner._timeline_markers = [{"id": "m1", "ms": 1250, "label": "Beat"}]
    owner._action_playhead_ms = 900
    registry = build_default_action_registry(owner)

    video_points = registry.execute("timeline.edit_points", {"track_kind": "video"}).to_dict()
    all_points = registry.execute(
        "timeline.edit_points",
        {"track_kind": "all", "include_markers": True},
    ).to_dict()
    dry_next = registry.execute(
        "timeline.jump_edit_point",
        {"direction": "next", "from_ms": 900, "track_kind": "video"},
        dry_run=True,
    ).to_dict()

    assert video_points["ok"] is True
    assert video_points["result"]["points"] == [0, 1000, 1500, 2500]
    assert all_points["result"]["points"] == [0, 750, 1000, 1250, 1500, 2500]
    assert dry_next["ok"] is True
    assert dry_next["dry_run"] is True
    assert dry_next["result"]["target_ms"] == 1000
    assert owner._action_playhead_ms == 900

    next_jump = registry.execute("timeline.jump_edit_point", {"direction": "next", "track_kind": "video"}).to_dict()
    assert next_jump["ok"] is True
    assert next_jump["changed"] is True
    assert owner._action_playhead_ms == 1000

    previous_jump = registry.execute(
        "timeline.jump_edit_point",
        {"direction": "previous", "track_kind": "video"},
    ).to_dict()
    assert previous_jump["ok"] is True
    assert previous_jump["result"]["target_ms"] == 0
    assert owner._action_playhead_ms == 0


def test_clip_copy_paste_and_cut_clipboard_actions():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(
                    id=10,
                    source_duration_ms=1000,
                    timeline_in_ms=0,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=20,
                ),
                VideoClip(id=11, source_duration_ms=1000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=12, source_duration_ms=1000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=1000, offset_ms=250)])]
    owner._selected_clips = [(1, 10), (1, 11)]
    registry = build_default_action_registry(owner)

    dry_copy = registry.execute("clip.copy", {}, dry_run=True).to_dict()
    assert dry_copy["ok"] is True
    assert dry_copy["result"]["count"] == 2
    assert dry_copy["result"]["linked_audio_count"] == 1
    assert not hasattr(owner, "_action_clipboard")

    copied = registry.execute("clip.copy", {}).to_dict()
    dry_paste = registry.execute("clip.paste", {"at_ms": 5000}, dry_run=True).to_dict()
    pasted = registry.execute("clip.paste", {"at_ms": 5000}).to_dict()

    assert copied["ok"] is True
    assert copied["result"]["count"] == 2
    assert copied["result"]["linked_audio_count"] == 1
    assert dry_paste["ok"] is True
    assert dry_paste["result"]["count"] == 2
    assert dry_paste["result"]["linked_audio_count"] == 1
    assert pasted["ok"] is True
    assert pasted["result"]["count"] == 2
    assert pasted["result"]["linked_audio_count"] == 1
    assert [row["timeline_in_ms"] for row in pasted["result"]["pasted"]] == [5000, 6000]
    assert pasted["result"]["pasted"][0]["linked_audio"]["offset_ms"] == 5250
    pasted_video = next(clip for clip in owner._tracks[0].clips if clip.id == pasted["result"]["pasted"][0]["clip_id"])
    pasted_audio_id = pasted["result"]["pasted"][0]["linked_audio"]["clip_id"]
    assert pasted_video.linked_audio_id == pasted_audio_id
    assert any(clip.id == pasted_audio_id and clip.offset_ms == 5250 for clip in owner._audio_tracks[0].clips)
    assert len(owner._tracks[0].clips) == 5
    assert owner._selected_clips == [(1, pasted["result"]["pasted"][0]["clip_id"]), (1, pasted["result"]["pasted"][1]["clip_id"])]

    owner._selected_clips = [(1, 12)]
    blocked = registry.execute("clip.cut_to_clipboard", {}).to_dict()
    cut = registry.execute("clip.cut_to_clipboard", {}, confirm_destructive=True).to_dict()

    assert blocked["ok"] is False
    assert blocked["error"] == "destructive action requires confirm_destructive=true"
    assert cut["ok"] is True
    assert cut["result"]["count"] == 1
    assert cut["result"]["deleted_count"] == 1
    assert 12 not in {clip.id for clip in owner._tracks[0].clips}


def test_clipboard_insert_and_overwrite_edits_respect_target_track():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._selected_clips = [(1, 10)]
    registry = build_default_action_registry(owner)
    copied = registry.execute("clip.copy", {"include_linked_audio": False}).to_dict()
    dry_insert = registry.execute("timeline.insert_clipboard", {"at_ms": 1500, "target_track_id": 1}, dry_run=True).to_dict()
    inserted = registry.execute("timeline.insert_clipboard", {"at_ms": 1500, "target_track_id": 1}).to_dict()

    assert copied["ok"] is True
    assert dry_insert["ok"] is True
    assert dry_insert["result"]["would_shift_clip_count"] == 2
    assert inserted["ok"] is True
    assert inserted["result"]["mode"] == "insert"
    assert inserted["result"]["duration_ms"] == 1000
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500, 2500, 4000]

    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._selected_clips = [(1, 10)]
    registry.execute("clip.copy", {"include_linked_audio": False}).to_dict()
    dry_overwrite = registry.execute("timeline.overwrite_clipboard", {"at_ms": 1500, "target_track_id": 1}, dry_run=True).to_dict()
    blocked = registry.execute("timeline.overwrite_clipboard", {"at_ms": 1500, "target_track_id": 1}).to_dict()
    overwritten = registry.execute(
        "timeline.overwrite_clipboard",
        {"at_ms": 1500, "target_track_id": 1},
        confirm_destructive=True,
    ).to_dict()

    assert dry_overwrite["ok"] is True
    assert dry_overwrite["result"]["would_delete_clip_count"] == 1
    assert blocked["ok"] is False
    assert "confirm_destructive" in blocked["error"]
    assert overwritten["ok"] is True
    assert overwritten["result"]["mode"] == "overwrite"
    assert overwritten["result"]["deleted_clip_count"] == 1
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500, 2500, 3000]


def test_source_record_monitor_three_point_insert_and_overwrite():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    loaded = registry.execute(
        "source_monitor.load_media",
        {"path": "C:/media/source.mp4", "name": "source.mp4", "kind": "video", "duration_ms": 6000},
    ).to_dict()
    source_in = registry.execute("source_monitor.set_in", {"ms": 1000}).to_dict()
    source_out = registry.execute("source_monitor.set_out", {"ms": 2500}).to_dict()
    record_in = registry.execute("record_monitor.set_in", {"ms": 1500}).to_dict()
    dry_insert = registry.execute("timeline.three_point_insert", {"target_track_id": 1}, dry_run=True).to_dict()
    inserted = registry.execute("timeline.three_point_insert", {"target_track_id": 1}).to_dict()

    assert loaded["ok"] is True
    assert source_in["result"]["after"]["source_in_ms"] == 1000
    assert source_out["result"]["after"]["source_out_ms"] == 2500
    assert record_in["result"]["after"]["in_ms"] == 1500
    assert dry_insert["ok"] is True
    assert dry_insert["result"]["would_shift_clip_count"] == 2
    assert inserted["ok"] is True
    assert inserted["result"]["duration_ms"] == 1500
    assert inserted["result"]["source_in_ms"] == 1000
    assert inserted["result"]["source_out_ms"] == 2500
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500, 3000, 4500]
    assert owner._selected_clips == [(1, inserted["result"]["clip_id"])]

    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=20, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=2000),
                VideoClip(id=30, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)
    registry.execute(
        "source_monitor.load_media",
        {"path": "C:/media/source.mp4", "kind": "video", "duration_ms": 6000, "source_in_ms": 500, "source_out_ms": 1500},
    )
    registry.execute("record_monitor.set_in", {"ms": 1500})
    dry_overwrite = registry.execute("timeline.three_point_overwrite", {"target_track_id": 1}, dry_run=True).to_dict()
    blocked = registry.execute("timeline.three_point_overwrite", {"target_track_id": 1}).to_dict()
    overwritten = registry.execute(
        "timeline.three_point_overwrite",
        {"target_track_id": 1},
        confirm_destructive=True,
    ).to_dict()

    assert dry_overwrite["ok"] is True
    assert dry_overwrite["result"]["would_delete_clip_count"] == 1
    assert blocked["ok"] is False
    assert "confirm_destructive" in blocked["error"]
    assert overwritten["ok"] is True
    assert overwritten["result"]["deleted_clip_count"] == 1
    assert overwritten["result"]["duration_ms"] == 1000
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500, 2500, 3000]


def test_source_record_workbench_returns_ui_ready_state():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    registry.execute(
        "source_monitor.load_media",
        {"path": "C:/media/source.mp4", "kind": "video", "duration_ms": 6000, "source_in_ms": 1000, "source_out_ms": 3000},
    )
    registry.execute("record_monitor.set_in", {"ms": 1500})
    registry.execute("timeline.track_target.set", {"kind": "video", "track_id": 1})

    workbench = registry.execute("source_record.workbench").to_dict()
    preview = registry.execute("source_record.edit_decision_preview", {"mode": "insert"}).to_dict()
    patch_matrix = registry.execute("source_record.patch_matrix").to_dict()
    layout = registry.execute("source_record.monitor_layout").to_dict()
    apply_board = registry.execute("source_record.apply_board").to_dict()
    keyboard_overlay = registry.execute("source_record.keyboard_overlay").to_dict()
    usability = registry.execute("source_record.usability_board").to_dict()

    assert workbench["ok"] is True
    result = workbench["result"]
    assert result["schema"] == "tigerstudio.nle.source_record_workbench.v1"
    assert result["source"]["loaded"] is True
    assert result["source"]["range_ms"] == 2000
    assert result["patching"]["has_video_target"] is True
    assert result["commands"]["insert_enabled"] is True
    assert result["commands"]["overwrite_enabled"] is True
    assert result["readiness"]["three_point_ready"] is True
    assert preview["ok"] is True
    assert preview["result"]["kind"] == "source_record_edit_decision_preview"
    assert preview["result"]["safe_to_apply"] is True
    assert preview["result"]["decision"]["duration_ms"] == 2000
    assert preview["result"]["decision"]["ripple_timeline"] is True
    assert patch_matrix["ok"] is True
    assert patch_matrix["result"]["kind"] == "source_record_patch_matrix"
    assert patch_matrix["result"]["ready"] is True
    assert patch_matrix["result"]["commands"]["show_patch_matrix_enabled"] is True
    assert layout["ok"] is True
    assert layout["result"]["kind"] == "source_record_monitor_layout"
    assert layout["result"]["ready"] is True
    assert len(layout["result"]["layout"]["panes"]) == 2
    assert layout["result"]["commands"]["insert_enabled"] is True
    assert apply_board["ok"] is True
    assert apply_board["result"]["kind"] == "source_record_apply_board"
    assert apply_board["result"]["ready"] is True
    assert apply_board["result"]["recommended_action"] == "insert"
    assert {row["id"] for row in apply_board["result"]["decisions"]} == {"insert", "overwrite"}
    overwrite = next(row for row in apply_board["result"]["decisions"] if row["id"] == "overwrite")
    assert overwrite["requires_confirmation"] is True
    assert overwrite["action_id"] == "timeline.three_point_overwrite"
    assert keyboard_overlay["ok"] is True
    assert keyboard_overlay["result"]["kind"] == "source_record_keyboard_overlay"
    assert keyboard_overlay["result"]["readiness"]["keyboard_overlay_ready"] is True
    assert keyboard_overlay["result"]["readiness"]["jkl_transport_visible"] is True
    assert keyboard_overlay["result"]["commands"]["jkl_transport_enabled"] is True
    assert usability["ok"] is True
    assert usability["result"]["kind"] == "source_record_usability_board"
    assert usability["result"]["readiness"]["source_record_usability_ready"] is True
    assert usability["result"]["readiness"]["review_before_apply_visible"] is True


def test_project_bin_workbench_returns_proxy_relink_state():
    from app.actions import build_default_action_registry

    class _MediaPool:
        def items(self):
            return ["C:/media/source.mp4", "C:/media/dialogue.wav"]

    owner = _ActionOwner()
    owner._media_pool = _MediaPool()
    registry = build_default_action_registry(owner)

    workbench = registry.execute("project_bin.workbench").to_dict()
    batch = registry.execute("project_bin.batch_plan").to_dict()
    conform = registry.execute("project_bin.conform_report").to_dict()
    review_board = registry.execute("project_bin.review_board").to_dict()
    offline_browser = registry.execute("project_bin.offline_browser").to_dict()
    relink_candidates = registry.execute("project_bin.relink_candidate_board").to_dict()
    proxy = registry.execute("project_bin.proxy_plan").to_dict()
    proxy_health = registry.execute("project_bin.proxy_health").to_dict()
    proxy_regen = registry.execute("project_bin.proxy_regeneration_board").to_dict()
    proxy_conflicts = registry.execute("project_bin.proxy_conflict_board").to_dict()
    proxy_apply = registry.execute("project_bin.proxy_apply_review_board").to_dict()
    conform_apply = registry.execute("project_bin.conform_apply_review_board").to_dict()
    search_filter = registry.execute(
        "project_bin.search_filter_model",
        {"query": "source", "kind": "video"},
    ).to_dict()

    assert workbench["ok"] is True
    result = workbench["result"]
    assert result["schema"] == "tigerstudio.nle.project_bin_workbench.v1"
    assert result["summary"]["media_count"] >= 1
    assert "proxy_state" in result["metadata_columns"]
    assert result["commands"]["metadata_search_enabled"] is True
    assert result["readiness"]["bin_workflow_ready"] is True
    assert batch["ok"] is True
    assert batch["result"]["schema"] == "tigerstudio.nle.project_bin_workbench.v1"
    assert batch["result"]["kind"] == "project_bin_batch_plan"
    assert batch["result"]["ready"] is True
    assert "proxy_refresh_enabled" in batch["result"]["commands"]
    assert conform["ok"] is True
    assert conform["result"]["kind"] == "project_bin_conform_report"
    assert conform["result"]["ready"] is True
    assert conform["result"]["summary"]["timeline_clip_count"] >= 1
    assert review_board["ok"] is True
    assert review_board["result"]["kind"] == "project_bin_review_board"
    assert review_board["result"]["ready"] is True
    assert {row["id"] for row in review_board["result"]["sections"]} >= {"bins", "proxy", "conform", "batch"}
    assert offline_browser["ok"] is True
    assert offline_browser["result"]["kind"] == "project_bin_offline_browser"
    assert offline_browser["result"]["ready"] is True
    assert {row["id"] for row in offline_browser["result"]["sections"]} >= {"offline_media", "missing_clips", "ambiguous", "name_only"}
    assert relink_candidates["ok"] is True
    assert relink_candidates["result"]["kind"] == "project_bin_relink_candidate_board"
    assert relink_candidates["result"]["ready"] is True
    assert {row["id"] for row in relink_candidates["result"]["sections"]} >= {"safe", "name_only", "ambiguous", "missing", "offline"}
    assert proxy["ok"] is True
    assert proxy["result"]["kind"] == "project_bin_proxy_plan"
    assert proxy["result"]["ready"] is True
    assert "batch_proxy_refresh_enabled" in proxy["result"]["commands"]
    assert proxy_health["ok"] is True
    assert proxy_health["result"]["kind"] == "project_bin_proxy_health_board"
    assert proxy_health["result"]["ready"] is True
    assert "state_cards" in proxy_health["result"]
    assert "background_regenerate_safe_enabled" in proxy_health["result"]["commands"]
    assert proxy_regen["ok"] is True
    assert proxy_regen["result"]["kind"] == "project_bin_proxy_regeneration_board"
    assert proxy_regen["result"]["ready"] is True
    assert "start_safe_background_jobs_enabled" in proxy_regen["result"]["commands"]
    assert proxy_conflicts["ok"] is True
    assert proxy_conflicts["result"]["kind"] == "project_bin_proxy_conflict_board"
    assert proxy_conflicts["result"]["ready"] is True
    assert "safe_background_jobs" in {row["id"] for row in proxy_conflicts["result"]["sections"]}
    assert "start_safe_background_jobs_enabled" in proxy_conflicts["result"]["commands"]
    assert proxy_apply["ok"] is True
    assert proxy_apply["result"]["kind"] == "proxy_apply_review_board"
    assert proxy_apply["result"]["readiness"]["proxy_apply_review_ready"] is True
    assert proxy_apply["result"]["readiness"]["stale_proxy_warning_ready"] is True
    assert conform_apply["ok"] is True
    assert conform_apply["result"]["kind"] == "conform_apply_review_board"
    assert conform_apply["result"]["readiness"]["conform_apply_review_ready"] is True
    assert conform_apply["result"]["readiness"]["batch_apply_review_required"] is True
    assert search_filter["ok"] is True
    assert search_filter["result"]["kind"] == "project_bin_search_filter_model"
    assert search_filter["result"]["readiness"]["search_filter_model_ready"] is True
    assert search_filter["result"]["readiness"]["metadata_columns_ready"] is True
    assert search_filter["result"]["commands"]["filter_enabled"] is True
    assert search_filter["result"]["summary"]["matched_count"] >= 1


def test_multicam_actions_build_group_switch_plan_and_export_handoff():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = []
    clip_id = 1
    for track_idx in range(3):
        clips = []
        for local_idx in range(4):
            clips.append(
                    VideoClip(
                        id=clip_id,
                        source_path=Path(f"C:/media/cam_{track_idx + 1}.mp4"),
                        source_duration_ms=12000,
                        timeline_in_ms=local_idx * 3000,
                        source_in_ms=local_idx * 3000,
                        source_out_ms=(local_idx + 1) * 3000,
                    )
                )
            setattr(clips[-1], "camera_id", f"cam_{track_idx + 1}")
            setattr(clips[-1], "waveform_sync_peak_ms", track_idx * 120)
            clip_id += 1
        owner._tracks.append(VideoTrack(id=track_idx + 1, clips=clips))

    registry = build_default_action_registry(owner)
    summary = registry.execute("timeline.multicam.summary").to_dict()
    created = registry.execute(
        "timeline.multicam.create_group",
        {"group_id": "mc_scene_1", "name": "Scene 1"},
    ).to_dict()
    plan = registry.execute(
        "timeline.multicam.switch_plan",
        {"group_id": "mc_scene_1", "strategy": "round_robin"},
    ).to_dict()
    sync = registry.execute(
        "timeline.multicam.sync_plan",
        {"group_id": "mc_scene_1", "strategy": "hybrid"},
    ).to_dict()
    angle_bins = registry.execute(
        "timeline.multicam.angle_bins",
        {"group_id": "mc_scene_1"},
    ).to_dict()
    switch = registry.execute(
        "timeline.multicam.set_active_angle",
        {"group_id": "mc_scene_1", "angle_id": "cam_2", "at_ms": 3000},
    ).to_dict()
    workbench = registry.execute(
        "timeline.multicam.switcher_workbench",
        {"group_id": "mc_scene_1", "strategy": "round_robin"},
    ).to_dict()
    tile_board = registry.execute(
        "timeline.multicam.tile_board",
        {"group_id": "mc_scene_1", "strategy": "round_robin"},
    ).to_dict()
    review_board = registry.execute(
        "timeline.multicam.review_board",
        {"group_id": "mc_scene_1", "strategy": "round_robin"},
    ).to_dict()
    live_dashboard = registry.execute(
        "timeline.multicam.live_switch_dashboard",
        {"group_id": "mc_scene_1", "strategy": "round_robin"},
    ).to_dict()
    sync_quality = registry.execute(
        "timeline.multicam.sync_quality_board",
        {"group_id": "mc_scene_1", "strategy": "hybrid"},
    ).to_dict()
    waveform_sync = registry.execute(
        "timeline.multicam.waveform_sync_board",
        {"group_id": "mc_scene_1", "strategy": "waveform"},
    ).to_dict()
    export_parity = registry.execute(
        "timeline.multicam.export_parity_board",
        {"group_id": "mc_scene_1"},
    ).to_dict()
    handoff = registry.execute("timeline.multicam.export_handoff", {"group_id": "mc_scene_1"}).to_dict()

    assert summary["ok"] is True
    assert summary["result"]["angle_count"] == 3
    assert created["ok"] is True
    assert created["changed"] is True
    assert created["result"]["group"]["id"] == "mc_scene_1"
    assert plan["ok"] is True
    assert plan["result"]["ready_for_export_handoff"] is True
    assert plan["result"]["switch_count"] >= 4
    assert sync["ok"] is True
    assert sync["result"]["ready"] is True
    assert sync["result"]["angle_count"] == 3
    assert angle_bins["ok"] is True
    assert angle_bins["result"]["ready"] is True
    assert angle_bins["result"]["angle_count"] == 3
    assert len(angle_bins["result"]["angle_bins"]) == 3
    assert angle_bins["result"]["summary"]["total_clip_count"] == 12
    assert switch["ok"] is True
    assert switch["changed"] is True
    assert workbench["ok"] is True
    assert workbench["result"]["ready"] is True
    assert len(workbench["result"]["angle_tiles"]) == 3
    assert workbench["result"]["commands"]["live_switch_enabled"] is True
    assert tile_board["ok"] is True
    assert tile_board["result"]["kind"] == "multicam_switcher_tile_board"
    assert tile_board["result"]["ready"] is True
    assert tile_board["result"]["grid"]["tile_count"] == 3
    assert tile_board["result"]["commands"]["keyboard_switch_enabled"] is True
    assert review_board["ok"] is True
    assert review_board["result"]["kind"] == "multicam_switch_review_board"
    assert review_board["result"]["ready"] is True
    assert {section["id"] for section in review_board["result"]["sections"]} >= {"angles", "coverage", "switches"}
    assert review_board["result"]["commands"]["export_handoff_enabled"] is True
    assert live_dashboard["ok"] is True
    assert live_dashboard["result"]["kind"] == "multicam_live_switch_dashboard"
    assert live_dashboard["result"]["readiness"]["live_switch_dashboard_ready"] is True
    assert {section["id"] for section in live_dashboard["result"]["sections"]} >= {"tiles", "switch_decisions", "sync_quality", "waveform"}
    assert sync_quality["ok"] is True
    assert sync_quality["result"]["kind"] == "multicam_sync_quality_board"
    assert sync_quality["result"]["readiness"]["sync_quality_board_ready"] is True
    assert sync_quality["result"]["readiness"]["has_confidence_rows"] is True
    assert sync_quality["result"]["summary"]["angle_count"] == 3
    assert waveform_sync["ok"] is True
    assert waveform_sync["result"]["kind"] == "multicam_waveform_sync_board"
    assert waveform_sync["result"]["readiness"]["waveform_sync_board_ready"] is True
    assert waveform_sync["result"]["summary"]["waveform_ready_count"] == 3
    assert export_parity["ok"] is True
    assert export_parity["result"]["kind"] == "multicam_export_parity_board"
    assert export_parity["result"]["readiness"]["multicam_export_parity_board_ready"] is True
    assert export_parity["result"]["summary"]["angle_count"] == 3
    assert handoff["ok"] is True
    assert handoff["result"]["ready"] is True
    assert handoff["result"]["decision_count"] >= 1


def test_core_edit_actions_use_registry_and_safety_gates():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    split = registry.execute("timeline.split", {"track_id": 1, "at_ms": 2500}).to_dict()
    assert split["ok"] is True
    assert split["changed"] is True
    assert len(owner._tracks[0].clips) == 2

    left_id = owner._tracks[0].clips[0].id
    right_id = owner._tracks[0].clips[1].id
    speed = registry.execute(
        "clip.set_speed",
        {"track_id": 1, "clip_id": left_id, "speed": 1.5},
    ).to_dict()
    fade = registry.execute(
        "clip.set_fade",
        {"track_id": 1, "clip_id": left_id, "fade_in_ms": 250, "fade_out_ms": 300},
    ).to_dict()
    duplicate = registry.execute(
        "clip.duplicate",
        {"track_id": 1, "clip_id": right_id, "at_ms": 6000},
    ).to_dict()
    blocked_delete = registry.execute("clip.delete", {"track_id": 1, "clip_id": right_id}).to_dict()
    dry_delete = registry.execute(
        "clip.delete",
        {"track_id": 1, "clip_id": right_id},
        dry_run=True,
    ).to_dict()
    confirmed_delete = registry.execute(
        "clip.delete",
        {"track_id": 1, "clip_id": right_id},
        confirm_destructive=True,
    ).to_dict()

    assert speed["ok"] is True
    assert owner._tracks[0].clips[0].speed_segments[0].speed == 1.5
    assert fade["ok"] is True
    assert fade["result"]["fade_count"] == 2
    assert duplicate["ok"] is True
    assert duplicate["result"]["new_clip_id"] != right_id
    assert blocked_delete["ok"] is False
    assert blocked_delete["error"] == "destructive action requires confirm_destructive=true"
    assert dry_delete["ok"] is True
    assert dry_delete["changed"] is False
    assert confirmed_delete["ok"] is True
    assert confirmed_delete["changed"] is True
    assert right_id not in {clip.id for clip in owner._tracks[0].clips}


def test_action_registry_blocks_unknown_and_owner_required_actions():
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(None)
    unknown = registry.execute("shell.run").to_dict()
    marker = registry.execute("timeline.marker.add", {"ms": 1, "label": "No owner"}).to_dict()
    dry_marker = registry.execute(
        "timeline.marker.add",
        {"ms": 1, "label": "No owner dry"},
        dry_run=True,
    ).to_dict()

    assert unknown["ok"] is False
    assert unknown["error"] == "unknown action: shell.run"
    assert marker["ok"] is False
    assert marker["error"] == "no editor owner"
    assert dry_marker["ok"] is True
    assert dry_marker["dry_run"] is True


def test_timeline_edit_actions_mutate_with_dry_run_and_confirmation():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    dry_split = registry.execute("timeline.split", {"track_id": 1, "at_ms": 2000}, dry_run=True).to_dict()
    assert dry_split["ok"] is True
    assert dry_split["dry_run"] is True
    assert len(owner._tracks[0].clips) == 1

    split = registry.execute("timeline.split", {"track_id": 1, "at_ms": 2000}).to_dict()
    assert split["ok"] is True
    assert split["changed"] is True
    assert len(owner._tracks[0].clips) == 2
    right_clip_id = split["result"]["right_clip_id"]

    speed = registry.execute("clip.set_speed", {"track_id": 1, "clip_id": right_clip_id, "speed": 1.5}).to_dict()
    right_clip = next(clip for clip in owner._tracks[0].clips if clip.id == right_clip_id)
    assert speed["ok"] is True
    assert right_clip.speed_segments[0].speed == 1.5

    dry_nudge_frames = registry.execute(
        "clip.nudge_frames",
        {"track_id": 1, "clip_id": right_clip_id, "frames": 3, "fps": 30},
        dry_run=True,
    ).to_dict()
    nudge_frames = registry.execute(
        "clip.nudge_frames",
        {"track_id": 1, "clip_id": right_clip_id, "frames": 3, "fps": 30},
    ).to_dict()
    assert dry_nudge_frames["ok"] is True
    assert dry_nudge_frames["result"]["frame_delta_ms"] == 100
    assert nudge_frames["ok"] is True
    assert right_clip.timeline_in_ms == 2100

    blocked_delete = registry.execute("clip.delete", {"track_id": 1, "clip_id": right_clip_id}).to_dict()
    assert blocked_delete["ok"] is False
    assert blocked_delete["error"] == "destructive action requires confirm_destructive=true"
    assert len(owner._tracks[0].clips) == 2

    deleted = registry.execute(
        "clip.delete",
        {"track_id": 1, "clip_id": right_clip_id},
        confirm_destructive=True,
    ).to_dict()
    assert deleted["ok"] is True
    assert len(owner._tracks[0].clips) == 1
    assert owner.refresh_count >= 3


def test_track_remove_requires_confirmation_and_updates_tracks():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    dry = registry.execute("track.remove", {"kind": "audio", "track_id": 2}, dry_run=True).to_dict()
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert len(owner._audio_tracks) == 1

    blocked = registry.execute("track.remove", {"kind": "audio", "track_id": 2}).to_dict()
    assert blocked["ok"] is False
    assert blocked["error"] == "destructive action requires confirm_destructive=true"

    removed_audio = registry.execute(
        "track.remove",
        {"kind": "audio", "track_id": 2},
        confirm_destructive=True,
    ).to_dict()
    assert removed_audio["ok"] is True
    assert removed_audio["result"]["removed_clip_count"] == 1
    assert owner._audio_tracks == []

    removed_video = registry.execute(
        "track.remove",
        {"kind": "video", "track_id": 1},
        confirm_destructive=True,
    ).to_dict()
    assert removed_video["ok"] is True
    assert removed_video["result"]["track_count_after"] == 0
    assert owner._tracks == []


def test_extended_timeline_media_selection_effect_node_and_text_actions(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    media_path = tmp_path / "sample.mp4"
    media_path.write_bytes(b"fake")

    imported = registry.execute(
        "media.import_to_timeline",
        {"path": str(media_path), "kind": "video", "track_id": 1, "at_ms": 7000, "duration_ms": 1200},
    ).to_dict()
    assert imported["ok"] is True
    assert imported["result"]["clip_id"] != 10
    assert len(owner._tracks[0].clips) == 2

    moved = registry.execute("clip.move", {"track_id": 1, "clip_id": 10, "at_ms": 1000}).to_dict()
    nudged = registry.execute("clip.nudge", {"track_id": 1, "clip_id": 10, "delta_ms": 250}).to_dict()
    assert moved["ok"] is True
    assert nudged["result"]["new_ms"] == 1250

    state = registry.execute("track.set_state", {"kind": "video", "track_id": 1, "locked": True, "muted": True}).to_dict()
    assert state["ok"] is True
    assert owner._tracks[0].locked is True
    assert owner._tracks[0].muted is True

    unlocked = registry.execute("track.lock", {"kind": "video", "track_id": 1, "locked": False}).to_dict()
    muted_audio = registry.execute("track.mute", {"kind": "audio", "track_id": 2, "muted": True}).to_dict()
    renamed = registry.execute("track.rename", {"kind": "video", "track_id": 1, "name": "B-roll"}).to_dict()
    assert unlocked["ok"] is True
    assert owner._tracks[0].locked is False
    assert muted_audio["ok"] is True
    assert getattr(owner._audio_tracks[0], "muted") is True
    assert renamed["ok"] is True
    assert owner._tracks[0].display_name == "B-roll"

    selection = registry.execute("selection.set", {"kind": "video", "track_id": 1, "clip_id": 10}).to_dict()
    clear = registry.execute("selection.clear").to_dict()
    assert selection["result"]["selected_count"] == 1
    assert clear["result"]["selected_count"] == 0

    owner._tracks[0].locked = False
    filters = registry.execute(
        "clip.set_filter",
        {"track_id": 1, "clip_id": 10, "params": {"sharpen": 0.4, "vignette": 0.2}},
    ).to_dict()
    grade = registry.execute(
        "clip.set_color_grade",
        {"track_id": 1, "clip_id": 10, "grade": {"brightness": 12, "contrast": 8}},
    ).to_dict()
    assert filters["result"]["video_filters"]["sharpen"] == 0.4
    assert grade["result"]["grade"]["brightness"] == 12

    transition = registry.execute(
        "transition.apply",
        {"track_id": 1, "clip_id": 10, "preset_id": "transition-dip-white"},
    ).to_dict()
    assert transition["ok"] is True
    assert owner._tracks[0].clips[0].transition_out_type == "fade_white"
    assert owner._tracks[0].clips[0].transition_out_ms == 260
    assert owner._tracks[0].clips[0].transition_preset_meta["preset_id"] == "transition-dip-white"
    cleared_transition = registry.execute("transition.clear", {"track_id": 1, "clip_id": 10}).to_dict()
    assert cleared_transition["ok"] is True
    assert owner._tracks[0].clips[0].transition_out_type == ""
    assert owner._tracks[0].clips[0].transition_out_ms == 0

    node = registry.execute(
        "node.add",
        {"track_id": 1, "kind": "glow", "label": "Glow", "params": {"intensity": 0.7}},
    ).to_dict()
    node_id = node["result"]["node_id"]
    param = registry.execute(
        "node.set_param",
        {"track_id": 1, "node_id": node_id, "params": {"intensity": 0.3}},
    ).to_dict()
    assert node["ok"] is True
    assert param["result"]["params"]["intensity"] == 0.3
    assert owner._tracks[0].node_graph_view_data["nodes"][0]["id"] == node_id

    text = registry.execute(
        "text.add",
        {
            "track_id": 1,
            "clip_id": 10,
            "text": "Review title",
            "start_ms": 0,
            "end_ms": 1500,
            "style": {"position_x": 0.45, "position_y": 0.2},
        },
    ).to_dict()
    text_id = text["result"]["text_id"]
    keyframes = registry.execute(
        "text.set_keyframes",
        {
            "track_id": 1,
            "clip_id": 10,
            "text_id": text_id,
            "keyframes": {"opacity": [{"time_ms": 0, "value": 1.0}, {"time_ms": 1000, "value": 0.0}]},
        },
    ).to_dict()
    assert text["ok"] is True
    assert keyframes["ok"] is True
    assert owner._tracks[0].clips[0].typography_actors[0].keyframes["opacity"][1]["value"] == 0.0
    assert owner._tracks[0].typography_actors[0] is owner._tracks[0].clips[0].typography_actors[0]


def test_selection_state_actions_normalize_toggle_and_select_range():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=1000, offset_ms=1500)])]
    owner._selected_clips = [(1, 10), {"track_kind": "video", "track_id": 1, "clip_id": 10}]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert {"selection.summary", "selection.select_range"} <= ids

    summary = registry.execute("selection.summary").to_dict()
    assert summary["ok"] is True
    assert summary["result"]["selected_count"] == 1
    assert summary["result"]["selection"][0]["clip_id"] == 10
    assert registry.execute("selected.clip").to_dict()["result"]["selection_state"]["selected_count"] == 1

    added = registry.execute("selection.set", {"kind": "video", "track_id": 1, "clip_id": 11, "mode": "add"}).to_dict()
    duplicate = registry.execute("selection.set", {"kind": "video", "track_id": 1, "clip_id": 11, "mode": "add"}).to_dict()
    assert added["result"]["selected_count"] == 2
    assert duplicate["result"]["selected_count"] == 2
    assert owner._selected_clips == [(1, 10), (1, 11)]

    toggled = registry.execute("selection.set", {"kind": "video", "track_id": 1, "clip_id": 10, "mode": "toggle"}).to_dict()
    assert toggled["result"]["selected_count"] == 1
    assert owner._selected_clips == [(1, 11)]

    audio = registry.execute("selection.set", {"kind": "audio", "track_id": 2, "clip_id": 20, "mode": "add"}).to_dict()
    assert audio["result"]["kind_counts"] == {"video": 1, "audio": 1}
    assert owner._selected_audio_clip_id == 20

    contained = registry.execute(
        "selection.select_range",
        {"start_ms": 900, "end_ms": 2400, "include_partial": False},
    ).to_dict()
    assert contained["result"]["selected_count"] == 1
    assert contained["result"]["selection"][0]["clip_id"] == 11
    assert owner._selected_clips == [(1, 11)]

    partial = registry.execute(
        "selection.select_range",
        {"start_ms": 900, "end_ms": 2600, "include_partial": True},
    ).to_dict()
    assert partial["result"]["matched_count"] == 3
    assert [row["clip_id"] for row in partial["result"]["selection"]] == [10, 11, 12]

    selected_clip = registry.execute("clip.select", {"kind": "video", "track_id": 1, "clip_id": 12}).to_dict()
    assert selected_clip["ok"] is True
    assert selected_clip["result"]["selected_count"] == 1
    assert owner._selected_clips == [(1, 12)]

    track_focus = registry.execute("track.select", {"kind": "audio", "track_id": 2}).to_dict()
    assert track_focus["ok"] is True
    assert track_focus["result"]["active_audio_track_id"] == 2
    assert owner._selected_clips == [(1, 12)]

    first_audio = registry.execute(
        "track.select",
        {"kind": "audio", "track_id": 2, "select_first_clip": True},
    ).to_dict()
    assert first_audio["ok"] is True
    assert first_audio["result"]["kind_counts"] == {"audio": 1}
    assert owner._selected_audio_clip_id == 20

    all_clips = registry.execute("timeline.select_all", {"kind": "all"}).to_dict()
    assert all_clips["ok"] is True
    assert all_clips["result"]["selected_count"] == 4
    assert all_clips["result"]["kind_counts"] == {"video": 3, "audio": 1}
    assert owner._selected_clips == [(1, 10), (1, 11), (1, 12)]


def test_snapped_clip_move_action_dry_runs_and_applies_marker_snap():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    owner._timeline_markers = [{"id": "m1", "ms": 5300, "label": "Beat"}]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert "clip.move_snapped" in ids

    dry = registry.execute(
        "clip.move_snapped",
        {"track_id": 1, "clip_id": 10, "at_ms": 5200, "snap_ms": 150},
        dry_run=True,
    ).to_dict()

    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert dry["result"]["changed"] is True
    assert dry["result"]["new_ms"] == 5300
    assert dry["result"]["snapped"] is True
    assert dry["result"]["snap_target_ms"] == 5300
    assert owner._tracks[0].clips[0].timeline_in_ms == 0

    applied = registry.execute(
        "clip.move_snapped",
        {"track_id": 1, "clip_id": 10, "at_ms": 5200, "snap_ms": 150},
    ).to_dict()

    assert applied["ok"] is True
    assert applied["changed"] is True
    assert applied["result"]["new_ms"] == 5300
    assert owner._tracks[0].clips[0].timeline_in_ms == 5300
    assert owner.changes[-1] == "Action snapped move clip"


def test_snapped_clip_move_action_can_use_native_drag_constraints(monkeypatch):
    from app.actions import build_default_action_registry

    def _native_plan(clips, **kwargs):
        assert len(clips) >= 1
        assert kwargs["desired_timeline_in_ms"] == 5200
        return {
            "timeline_in_ms": 5300,
            "requested_timeline_in_ms": 5200,
            "snapped": True,
            "snap_target_ms": 5300,
            "snap_edge": "in",
            "snap_source": "marker/playhead",
            "collided": False,
            "clamped": False,
            "clamp_target_ms": None,
            "backend": "rust_worker",
        }

    monkeypatch.setattr("app.native_worker.native_timeline_drag_constraints", _native_plan)
    owner = _ActionOwner()
    owner._timeline_markers = [{"id": "m1", "ms": 5300, "label": "Beat"}]
    registry = build_default_action_registry(owner)

    dry = registry.execute(
        "clip.move_snapped",
        {"track_id": 1, "clip_id": 10, "at_ms": 5200, "snap_ms": 150},
        dry_run=True,
    ).to_dict()

    assert dry["ok"] is True
    assert dry["result"]["new_ms"] == 5300
    assert dry["result"]["constraint_backend"] == "rust_worker"
    assert dry["result"]["snap_source"] == "marker/playhead"


def test_polish_edit_actions_slip_roll_and_slide_use_timeline_model():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=1, source_duration_ms=6000, timeline_in_ms=0, source_in_ms=0, source_out_ms=3000),
                VideoClip(id=2, source_duration_ms=6000, timeline_in_ms=3000, source_in_ms=1000, source_out_ms=3000),
                VideoClip(id=3, source_duration_ms=6000, timeline_in_ms=5000, source_in_ms=1000, source_out_ms=4000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert {"clip.slip", "clip.roll", "clip.slide"} <= ids

    dry_slip = registry.execute(
        "clip.slip",
        {"track_id": 1, "clip_id": 2, "delta_ms": 500},
        dry_run=True,
    ).to_dict()
    assert dry_slip["ok"] is True
    assert dry_slip["dry_run"] is True
    assert dry_slip["result"]["new"]["timeline_in_ms"] == 3000
    assert dry_slip["result"]["new"]["source_in_ms"] == 1500
    assert owner._tracks[0].clips[1].source_in_ms == 1000

    slipped = registry.execute("clip.slip", {"track_id": 1, "clip_id": 2, "delta_ms": 500}).to_dict()
    assert slipped["ok"] is True
    assert slipped["changed"] is True
    assert owner._tracks[0].clips[1].timeline_in_ms == 3000
    assert owner._tracks[0].clips[1].source_in_ms == 1500

    dry_roll = registry.execute(
        "clip.roll",
        {"track_id": 1, "left_clip_id": 1, "right_clip_id": 2, "delta_ms": 400},
        dry_run=True,
    ).to_dict()
    assert dry_roll["ok"] is True
    assert dry_roll["result"]["new"]["1"]["timeline_out_ms"] == 3400
    assert owner._tracks[0].clips[0].timeline_out_ms == 3000

    rolled = registry.execute(
        "clip.roll",
        {"track_id": 1, "left_clip_id": 1, "right_clip_id": 2, "delta_ms": 400},
    ).to_dict()
    left = next(clip for clip in owner._tracks[0].clips if clip.id == 1)
    middle = next(clip for clip in owner._tracks[0].clips if clip.id == 2)
    assert rolled["ok"] is True
    assert left.timeline_out_ms == middle.timeline_in_ms == 3400
    assert middle.timeline_out_ms == 5000

    slid = registry.execute("clip.slide", {"track_id": 1, "clip_id": 2, "delta_ms": 200}).to_dict()
    left = next(clip for clip in owner._tracks[0].clips if clip.id == 1)
    middle = next(clip for clip in owner._tracks[0].clips if clip.id == 2)
    right = next(clip for clip in owner._tracks[0].clips if clip.id == 3)
    assert slid["ok"] is True
    assert slid["changed"] is True
    assert (left.timeline_in_ms, right.timeline_out_ms) == (0, 8000)
    assert left.timeline_out_ms == middle.timeline_in_ms == 3600
    assert middle.timeline_out_ms == right.timeline_in_ms == 5200


def test_linked_clip_actions_move_link_unlink_and_j_l_cut():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=3000),
            ],
        )
    ]
    owner._audio_tracks = [
        AudioTrack(
            id=2,
            clips=[
                AudioClip(id=20, duration_ms=5000, offset_ms=1000, trim_start_ms=1000, trim_end_ms=4000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert {
        "clip.link_audio",
        "clip.unlink_audio",
        "clip.move_linked",
        "clip.set_sync_offset",
        "clip.j_cut",
        "clip.l_cut",
    } <= ids

    linked = registry.execute("clip.link_audio", {"track_id": 1, "clip_id": 10, "audio_clip_id": 20}).to_dict()
    assert linked["ok"] is True
    assert owner._tracks[0].clips[0].linked_audio_id == 20

    dry_move = registry.execute(
        "clip.move_linked",
        {"track_id": 1, "clip_id": 10, "delta_ms": 250},
        dry_run=True,
    ).to_dict()
    assert dry_move["ok"] is True
    assert dry_move["dry_run"] is True
    assert dry_move["result"]["video_moves"][0]["timeline_in_ms"] == 1250
    assert dry_move["result"]["audio_moves"][0]["offset_ms"] == 1250
    assert owner._tracks[0].clips[0].timeline_in_ms == 1000
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    moved = registry.execute("clip.move_linked", {"track_id": 1, "clip_id": 10, "delta_ms": 250}).to_dict()
    assert moved["ok"] is True
    assert owner._tracks[0].clips[0].timeline_in_ms == 1250
    assert owner._audio_tracks[0].clips[0].offset_ms == 1250

    offset = registry.execute(
        "clip.set_sync_offset",
        {"track_id": 1, "clip_id": 10, "sync_offset_ms": -250},
    ).to_dict()
    assert offset["ok"] is True
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    jcut = registry.execute("clip.j_cut", {"track_id": 1, "clip_id": 10, "extend_ms": 500}).to_dict()
    assert jcut["ok"] is True
    assert owner._audio_tracks[0].clips[0].offset_ms == 500
    assert owner._audio_tracks[0].clips[0].trim_start_ms == 500

    lcut = registry.execute("clip.l_cut", {"track_id": 1, "clip_id": 10, "extend_ms": 500}).to_dict()
    assert lcut["ok"] is True
    assert owner._audio_tracks[0].clips[0].trim_end_ms == 4500

    unlinked = registry.execute("clip.unlink_audio", {"track_id": 1, "clip_id": 10}).to_dict()
    assert unlinked["ok"] is True
    assert owner._tracks[0].clips[0].linked_audio_id is None


def test_selection_move_actions_move_multi_selected_clips_and_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(
                    id=10,
                    source_duration_ms=5000,
                    timeline_in_ms=0,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=20,
                ),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=3500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [
        AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=1000, offset_ms=0)]),
    ]
    owner._selected_clips = [
        (1, 10),
        {"track_kind": "video", "track_id": 1, "clip_id": 11},
        {"track_kind": "audio", "track_id": 2, "clip_id": 20},
    ]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert {"selection.move", "selection.nudge", "selection.nudge_frames", "timeline.nudge", "timeline.nudge_frames"} <= ids

    dry = registry.execute("selection.move", {"delta_ms": 500}, dry_run=True).to_dict()
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert dry["result"]["selected_count"] == 2
    assert [row["timeline_in_ms"] for row in dry["result"]["video_moves"]] == [500, 1500]
    assert dry["result"]["audio_moves"][0]["offset_ms"] == 500
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 3500]
    assert owner._audio_tracks[0].clips[0].offset_ms == 0

    moved = registry.execute("selection.nudge", {"delta_ms": 500}).to_dict()
    assert moved["ok"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [500, 1500, 3500]
    assert owner._audio_tracks[0].clips[0].offset_ms == 500

    timeline_nudge = registry.execute("timeline.nudge", {"delta_ms": 500}).to_dict()
    assert timeline_nudge["ok"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [1000, 2000, 3500]
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    frame_nudge = registry.execute("selection.nudge_frames", {"frames": 3, "fps": 30}).to_dict()
    assert frame_nudge["ok"] is True
    assert frame_nudge["result"]["frame_delta_ms"] == 100
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [1100, 2100, 3500]
    assert owner._audio_tracks[0].clips[0].offset_ms == 1100


def test_selection_align_actions_use_snap_targets_and_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(
                    id=10,
                    source_duration_ms=5000,
                    timeline_in_ms=1000,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=20,
                ),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=6500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=1000, offset_ms=1000)])]
    owner._selected_clips = [(1, 10)]
    owner._timeline_markers = [{"id": "m1", "ms": 5000, "label": "Beat"}]
    owner._action_playhead_ms = 4200
    registry = build_default_action_registry(owner)

    dry_playhead = registry.execute("selection.align_to_playhead", dry_run=True).to_dict()
    assert dry_playhead["ok"] is True
    assert dry_playhead["dry_run"] is True
    assert dry_playhead["changed"] is False
    assert dry_playhead["result"]["delta_ms"] == 3200
    assert owner._tracks[0].clips[0].timeline_in_ms == 1000
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    marker = registry.execute("selection.align_to_marker", {"direction": "next", "from_ms": 4200}).to_dict()
    assert marker["ok"] is True
    assert marker["changed"] is True
    assert marker["result"]["marker"]["id"] == "m1"
    assert owner._tracks[0].clips[0].timeline_in_ms == 5000
    assert owner._audio_tracks[0].clips[0].offset_ms == 5000

    owner._tracks[0].clips[0].timeline_in_ms = 4800
    owner._audio_tracks[0].clips[0].offset_ms = 4800
    registry.execute("timeline.snap.set", {"include_edit_points": False}).to_dict()
    snapped = registry.execute("selection.snap_to_nearest").to_dict()
    assert snapped["ok"] is True
    assert snapped["result"]["target_ms"] == 5000
    assert snapped["result"]["within_tolerance"] is True
    assert owner._tracks[0].clips[0].timeline_in_ms == 5000
    assert owner._audio_tracks[0].clips[0].offset_ms == 5000


def test_trim_to_playhead_action_trims_selected_clip_and_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(
                    id=10,
                    source_duration_ms=5000,
                    timeline_in_ms=1000,
                    source_in_ms=0,
                    source_out_ms=4000,
                    linked_audio_id=20,
                )
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=4000, offset_ms=1000)])]
    owner._selected_clips = [(1, 10)]
    owner._action_playhead_ms = 1800
    registry = build_default_action_registry(owner)

    dry = registry.execute("timeline.trim_to_playhead", {"edge": "left"}, dry_run=True).to_dict()
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["result"]["new"]["timeline_in_ms"] == 1800
    assert dry["result"]["new"]["source_in_ms"] == 800
    assert dry["result"]["shifted_audio"][0]["offset_ms"] == 1800
    assert owner._tracks[0].clips[0].timeline_in_ms == 1000
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    applied = registry.execute("timeline.trim_to_playhead", {"edge": "left"}).to_dict()
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert owner._tracks[0].clips[0].timeline_in_ms == 1800
    assert owner._tracks[0].clips[0].source_in_ms == 800
    assert owner._audio_tracks[0].clips[0].offset_ms == 1800

    owner._action_playhead_ms = 2500
    right = registry.execute("timeline.trim_to_playhead", {"edge": "right"}).to_dict()
    assert right["ok"] is True
    assert right["result"]["new"]["timeline_out_ms"] == 2500
    assert owner._tracks[0].clips[0].timeline_in_ms == 1800
    assert owner._tracks[0].clips[0].source_out_ms == 1500


def test_selection_ripple_delete_removes_multi_selected_clips_and_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000, linked_audio_id=20),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000, linked_audio_id=21),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [
        AudioTrack(
            id=2,
            clips=[
                AudioClip(id=20, duration_ms=1000, offset_ms=0),
                AudioClip(id=21, duration_ms=1000, offset_ms=1000),
                AudioClip(id=22, duration_ms=500, offset_ms=2500),
            ],
        )
    ]
    owner._selected_clips = [(1, 10), (1, 11)]
    registry = build_default_action_registry(owner)

    dry = registry.execute("selection.ripple_delete", dry_run=True).to_dict()
    blocked = registry.execute("selection.ripple_delete").to_dict()
    applied = registry.execute("selection.ripple_delete", confirm_destructive=True).to_dict()

    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert dry["result"]["deleted_video_count"] == 2
    assert dry["result"]["deleted_linked_audio_count"] == 2
    assert dry["result"]["video_tracks"][0]["remaining"][0]["clip_id"] == 12
    assert dry["result"]["video_tracks"][0]["remaining"][0]["timeline_in_ms"] == 500
    assert dry["result"]["audio_tracks"][0]["remaining"][0]["clip_id"] == 22
    assert dry["result"]["audio_tracks"][0]["remaining"][0]["offset_ms"] == 500
    assert blocked["ok"] is False
    assert "confirm_destructive" in blocked["error"]
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert [clip.id for clip in owner._tracks[0].clips] == [12]
    assert owner._tracks[0].clips[0].timeline_in_ms == 500
    assert [clip.id for clip in owner._audio_tracks[0].clips] == [22]
    assert owner._audio_tracks[0].clips[0].offset_ms == 500
    assert owner._selected_clips == []


def test_timeline_edge_issues_and_cleanup_actions_fix_micro_edges():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1020, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=1990, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    issues = registry.execute("timeline.edge_issues", {"frame_ms": 33}).to_dict()
    dry = registry.execute("timeline.cleanup_edges", {"frame_ms": 33}, dry_run=True).to_dict()

    assert issues["ok"] is True
    assert issues["changed"] is False
    assert issues["result"]["issue_count"] == 2
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert dry["result"]["action_count"] == 2
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1020, 1990]
    applied = registry.execute("timeline.cleanup_edges", {"frame_ms": 33}).to_dict()
    assert applied["ok"] is True
    assert applied["changed"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1970]
    assert owner._tracks[0].clips[1].source_out_ms == 970
    assert owner._tracks[0].clips[1].timeline_out_ms == 1970


def test_timeline_gap_actions_list_and_close_gaps():
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._action_playhead_ms = 1200
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1500, source_in_ms=0, source_out_ms=500),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    gaps = registry.execute("timeline.gaps", {"track_id": 1}).to_dict()
    dry_close = registry.execute("timeline.close_gap", {"track_id": 1}, dry_run=True).to_dict()

    assert gaps["ok"] is True
    assert gaps["result"]["gap_count"] == 2
    assert gaps["result"]["tracks"][0]["gaps"][0]["start_ms"] == 1000
    assert gaps["result"]["tracks"][0]["gaps"][0]["end_ms"] == 1500
    assert dry_close["ok"] is True
    assert dry_close["result"]["gap"]["start_ms"] == 1000
    assert dry_close["changed"] is False
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1500, 3000]
    close = registry.execute("timeline.close_gap", {"track_id": 1}).to_dict()
    assert close["ok"] is True
    assert close["changed"] is True
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 2500]

    all_gaps = registry.execute("timeline.close_all_gaps", {"track_id": 1}).to_dict()
    assert all_gaps["ok"] is True
    assert all_gaps["changed"] is True
    assert all_gaps["result"]["gap_count"] == 1
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 1500]


def test_timeline_gap_actions_can_use_native_gap_planner(monkeypatch):
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    def _native_gaps(clips, *, min_gap_ms=1):
        assert len(clips) == 3
        return {
            "gap_count": 1,
            "gaps": [
                {"index": 0, "start_ms": 1000, "end_ms": 1500, "duration_ms": 500, "next_clip_id": 11}
            ],
            "min_gap_ms": min_gap_ms,
            "backend": "rust_worker",
        }

    monkeypatch.setattr("app.native_worker.native_timeline_gaps", _native_gaps)
    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1500, source_in_ms=0, source_out_ms=500),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=3000, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    gaps = registry.execute("timeline.gaps", {"track_id": 1}).to_dict()

    assert gaps["ok"] is True
    assert gaps["result"]["gap_count"] == 1
    assert gaps["result"]["tracks"][0]["gaps"][0]["next_clip_id"] == 11


def test_ripple_trim_action_moves_following_clips_and_linked_audio():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(
                    id=11,
                    source_duration_ms=5000,
                    timeline_in_ms=1000,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=20,
                ),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=20, duration_ms=1000, offset_ms=1000)])]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert "clip.ripple_trim" in ids

    dry = registry.execute(
        "clip.ripple_trim",
        {"track_id": 1, "clip_id": 10, "edge": "right", "delta_ms": -200},
        dry_run=True,
    ).to_dict()
    assert dry["ok"] is True
    assert dry["changed"] is False
    assert dry["result"]["new"]["source_out_ms"] == 800
    assert [row["timeline_in_ms"] for row in dry["result"]["shifted_clips"]] == [800, 2300]
    assert dry["result"]["shifted_linked_audio"][0]["offset_ms"] == 800
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 1000, 2500]
    assert owner._audio_tracks[0].clips[0].offset_ms == 1000

    applied = registry.execute(
        "clip.ripple_trim",
        {"track_id": 1, "clip_id": 10, "edge": "right", "delta_ms": -200},
    ).to_dict()
    assert applied["ok"] is True
    assert owner._tracks[0].clips[0].source_out_ms == 800
    assert [clip.timeline_in_ms for clip in owner._tracks[0].clips] == [0, 800, 2300]
    assert owner._audio_tracks[0].clips[0].offset_ms == 800

    left = registry.execute(
        "clip.ripple_trim",
        {"track_id": 1, "clip_id": 11, "edge": "left", "delta_ms": 200},
    ).to_dict()
    assert left["ok"] is True
    assert owner._tracks[0].clips[1].timeline_in_ms == 800
    assert owner._tracks[0].clips[1].source_in_ms == 200
    assert owner._tracks[0].clips[1].timeline_out_ms == 1600
    assert owner._tracks[0].clips[2].timeline_in_ms == 2100


def test_ripple_trim_action_can_use_native_trim_plan(monkeypatch):
    from app.actions import build_default_action_registry
    from app.timeline_model import VideoClip, VideoTrack

    def _native_trim_plan(clips, **kwargs):
        assert len(clips) == 3
        assert kwargs["mode"] == "ripple_trim"
        assert kwargs["edge"] == "right"
        assert kwargs["delta_ms"] == 500
        selected = clips[kwargs["clip_index"]]
        assert selected["id"] == 11
        return {
            "backend": "rust_worker",
            "mode": "ripple_trim",
            "clip_id": 11,
            "edge": "right",
            "requested_delta_ms": 500,
            "ripple": True,
            "ripple_delta_ms": 500,
            "old": {
                "id": 11,
                "timeline_in_ms": 1000,
                "timeline_out_ms": 2000,
                "source_in_ms": 0,
                "source_out_ms": 1000,
            },
            "new": {
                "id": 11,
                "timeline_in_ms": 1000,
                "timeline_out_ms": 2500,
                "source_in_ms": 0,
                "source_out_ms": 1500,
            },
            "timeline_delta_ms": 0,
            "shifted_clips": [{"clip_id": 12, "timeline_in_ms": 3000}],
            "changed": True,
        }

    monkeypatch.setattr("app.native_worker.native_timeline_trim_plan", _native_trim_plan)
    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=11, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=0, source_out_ms=1000),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    registry = build_default_action_registry(owner)

    applied = registry.execute(
        "clip.ripple_trim",
        {"track_id": 1, "clip_id": 11, "edge": "right", "delta_ms": 500},
    ).to_dict()

    assert applied["ok"] is True
    assert applied["result"]["trim_backend"] == "rust_worker"
    assert owner._tracks[0].clips[1].source_out_ms == 1500
    assert owner._tracks[0].clips[2].timeline_in_ms == 3000


def test_precision_trim_action_supports_exact_values_deltas_ripple_and_dry_run():
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(
                    id=10,
                    source_duration_ms=5000,
                    timeline_in_ms=0,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=20,
                ),
                VideoClip(
                    id=11,
                    source_duration_ms=5000,
                    timeline_in_ms=1000,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=21,
                ),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [
        AudioTrack(
            id=2,
            clips=[
                AudioClip(id=20, duration_ms=500, offset_ms=0),
                AudioClip(id=21, duration_ms=1000, offset_ms=1000),
            ],
        ),
    ]
    registry = build_default_action_registry(owner)
    ids = {row["id"] for row in registry.specs()}

    assert "timeline.precision_trim" in ids

    dry = registry.execute(
        "timeline.precision_trim",
        {"track_id": 1, "clip_id": 10, "source_out_ms": 800, "ripple": True},
        dry_run=True,
    ).to_dict()
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["changed"] is False
    assert dry["result"]["new"]["source_out_ms"] == 800
    assert dry["result"]["shifted_clips"][0]["timeline_in_ms"] == 800
    assert dry["result"]["shifted_audio"][0]["offset_ms"] == 800
    assert owner._tracks[0].clips[0].source_out_ms == 1000
    assert owner._tracks[0].clips[1].timeline_in_ms == 1000
    assert owner._audio_tracks[0].clips[1].offset_ms == 1000

    applied = registry.execute(
        "timeline.precision_trim",
        {"track_id": 1, "clip_id": 10, "source_out_ms": 800, "ripple": True},
    ).to_dict()
    assert applied["ok"] is True
    assert owner._tracks[0].clips[0].source_out_ms == 800
    assert owner._tracks[0].clips[1].timeline_in_ms == 800
    assert owner._audio_tracks[0].clips[1].offset_ms == 800

    exact = registry.execute(
        "timeline.precision_trim",
        {"track_id": 1, "clip_id": 10, "timeline_in_ms": 100, "source_in_ms": 100, "source_out_ms": 800},
    ).to_dict()
    assert exact["ok"] is True
    assert owner._tracks[0].clips[0].timeline_in_ms == 100
    assert owner._tracks[0].clips[0].source_in_ms == 100
    assert owner._audio_tracks[0].clips[0].offset_ms == 100


def test_precision_trim_action_can_use_native_trim_plan(monkeypatch):
    from app.actions import build_default_action_registry
    from app.audio_tracks import AudioClip, AudioTrack
    from app.timeline_model import VideoClip, VideoTrack

    def _native_trim_plan(clips, **kwargs):
        assert len(clips) == 3
        assert kwargs["mode"] == "precision_trim"
        assert kwargs["source_out_ms"] == 700
        assert kwargs["ripple"] is True
        return {
            "backend": "rust_worker",
            "mode": "precision_trim",
            "clip_id": 10,
            "edge": "",
            "requested_delta_ms": 0,
            "ripple": True,
            "ripple_delta_ms": -300,
            "old": {
                "id": 10,
                "timeline_in_ms": 0,
                "timeline_out_ms": 1000,
                "source_in_ms": 0,
                "source_out_ms": 1000,
            },
            "new": {
                "id": 10,
                "timeline_in_ms": 0,
                "timeline_out_ms": 700,
                "source_in_ms": 0,
                "source_out_ms": 700,
            },
            "timeline_delta_ms": 0,
            "shifted_clips": [{"clip_id": 11, "timeline_in_ms": 700}, {"clip_id": 12, "timeline_in_ms": 2200}],
            "changed": True,
        }

    monkeypatch.setattr("app.native_worker.native_timeline_trim_plan", _native_trim_plan)
    owner = _ActionOwner()
    owner._tracks = [
        VideoTrack(
            id=1,
            clips=[
                VideoClip(id=10, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
                VideoClip(
                    id=11,
                    source_duration_ms=5000,
                    timeline_in_ms=1000,
                    source_in_ms=0,
                    source_out_ms=1000,
                    linked_audio_id=21,
                ),
                VideoClip(id=12, source_duration_ms=5000, timeline_in_ms=2500, source_in_ms=0, source_out_ms=1000),
            ],
        )
    ]
    owner._audio_tracks = [AudioTrack(id=2, clips=[AudioClip(id=21, duration_ms=1000, offset_ms=1000)])]
    registry = build_default_action_registry(owner)

    dry = registry.execute(
        "timeline.precision_trim",
        {"track_id": 1, "clip_id": 10, "source_out_ms": 700, "ripple": True},
        dry_run=True,
    ).to_dict()
    assert dry["ok"] is True
    assert dry["result"]["trim_backend"] == "rust_worker"
    assert dry["result"]["shifted_audio"][0]["offset_ms"] == 700
    assert owner._tracks[0].clips[0].source_out_ms == 1000

    applied = registry.execute(
        "timeline.precision_trim",
        {"track_id": 1, "clip_id": 10, "source_out_ms": 700, "ripple": True},
    ).to_dict()
    assert applied["ok"] is True
    assert owner._tracks[0].clips[0].source_out_ms == 700
    assert owner._tracks[0].clips[1].timeline_in_ms == 700
    assert owner._audio_tracks[0].clips[0].offset_ms == 700


def test_extended_audio_actions_and_track_reorder():
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)

    added = registry.execute("track.add", {"kind": "video", "track_id": 3}).to_dict()
    reordered = registry.execute("track.reorder", {"kind": "video", "track_id": 3, "index": 0}).to_dict()
    assert added["ok"] is True
    assert reordered["ok"] is True
    assert [track.id for track in owner._tracks] == [3, 1]

    split = registry.execute("audio.clip.split", {"track_id": 2, "clip_id": 20, "at_ms": 1500}).to_dict()
    right_clip_id = split["result"]["right_clip_id"]
    gain = registry.execute("audio.clip.set_gain", {"track_id": 2, "clip_id": right_clip_id, "gain": 0.6}).to_dict()
    mix = registry.execute("audio.track.set_mix", {"track_id": 2, "volume": 0.8, "pan": -0.25}).to_dict()
    volume = registry.execute("audio.track.set_volume", {"track_id": 2, "volume": 0.72}).to_dict()
    pan = registry.execute("audio.track.set_pan", {"track_id": 2, "pan": 0.35}).to_dict()
    muted = registry.execute("audio.track.mute", {"track_id": 2, "muted": True}).to_dict()
    solo = registry.execute("audio.track.solo", {"track_id": 2, "solo": True}).to_dict()
    track_type = registry.execute("audio.track.set_type", {"track_id": 2, "track_type": "dialogue"}).to_dict()
    insert = registry.execute("audio.track.insert.set", {"track_id": 2, "slot": "eq", "enabled": True}).to_dict()
    send = registry.execute("audio.track.send.set_level", {"track_id": 2, "send_id": "reverb", "level": 0.25}).to_dict()
    bus = registry.execute("audio.track.route_to_bus", {"track_id": 2, "bus_id": "dialogue"}).to_dict()
    automation = registry.execute(
        "audio.automation.write",
        {"track_id": 2, "parameter": "volume", "time_ms": 1500, "value": 0.7, "read": True, "write": True},
    ).to_dict()
    meter = registry.execute("audio.track.meter.state", {"track_id": 2}).to_dict()
    automation_state = registry.execute("audio.automation.state", {"track_id": 2}).to_dict()
    snapshot = registry.execute("audio.mixer.snapshot.save", {"snapshot_id": "mix_a", "name": "Mix A"}).to_dict()
    changed_volume = registry.execute("audio.track.set_volume", {"track_id": 2, "volume": 0.4}).to_dict()
    snapshot_compare = registry.execute("audio.mixer.snapshot.compare", {"snapshot_id": "mix_a"}).to_dict()
    snapshot_apply = registry.execute("audio.mixer.snapshot.apply", {"snapshot_id": "mix_a"}).to_dict()
    state = registry.execute("audio.mixer.state").to_dict()
    assert split["ok"] is True
    assert len(owner._audio_tracks[0].clips) == 2
    assert gain["result"]["gain"] == 0.6
    assert mix["result"]["new"]["volume"] == 0.8
    assert volume["result"]["new"]["volume"] == 0.72
    assert pan["result"]["new"]["pan"] == 0.35
    assert muted["result"]["new"]["muted"] is True
    assert solo["result"]["new"]["solo"] is True
    assert track_type["result"]["new"]["track_type"] == "dialogue"
    assert insert["ok"] is True
    assert send["result"]["new"]["reverb"] == 0.25
    assert bus["result"]["new"]["bus_id"] == "dialogue"
    assert automation["result"]["new"]["write"] is True
    assert automation_state["result"]["tracks"][0]["point_count"] == 1
    assert meter["result"]["schema"] == "tigerstudio.audio.meter.v1"
    assert snapshot["result"]["snapshot"]["id"] == "mix_a"
    assert changed_volume["result"]["new"]["volume"] == 0.4
    assert snapshot_compare["result"]["delta_count"] >= 1
    assert snapshot_apply["result"]["applied_count"] == 1
    assert owner._audio_tracks[0].pan == 0.35
    assert owner._audio_tracks[0].volume == 0.72
    assert owner._audio_tracks[0].track_type == "dialogue"
    assert owner._audio_tracks[0].insert_slots[0]["enabled"] is True
    assert owner._audio_tracks[0].sends["reverb"] == 0.25
    assert owner._audio_tracks[0].automation_write is True
    assert state["result"]["schema"] == "tigerstudio.audio.mixer.v1"
    assert state["result"]["tracks"][0]["muted"] is True
    assert state["result"]["tracks"][0]["solo"] is True
    assert state["result"]["tracks"][0]["track_type"] == "dialogue"
    assert state["result"]["tracks"][0]["automation"]["point_count"] == 1
    assert state["result"]["tracks"][0]["meter"]["clip_led"] is False
    assert state["result"]["snapshot_count"] == 1

    blocked_delete = registry.execute("audio.clip.delete", {"track_id": 2, "clip_id": right_clip_id}).to_dict()
    deleted = registry.execute(
        "audio.clip.delete",
        {"track_id": 2, "clip_id": right_clip_id},
        confirm_destructive=True,
    ).to_dict()
    assert blocked_delete["ok"] is False
    assert deleted["ok"] is True
    assert len(owner._audio_tracks[0].clips) == 1


def test_sound_editor_actions_drive_workbench_state():
    from app.actions import build_default_action_registry

    class _FakeJog:
        def __init__(self) -> None:
            self.clip = None
            self.position_ms = 0
            self.playing = False
            self.visible = True

        def set_clip(self, clip) -> None:
            self.clip = clip

        def _set_position_ms(self, value: int, *, emit: bool = True) -> None:
            self.position_ms = int(value)

        def _set_playing(self, playing: bool) -> None:
            self.playing = bool(playing)

        def isVisible(self) -> bool:
            return self.visible

    class _FakeSoundEditorPanel:
        def __init__(self) -> None:
            self._clip = None
            self._advanced_expanded = False
            self._jog_shuttle = _FakeJog()

        def _set_advanced_lab_expanded(self, expanded: bool) -> None:
            self._advanced_expanded = bool(expanded)

        def isVisible(self) -> bool:
            return True

    class _FakeWorkbenchPanel:
        def __init__(self, sound_panel) -> None:
            self._sound_editor_panel = sound_panel
            self.inspector_tab = ""
            self.target = None

        def set_audio_clip(self, track, clip) -> None:
            self.target = (track, clip)
            self._sound_editor_panel._clip = clip

        def _set_inspector_tab(self, tab: str) -> None:
            self.inspector_tab = str(tab)

    owner = _ActionOwner()
    sound_panel = _FakeSoundEditorPanel()
    owner._workbench_panel = _FakeWorkbenchPanel(sound_panel)
    owner._advanced_sound_labs = []
    registry = build_default_action_registry(owner)

    initial = registry.execute(
        "audio.sound_editor.jog_shuttle.state",
        {"track_id": 2, "clip_id": 20},
    ).to_dict()
    assert initial["ok"] is True
    assert initial["result"]["reference_design"] == "05"
    assert initial["result"]["duration_ms"] == 3000

    jog = registry.execute(
        "audio.sound_editor.jog_shuttle.set",
        {"track_id": 2, "clip_id": 20, "position_ms": 1200, "playing": True},
    ).to_dict()
    clip = owner._audio_tracks[0].clips[0]
    assert jog["ok"] is True
    assert jog["result"]["position_ms"] == 1200
    assert jog["result"]["playing"] is True
    assert jog["result"]["ui_updated"] is True
    assert getattr(clip, "_se_jog_ms") == 1200
    assert getattr(clip, "_se_jog_playing") is True
    assert sound_panel._jog_shuttle.position_ms == 1200
    assert sound_panel._jog_shuttle.playing is True
    assert owner._workbench_panel.inspector_tab == "audio"

    expanded = registry.execute(
        "audio.sound_editor.advanced_lab.set",
        {"track_id": 2, "clip_id": 20, "expanded": True},
    ).to_dict()
    assert expanded["ok"] is True
    assert expanded["result"]["expanded"] is True
    assert expanded["result"]["inline"] is True
    assert expanded["result"]["opened_legacy_window"] is False
    assert sound_panel._advanced_expanded is True
    assert sound_panel._jog_shuttle.visible is True

    collapsed = registry.execute(
        "audio.sound_editor.advanced_lab.set",
        {"track_id": 2, "clip_id": 20, "expanded": False},
    ).to_dict()
    assert collapsed["ok"] is True
    assert collapsed["result"]["expanded"] is False
    assert sound_panel._advanced_expanded is False
    assert sound_panel._jog_shuttle.visible is True


def test_sound_editor_full_feature_actions_apply_effects_and_reports():
    import numpy as np
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    clip = owner._audio_tracks[0].clips[0]
    x = np.linspace(-0.25, 0.25, 256, dtype=np.float32)
    clip.waveform = np.vstack([x, x * 0.8]).astype(np.float32)

    applied = registry.execute(
        "audio.sound_editor.apply_effects",
        {
            "track_id": 2,
            "clip_id": 20,
            "basic": {
                "gain_db": 3,
                "pan": -25,
                "fade_in_ms": 250,
                "speed": 1.12,
                "pitch": -1.5,
                "reverse": True,
            },
            "effects": {
                "eq": {"enabled": True, "mid": {"freq": 1800, "gain": 3.5, "q": 1.4}},
                "comp": {"enabled": True, "attack_ms": 7.5, "release_ms": 180, "knee_db": 3.0},
                "gate": {"enabled": True, "reduction": 62},
                "reverb": {"enabled": True, "type": "Plate", "size": 50, "decay_s": 2.1, "damping": 42},
                "delay": {"enabled": True, "time_ms": 180, "feedback": 24},
                "time_stretch": {"enabled": True, "ratio": 1.08, "algorithm": "rubberband"},
            },
        },
    ).to_dict()

    assert applied["ok"] is True
    assert clip.fade_in_ms == 250
    assert getattr(clip, "_se_speed") == 1.12
    assert getattr(clip, "_se_pitch") == -1.5
    assert getattr(clip, "_se_reverse") is True
    assert getattr(clip, "_se_pan") == -0.25
    assert owner._audio_tracks[0].pan == -0.25
    assert clip.effects["eq"]["mid"]["freq"] == 1800
    assert clip.effects["eq"]["mid"]["q"] == 1.4
    assert clip.effects["comp"]["attack_ms"] == 7.5
    assert clip.effects["gate"]["reduction"] == 62
    assert clip.effects["reverb"]["type"] == "Plate"
    assert clip.effects["delay"]["time_ms"] == 180
    assert clip.effects["time_stretch"]["algorithm"] == "rubberband"

    ai = registry.execute(
        "audio.sound_editor.apply_ai_preset",
        {"track_id": 2, "clip_id": 20, "preset": "ACE-Step", "focus_workbench": False},
    ).to_dict()
    assert ai["ok"] is True
    assert clip.effects["ai_master"]["enabled"] is True
    assert clip.effects["ai_master"]["preset"] == "ACE-Step"
    assert clip.effects["ai_master"]["width"] == 140.0

    report = registry.execute(
        "audio.loudness_report",
        {"track_id": 2, "clip_id": 20, "target_lufs": -16, "true_peak_limit_db": -1},
    ).to_dict()
    assert report["ok"] is True
    assert report["result"]["available"] is True
    assert report["result"]["target_lufs"] == -16.0

    export_plan = registry.execute(
        "audio.export_clip",
        {"track_id": 2, "clip_id": 20, "format": "wav"},
    ).to_dict()
    assert export_plan["ok"] is True
    assert export_plan["result"]["exported"] is False
    assert "[out]" in export_plan["result"]["filter_graph"]

    stems_preview = registry.execute(
        "audio.separate_stems",
        {"track_id": 2, "clip_id": 20},
        dry_run=True,
    ).to_dict()
    assert stems_preview["ok"] is True
    assert stems_preview["dry_run"] is True


def test_capture_actions_write_screenshot_and_gif(tmp_path):
    from app.actions import build_default_action_registry

    owner = _ActionOwner()
    registry = build_default_action_registry(owner)
    screenshot_path = tmp_path / "action.png"
    gif_path = tmp_path / "action.gif"

    screenshot = registry.execute("capture.screenshot", {"path": str(screenshot_path)}).to_dict()
    gif = registry.execute("capture.gif", {"path": str(gif_path), "duration_ms": 1, "fps": 1}).to_dict()

    assert screenshot["ok"] is True
    assert screenshot_path.exists()
    assert gif["ok"] is True
    assert gif["result"]["backend"] == "qt_grab_fallback"
    assert gif["result"]["frames"] == 1
    assert gif_path.exists()


def test_review_scenario_action_runs_report_without_editor_owner(tmp_path):
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(None)
    report_path = tmp_path / "review" / "report.json"
    result = registry.execute(
        "review.scenario.run",
        {
            "scenario": "summary",
            "params": {
                "project_root": str(tmp_path),
                "out_dir": str(tmp_path / "review"),
                "report_path": str(report_path),
                "sample_manifest": str(tmp_path / "missing_manifest.json"),
                "write_html": False,
                "write_ppt": False,
            },
        },
    ).to_dict()

    assert result["ok"] is True
    assert result["result"]["executed"] is True
    assert result["result"]["deck_mode"] == "summary"
    assert report_path.exists()
