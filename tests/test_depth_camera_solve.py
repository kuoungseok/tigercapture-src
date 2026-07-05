import numpy as np

from app.camera_solve.cache import load_camera_solution, store_camera_solution
from app.camera_solve.solver import solve_road_plane_from_points
from app.depth.cache import depth_cache_diagnostics, depth_source_id, load_depth_frame, store_depth_frame
from app.depth.estimator import depth_backend_status, estimate_depth_from_luma


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

    payload = store_depth_frame(source_id, 120, depth, root=tmp_path)
    loaded = load_depth_frame(source_id, 120, root=tmp_path)
    report = depth_cache_diagnostics(source_id, root=tmp_path)

    assert payload["ok"] is True
    np.testing.assert_allclose(loaded, depth)
    assert report["frame_count"] == 1


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

