from __future__ import annotations

import os
from pathlib import Path


class _FakePlayer:
    def __init__(self) -> None:
        self.tracks = []
        self.refreshed = 0

    def position(self) -> int:
        return 1500

    def duration(self) -> int:
        return 9000

    def set_mmd_tracks(self, tracks) -> None:
        self.tracks = list(tracks or [])

    def refresh_current_frame(self) -> None:
        self.refreshed += 1


class _FakePool:
    def __init__(self, items=None) -> None:
        self._items = list(items or [])
        self.added = []

    def items(self):
        return list(self._items)

    def add_path(self, path) -> bool:
        self.added.append(str(Path(path).resolve()))
        return True


class _FakeWorkbench:
    def __init__(self) -> None:
        self.shown_track = None
        self._target = None

    def set_mmd_track(self, track) -> None:
        self.shown_track = track
        self._target = ("mmd", track)

    def current_target(self):
        return self._target


def _editor(pool_items=None):
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    editor._mmd_tracks = []
    editor._next_mmd_id = 1
    editor._media_pool = _FakePool(pool_items)
    editor._player = _FakePlayer()
    editor._refresh_player_tracks = lambda: None
    editor._register_change = lambda _label: None
    editor._flash_messages = []
    editor._flash_status = lambda text: editor._flash_messages.append(text)
    return editor


def test_video_editor_adds_mmd_track_and_auto_pairs_single_pool_motion(tmp_path) -> None:
    from app.video_editor_window import VideoEditorWindow

    model = tmp_path / "hero.pmx"
    motion = tmp_path / "dance.vmd"
    model.write_bytes(b"pmx")
    motion.write_bytes(b"vmd")
    editor = _editor(pool_items=[str(motion)])

    track = VideoEditorWindow._add_mmd_asset_to_timeline(editor, model)

    assert track is not None
    assert editor._mmd_tracks == [track]
    assert editor._player.tracks == [track]
    assert track["id"] == "mmd_001"
    assert track["model_path"] == str(model.resolve())
    assert track["motion_path"] == str(motion.resolve())
    assert track["start_ms"] == 1500
    assert editor._next_mmd_id == 2
    assert editor._player.refreshed == 1


def test_video_editor_mmd_track_shows_workbench_and_updates_physics(tmp_path) -> None:
    from app.video_editor_window import VideoEditorWindow

    model = tmp_path / "hero.pmx"
    model.write_bytes(b"pmx")
    editor = _editor()
    editor._workbench_panel = _FakeWorkbench()
    track = VideoEditorWindow._add_mmd_asset_to_timeline(editor, model, start_ms=0)

    assert editor._workbench_panel.shown_track is track
    assert editor._selected_mmd_track_id == "mmd_001"

    VideoEditorWindow._on_workbench_mmd_rotation_hint_changed(editor, 0.22)
    VideoEditorWindow._on_workbench_mmd_spring_response_changed(editor, 0.84)

    assert track["playback"]["physics_rotation_hint_scale"] == 0.22
    assert track["playback"]["physics_spring_response"] == 0.84
    assert editor._player.tracks == [track]
    assert editor._player.refreshed == 3


def test_workbench_mmd_track_surface_exposes_physics_sliders() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.workbench_panel import WorkbenchPanel

    QApplication.instance() or QApplication([])
    panel = WorkbenchPanel()
    track = {
        "id": "mmd_001",
        "model_path": "E:/models/flashy_heroine.pmx",
        "motion_path": "E:/motions/dance.vmd",
        "start_ms": 1200,
        "end_ms": 6200,
        "playback": {
            "enable_physics": True,
            "gpu_skinning": True,
            "physics_rotation_hint_scale": 0.12,
            "physics_spring_response": 0.60,
        },
    }
    seen: list[tuple[str, float]] = []
    panel.mmd_physics_rotation_hint_scale_changed.connect(lambda v: seen.append(("cloth", round(float(v), 2))))
    panel.mmd_physics_spring_response_changed.connect(lambda v: seen.append(("follow", round(float(v), 2))))

    panel.set_mmd_track(track)

    assert panel.current_target() == ("mmd", track)
    assert not panel._row_mmd_cloth_hair.isHidden()
    assert not panel._row_mmd_follow.isHidden()
    assert panel._row_mmd_cloth_hair._readout.text() == "0.12"
    assert panel._row_mmd_follow._readout.text() == "0.60"

    panel._row_mmd_cloth_hair._slider.setValue(18)
    panel._row_mmd_follow._slider.setValue(72)

    assert seen[-2:] == [("cloth", 0.18), ("follow", 0.72)]
    panel.deleteLater()


def test_mmd_actor_lane_row_tracks_range_and_media_mime(tmp_path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QMimeData
    from PySide6.QtWidgets import QApplication

    from app.mmd.actor_lane_row import MMDActorLaneRow, MMD_MODEL_MIME

    QApplication.instance() or QApplication([])
    model = tmp_path / "hero.pmx"
    motion = tmp_path / "dance.vmd"
    model.write_bytes(b"pmx")
    motion.write_bytes(b"vmd")
    track = {
        "id": "mmd_001",
        "model_path": str(model),
        "motion_path": "",
        "start_ms": 1000,
        "end_ms": 5000,
    }
    row = MMDActorLaneRow(track)
    row.set_px_per_sec(80.0)
    row.set_lane_index(2)
    selected: list[str] = []
    duplicated: list[str] = []
    deleted: list[str] = []
    toggled: list[bool] = []
    row.track_selected.connect(lambda t: selected.append(str(t.get("id") or "")))
    row.track_duplicate_requested.connect(lambda t: duplicated.append(str(t.get("id") or "")))
    row.track_delete_requested.connect(lambda t: deleted.append(str(t.get("id") or "")))
    row.physics_toggle_requested.connect(lambda _t, enabled: toggled.append(bool(enabled)))

    row._set_range(250, 1750)
    row.set_selected(True)

    assert track["start_ms"] == 250
    assert track["end_ms"] == 1750
    assert track["duration_ms"] == 1500
    assert row._preferred_width() > 0

    mime = QMimeData()
    mime.setData(MMD_MODEL_MIME, f"{model}\n{motion}".encode("utf-8"))
    paths = MMDActorLaneRow._paths_from_mime(mime)

    assert paths == [model, motion]
    assert row._drop_label_for_mime(mime) == "ACTOR+VMD"
    row.deleteLater()


def test_video_editor_motion_drop_assigns_existing_mmd_track(tmp_path) -> None:
    from app.video_editor_window import VideoEditorWindow

    model = tmp_path / "hero.pmx"
    motion = tmp_path / "dance.vmd"
    model.write_bytes(b"pmx")
    motion.write_bytes(b"vmd")
    editor = _editor()
    track = VideoEditorWindow._add_mmd_asset_to_timeline(editor, model, start_ms=0)

    assigned = VideoEditorWindow._add_mmd_asset_to_timeline(editor, motion, start_ms=2000)

    assert assigned is track
    assert track["motion_path"] == str(motion.resolve())
    assert editor._player.tracks == [track]
    assert editor._player.refreshed == 2


def test_mmd_action_namespace_adds_actor_lists_motion_and_applies_settings(tmp_path) -> None:
    from app.actions import build_default_action_registry

    model = tmp_path / "hero.pmx"
    motion = tmp_path / "dance.vmd"
    model.write_bytes(b"pmx")
    motion.write_bytes(b"vmd")
    editor = _editor()
    registry = build_default_action_registry(editor)

    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "mmd.summary",
        "mmd.diagnostics",
        "mmd.actor.add",
        "mmd.actor.delete",
        "mmd.actor.duplicate",
        "mmd.track.move",
        "mmd.track.trim",
        "mmd.motion.list",
        "mmd.motion.add",
        "mmd.motion.apply",
        "mmd.settings.apply",
        "mmd.editor.open",
    } <= action_ids

    added = registry.execute("mmd.actor.add", {"path": str(model), "start_ms": 250}).to_dict()
    assert added["ok"] is True
    track_id = added["result"]["track_id"]
    track = editor._mmd_tracks[0]

    listed = registry.execute("mmd.motion.list", {"track_id": track_id}).to_dict()
    assert listed["ok"] is True
    assert str(motion.resolve()) in {row["path"] for row in listed["result"]["motions"]}

    added_motion = registry.execute("mmd.motion.add", {"track_id": track_id, "motion_path": str(motion)}).to_dict()
    assert added_motion["ok"] is True
    assert str(motion.resolve()) in {row["path"] for row in added_motion["result"]["motions"]}

    applied_motion = registry.execute("mmd.motion.apply", {"track_id": track_id, "motion_path": str(motion)}).to_dict()
    assert applied_motion["ok"] is True
    assert track["motion_path"] == str(motion.resolve())

    moved = registry.execute("mmd.track.move", {"track_id": track_id, "start_ms": 1000}).to_dict()
    assert moved["ok"] is True
    assert track["start_ms"] == 1000
    duration_after_move = track["end_ms"] - track["start_ms"]

    trimmed = registry.execute("mmd.track.trim", {"track_id": track_id, "duration_ms": 2200}).to_dict()
    assert trimmed["ok"] is True
    assert track["duration_ms"] == 2200
    assert track["end_ms"] - track["start_ms"] == 2200
    assert duration_after_move >= 1000

    duplicated = registry.execute("mmd.actor.duplicate", {"track_id": track_id}).to_dict()
    assert duplicated["ok"] is True
    duplicate_id = duplicated["result"]["track_id"]
    assert duplicate_id != track_id
    assert len(editor._mmd_tracks) == 2

    settings = registry.execute(
        "mmd.settings.apply",
        {
            "track_id": track_id,
            "playback": {
                "physics_rotation_hint_scale": 0.18,
                "physics_spring_response": 0.72,
            },
            "render": {
                "lighting_preset": "night_stage",
                "bloom_strength": 0.55,
            },
            "material": {
                "skin_warmth": 1.25,
                "hair_highlight": 0.8,
            },
        },
    ).to_dict()
    assert settings["ok"] is True
    assert track["playback"]["physics_rotation_hint_scale"] == 0.18
    assert track["playback"]["physics_spring_response"] == 0.72
    assert track["render"]["lighting_preset"] == "night_stage"
    assert track["render"]["bloom_strength"] == 0.55
    assert track["render"]["material"]["skin_warmth"] == 1.25
    assert track["render"]["material"]["hair_highlight"] == 0.8

    diagnostics = registry.execute(
        "mmd.diagnostics",
        {"track_id": track_id, "include_materials": False},
    ).to_dict()
    assert diagnostics["ok"] is True
    assert diagnostics["changed"] is False
    assert diagnostics["result"]["track_count"] == 1
    assert diagnostics["result"]["tracks"][0]["id"] == track_id

    deleted = registry.execute(
        "mmd.actor.delete",
        {"track_id": duplicate_id},
        confirm_destructive=True,
    ).to_dict()
    assert deleted["ok"] is True
    assert [row["id"] for row in editor._mmd_tracks] == [track_id]
    assert editor._player.tracks == [track]


def test_mmd_qa_actions_run_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd
    import tools.mmd_qa_visual_corpus as visual_corpus

    def fake_text_run(manifest):
        return {
            "ok": True,
            "manifest": str(manifest),
            "run_count": 1,
            "entry_count": 1,
            "blocked_count": 0,
            "entries": [
                {
                    "id": "tiny",
                    "status": "ready",
                    "ok": True,
                    "report": {
                        "risk_codes": ["mmd_lightweight_physics_backend"],
                        "feature_flags": ["vmd_interpolation_curves"],
                    },
                }
            ],
            "blocked_entries": [],
        }

    def fake_visual_run(manifest, out_dir, *, width, height, use_gpu_skinning):
        return {
            "ok": True,
            "manifest": str(manifest),
            "out_dir": str(out_dir),
            "contact_sheet": str(tmp_path / "sheet.png"),
            "report": str(tmp_path / "report.json"),
            "run_count": 1,
            "entry_count": 1,
            "blocked_count": 0,
            "width": width,
            "height": height,
            "gpu_skinning_requested": use_gpu_skinning,
            "results": [
                {
                    "id": "tiny_visual",
                    "status": "ready",
                    "ok": True,
                    "screenshot": str(tmp_path / "tiny.png"),
                    "visual_metrics": {"alpha_coverage": 0.12},
                }
            ],
            "blocked_entries": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_qa_manifest", fake_text_run)
    monkeypatch.setattr(visual_corpus, "run_visual_corpus", fake_visual_run)

    registry = build_default_action_registry(None)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "mmd.qa.run",
        "mmd.qa.visual_run",
        "mmd.qa.composite_run",
        "mmd.qa.timeline_run",
        "mmd.qa.segment_run",
        "mmd.qa.render_queue_run",
        "mmd.qa.render_queue_export_run",
        "mmd.qa.long_project_run",
        "mmd.qa.workflow_run",
    } <= action_ids

    text = registry.execute("mmd.qa.run", {"manifest": "manifest.json"}).to_dict()
    assert text["ok"] is True
    assert text["changed"] is False
    assert text["result"]["run_count"] == 1
    assert text["result"]["entries"][0]["risk_codes"] == ["mmd_lightweight_physics_backend"]

    visual = registry.execute(
        "mmd.qa.visual_run",
        {
            "manifest": "manifest.json",
            "out_dir": str(tmp_path),
            "width": 320,
            "height": 180,
        },
    ).to_dict()
    assert visual["ok"] is True
    assert visual["changed"] is False
    assert visual["result"]["contact_sheet"].endswith("sheet.png")
    assert visual["result"]["gpu_skinning_requested"] is True
    assert visual["result"]["entries"][0]["visual_metrics"]["alpha_coverage"] == 0.12


def test_mmd_composite_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_composite_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        assert kwargs["width"] == 320
        assert kwargs["height"] == 180
        assert kwargs["duration_ms"] == 1000
        assert kwargs["fps"] == 12
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_editor_composite_qa.json"),
            "outputs": {
                "preview_composite": str(tmp_path / "preview.png"),
                "export_frame": str(tmp_path / "export_frame.png"),
            },
            "summary": {
                "alpha_coverage": 0.07,
                "export_inside_mean_abs_diff": 42.0,
                "export_outside_mean_abs_diff": 1.8,
            },
            "checks": {"mmd_export_ok": True},
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_editor_composite_qa", fake_composite_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.composite_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["entry_id"] == "cantarella_wavefile_cloth_motion"
    assert result["result"]["summary"]["alpha_coverage"] == 0.07
    assert result["result"]["outputs"]["export_frame"].endswith("export_frame.png")
    assert result["result"]["raw"]["checks"]["mmd_export_ok"] is True


def test_mmd_timeline_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_timeline_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        assert kwargs["width"] == 360
        assert kwargs["height"] == 202
        assert kwargs["duration_ms"] == 2200
        assert kwargs["fps"] == 12
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_timeline_qa.json"),
            "outputs": {
                "out_dir": str(tmp_path),
                "export_video": str(tmp_path / "mmd_timeline_export.mp4"),
            },
            "summary": {
                "active_counts": [0, 1, 2, 1, 0],
                "sample_count": 5,
                "max_active_export_inside_diff": 40.0,
                "max_inactive_export_mean_diff": 1.4,
            },
            "checks": {"all_sample_timings_ok": True},
            "samples": [
                {
                    "ok": True,
                    "output_ms": 950,
                    "project_ms": 1050,
                    "expected_active_track_ids": ["mmd_timeline_a", "mmd_timeline_b"],
                    "render_item_track_ids": ["mmd_timeline_a", "mmd_timeline_b"],
                    "export_delta": {"inside_mean_abs_diff": 40.0},
                    "preview_frame": str(tmp_path / "preview.png"),
                    "export_frame": str(tmp_path / "export.png"),
                }
            ],
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_timeline_qa", fake_timeline_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.timeline_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["active_counts"] == [0, 1, 2, 1, 0]
    assert result["result"]["samples"][0]["expected_active_track_ids"] == ["mmd_timeline_a", "mmd_timeline_b"]
    assert result["result"]["raw"]["checks"]["all_sample_timings_ok"] is True


def test_mmd_segment_timing_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_segment_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        assert kwargs["width"] == 360
        assert kwargs["height"] == 202
        assert kwargs["duration_ms"] == 3000
        assert kwargs["fps"] == 12
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_segment_timing_qa.json"),
            "outputs": {
                "out_dir": str(tmp_path),
                "export_video": str(tmp_path / "mmd_segment_export.mp4"),
            },
            "summary": {
                "active_counts": [0, 1, 0, 1, 1, 0],
                "project_ms_samples": [100, 350, 800, 1700, 2040, 2300],
                "sample_count": 6,
                "gap_track_rendered": False,
                "max_active_export_inside_diff": 41.0,
                "max_inactive_export_mean_diff": 1.5,
            },
            "checks": {
                "segments_include_trim_gap_and_speed": True,
                "gap_only_track_not_rendered": True,
                "all_segment_samples_ok": True,
            },
            "samples": [
                {
                    "ok": True,
                    "output_ms": 1000,
                    "project_ms": 1700,
                    "expected_active_track_ids": ["mmd_segment_b"],
                    "render_item_track_ids": ["mmd_segment_b"],
                    "export_delta": {"inside_mean_abs_diff": 41.0},
                    "preview_frame": str(tmp_path / "preview.png"),
                    "export_frame": str(tmp_path / "export.png"),
                }
            ],
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_segment_timing_qa", fake_segment_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.segment_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["active_counts"] == [0, 1, 0, 1, 1, 0]
    assert result["result"]["summary"]["project_ms_samples"] == [100, 350, 800, 1700, 2040, 2300]
    assert result["result"]["checks"]["gap_only_track_not_rendered"] is True
    assert result["result"]["samples"][0]["expected_active_track_ids"] == ["mmd_segment_b"]
    assert result["result"]["raw"]["checks"]["segments_include_trim_gap_and_speed"] is True


def test_mmd_render_queue_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_render_queue_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_render_queue_qa.json"),
            "outputs": {"out_dir": str(tmp_path)},
            "summary": {
                "queued_jobs": 1,
                "pre_render_calls": 1,
                "thread_inits": 1,
                "segments": [(500, 900, 1.0), (900, 1500, 2.0)],
                "progress_values": [28],
            },
            "checks": {
                "pre_render_called_for_mmd_tracks": True,
                "thread_receives_mmd_pre_rendered_overlay": True,
            },
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_render_queue_wiring_qa", fake_render_queue_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.render_queue_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["queued_jobs"] == 1
    assert result["result"]["summary"]["progress_values"] == [28]
    assert result["result"]["checks"]["thread_receives_mmd_pre_rendered_overlay"] is True
    assert result["result"]["raw"]["summary"]["pre_render_calls"] == 1


def test_mmd_render_queue_export_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_render_queue_export_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        assert kwargs["width"] == 640
        assert kwargs["height"] == 360
        assert kwargs["duration_ms"] == 2400
        assert kwargs["fps"] == 24
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_render_queue_export_qa.json"),
            "outputs": {
                "out_dir": str(tmp_path),
                "export_video": str(tmp_path / "mmd_render_queue_export.mp4"),
                "export_frame": str(tmp_path / "mmd_render_queue_export_frame.png"),
            },
            "summary": {
                "queued_jobs": 1,
                "pre_render_count": 1,
                "pre_render_sizes": [8192],
                "alpha_coverage": 0.05,
                "export_inside_mean_abs_diff": 42.0,
                "export_outside_mean_abs_diff": 1.9,
            },
            "checks": {
                "mmd_prerender_alpha_mov_created": True,
                "export_composite_changes_mmd_region": True,
            },
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_render_queue_export_qa", fake_render_queue_export_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.render_queue_export_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["pre_render_count"] == 1
    assert result["result"]["summary"]["export_inside_mean_abs_diff"] == 42.0
    assert result["result"]["checks"]["export_composite_changes_mmd_region"] is True
    assert result["result"]["raw"]["summary"]["pre_render_sizes"] == [8192]


def test_mmd_long_project_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.actions.editor_adapter_mmd as adapter_mmd

    def fake_long_project_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        assert kwargs["width"] == 480
        assert kwargs["height"] == 270
        assert kwargs["duration_ms"] == 10000
        assert kwargs["fps"] == 12
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_long_project_export_qa.json"),
            "outputs": {
                "out_dir": str(tmp_path),
                "export_video": str(tmp_path / "mmd_long_project_export.mp4"),
            },
            "summary": {
                "queued_jobs": 1,
                "mmd_track_count": 2,
                "pre_render_count": 1,
                "sample_project_ms": [1100, 4750, 8850],
                "max_export_inside_mean_abs_diff": 43.0,
                "max_export_outside_mean_abs_diff": 1.8,
            },
            "checks": {
                "long_project_duration": True,
                "trimmed_speed_segments_preserved": True,
                "all_long_samples_ok": True,
            },
            "samples": [
                {
                    "ok": True,
                    "output_ms": 600,
                    "project_ms": 1100,
                    "expected_active_track_ids": ["mmd_long_project_001"],
                    "render_item_track_ids": ["mmd_long_project_001"],
                    "export_delta": {"inside_mean_abs_diff": 43.0},
                    "baseline_frame": str(tmp_path / "baseline.png"),
                    "export_frame": str(tmp_path / "export.png"),
                }
            ],
            "failures": [],
        }

    monkeypatch.setattr(adapter_mmd, "run_mmd_long_project_export_qa", fake_long_project_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.long_project_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["mmd_track_count"] == 2
    assert result["result"]["checks"]["trimmed_speed_segments_preserved"] is True
    assert result["result"]["samples"][0]["expected_active_track_ids"] == ["mmd_long_project_001"]
    assert result["result"]["raw"]["summary"]["sample_project_ms"] == [1100, 4750, 8850]


def test_mmd_workflow_qa_action_runs_without_editor_owner(monkeypatch, tmp_path) -> None:
    from app.actions import build_default_action_registry
    import app.mmd.workflow_qa as workflow_qa

    def fake_workflow_run(**kwargs):
        assert kwargs["entry_id"] == "cantarella_wavefile_cloth_motion"
        return {
            "ok": True,
            "entry_id": kwargs["entry_id"],
            "manifest": str(kwargs["manifest"]),
            "report": str(tmp_path / "mmd_workflow_qa.json"),
            "outputs": {"out_dir": str(tmp_path)},
            "summary": {
                "checks": 8,
                "passing": 8,
                "failing": 0,
                "action_count": 13,
                "final_track_count": 1,
            },
            "checks": {"motion_library_add_visible": True},
            "failures": [],
        }

    monkeypatch.setattr(workflow_qa, "run_mmd_workflow_qa", fake_workflow_run)

    registry = build_default_action_registry(None)
    result = registry.execute("mmd.qa.workflow_run", {"include_reports": True}).to_dict()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["summary"]["action_count"] == 13
    assert result["result"]["checks"]["motion_library_add_visible"] is True
    assert result["result"]["raw"]["summary"]["final_track_count"] == 1
