import numpy as np

from app.ar_pbr.animation import animated_vertices_for_geometry
from app.ar_pbr.gpu_preview import build_gpu_preview_items
from app.ar_pbr.project_tracks import DEFAULT_PREVIEW_SCALE, create_preview_ar_track, transform_position_from_frame_point
from app.ar_pbr.schema import normalize_ar_tracks
from app.project_player import (
    AR_PBR_PLAYBACK_TRIANGLE_LIMIT,
    AR_PBR_PREVIEW_TRIANGLE_LIMIT,
    ProjectPlayer,
)
from app.simple_video_player import PlayerState


def test_frame_point_maps_to_compositor_transform():
    assert transform_position_from_frame_point(0.5, 0.5) == [0.0, 0.0, 0.0]
    assert transform_position_from_frame_point(1.0, 0.0) == [2.0, 2.0, 0.0]


def test_project_player_ar_pbr_preview_auto_uses_full_gpu_only_when_not_playing(monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", raising=False)
    player = ProjectPlayer()

    player._state = PlayerState.STOPPED
    assert player._ar_pbr_preview_renderer_mode() == "auto"
    assert player._ar_pbr_should_use_full_gpu_preview() is True

    player._state = PlayerState.PAUSED
    assert player._ar_pbr_should_use_full_gpu_preview() is True

    player._state = PlayerState.PLAYING
    assert player._ar_pbr_should_use_full_gpu_preview() is False


def test_project_player_ar_pbr_playback_uses_lower_gpu_triangle_budget(monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PREVIEW_TRIANGLE_LIMIT", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PLAYBACK_TRIANGLE_LIMIT", raising=False)
    player = ProjectPlayer()

    player._state = PlayerState.STOPPED
    assert player._ar_pbr_gpu_preview_triangle_limit() == AR_PBR_PREVIEW_TRIANGLE_LIMIT

    player._state = PlayerState.PLAYING
    assert player._ar_pbr_gpu_preview_triangle_limit() == AR_PBR_PLAYBACK_TRIANGLE_LIMIT


def test_project_player_reuses_static_ar_pbr_gpu_packet_during_playback(tmp_path, monkeypatch):
    monkeypatch.setenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", "packet")
    asset = tmp_path / "static.glb"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_static_cache",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "id": "asset_static",
        "mesh_count": 1,
        "material_count": 1,
        "animation_count": 0,
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.25, 0.05, 1.0]}],
    }
    calls = []

    def fake_build_gpu_preview_items(**kwargs):
        calls.append(int(kwargs["time_ms"]))
        return [
            {
                "track_id": "ar_pbr_static_cache",
                "vertices": [0.0, 0.0, 1.0, 0.0, 0.0, 1.0] * 3,
                "triangle_count": 1,
            }
        ], {"ok": True, "mode": "gpu_preview", "triangle_count": 1}

    monkeypatch.setattr(
        "app.ar_pbr.gpu_preview.build_gpu_preview_items",
        fake_build_gpu_preview_items,
    )
    player = ProjectPlayer()
    player._state = PlayerState.PLAYING
    player.set_qimage_frame_enabled(False)
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    _out1, meta1 = player._apply_or_defer_ar_pbr_overlay(base, 10)
    _out2, meta2 = player._apply_or_defer_ar_pbr_overlay(base, 43)

    assert len(calls) == 1
    assert calls == [10]
    assert meta1 and meta1["ar_pbr_items"]
    assert meta2 and meta2["ar_pbr_items"]
    assert player._ar_pbr_last_diagnostics["packet_cache_hit"] is True
    assert meta1["ar_pbr_items"][0]["packet_cache_id"]
    assert meta2["ar_pbr_items"][0]["packet_cache_id"] == meta1["ar_pbr_items"][0]["packet_cache_id"]
    assert player._ar_pbr_last_diagnostics["packet_cache_id"] == meta2["ar_pbr_items"][0]["packet_cache_id"]


def test_project_player_prewarms_ar_pbr_asset_import_before_track_in_point(tmp_path, monkeypatch):
    asset = tmp_path / "future.glb"
    asset.write_bytes(b"glTF")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_future",
        start_ms=5000,
        duration_ms=1000,
    )
    player = ProjectPlayer()
    calls = []

    def fake_start(cache_key, path):
        calls.append((cache_key, path))

    monkeypatch.setattr(player, "_ar_pbr_start_asset_import", fake_start)

    player.set_ar_pbr_tracks([track])

    resolved = asset.resolve()
    assert calls == [(f"{resolved}|triangles:{AR_PBR_PREVIEW_TRIANGLE_LIMIT}", resolved)]


def test_project_player_skips_runtime_scene_anchor_update_during_playback(monkeypatch):
    import app.ar_pbr.scene_anchor as scene_anchor

    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PLAYBACK_SCENE_ANCHOR", raising=False)
    calls = []

    def fake_update(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("runtime scene anchor should not update while playing")

    monkeypatch.setattr(scene_anchor, "update_scene_anchor_for_frame", fake_update)
    player = ProjectPlayer()
    player._state = PlayerState.PLAYING
    track = {
        "id": "ar_pbr_scene",
        "asset_path": "scene.glb",
        "placement": {"mode": "road_plane_anchor"},
        "camera_solution": {"id": "cam_001", "plane": {"normal": [0, 1, 0], "distance": 1.0}},
    }
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)

    runtime, depth, solution, diagnostics = player._ar_pbr_runtime_tracks_for_frame([track], rgb, 100)

    assert calls == []
    assert runtime == [track]
    assert depth is None
    assert solution == track["camera_solution"]
    assert diagnostics[0]["skipped_during_playback"] is True


def test_project_player_skips_synthetic_depth_for_scene_anchor_playback(monkeypatch):
    import app.depth.estimator as estimator

    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PLAYBACK_DEPTH", raising=False)
    calls = []

    def fake_estimate(*_args, **_kwargs):
        calls.append(True)
        raise AssertionError("synthetic depth should not run while playing")

    monkeypatch.setattr(estimator, "estimate_depth_from_luma", fake_estimate)
    player = ProjectPlayer()
    player._state = PlayerState.PLAYING
    track = {
        "id": "ar_pbr_scene",
        "placement": {"mode": "road_plane_anchor"},
        "occlusion": False,
    }
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)

    assert player._ar_pbr_depth_frame_for_tracks(rgb, 100, [track]) is None
    assert calls == []


def test_project_player_ar_pbr_preview_renderer_env_can_force_packet(monkeypatch):
    monkeypatch.setenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", "packet")
    player = ProjectPlayer()
    player._state = PlayerState.STOPPED

    assert player._ar_pbr_preview_renderer_mode() == "packet"
    assert player._ar_pbr_should_use_full_gpu_preview() is False


def test_project_player_full_gpu_preview_requests_shadow_map():
    player = ProjectPlayer()

    settings = player._ar_pbr_software_settings([], renderer="full_gpu")

    assert settings["renderer"] == "full_gpu"
    assert settings["enable_shadow_map"] is True


def test_video_editor_ar_pbr_model_view_settings_persist_render_profile():
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow.__new__(VideoEditorWindow)
    track = {"render": {"lighting": {"ibl_exposure": 1.0}}}

    VideoEditorWindow._apply_ar_pbr_lighting_settings_to_track(
        editor,
        track,
        {
            "render_profile": "marmoset_pbr",
            "ibl_exposure": 1.7,
            "shadow_strength": 0.2,
            "shadow_filter": "pcss",
            "shadow_light_type": "spot",
            "shadow_pcf_radius": 2.4,
            "shadow_pcss_blocker_radius": 3.25,
            "shadow_bias": 0.004,
            "shadow_normal_bias": 0.006,
            "shadow_spot_inner_angle": 24.0,
            "shadow_spot_outer_angle": 47.0,
            "shadow_catcher_opacity": 0.83,
            "shadow_catcher_softness": 0.71,
            "shadow_catcher_matte_alpha": 0.16,
            "reflection_catcher_opacity": 0.58,
            "reflection_catcher_roughness": 0.73,
            "reflection_catcher_softness": 0.64,
            "contact_reflection_strength": 0.41,
            "contact_reflection_falloff": 0.67,
            "tone_mapping": "agx",
            "tone_exposure": 0.75,
            "tone_white_balance": 5200,
            "tone_gamma": 2.35,
            "self_shadow_strength": 0.8,
            "surface_override_strength": 0.64,
            "surface_roughness": 0.28,
            "surface_metallic": 0.22,
            "surface_reflectance": 0.46,
            "clearcoat_strength": 0.53,
            "clearcoat_roughness": 0.09,
            "clearcoat_ior": 1.56,
        },
    )

    assert track["render"]["render_profile"] == "marmoset_pbr"
    assert track["render"]["lighting"]["ibl_exposure"] == 1.7
    assert track["render"]["lighting"]["shadow_filter"] == "pcss"
    assert track["render"]["lighting"]["shadow_light_type"] == "spot"
    assert track["render"]["lighting"]["shadow_pcf_radius"] == 2.4
    assert track["render"]["lighting"]["shadow_pcss_blocker_radius"] == 3.25
    assert track["render"]["lighting"]["shadow_bias"] == 0.004
    assert track["render"]["lighting"]["shadow_normal_bias"] == 0.006
    assert track["render"]["lighting"]["shadow_spot_inner_angle"] == 24.0
    assert track["render"]["lighting"]["shadow_spot_outer_angle"] == 47.0
    assert track["render"]["lighting"]["shadow_catcher_opacity"] == 0.83
    assert track["render"]["lighting"]["shadow_catcher_softness"] == 0.71
    assert track["render"]["lighting"]["shadow_catcher_matte_alpha"] == 0.16
    assert track["render"]["lighting"]["reflection_catcher_opacity"] == 0.58
    assert track["render"]["lighting"]["reflection_catcher_roughness"] == 0.73
    assert track["render"]["lighting"]["reflection_catcher_softness"] == 0.64
    assert track["render"]["lighting"]["contact_reflection_strength"] == 0.41
    assert track["render"]["lighting"]["contact_reflection_falloff"] == 0.67
    assert track["render"]["lighting"]["tone_mapping"] == "agx"
    assert track["render"]["lighting"]["tone_exposure"] == 0.75
    assert track["render"]["lighting"]["tone_white_balance"] == 5200.0
    assert track["render"]["lighting"]["tone_gamma"] == 2.35
    assert track["render"]["lighting"]["self_shadow_strength"] == 0.8
    assert track["render"]["lighting"]["surface_override_strength"] == 0.64
    assert track["render"]["lighting"]["surface_roughness"] == 0.28
    assert track["render"]["lighting"]["surface_metallic"] == 0.22
    assert track["render"]["lighting"]["surface_reflectance"] == 0.46
    assert track["render"]["lighting"]["clearcoat_strength"] == 0.53
    assert track["render"]["lighting"]["clearcoat_roughness"] == 0.09
    assert track["render"]["lighting"]["clearcoat_ior"] == 1.56
    assert track["shadow_catcher"] is True


def test_create_preview_ar_track_uses_drop_position_and_duration(tmp_path):
    asset = tmp_path / "scooter.fbx"
    asset.write_bytes(b"Kaydara FBX Binary  \x00\x1a\x00")

    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_007",
        start_ms=1200,
        duration_ms=3400,
        image_point=(0.75, 0.25),
    )

    assert track["id"] == "ar_pbr_007"
    assert track["asset_path"] == str(asset.resolve())
    assert track["start_ms"] == 1200
    assert track["end_ms"] == 4600
    assert track["transform"]["position"] == [1.0, 1.0, 0.0]
    assert track["transform"]["scale"] == [DEFAULT_PREVIEW_SCALE, DEFAULT_PREVIEW_SCALE, DEFAULT_PREVIEW_SCALE]
    assert track["placement"]["image_point"] == [0.75, 0.25]
    assert track["material_override"] is False
    assert track["animation"]["auto_play"] is True
    assert track["animation"]["loop"] is True

    normalized_again = normalize_ar_tracks([track])[0]
    assert normalized_again["material_override"] is False
    assert normalized_again["animation"]["auto_play"] is True


def test_project_player_pending_ar_pbr_descriptor_has_public_support(tmp_path):
    asset = tmp_path / "loading.glb"
    descriptor = ProjectPlayer._ar_pbr_pending_descriptor_for_path(asset)

    assert descriptor["support"]["support_level"] == "placeholder"
    assert descriptor["support_ui"]["label"] == "Loading: checking 3D support"
    assert "issue_codes" not in descriptor["support_ui"]


def test_pending_ar_pbr_descriptor_does_not_emit_placeholder_mesh(tmp_path):
    asset = tmp_path / "loading_mesh.glb"
    descriptor = ProjectPlayer._ar_pbr_pending_descriptor_for_path(asset)
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_loading",
        start_ms=0,
        duration_ms=1000,
    )

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[track],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={"asset_descriptors": {str(asset): descriptor, str(asset.resolve()): descriptor}},
    )

    assert items == []
    assert diag["pending_track_count"] == 1
    assert diag["triangle_count"] == 0


def test_software_pbr_pending_descriptor_keeps_video_frame_clean(tmp_path):
    asset = tmp_path / "loading_composite.glb"
    descriptor = ProjectPlayer._ar_pbr_pending_descriptor_for_path(asset)
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_loading_cpu",
        start_ms=0,
        duration_ms=1000,
    )
    player = ProjectPlayer()
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((64, 64, 3), dtype=np.uint8)

    out = player._composite_ar_pbr_tracks(base, 10)

    assert np.array_equal(out, base)
    assert player._ar_pbr_last_diagnostics["software_renderer"]["pending_track_count"] == 1
    assert player._ar_pbr_last_diagnostics["software_renderer"]["triangle_count"] == 0


def test_ar_pbr_direct_gl_painter_batches_rows_by_texture_maps():
    from app.opengl_preview import _ARPBRDirectGLPainter

    row_a = list(range(69))
    row_b = list(range(69, 138))
    row_c = list(range(138, 207))
    rows = [
        {"texture": "body.png", "maps": {"base": "body.png", "roughness": "rough.png"}, "vertices": row_a},
        {"texture": "body.png", "maps": {"roughness": "rough.png", "base": "body.png"}, "vertices": row_b},
        {"texture": "strap.png", "maps": {"base": "strap.png"}, "vertices": row_c},
    ]

    batches = _ARPBRDirectGLPainter._pbr_row_batches(rows)

    assert len(batches) == 2
    assert len(batches[0]["vertices"]) == 138
    assert batches[0]["path"] == "body.png"
    assert batches[1]["path"] == "strap.png"
    assert _ARPBRDirectGLPainter._vec3([1, 2, 3], (0, 0, 0)).z() == 3.0


def test_project_player_composites_ar_pbr_track_from_cached_descriptor(tmp_path):
    asset = tmp_path / "triangle.fbx"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.25, 0.05, 1.0]}],
    }

    player = ProjectPlayer()
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    out = player._composite_ar_pbr_tracks(base, 10)

    assert out.shape == base.shape
    assert out.sum() > 0
    assert player._ar_pbr_last_diagnostics["mode"] == "software_pbr"


def test_gpu_preview_items_render_descriptor_triangles():
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.2, 0.8, 1.0, 1.0]}],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_001",
            "type": "ar_pbr_object",
            "asset_path": "triangle.fbx",
            "start_ms": 0,
            "end_ms": 1000,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {"triangle.fbx": descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "gpu_preview"
    assert diag["triangle_count"] == 1
    assert len(items) == 1
    assert len(items[0]["vertices"]) == 18


def test_gpu_preview_auto_plays_static_mesh_transform_animation():
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "models": [{"id": "model_1", "name": "Box", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}],
        "geometries": [
            {
                "model_id": "model_1",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.2, 0.8, 1.0, 1.0]}],
        "animation_clips": [{
            "id": "clip_001",
            "name": "MoveRight",
            "duration_ms": 1000.0,
            "model_curves": {
                "model_1": {
                    "translation": {
                        "x": [[0.0, 0.0], [1000.0, 1.0]],
                    },
                },
            },
        }],
    }
    track = {
        "id": "ar_pbr_anim",
        "type": "ar_pbr_object",
        "asset_path": "animated.fbx",
        "start_ms": 0,
        "end_ms": 2000,
        "animation": {"auto_play": True, "loop": False, "speed": 1.0},
    }

    first, first_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=0,
        ar_tracks=[track],
        camera_solution={"frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {"animated.fbx": descriptor}, "camera_z": 3.0},
    )
    later, later_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=500,
        ar_tracks=[track],
        camera_solution={"frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {"animated.fbx": descriptor}, "camera_z": 3.0},
    )

    assert first_diag["triangle_count"] == 1
    assert later_diag["triangle_count"] == 1
    assert first[0]["vertices"] != later[0]["vertices"]


def test_gpu_preview_auto_plays_skeletal_skin_translation_animation():
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "models": [
            {"id": "mesh_model", "name": "Mesh", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            {"id": "bone_1", "name": "Root", "kind": "LimbNode", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
        ],
        "bones": [{"id": "bone_1", "name": "Root"}],
        "skeletal_mesh_count": 1,
        "geometries": [
            {
                "model_id": "mesh_model",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                "skin_weights": [
                    [{"bone_id": "bone_1", "weight": 1.0}],
                    [{"bone_id": "bone_1", "weight": 1.0}],
                    [{"bone_id": "bone_1", "weight": 1.0}],
                ],
            }
        ],
        "materials": [{"base_color": [0.2, 0.8, 1.0, 1.0]}],
        "animation_clips": [{
            "id": "clip_001",
            "name": "BoneMove",
            "duration_ms": 1000.0,
            "model_curves": {
                "bone_1": {
                    "translation": {
                        "x": [[0.0, 0.0], [1000.0, 1.0]],
                    },
                },
            },
        }],
    }
    track = {
        "id": "ar_pbr_skel",
        "type": "ar_pbr_object",
        "asset_path": "skeletal.fbx",
        "start_ms": 0,
        "end_ms": 2000,
        "animation": {"auto_play": True, "loop": False, "speed": 1.0},
    }

    first, _first_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=0,
        ar_tracks=[track],
        camera_solution={"frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {"skeletal.fbx": descriptor}, "camera_z": 3.0},
    )
    later, _later_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=500,
        ar_tracks=[track],
        camera_solution={"frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {"skeletal.fbx": descriptor}, "camera_z": 3.0},
    )

    assert first[0]["vertices"] != later[0]["vertices"]


def test_animation_helper_applies_skeletal_rotation_and_parent_hierarchy():
    geometry = {
        "model_id": "mesh_model",
        "vertices": [[1, 0, 0], [2, 0, 0], [1, 1, 0]],
        "triangles": [[0, 1, 2]],
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "skin_weights": [
            [{"bone_id": "child_bone", "weight": 1.0}],
            [{"bone_id": "child_bone", "weight": 1.0}],
            [{"bone_id": "child_bone", "weight": 1.0}],
        ],
    }
    descriptor = {
        "units": {"scale_to_meters": 1.0},
        "models": [
            {"id": "mesh_model", "name": "Mesh", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            {"id": "root_bone", "name": "Root", "kind": "LimbNode", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
            {"id": "child_bone", "parent_id": "root_bone", "name": "Child", "kind": "LimbNode", "translation": [1, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
        ],
        "bones": [
            {"id": "root_bone", "name": "Root"},
            {"id": "child_bone", "name": "Child", "parent_id": "root_bone"},
        ],
        "animation_clips": [{
            "id": "clip_001",
            "name": "RotateChild",
            "duration_ms": 1000.0,
            "model_curves": {
                "root_bone": {
                    "rotation": {"z": [[0.0, 0.0], [1000.0, 90.0]]},
                },
                "child_bone": {
                    "rotation": {"z": [[0.0, 0.0], [1000.0, 90.0]]},
                },
            },
        }],
    }
    track = {
        "id": "ar_pbr_skel_rotate",
        "asset_path": "skeletal.fbx",
        "start_ms": 0,
        "end_ms": 2000,
        "animation": {"auto_play": True, "loop": False, "speed": 1.0},
    }

    out = animated_vertices_for_geometry(
        geometry["vertices"],
        geometry=geometry,
        descriptor=descriptor,
        track=track,
        time_ms=1000,
    )

    assert out != geometry["vertices"]
    assert out[0][0] < 0.1
    assert out[0][1] > 0.9


def test_gpu_preview_reports_texture_plan_and_tints_packet_colors(tmp_path):
    from PIL import Image

    asset = tmp_path / "body_car.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    roughness = tmp_path / "body_bodyr.png"
    metallic = tmp_path / "body_bodym.png"
    specular = tmp_path / "body_bodys.png"
    normal = tmp_path / "body_bodyn.png"
    occlusion = tmp_path / "body_bodyao.png"
    emissive = tmp_path / "body_emissive.png"
    opacity = tmp_path / "body_opacity.png"
    Image.new("RGB", (4, 4), (24, 210, 96)).save(texture)
    Image.new("L", (4, 4), 160).save(roughness)
    Image.new("L", (4, 4), 24).save(metallic)
    Image.new("L", (4, 4), 192).save(specular)
    Image.new("RGB", (4, 4), (128, 128, 255)).save(normal)
    Image.new("L", (4, 4), 180).save(occlusion)
    Image.new("RGB", (4, 4), (255, 64, 16)).save(emissive)
    Image.new("L", (4, 4), 220).save(opacity)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                    "name": "BodyPaint",
                    "base_color": [1.0, 0.05, 0.02, 1.0],
                    "base_texture": str(texture),
                    "roughness_texture": str(roughness),
                    "metallic_texture": str(metallic),
                    "specular_texture": str(specular),
                    "normal_texture": str(normal),
                    "occlusion_texture": str(occlusion),
                    "emissive_texture": str(emissive),
                    "opacity_texture": str(opacity),
                    "alpha_mode": "MASK",
                    "alpha_cutoff": 0.25,
                    "emissive_factor": [1.0, 0.2, 0.1],
                }
            ],
        }

    far_depth = np.ones((96, 96), dtype=np.float32)
    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_textured",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
            "occlusion": True,
            "render": {
                "lighting": {
                    "hdri_id": "wide_street_01",
                    "ibl_rotation": 0.1,
                    "ibl_exposure": 1.3,
                    "direct_strength": 0.8,
                    "shadow_filter": "pcss",
                    "shadow_light_type": "spot",
                    "shadow_pcf_radius": 2.2,
                    "shadow_pcss_blocker_radius": 3.1,
                    "shadow_bias": 0.004,
                    "shadow_normal_bias": 0.005,
                    "shadow_spot_inner_angle": 26.0,
                    "shadow_spot_outer_angle": 49.0,
                    "tone_mapping": "agx",
                    "tone_exposure": 0.5,
                    "tone_white_balance": 5600,
                    "tone_gamma": 2.3,
                    "surface_override_strength": 0.6,
                    "surface_roughness": 0.31,
                    "surface_metallic": 0.18,
                    "surface_reflectance": 0.44,
                },
            },
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=far_depth,
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["texture_map_count"] >= 8
    assert diag["texture_material_count"] == 1
    assert diag["texture_tinted_triangle_count"] == 1
    assert diag["texture_triangle_count"] == 1
    assert diag["pbr_triangle_count"] == 1
    assert diag["gpu_renderer"]["texture_sampling"] == "gl_preview_pbr_texture_export_affine_uv"
    assert diag["gpu_renderer"]["pbr_preview"] == "gl_model_view_material_map_pbr_packet_ready"
    assert diag["gpu_renderer"]["depth_occlusion"] == "live_depth_texture_fragment"
    assert diag["gpu_renderer"]["color_management"] == "agx"
    assert diag["gpu_renderer"]["render_pass_safe_color"] == "scene_linear_display_transform_preserve_alpha"
    assert diag["live_depth_texture_triangle_count"] == 1
    assert items[0]["texture_status"] == "ready"
    assert items[0]["depth_texture"] is not None
    assert items[0]["depth_texture"].dtype == np.uint8
    assert items[0]["pbr_depth_occlusion"]["enabled"] is True
    assert items[0]["pbr_depth_occlusion"]["mode"] == "live_depth_texture_fragment"
    assert items[0]["texture_triangle_count"] == 1
    assert items[0]["texture_triangles"][0]["texture"] == str(texture)
    assert items[0]["pbr_triangle_count"] == 1
    assert items[0]["pbr_triangles"][0]["texture"] == str(texture)
    assert items[0]["pbr_triangles"][0]["maps"]["base"] == str(texture)
    assert items[0]["pbr_triangles"][0]["maps"]["roughness"] == str(roughness)
    assert items[0]["pbr_triangles"][0]["maps"]["metallic"] == str(metallic)
    assert items[0]["pbr_triangles"][0]["maps"]["specular"] == str(specular)
    assert items[0]["pbr_triangles"][0]["maps"]["normal"] == str(normal)
    assert items[0]["pbr_triangles"][0]["maps"]["occlusion"] == str(occlusion)
    assert items[0]["pbr_triangles"][0]["maps"]["emissive"] == str(emissive)
    assert items[0]["pbr_triangles"][0]["maps"]["opacity"] == str(opacity)
    assert items[0]["pbr_triangles"][0]["maps"]["alpha_cutoff"] == "0.25"
    assert items[0]["pbr_triangles"][0]["maps"]["emissive_factor"] == "1.0,0.2,0.1"
    assert len(items[0]["pbr_triangles"][0]["vertices"]) == 69
    assert items[0]["pbr_vertex_stride_floats"] == 23
    assert diag["gpu_renderer"]["pbr_vertex_stride_floats"] == 23
    assert items[0]["pbr_lighting"]["shadow_filter"] == "pcss"
    assert items[0]["pbr_lighting"]["shadow_light_type"] == "spot"
    assert items[0]["pbr_lighting"]["shadow_pcf_radius"] == 2.2
    assert items[0]["pbr_lighting"]["shadow_pcss_blocker_radius"] == 3.1
    assert items[0]["pbr_lighting"]["shadow_bias"] == 0.004
    assert items[0]["pbr_lighting"]["shadow_normal_bias"] == 0.005
    assert items[0]["pbr_lighting"]["shadow_spot_inner_angle"] == 26.0
    assert items[0]["pbr_lighting"]["shadow_spot_outer_angle"] == 49.0
    assert items[0]["pbr_lighting"]["contact_shadow_role"] == "helper_only"
    assert items[0]["pbr_lighting"]["tone_mapping"] == "agx"
    assert items[0]["pbr_lighting"]["tone_mapping_mode"] == 1
    assert items[0]["pbr_lighting"]["tone_exposure"] == 0.5
    assert items[0]["pbr_lighting"]["tone_white_balance"] == 5600.0
    assert items[0]["pbr_lighting"]["tone_gamma"] == 2.3
    assert items[0]["color_management"]["schema"] == "tigerstudio.ar_pbr.color_management.v1"
    assert items[0]["pbr_lighting"]["self_shadow_strength"] == 0.45
    assert items[0]["pbr_lighting"]["ibl_rotation"] == 0.1
    assert items[0]["pbr_lighting"]["hdri_enabled"] is True
    assert items[0]["pbr_lighting"]["surface_override_strength"] == 0.6
    assert items[0]["pbr_lighting"]["surface_roughness"] == 0.31
    assert items[0]["pbr_lighting"]["surface_metallic"] == 0.18
    assert items[0]["pbr_lighting"]["surface_reflectance"] == 0.44
    vertices = items[0]["vertices"]
    red = vertices[2::6]
    green = vertices[3::6]
    assert sum(green) / len(green) > sum(red) / len(red)


def test_gpu_preview_prefers_face_corner_triangle_uvs(tmp_path):
    from PIL import Image

    asset = tmp_path / "uv_seam.fbx"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "uv_base.png"
    Image.new("RGB", (4, 4), (64, 128, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[9, 9], [9, 9], [9, 9]],
                "triangle_uvs": [[[0.11, 0.22], [0.33, 0.44], [0.55, 0.66]]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"name": "UvMat", "base_color": [1.0, 1.0, 1.0, 1.0], "base_texture": str(texture)}],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_uv",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["texture_triangle_count"] == 1
    row = items[0]["texture_triangles"][0]["vertices"]
    assert np.allclose([row[2], row[3]], [0.11, 0.22])
    assert np.allclose([row[10], row[11]], [0.33, 0.44])
    assert np.allclose([row[18], row[19]], [0.55, 0.66])
    pbr_row = items[0]["pbr_triangles"][0]["vertices"]
    assert np.allclose([pbr_row[2], pbr_row[3]], [0.11, 0.22])


def test_gpu_preview_applies_gltf_material_uv_set_and_transform(tmp_path):
    from PIL import Image

    asset = tmp_path / "atlas.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "atlas.png"
    Image.new("RGB", (4, 4), (255, 128, 64)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[9, 9], [9, 9], [9, 9]],
                "uv_sets": {
                    "1": [[0.2, 0.3], [0.4, 0.5], [0.6, 0.7]],
                },
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "AtlasMat",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "uv_set": 1,
                "uv_transform": {"offset": [0.1, 0.2], "scale": [0.5, 2.0], "rotation": 0.0},
                "base_wrap_s": "repeat",
                "base_wrap_t": "mirrored_repeat",
            }
        ],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_gltf_uv",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["texture_triangle_count"] == 1
    row = items[0]["texture_triangles"][0]["vertices"]
    assert np.allclose([row[2], row[3]], [0.2, 0.8])
    assert np.allclose([row[10], row[11]], [0.3, 1.2])
    assert np.allclose([row[18], row[19]], [0.4, 1.6])
    maps = items[0]["pbr_triangles"][0]["maps"]
    assert maps["base_wrap_s"] == "repeat"
    assert maps["base_wrap_t"] == "mirrored_repeat"


def test_gpu_preview_marks_unlit_vrm_materials_for_export_packet(tmp_path):
    from PIL import Image

    from app.ar_pbr.export_packet_renderer import rasterize_gpu_preview_items

    asset = tmp_path / "milica.vrm"
    asset.write_bytes(b"glTF")
    texture = tmp_path / "face.png"
    Image.new("RGBA", (4, 4), (245, 210, 190, 255)).save(texture)
    descriptor = {
        "source_ext": ".vrm",
        "vrm": {"profile": "VRM0", "title": "Milica"},
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                "material_id": "mat_0",
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Face",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "shader_model": "vrm_mtoon",
                "source_shader": "VRM/MToon",
                "unlit": True,
            }
        ],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=0,
        ar_tracks=[{
            "id": "milica_vrm",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["pbr_triangle_count"] == 1
    assert items[0]["pbr_triangles"][0]["maps"]["unlit"] == "1"

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    _out, draw_diag = rasterize_gpu_preview_items(base, items, settings={"camera_z": 3.0})

    assert draw_diag["pbr_sampled_triangle_count"] == 1
    assert draw_diag["pbr_unlit_sampled_triangle_count"] == 1


def test_gpu_preview_can_request_marmoset_pbr_for_vrm_with_pbr_data(tmp_path):
    from PIL import Image

    from app.ar_pbr.export_packet_renderer import rasterize_gpu_preview_items

    asset = tmp_path / "milica_pbr.vrm"
    asset.write_bytes(b"glTF")
    texture = tmp_path / "face.png"
    normal = tmp_path / "face_n.png"
    Image.new("RGBA", (4, 4), (245, 210, 190, 255)).save(texture)
    Image.new("RGBA", (4, 4), (128, 128, 255, 255)).save(normal)
    descriptor = {
        "source_ext": ".vrm",
        "vrm": {"profile": "VRM0", "title": "Milica"},
        "render_profiles": {
            "schema": "tigerstudio.ar_pbr.render_profiles.v1",
            "default_profile": "authored",
            "active_profile": "authored",
            "source_style": "vrm_mtoon",
            "available_profiles": ["authored", "marmoset_pbr"],
            "profiles": {
                "authored": {"available": True},
                "marmoset_pbr": {"available": True},
            },
        },
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                "material_id": "mat_0",
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Face",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "base_texture_source": "gltf_pbr_base_color_texture",
                "normal_texture": str(normal),
                "normal_texture_source": "gltf_pbr_normal_texture",
                "roughness": 0.4,
                "metallic": 0.2,
                "shader_model": "vrm_mtoon",
                "source_shader": "VRM/MToon",
                "unlit": True,
                "pbr_available": True,
            }
        ],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=0,
        ar_tracks=[{
            "id": "milica_vrm",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
            "render": {"render_profile": "marmoset_pbr"},
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert items[0]["render_profile"] == "marmoset_pbr"
    assert items[0]["marmoset_pbr_triangle_count"] == 1
    assert "unlit" not in items[0]["pbr_triangles"][0]["maps"]
    assert diag["marmoset_pbr_triangle_count"] == 1

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    _out, draw_diag = rasterize_gpu_preview_items(base, items, settings={"camera_z": 3.0})

    assert draw_diag["pbr_sampled_triangle_count"] == 1
    assert draw_diag.get("pbr_unlit_sampled_triangle_count", 0) == 0


def test_gpu_preview_items_emit_shadow_and_reflection_catchers():
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.35, 0.12, 1.0]}],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(160, 100),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_catcher_001",
            "type": "ar_pbr_object",
            "asset_path": "catcher.fbx",
            "start_ms": 0,
            "end_ms": 1000,
            "shadow_catcher": True,
            "reflection_catcher": True,
            "render": {
                "lighting": {
                    "shadow_catcher_opacity": 0.82,
                    "shadow_catcher_softness": 0.74,
                    "shadow_catcher_matte_alpha": 0.12,
                    "reflection_catcher_opacity": 0.59,
                    "reflection_catcher_roughness": 0.78,
                    "reflection_catcher_softness": 0.67,
                    "contact_reflection_strength": 0.46,
                    "contact_reflection_falloff": 0.61,
                }
            },
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [160, 100],
            "intrinsics": {"fx": 120, "fy": 120, "cx": 80, "cy": 50},
        },
        settings={
            "asset_descriptors": {"catcher.fbx": descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["gpu_renderer"]["shadow_catcher"] == "matte_soft_contact_shadow_packet"
    assert diag["gpu_renderer"]["reflection_catcher"] == "roughness_blur_contact_reflection_packet"
    assert diag["gpu_renderer"]["reflection_quality"] == "roughness_blur_contact_reflection_packet"
    assert diag["shadow_triangle_count"] > 0
    assert diag["reflection_triangle_count"] >= 6
    assert len(items) == 1
    assert len(items[0]["shadow_vertices"]) >= 18
    assert len(items[0]["reflection_vertices"]) >= 108
    assert items[0]["catcher"]["schema"] == "tigerstudio.ar_pbr.catcher.v1"
    assert items[0]["catcher"]["shadow_catcher"]["opacity"] == 0.82
    assert items[0]["catcher"]["shadow_catcher"]["softness"] == 0.74
    assert items[0]["catcher"]["shadow_catcher"]["matte_alpha"] == 0.12
    assert items[0]["catcher"]["reflection_catcher"]["opacity"] == 0.59
    assert items[0]["catcher"]["reflection_catcher"]["roughness"] == 0.78
    assert items[0]["catcher"]["reflection_catcher"]["softness"] == 0.67
    assert items[0]["catcher"]["reflection_catcher"]["contact_reflection_strength"] == 0.46


def test_gpu_preview_applies_road_plane_anchor_placement():
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [1, 1, 0], [-1, 1, 0]],
                "triangles": [[0, 1, 2], [0, 2, 3]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.2, 0.8, 1.0, 1.0]}],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(100, 100),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_anchored",
            "type": "ar_pbr_object",
            "asset_path": "anchored.fbx",
            "start_ms": 0,
            "end_ms": 1000,
            "placement": {
                "mode": "road_plane_anchor",
                "coordinate_space": "normalized",
                "image_point": [0.5, 0.5],
            },
        }],
        camera_solution={
            "id": "cam_plane",
            "frame_size": [100, 100],
            "intrinsics": {"fx": 100, "fy": 100, "cx": 50, "cy": 50},
            "plane": {"point": [0.0, 0.0, 3.0], "normal": [0.0, 0.0, 1.0], "d": -3.0},
        },
        settings={
            "asset_descriptors": {"anchored.fbx": descriptor},
            "camera_z": 3.25,
        },
    )

    vertices = items[0]["vertices"]
    xs = vertices[0::6]
    ys = vertices[1::6]
    assert diag["placement_applied_count"] == 1
    assert diag["placements"][0]["applied"] is True
    assert abs(sum(xs) / len(xs)) < 0.05
    assert abs(sum(ys) / len(ys)) < 0.05


def test_gpu_preview_reports_coarse_depth_occlusion():
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.35, 0.12, 1.0]}],
    }
    near_depth = np.zeros((96, 96), dtype=np.float32)

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_occluded",
            "type": "ar_pbr_object",
            "asset_path": "occluded.fbx",
            "start_ms": 0,
            "end_ms": 1000,
            "occlusion": True,
            "shadow_catcher": False,
            "reflection_catcher": False,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=near_depth,
        settings={
            "asset_descriptors": {"occluded.fbx": descriptor},
            "camera_z": 3.0,
        },
    )

    assert items == []
    assert diag["visible_triangle_count"] == 0
    assert diag["occluded_triangle_count"] == 1
    assert diag["gpu_renderer"]["depth_occlusion"] == "coarse"


def test_gpu_preview_keeps_textured_pbr_triangles_for_live_depth_texture(tmp_path):
    from PIL import Image

    asset = tmp_path / "occluded_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    Image.new("RGB", (4, 4), (180, 80, 20)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"name": "BodyPaint", "base_texture": str(texture)}],
    }
    near_depth = np.zeros((96, 96), dtype=np.float32)

    items, diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=10,
        ar_tracks=[{
            "id": "ar_pbr_live_depth",
            "type": "ar_pbr_object",
            "asset_path": str(asset),
            "start_ms": 0,
            "end_ms": 1000,
            "occlusion": True,
            "shadow_catcher": False,
            "reflection_catcher": False,
        }],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=near_depth,
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert len(items) == 1
    assert diag["visible_triangle_count"] == 1
    assert diag["occluded_triangle_count"] == 0
    assert diag["pbr_triangle_count"] == 1
    assert diag["live_depth_texture_triangle_count"] == 1
    assert diag["gpu_renderer"]["depth_occlusion"] == "live_depth_texture_fragment"
    assert items[0]["depth_texture"] is not None


def test_project_player_defers_ar_pbr_to_gpu_metadata_when_qimage_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", "packet")
    asset = tmp_path / "triangle.fbx"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_gpu_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.25, 0.05, 1.0]}],
    }

    player = ProjectPlayer()
    player.set_qimage_frame_enabled(False)
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 10)

    assert out is base
    assert meta is not None
    assert "ar_pbr_items" in meta
    assert meta["ar_pbr_items"][0]["triangle_count"] == 1
    assert player._ar_pbr_last_diagnostics["mode"] == "gpu_preview"


def test_project_player_defers_ar_pbr_to_gpu_metadata_when_qimage_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", "packet")
    asset = tmp_path / "triangle_qimage.glb"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_gpu_qimage_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.2, 0.75, 1.0, 1.0]}],
    }

    player = ProjectPlayer()
    player.set_qimage_frame_enabled(True)
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 10)

    assert out is base
    assert meta is not None
    assert meta["ar_pbr_items"][0]["triangle_count"] == 1
    assert player._ar_pbr_last_diagnostics["mode"] == "gpu_preview"


def test_project_player_depth_view_mode_shows_depth_map_without_compositing(tmp_path, monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", raising=False)
    asset = tmp_path / "depth_view.glb"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_depth_view_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    track["occlusion"] = False
    player = ProjectPlayer()
    player._state = PlayerState.STOPPED
    player.set_ar_pbr_tracks([track])
    player.set_ar_pbr_depth_view_mode("depth_map")
    base = np.zeros((24, 32, 3), dtype=np.uint8)
    base[:, :, 0] = np.linspace(0, 255, 32, dtype=np.uint8)[None, :]
    base[:, :, 1] = np.linspace(255, 0, 24, dtype=np.uint8)[:, None]

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 10)

    assert meta is None
    assert out.shape == base.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, base)
    diagnostics = player._ar_pbr_last_diagnostics
    assert diagnostics["preview_renderer_selected"] == "depth_map_only"
    assert diagnostics["depth_view"]["mode"] == "matte"
    assert diagnostics["depth_view"]["near_is_white"] is True


def test_project_player_depth_view_mode_works_without_ar_pbr_tracks(monkeypatch):
    import app.depth.estimator as estimator

    def fake_estimate(frame, *, source_id="", time_ms=0, **_kwargs):
        h, w = frame.shape[:2]
        depth = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :].repeat(h, axis=0)
        return depth, {"provider": "fake", "source_id": source_id, "time_ms": time_ms}

    monkeypatch.setattr(estimator, "estimate_depth", fake_estimate)
    player = ProjectPlayer()
    player._state = PlayerState.PAUSED
    player.set_ar_pbr_depth_view_mode("depth_map")
    base = np.zeros((18, 24, 3), dtype=np.uint8)

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 33)

    assert meta is None
    assert out.shape == base.shape
    assert out.dtype == np.uint8
    assert not np.array_equal(out, base)
    diagnostics = player._ar_pbr_last_diagnostics
    assert diagnostics["preview_renderer_selected"] == "depth_map_only"
    assert diagnostics["active_track_count"] == 0
    assert diagnostics["depth_view"]["mode"] == "matte"


def test_project_player_auto_paused_uses_full_gpu_before_packet(tmp_path, monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", raising=False)
    asset = tmp_path / "tinted_triangle.glb"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_auto_gpu_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.08, 0.72, 0.95, 1.0]}],
    }

    player = ProjectPlayer()
    player._state = PlayerState.PAUSED
    player.set_qimage_frame_enabled(False)
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)
    calls = []

    def fake_full_gpu(rgb, pos_ms, *, context=None, renderer="software_pbr"):
        calls.append((renderer, int(pos_ms), bool(context)))
        player._ar_pbr_last_diagnostics = {
            "ok": True,
            "fallback": False,
            "mode": "full_model_view_gpu_export_service",
            "renderer_quality": "full_model_view_gpu_pbr",
            "rendered_track_count": 1,
        }
        out = rgb.copy()
        out[:, :, 1] = 64
        return out

    monkeypatch.setattr(player, "_composite_ar_pbr_tracks", fake_full_gpu)

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 10)

    assert meta is None
    assert out is not base
    assert int(out[0, 0, 1]) == 64
    assert calls == [("full_gpu", 10, True)]
    assert player._ar_pbr_last_diagnostics["mode"] == "full_model_view_gpu_export_service"
    assert player._ar_pbr_last_diagnostics["preview_renderer_selected"] == "full_gpu"
    assert player._ar_pbr_last_diagnostics["packet_preview_skipped"] is True


def test_project_player_auto_paused_falls_back_to_packet_when_full_gpu_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("TIGERCAPTURE_AR_PBR_PREVIEW_RENDERER", raising=False)
    asset = tmp_path / "fallback_triangle.glb"
    asset.write_bytes(b"placeholder")
    track = create_preview_ar_track(
        asset,
        track_id="ar_pbr_auto_gpu_fallback_001",
        start_ms=0,
        duration_ms=1000,
        image_point=(0.5, 0.5),
        scale=1.0,
    )
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.08, 0.72, 0.95, 1.0]}],
    }

    player = ProjectPlayer()
    player._state = PlayerState.PAUSED
    player.set_qimage_frame_enabled(False)
    player.set_ar_pbr_tracks([track])
    player._ar_pbr_asset_descriptor_cache[str(asset.resolve())] = descriptor
    base = np.zeros((96, 96, 3), dtype=np.uint8)

    def fake_full_gpu(rgb, pos_ms, *, context=None, renderer="software_pbr"):
        player._ar_pbr_last_diagnostics = {
            "ok": False,
            "fallback": True,
            "mode": "full_model_view_gpu_export_service",
            "errors": ["service unavailable"],
        }
        return rgb

    monkeypatch.setattr(player, "_composite_ar_pbr_tracks", fake_full_gpu)

    out, meta = player._apply_or_defer_ar_pbr_overlay(base, 10)

    assert out is base
    assert meta is not None
    assert "ar_pbr_items" in meta
    assert meta["ar_pbr_items"][0]["triangle_count"] == 1
    assert player._ar_pbr_last_diagnostics["preview_renderer_selected"] == "packet_fallback_after_full_gpu"
    assert player._ar_pbr_last_diagnostics["full_gpu_preview_failed"]["mode"] == "full_model_view_gpu_export_service"


def test_history_snapshot_restores_ar_pbr_tracks():
    from app.history import apply_editor_snapshot, capture_editor_snapshot

    class Player:
        def __init__(self):
            self.ar_tracks = []

        def position(self):
            return 0

        def set_position(self, _value):
            pass

        def set_ar_pbr_tracks(self, tracks):
            self.ar_tracks = list(tracks)

    class Editor:
        def __init__(self):
            self._tracks = []
            self._audio_tracks = []
            self._subtitle_panel = None
            self._active_track_id = None
            self._track_rows = {}
            self._audio_rows = {}
            self._selected_clips = []
            self._ar_pbr_tracks = [{"id": "ar_pbr_001", "asset_path": "scooter.fbx"}]
            self._player = Player()
            self.refreshes = 0

        def _refresh_player_tracks(self):
            self.refreshes += 1

        def _sync_ar_pbr_tracks_to_player(self):
            self._player.set_ar_pbr_tracks(self._ar_pbr_tracks)

    editor = Editor()
    snap = capture_editor_snapshot(editor)
    editor._ar_pbr_tracks = []

    apply_editor_snapshot(editor, snap)

    assert editor._ar_pbr_tracks == [{"id": "ar_pbr_001", "asset_path": "scooter.fbx"}]
    assert editor._player.ar_tracks == editor._ar_pbr_tracks
    assert editor.refreshes >= 1
