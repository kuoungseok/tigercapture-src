import numpy as np

from app.camera_solve.cache import load_camera_solution, store_camera_solution
from app.camera_solve.solver import solve_road_plane_from_points
from app.depth.cache import (
    depth_cache_diagnostics,
    depth_source_id,
    load_depth_frame,
    load_depth_manifest,
    store_depth_frame,
)
from app.depth.estimator import depth_backend_status, estimate_depth, estimate_depth_from_luma
from app.depth.jobs import generate_depth_cache_for_frames
from app.depth.refinement import (
    build_depth_invalid_mask,
    layered_depth_matte_for_viewer,
    refine_depth_for_compositing,
)
from app.ar_pbr.depth_view import depth_frame_to_rgb


def test_synthetic_depth_estimator_returns_normalized_depth():
    frame = np.zeros((8, 10, 3), dtype=np.uint8)
    frame[:, :, 1] = 128

    depth, diag = estimate_depth_from_luma(frame, source_id="depth_test", time_ms=40)

    assert depth.shape == (8, 10)
    assert depth.dtype == np.float32
    assert 0.0 <= float(depth.min()) <= float(depth.max()) <= 1.0
    assert diag["ok"] is True
    assert diag["depth_source_id"] == "depth_test"
    assert depth_backend_status()["cloud_enabled"] is False


def test_depth_cache_roundtrip(tmp_path):
    source_id = depth_source_id("street.mp4", backend="synthetic")
    depth = np.linspace(0, 1, 12, dtype=np.float32).reshape(3, 4)

    payload = store_depth_frame(
        source_id,
        120,
        depth,
        diagnostics={"provider_id": "synthetic_luma_depth"},
        source_path="street.mp4",
        root=tmp_path,
    )
    loaded = load_depth_frame(source_id, 120, root=tmp_path)
    nearest = load_depth_frame(source_id, 150, root=tmp_path, allow_nearest_ms=40)
    report = depth_cache_diagnostics(source_id, root=tmp_path)
    manifest = load_depth_manifest(source_id, root=tmp_path)

    assert payload["ok"] is True
    np.testing.assert_allclose(loaded, depth)
    np.testing.assert_allclose(nearest, depth)
    assert report["frame_count"] == 1
    assert report["provider_id"] == "synthetic_luma_depth"
    assert manifest["frame_count"] == 1
    assert manifest["frames"][0]["time_ms"] == 120


def test_depth_provider_auto_falls_back_to_synthetic(monkeypatch):
    monkeypatch.setenv("TIGERCAPTURE_DEPTH_PROVIDER", "onnx_monocular_depth")
    monkeypatch.delenv("TIGERCAPTURE_DEPTH_ONNX_MODEL_PATH", raising=False)
    frame = np.zeros((6, 6, 3), dtype=np.uint8)

    depth, diag = estimate_depth(frame, source_id="depth_auto", time_ms=10)
    status = depth_backend_status()

    assert depth.shape == (6, 6)
    assert diag["provider_id"] == "synthetic_luma_depth"
    assert "onnx_monocular_depth" in status["capabilities"]
    assert "video_temporal_depth" in status["capabilities"]


def test_generate_depth_cache_for_frames_manifest(tmp_path):
    frame_a = np.zeros((8, 10, 3), dtype=np.uint8)
    frame_b = np.ones((8, 10, 3), dtype=np.uint8) * 96

    manifest = generate_depth_cache_for_frames(
        "clip.mp4",
        [(0, frame_a), (40, frame_b)],
        provider="synthetic_luma_depth",
        root=tmp_path,
    )

    assert manifest["ok"] is True
    assert manifest["provider_id"] == "synthetic_luma_depth"
    assert manifest["frame_count"] == 2
    loaded = load_depth_frame(manifest["depth_source_id"], 40, root=tmp_path)
    assert loaded.shape == (8, 10)


def test_video_temporal_depth_provider_wraps_base_provider():
    frame_a = np.zeros((8, 8, 3), dtype=np.uint8)
    frame_b = np.ones((8, 8, 3), dtype=np.uint8) * 64
    previous, _ = estimate_depth(frame_a, provider="synthetic_luma_depth", source_id="depth_temporal", time_ms=0)

    depth, diag = estimate_depth(
        frame_b,
        provider="video_temporal_depth",
        source_id="depth_temporal",
        time_ms=40,
        options={"previous_depth": previous, "previous_frame": frame_a},
    )

    assert depth.shape == (8, 8)
    assert diag["provider_id"] == "video_temporal_depth"
    assert diag["base_provider_id"] == "synthetic_luma_depth"
    assert diag["temporal"]["ok"] is True


def test_depth_refinement_smooths_inside_regions_without_washing_edges():
    rng = np.random.default_rng(1234)
    rgb = np.zeros((72, 96, 3), dtype=np.uint8)
    rgb[:, :] = [36, 40, 48]
    rgb[18:54, 28:68] = [226, 230, 220]
    raw = np.ones((72, 96), dtype=np.float32) * 0.78
    raw[18:54, 28:68] = 0.24
    raw += rng.normal(0.0, 0.035, raw.shape).astype(np.float32)
    raw = np.clip(raw, 0.0, 1.0)

    refined, diag = refine_depth_for_compositing(
        raw,
        rgb,
        settings={
            "edge_smooth_radius_px": 3,
            "edge_smooth_iterations": 2,
            "edge_strength": 30.0,
            "depth_sigma": 0.08,
        },
        return_diagnostics=True,
    )

    raw_inside_std = float(np.std(raw[24:48, 34:62]))
    refined_inside_std = float(np.std(refined[24:48, 34:62]))
    inside_mean = float(np.mean(refined[24:48, 34:62]))
    outside_mean = float(np.mean(refined[24:48, 8:22]))

    assert diag["ok"] is True
    assert refined_inside_std < raw_inside_std * 0.75
    assert outside_mean - inside_mean > 0.35


def test_depth_invalid_mask_detects_letterbox_like_edge_bands():
    rgb = np.ones((40, 60, 3), dtype=np.uint8) * 120
    rgb[:5, :] = 0
    rgb[-6:, :] = 255
    depth = np.linspace(0.2, 0.8, 40, dtype=np.float32)[:, None].repeat(60, axis=1)
    depth[:5, :] = 0.0
    depth[-6:, :] = 1.0

    mask, diag = build_depth_invalid_mask(depth, rgb)

    assert diag["top"] >= 5
    assert diag["bottom"] >= 6
    assert bool(mask[0, 10]) is True
    assert bool(mask[-1, 10]) is True
    assert bool(mask[20, 10]) is False


def test_depth_invalid_mask_uses_rgb_letterbox_when_depth_is_flat():
    rgb = np.ones((50, 80, 3), dtype=np.uint8) * 96
    rgb[8:42, :, 1] = np.linspace(40, 190, 34, dtype=np.uint8)[:, None]
    rgb[:8, :] = 0
    rgb[42:, :] = 0
    depth = np.ones((50, 80), dtype=np.float32) * 0.5

    mask, diag = build_depth_invalid_mask(depth, rgb)

    assert diag["video_letterbox"]["ok"] is True
    assert diag["top"] >= 8
    assert diag["bottom"] >= 8
    assert bool(mask[0, 10]) is True
    assert bool(mask[-1, 10]) is True
    assert bool(mask[25, 10]) is False


def test_layered_depth_matte_flattens_depth_into_viewer_bands():
    rgb = np.zeros((48, 64, 3), dtype=np.uint8)
    rgb[:, :32] = [40, 44, 50]
    rgb[:, 32:] = [210, 218, 224]
    depth = np.tile(np.linspace(0.1, 0.9, 64, dtype=np.float32), (48, 1))
    depth[:, 24:40] = 0.28

    layered, diag = layered_depth_matte_for_viewer(
        depth,
        rgb,
        settings={
            "viewer_smooth_radius_px": 0,
            "viewer_layer_smooth_radius_px": 0,
            "viewer_layer_count": 8,
            "viewer_layer_mix": 1.0,
        },
    )
    unique_levels = np.unique(np.round(layered, 3))

    assert diag["ok"] is True
    assert diag["mode"] == "layered_depth_matte"
    assert unique_levels.size <= 8
    assert layered.shape == depth.shape


def test_depth_view_uses_layered_refinement_when_reference_frame_is_available():
    rgb = np.zeros((32, 48, 3), dtype=np.uint8)
    rgb[:, :24] = [30, 30, 34]
    rgb[:, 24:] = [230, 230, 220]
    depth = np.tile(np.linspace(0.0, 1.0, 48, dtype=np.float32), (32, 1))

    preview, diag = depth_frame_to_rgb(
        depth,
        48,
        32,
        mode="depth_map",
        reference_frame=rgb,
        settings={"viewer_layer_count": 6, "viewer_layer_mix": 1.0},
    )

    assert preview.shape == (32, 48, 3)
    assert diag["ok"] is True
    assert diag["mode"] == "matte"
    assert diag["near_is_white"] is True
    assert diag["viewer_refinement"]["mode"] == "layered_depth_matte"
    assert diag["viewer_refinement"]["ok"] is True


def test_depth_view_matte_keeps_dark_background_subject_as_foreground():
    h, w = 90, 120
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = 60.0, 43.0
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    flower = np.zeros((h, w), dtype=bool)
    for angle in np.linspace(0.0, np.pi * 2.0, 24, endpoint=False):
        ca, sa = np.cos(angle), np.sin(angle)
        u = (xx - cx) * ca + (yy - cy) * sa
        v = -(xx - cx) * sa + (yy - cy) * ca
        petal = ((u - 18.0) / 28.0) ** 2 + (v / 4.2) ** 2 < 1.0
        flower |= petal
    center = ((xx - cx) / 16.0) ** 2 + ((yy - cy) / 13.0) ** 2 < 1.0
    flower |= center
    rgb[flower] = [238, 188, 18]
    rgb[center] = [255, 228, 54]
    shadow = flower & (((xx + yy).astype(np.int32) % 13) < 3)
    rgb[shadow] = [118, 76, 4]

    luma = (
        rgb[..., 0].astype(np.float32) * 0.2126
        + rgb[..., 1].astype(np.float32) * 0.7152
        + rgb[..., 2].astype(np.float32) * 0.0722
    ) / 255.0
    y_depth = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None].repeat(w, axis=1)
    synthetic_depth = np.clip(y_depth * 0.70 + luma * 0.30, 0.0, 1.0).astype(np.float32)

    preview, diag = depth_frame_to_rgb(
        synthetic_depth,
        w,
        h,
        mode="matte",
        reference_frame=rgb,
        settings={"viewer_layer_count": 10, "viewer_layer_mix": 1.0},
    )

    foreground_mean = float(np.mean(preview[flower]))
    foreground_std = float(np.std(preview[flower]))
    background_mean = float(np.mean(preview[~flower]))
    refinement = diag["viewer_refinement"]

    assert diag["ok"] is True
    assert refinement["foreground_prior"]["applied"] is True
    assert refinement["invalid_mask"]["top"] == 0
    assert refinement["invalid_mask"]["bottom"] == 0
    assert refinement["invalid_mask"]["left"] == 0
    assert refinement["invalid_mask"]["right"] == 0
    assert foreground_mean > 170.0
    assert foreground_std > 16.0
    assert background_mean < 60.0
    assert foreground_mean - background_mean > 130.0


def test_depth_view_matte_uses_global_dark_background_when_leaves_touch_edges():
    h, w = 96, 144
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)

    leaf_masks = []
    for cx, cy, rx, ry, tilt in [
        (20.0, 8.0, 44.0, 11.0, -0.22),
        (126.0, 26.0, 30.0, 16.0, 0.35),
        (18.0, 76.0, 34.0, 7.0, 1.02),
        (116.0, 86.0, 36.0, 8.0, -0.32),
    ]:
        ca, sa = np.cos(tilt), np.sin(tilt)
        u = (xx - cx) * ca + (yy - cy) * sa
        v = -(xx - cx) * sa + (yy - cy) * ca
        leaf_masks.append((u / rx) ** 2 + (v / ry) ** 2 < 1.0)
    leaves = np.logical_or.reduce(leaf_masks)
    rgb[leaves] = [35, 116, 21]
    rgb[leaves & (((xx + yy).astype(np.int32) % 9) < 2)] = [10, 58, 7]

    stems = (
        (np.abs(xx - (28 + yy * 0.28)) < 2.0)
        | (np.abs(xx - (54 + yy * 0.08)) < 1.8)
        | (np.abs(xx - (110 - yy * 0.22)) < 2.2)
    ) & (yy > 8)
    rgb[stems] = [28, 104, 10]

    flower = ((xx - 73.0) / 22.0) ** 2 + ((yy - 42.0) / 26.0) ** 2 < 1.0
    notch = ((xx - 86.0) / 13.0) ** 2 + ((yy - 32.0) / 16.0) ** 2 < 1.0
    flower |= notch
    rgb[flower] = [214, 9, 24]
    rgb[flower & (((xx * 1.7 + yy).astype(np.int32) % 11) < 3)] = [116, 0, 17]
    spadix = ((xx - 90.0) / 4.0) ** 2 + ((yy - 42.0) / 19.0) ** 2 < 1.0
    rgb[spadix] = [252, 216, 8]

    luma = (
        rgb[..., 0].astype(np.float32) * 0.2126
        + rgb[..., 1].astype(np.float32) * 0.7152
        + rgb[..., 2].astype(np.float32) * 0.0722
    ) / 255.0
    y_depth = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None].repeat(w, axis=1)
    synthetic_depth = np.clip(y_depth * 0.70 + luma * 0.30, 0.0, 1.0).astype(np.float32)

    preview, diag = depth_frame_to_rgb(
        synthetic_depth,
        w,
        h,
        mode="matte",
        reference_frame=rgb,
        settings={"viewer_layer_count": 10, "viewer_layer_mix": 1.0},
    )

    subject = leaves | stems | flower | spadix
    dark_background = ~subject
    bottom_background = dark_background & (yy > h * 0.72)
    foreground_prior = diag["viewer_refinement"]["foreground_prior"]

    assert diag["ok"] is True
    assert foreground_prior["applied"] is True
    assert foreground_prior["trigger"] == "global_dark_background"
    assert float(np.mean(preview[dark_background])) < 65.0
    assert float(np.mean(preview[bottom_background])) < 70.0
    assert float(np.mean(preview[flower | spadix])) > 145.0
    assert float(np.std(preview[flower | spadix])) > 12.0
    assert float(np.mean(preview[flower | spadix])) - float(np.mean(preview[dark_background])) > 95.0


def test_depth_view_distance_mode_adds_contours_for_distance_check():
    rgb = np.zeros((36, 64, 3), dtype=np.uint8)
    rgb[:, :] = [80, 82, 84]
    depth = np.tile(np.linspace(0.0, 1.0, 64, dtype=np.float32), (36, 1))

    preview, diag = depth_frame_to_rgb(depth, 64, 36, mode="distance", reference_frame=rgb)

    assert preview.shape == (36, 64, 3)
    assert diag["mode"] == "distance"
    assert diag["distance_view"]["enabled"] is True
    assert diag["distance_view"]["contour_pixel_count"] > 0


def test_depth_view_plane_mode_marks_floor_candidates():
    rgb = np.ones((48, 64, 3), dtype=np.uint8) * 96
    depth = np.tile(np.linspace(0.2, 0.8, 48, dtype=np.float32)[:, None], (1, 64))
    depth[:18, :] += np.linspace(0.0, 0.2, 64, dtype=np.float32)[None, :]
    depth = np.clip(depth, 0.0, 1.0)

    preview, diag = depth_frame_to_rgb(depth, 64, 48, mode="plane", reference_frame=rgb)

    assert preview.shape == (48, 64, 3)
    assert diag["mode"] == "plane"
    assert diag["plane_view"]["enabled"] is True
    assert diag["plane_view"]["candidate_pixel_count"] > 0


def test_road_plane_solver_from_depth_points():
    depth = np.ones((100, 100), dtype=np.float32) * 0.5
    points = [(30, 80), (70, 80), (50, 45)]

    solution, diag = solve_road_plane_from_points(
        points,
        depth_frame=depth,
        frame_size=(100, 100),
        depth_source_id="depth_001",
        time_ms=100,
    )

    assert diag["ok"] is True
    assert solution is not None
    assert solution["id"].startswith("cam_")
    assert solution["depth_source_id"] == "depth_001"
    normal = np.asarray(solution["plane"]["normal"], dtype=np.float64)
    assert abs(float(np.linalg.norm(normal)) - 1.0) < 1e-6


def test_camera_solution_cache_roundtrip(tmp_path):
    solution = {
        "id": "cam_test",
        "model": "manual_depth_plane_v1",
        "frame_size": [100, 100],
        "intrinsics": {"fx": 90.0, "fy": 90.0, "cx": 50.0, "cy": 50.0},
        "plane": {"point": [0.0, 0.0, 0.5], "normal": [0.0, 1.0, 0.0], "d": 0.0},
    }

    payload = store_camera_solution(solution, root=tmp_path)
    loaded = load_camera_solution("cam_test", root=tmp_path)

    assert payload["ok"] is True
    assert loaded == solution
