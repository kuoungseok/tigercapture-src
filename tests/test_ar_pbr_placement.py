import numpy as np

from app.ar_pbr.compositor import composite_preview_frame
from app.ar_pbr.placement import camera_ray_from_image_point, intersect_ray_plane, resolve_track_placement
from app.ar_pbr.scene_anchor import promote_track_to_scene_anchor, road_plane_sample_points, update_scene_anchor_for_frame
from app.ar_pbr.schema import normalize_ar_track


def _draw_tracking_patch(frame, *, center, scale=1.0, rotation_deg=0.0):
    try:
        import cv2
    except Exception:
        return False
    patch = np.zeros((24, 24, 3), dtype=np.uint8)
    patch[4:20, 5:9] = [245, 245, 245]
    patch[15:19, 5:20] = [210, 210, 210]
    patch[5:11, 14:20] = [150, 150, 150]
    size = max(8, int(round(24 * float(scale))))
    patch = cv2.resize(patch, (size, size), interpolation=cv2.INTER_LINEAR)
    if abs(float(rotation_deg)) > 1e-6:
        matrix = cv2.getRotationMatrix2D((size * 0.5, size * 0.5), float(rotation_deg), 1.0)
        patch = cv2.warpAffine(patch, matrix, (size, size), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))
    cx, cy = int(center[0]), int(center[1])
    x0 = max(0, cx - size // 2)
    y0 = max(0, cy - size // 2)
    x1 = min(frame.shape[1], x0 + size)
    y1 = min(frame.shape[0], y0 + size)
    px1 = x1 - x0
    py1 = y1 - y0
    frame[y0:y1, x0:x1] = np.maximum(frame[y0:y1, x0:x1], patch[:py1, :px1])
    return True


def _camera_solution():
    return {
        "id": "cam_plane",
        "frame_size": [100, 100],
        "intrinsics": {"fx": 100.0, "fy": 100.0, "cx": 50.0, "cy": 50.0},
        "plane": {
            "point": [0.0, 0.0, 3.0],
            "normal": [0.0, 0.0, 1.0],
            "d": -3.0,
        },
    }


def _triangle_descriptor():
    return {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.2, 0.05, 1.0]}],
    }


def test_camera_ray_from_center_points_forward():
    _, direction = camera_ray_from_image_point((50, 50), _camera_solution(), frame_size=(100, 100))

    np.testing.assert_allclose(direction, [0.0, 0.0, 1.0])


def test_intersect_ray_plane_returns_camera_space_point():
    origin, direction = camera_ray_from_image_point((50, 50), _camera_solution(), frame_size=(100, 100))
    hit = intersect_ray_plane(origin, direction, _camera_solution()["plane"])

    assert hit == (0.0, 0.0, 3.0)


def test_resolve_track_placement_writes_renderer_transform():
    track = normalize_ar_track({
        "id": "placed",
        "asset_path": "car.fbx",
        "placement": {
            "mode": "road_plane_anchor",
            "image_point": [50, 50],
        },
    })

    resolved, diag = resolve_track_placement(
        track,
        _camera_solution(),
        frame_size=(100, 100),
        settings={"camera_z": 3.25},
    )

    assert diag["applied"] is True
    np.testing.assert_allclose(diag["camera_space_point"], [0.0, 0.0, 3.0])
    np.testing.assert_allclose(resolved["transform"]["position"], [0.0, 0.0, -0.25])


def test_software_renderer_applies_road_plane_anchor():
    base = np.zeros((100, 100, 3), dtype=np.uint8)
    track = normalize_ar_track({
        "id": "placed",
        "asset_path": "car.fbx",
        "placement": {
            "mode": "road_plane_anchor",
            "image_point": [50, 50],
        },
    })

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[track],
        camera_solution=_camera_solution(),
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {"car.fbx": _triangle_descriptor()},
            "camera_z": 3.25,
            "shadow_blur": 0,
        },
    )

    assert diag["mode"] == "software_pbr"
    assert diag["software_renderer"]["placement_applied_count"] == 1
    assert diag["software_renderer"]["placements"][0]["renderer_position"] == [0.0, 0.0, -0.25]
    assert out.sum() > 0


def test_scene_anchor_promotes_manual_track_from_preview_frame(tmp_path):
    frame = np.zeros((80, 120, 3), dtype=np.uint8)
    frame[:, :, 1] = np.linspace(40, 220, 80, dtype=np.uint8)[:, None]
    track = normalize_ar_track({
        "id": "placed",
        "asset_path": "car.fbx",
        "placement": {
            "mode": "manual",
            "image_point": [0.5, 0.68],
            "coordinate_space": "normalized",
        },
        "transform": {
            "position": [0.0, -0.72, 0.0],
            "rotation": [0.0, 18.0, 0.0],
            "scale": [1.4, 1.4, 1.4],
        },
    })

    anchored, diag = promote_track_to_scene_anchor(
        track,
        frame,
        time_ms=120,
        source_id="unit_test_scene",
        store_caches=False,
    )

    assert diag["ok"] is True
    assert anchored["placement"]["mode"] == "road_plane_anchor"
    assert anchored["placement"]["anchor_world"]
    assert anchored["camera_solution"]["plane"]["normal"]
    assert anchored["camera_solution_id"].startswith("cam_")
    assert anchored["depth_source_id"].startswith("depth_")
    assert anchored["transform"]["position"] == [0.0, 0.0, 0.0]
    assert anchored["transform"]["scale"] == [1.4, 1.4, 1.4]
    assert "probe_templates" in anchored["placement"]["tracking"]


def test_road_plane_sample_points_are_clamped_to_frame():
    points = road_plane_sample_points((0.02, 0.98), (100, 50))

    assert len(points) == 3
    assert all(0.0 <= x <= 99.0 and 0.0 <= y <= 49.0 for x, y in points)


def test_scene_anchor_runtime_tracking_updates_image_point():
    frame = np.zeros((96, 128, 3), dtype=np.uint8)
    frame[:, :, 1] = 40
    frame[54:68, 44:58] = [240, 240, 240]
    track = normalize_ar_track({
        "id": "placed",
        "asset_path": "car.fbx",
        "placement": {
            "mode": "manual",
            "image_point": [51 / 128, 61 / 96],
            "coordinate_space": "normalized",
        },
    })
    anchored, diag = promote_track_to_scene_anchor(
        track,
        frame,
        time_ms=0,
        source_id="tracking_test",
        store_caches=False,
    )
    assert diag["ok"] is True

    shifted = np.zeros_like(frame)
    shifted[:, :, 1] = 40
    shifted[54:68, 62:76] = [240, 240, 240]
    updated, depth, solution, runtime_diag = update_scene_anchor_for_frame(
        anchored,
        shifted,
        time_ms=33,
        source_id="tracking_test",
    )

    assert runtime_diag["ok"] is True
    assert depth is not None
    assert solution is not None
    assert updated["placement"]["mode"] == "road_plane_anchor"
    assert updated["placement"]["image_point"][0] > anchored["placement"]["image_point"][0] + 0.05


def test_scene_anchor_runtime_tracking_updates_scale_and_rotation():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[:, :, 1] = 35
    if not _draw_tracking_patch(frame, center=(68, 76), scale=1.0, rotation_deg=0.0):
        return
    track = normalize_ar_track({
        "id": "placed",
        "asset_path": "car.fbx",
        "placement": {
            "mode": "manual",
            "image_point": [68 / 160, 76 / 120],
            "coordinate_space": "normalized",
        },
        "transform": {
            "position": [0.0, -0.72, 0.0],
            "rotation": [0.0, 8.0, 3.0],
            "scale": [1.2, 1.2, 1.2],
        },
    })
    anchored, diag = promote_track_to_scene_anchor(
        track,
        frame,
        time_ms=0,
        source_id="affine_tracking_test",
        store_caches=False,
    )
    assert diag["ok"] is True

    shifted = np.zeros_like(frame)
    shifted[:, :, 1] = 35
    _draw_tracking_patch(shifted, center=(87, 76), scale=1.22, rotation_deg=18.0)
    updated, depth, solution, runtime_diag = update_scene_anchor_for_frame(
        anchored,
        shifted,
        time_ms=33,
        source_id="affine_tracking_test",
    )

    assert runtime_diag["ok"] is True
    assert depth is not None
    assert solution is not None
    assert updated["placement"]["image_point"][0] > anchored["placement"]["image_point"][0] + 0.07
    assert runtime_diag["tracking"]["scale"] > 1.05
    assert abs(runtime_diag["tracking"]["rotation_deg"]) >= 9.0
    assert runtime_diag["tracking"]["multi_probe"]["ok"] is True
    assert runtime_diag["tracking"]["multi_probe"]["matched_probe_count"] >= 3
    assert runtime_diag["slam_assist"]["mode"] == "template_depth_plane_slam_assist"
    assert runtime_diag["slam_assist"]["translation_px"][0] > 10.0
    assert abs(runtime_diag["slam_assist"]["roll_deg"]) >= 9.0
    assert "not_full_slam" in runtime_diag["slam_assist"]["limits"]
    assert updated["camera_motion_hint"]["mode"] == "template_depth_plane_slam_assist"
    assert updated["transform"]["scale"][0] > anchored["transform"]["scale"][0] * 1.05
    assert abs(updated["transform"]["rotation"][2] - anchored["transform"]["rotation"][2]) >= 9.0
