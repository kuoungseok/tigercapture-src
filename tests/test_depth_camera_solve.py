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
