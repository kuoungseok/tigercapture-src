from types import SimpleNamespace

import numpy as np

from app.mmd.schema import (
    is_supported_model_path,
    normalize_mmd_track,
    normalize_mmd_tracks,
    track_active_at,
    track_schema_diagnostics,
)
from app.project_player import ProjectPlayer


def test_normalize_mmd_track_clamps_view_render_and_playback() -> None:
    track = normalize_mmd_track(
        {
            "id": "hero",
            "asset_path": "model.pmx",
            "vmd_path": "dance.vmd",
            "start_ms": -25,
            "duration_ms": 2400,
            "view": {"pitch": -200, "zoom": 20, "offset_y": -8},
            "render": {
                "mode": "marmoset",
                "bloom_strength": 9,
                "lighting": {"key_intensity": "1.4"},
                "material": {"skin_warmth": 3.0, "hair_highlight": -1.0, "eye_highlight": 1.4},
            },
            "playback": {
                "loop": "yes",
                "enable_ik": "true",
                "gpu_skinning": "off",
                "gpu_morph_slots": 12,
                "physics_update_interval_frames": 99,
                "physics_smoothing_response": 2.5,
                "physics_rotation_hint_scale": 9,
                "physics_spring_response": 0.01,
                "foot_ik_reach_limit": 0.1,
            },
        }
    )

    assert track["type"] == "mmd_model"
    assert track["model_path"] == "model.pmx"
    assert track["motion_path"] == "dance.vmd"
    assert track["start_ms"] == 0
    assert track["end_ms"] == 2400
    assert track["view"]["pitch"] == -80.0
    assert track["view"]["zoom"] == 2.2
    assert track["view"]["offset_y"] == -2.0
    assert track["render"]["mode"] == "toon"
    assert track["render"]["bloom_strength"] == 2.0
    assert track["render"]["lighting"]["key_intensity"] == 1.4
    assert track["render"]["material"]["skin_warmth"] == 2.0
    assert track["render"]["material"]["hair_highlight"] == 0.0
    assert track["render"]["material"]["eye_highlight"] == 1.4
    assert track["playback"]["loop"] is True
    assert track["playback"]["enable_ik"] is True
    assert track["playback"]["gpu_skinning"] is False
    assert track["playback"]["gpu_morph_slots"] == 2
    assert track["playback"]["physics_backend"] == "auto"
    assert track["playback"]["physics_update_interval_frames"] == 6.0
    assert track["playback"]["physics_smoothing_response"] == 1.0
    assert track["playback"]["physics_rotation_hint_scale"] == 0.30
    assert track["playback"]["physics_spring_response"] == 0.15
    assert track["playback"]["foot_ik_reach_limit"] == 0.7


def test_mmd_track_diagnostics_and_active_range() -> None:
    tracks = normalize_mmd_tracks(
        [
            {"id": "missing"},
            {"id": "bad_model", "model_path": "mesh.obj", "motion_path": "walk.bvh"},
            {"id": "ok", "model_path": "miku.pmd", "motion_path": "dance.vmd", "start_ms": 100, "end_ms": 200},
        ]
    )
    diag = track_schema_diagnostics(tracks)

    assert diag["track_count"] == 3
    assert diag["missing_model_track_ids"] == ["missing"]
    assert diag["unsupported_model_paths"] == ["mesh.obj"]
    assert diag["unsupported_motion_paths"] == ["walk.bvh"]
    assert track_active_at(tracks[2], 100)
    assert not track_active_at(tracks[2], 200)


def test_mmd_schema_accepts_aplaybox_pbx_json_models() -> None:
    assert is_supported_model_path("Cantarella.pbx.json")
    assert not is_supported_model_path("plain_model.json")


def test_create_preview_mmd_track_pairs_model_and_motion(tmp_path) -> None:
    from app.mmd.project_tracks import create_preview_mmd_track, split_mmd_paths

    model = tmp_path / "hero.pmx"
    motion = tmp_path / "dance.vmd"
    model.write_bytes(b"pmx")
    motion.write_bytes(b"vmd")

    models, motions = split_mmd_paths([motion, model])
    track = create_preview_mmd_track(
        model,
        track_id="mmd_042",
        start_ms=1200,
        duration_ms=3400,
        motion_path=motion,
    )

    assert models == [model.resolve()]
    assert motions == [motion.resolve()]
    assert track["id"] == "mmd_042"
    assert track["model_path"] == str(model.resolve())
    assert track["motion_path"] == str(motion.resolve())
    assert track["start_ms"] == 1200
    assert track["end_ms"] == 4600
    assert track["render"]["mode"] == "toon"
    assert track["playback"]["enable_ik"] is True
    assert track["playback"]["gpu_skinning"] is True
    assert track["playback"]["gpu_morph_slots"] == 2
    assert track["playback"]["physics_update_interval_frames"] == 2.0
    assert track["playback"]["physics_smoothing_response"] == 0.88
    assert track["playback"]["physics_rotation_hint_scale"] == 0.12
    assert track["playback"]["physics_spring_response"] == 0.60


def test_project_player_passes_mmd_items_as_gpu_meta(monkeypatch) -> None:
    player = ProjectPlayer()
    try:
        player.set_mmd_tracks([{"id": "mmd_1", "model_path": "hero.pmx", "start_ms": 0, "end_ms": 1000}])
        monkeypatch.setattr(player, "_mmd_overlay_items", lambda pos_ms, animate=True: [{"track_id": "mmd_1"}])

        rgb = np.zeros((8, 8, 3), dtype=np.uint8)
        out, meta = player._apply_or_defer_mmd_overlay(rgb, 120, True)

        assert out is rgb
        assert meta == {"mmd_items": [{"track_id": "mmd_1"}]}
    finally:
        player.release()


def test_video_exporter_tracks_mmd_export_as_pending_offscreen_renderer(tmp_path) -> None:
    from app.video_exporter import VideoExportThread

    exporter = VideoExportThread(
        source_path=tmp_path / "in.mp4",
        out_path=tmp_path / "out.mp4",
        segments=[(0, 1000, 1.0)],
        mmd_tracks=[
            {
                "id": "mmd_export",
                "model_path": "hero.pmx",
                "motion_path": "dance.vmd",
                "start_ms": 0,
                "end_ms": 1000,
            }
        ],
    )
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)

    out = exporter._apply_mmd_export_cpu(rgb, 120)

    assert out is rgb
    assert exporter._mmd_tracks[0]["id"] == "mmd_export"
    assert exporter._mmd_last_export_diagnostics["mode"] == "preview_only_pending_offscreen_renderer"
    assert exporter._mmd_last_export_diagnostics["active_track_count"] == 1
    assert exporter._mmd_last_export_diagnostics["rendered_track_count"] == 0


def test_video_exporter_uses_prerendered_mmd_overlay_without_pending_warning(tmp_path) -> None:
    from app.video_exporter import VideoExportThread

    overlay = tmp_path / "mmd.mov"
    overlay.write_bytes(b"mov")
    exporter = VideoExportThread(
        source_path=tmp_path / "in.mp4",
        out_path=tmp_path / "out.mp4",
        segments=[(0, 1000, 1.0)],
        mmd_tracks=[
            {
                "id": "mmd_export",
                "model_path": "hero.pmx",
                "motion_path": "dance.vmd",
                "start_ms": 0,
                "end_ms": 1000,
            }
        ],
        mmd_pre_rendered=[(str(overlay), 0.0, 1.0)],
    )
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)

    out = exporter._apply_mmd_export_cpu(rgb, 120)

    assert out is rgb
    assert exporter._mmd_last_export_diagnostics["ok"] is True
    assert exporter._mmd_last_export_diagnostics["mode"] == "pre_rendered_alpha_overlay"
    assert exporter._mmd_last_export_diagnostics["overlay_count"] == 1


def test_project_player_mmd_frame_loops_motion() -> None:
    player = ProjectPlayer()
    try:
        track = normalize_mmd_track(
            {
                "model_path": "hero.pmx",
                "start_ms": 1000,
                "end_ms": 5000,
                "playback": {"motion_start_ms": 0, "loop": True},
            }
        )
        frame = player._mmd_frame_for_track(track, SimpleNamespace(max_frame=30), 2500)
        assert frame == 15.0
    finally:
        player.release()


def test_project_player_mmd_physics_backend_uses_track_cadence() -> None:
    from app.mmd.physics import DecimatedPhysicsBackend, NoPhysicsBackend, SpringPhysicsBackend

    player = ProjectPlayer()
    try:
        disabled = player._mmd_physics_backend_for_track("mmd_1", 0.0, False)
        assert isinstance(disabled, NoPhysicsBackend)

        backend = player._mmd_physics_backend_for_track(
            "mmd_1",
            0.0,
            True,
            "spring",
            update_interval_frames=4.0,
            smoothing_response=0.25,
            rotation_hint_scale=0.20,
            spring_response=0.50,
        )
        assert isinstance(backend, DecimatedPhysicsBackend)
        assert backend.update_interval_frames == 4.0
        assert backend.smoothing_response == 0.25
        assert isinstance(backend.backend, SpringPhysicsBackend)
        assert backend.backend.secondary_rotation_scale == 0.20
        assert backend.backend.spring_response == 0.50
    finally:
        player.release()


def test_project_player_mmd_overlay_uses_gpu_morph_track_settings(monkeypatch) -> None:
    import app.mmd.animation as animation_mod
    import app.mmd.gpu_preview as gpu_preview_mod
    import app.mmd.vmd as vmd_mod

    player = ProjectPlayer()
    calls = {}
    try:
        fake_model = SimpleNamespace(
            weights=SimpleNamespace(weight_types=np.asarray([0, 0, 0], dtype=np.uint8)),
        )
        fake_motion = SimpleNamespace(max_frame=60)
        player._mmd_model_for_path = lambda _path: fake_model
        player._mmd_motion_for_path = lambda _path: fake_motion

        def fake_evaluate(_model, _motion, frame, **kwargs):
            calls["frame"] = frame
            calls["skin_vertices"] = kwargs.get("skin_vertices")
            calls["gpu_morph_slots"] = kwargs.get("gpu_morph_slots")
            return SimpleNamespace()

        def fake_build(_model, **kwargs):
            calls["pose_geometry"] = kwargs.get("pose_geometry")
            return {"gpu_skinning": True, "diagnostics": {}}

        monkeypatch.setattr(animation_mod, "evaluate_model_pose", fake_evaluate)
        monkeypatch.setattr(gpu_preview_mod, "build_mmd_render_item", fake_build)
        monkeypatch.setattr(vmd_mod, "camera_at", lambda _motion, _frame: None)
        monkeypatch.setattr(
            vmd_mod,
            "camera_to_view_controls",
            lambda _camera, **fallbacks: {
                "yaw": fallbacks["fallback_yaw"],
                "pitch": fallbacks["fallback_pitch"],
                "zoom": fallbacks["fallback_zoom"],
                "offset_x": fallbacks["fallback_offset_x"],
                "offset_y": fallbacks["fallback_offset_y"],
            },
        )

        player.set_mmd_tracks(
            [
                {
                    "id": "mmd_gpu",
                    "model_path": "hero.pmx",
                    "motion_path": "dance.vmd",
                    "start_ms": 0,
                    "end_ms": 2000,
                    "playback": {"gpu_skinning": True, "gpu_morph_slots": 2},
                }
            ]
        )
        items = player._mmd_overlay_items(500, animate=True)

        assert len(items) == 1
        assert calls["skin_vertices"] is False
        assert calls["gpu_morph_slots"] == 2
        assert items[0]["diagnostics"]["track_gpu_skinning_active"] is True
        assert items[0]["diagnostics"]["track_gpu_morph_slots"] == 2
    finally:
        player.release()


def test_project_player_mmd_overlay_reports_sdef_gpu_fallback(monkeypatch) -> None:
    import app.mmd.animation as animation_mod
    import app.mmd.gpu_preview as gpu_preview_mod
    import app.mmd.vmd as vmd_mod

    player = ProjectPlayer()
    calls = {}
    try:
        fake_model = SimpleNamespace(
            weights=SimpleNamespace(weight_types=np.asarray([3, 0, 0], dtype=np.uint8)),
        )
        fake_motion = SimpleNamespace(max_frame=60)
        player._mmd_model_for_path = lambda _path: fake_model
        player._mmd_motion_for_path = lambda _path: fake_motion

        def fake_evaluate(_model, _motion, frame, **kwargs):
            calls["frame"] = frame
            calls["skin_vertices"] = kwargs.get("skin_vertices")
            calls["gpu_morph_slots"] = kwargs.get("gpu_morph_slots")
            return SimpleNamespace()

        def fake_build(_model, **kwargs):
            calls["pose_geometry"] = kwargs.get("pose_geometry")
            return {"gpu_skinning": False, "diagnostics": {"sdef_cpu_skinning_required": True}}

        monkeypatch.setattr(animation_mod, "evaluate_model_pose", fake_evaluate)
        monkeypatch.setattr(gpu_preview_mod, "build_mmd_render_item", fake_build)
        monkeypatch.setattr(vmd_mod, "camera_at", lambda _motion, _frame: None)
        monkeypatch.setattr(
            vmd_mod,
            "camera_to_view_controls",
            lambda _camera, **fallbacks: {
                "yaw": fallbacks["fallback_yaw"],
                "pitch": fallbacks["fallback_pitch"],
                "zoom": fallbacks["fallback_zoom"],
                "offset_x": fallbacks["fallback_offset_x"],
                "offset_y": fallbacks["fallback_offset_y"],
            },
        )

        player.set_mmd_tracks(
            [
                {
                    "id": "mmd_sdef",
                    "model_path": "hero_sdef.pmx",
                    "motion_path": "dance.vmd",
                    "start_ms": 0,
                    "end_ms": 2000,
                    "playback": {"gpu_skinning": True, "gpu_morph_slots": 2},
                }
            ]
        )
        items = player._mmd_overlay_items(500, animate=True)

        assert len(items) == 1
        assert calls["skin_vertices"] is True
        assert calls["gpu_morph_slots"] == 0
        assert items[0]["diagnostics"]["track_gpu_skinning_requested"] is True
        assert items[0]["diagnostics"]["track_gpu_skinning_active"] is False
        assert items[0]["diagnostics"]["track_sdef_cpu_skinning_required"] is True
        assert items[0]["diagnostics"]["track_gpu_skinning_fallback_reason"] == "sdef_cpu_skinning_required"
    finally:
        player.release()
