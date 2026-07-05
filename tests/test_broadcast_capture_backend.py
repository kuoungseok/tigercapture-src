import numpy as np


def test_broadcast_capture_backend_plan_reports_obs_free_source_support():
    from app.broadcast_capture_backend import broadcast_capture_backend_plan

    scene = {
        "id": "studio",
        "sources": [
            {"id": "bg", "type": "color", "settings": {"color": "#00ff00"}},
            {"id": "avatar", "type": "frame"},
            {"id": "logo", "type": "image", "settings": {"path": "logo.png"}},
            {"id": "cam", "type": "camera", "settings": {"device_index": 0}},
            {"id": "screen", "type": "display_capture", "settings": {"region": {"left": 0, "top": 0, "width": 640, "height": 360}}},
        ],
    }

    plan = broadcast_capture_backend_plan(
        scene,
        dependency_availability={"opencv": True, "mss": True, "pillow": True},
    )
    rows = {row["source_id"]: row for row in plan["sources"]}

    assert plan["schema"] == "tigerstudio.broadcast.capture_backend_plan.v1"
    assert plan["ok"] is True
    assert rows["bg"]["backend"] == "generated"
    assert rows["avatar"]["backend"] == "frame_map"
    assert rows["logo"]["backend"] == "image_file"
    assert rows["cam"]["backend"] == "opencv_camera"
    assert rows["screen"]["backend"] == "screen_region"


def test_resolve_broadcast_frame_map_reads_image_and_preserves_overrides():
    from app.broadcast_capture_backend import resolve_broadcast_frame_map

    avatar = np.zeros((2, 2, 4), dtype=np.uint8)
    avatar[:, :] = [255, 0, 0, 255]
    logo = np.zeros((2, 3, 3), dtype=np.uint8)
    logo[:, :] = [0, 80, 200]
    scene = {
        "sources": [
            {"id": "bg", "type": "color"},
            {"id": "avatar", "type": "frame"},
            {"id": "logo", "type": "image", "settings": {"path": "logo.png"}},
        ]
    }

    frames, diag = resolve_broadcast_frame_map(
        scene,
        frame_overrides={"avatar": avatar},
        image_reader=lambda path: logo,
    )

    assert diag["ok"] is True
    assert diag["resolved_source_count"] == 3
    assert frames["avatar"].shape == (2, 2, 4)
    assert frames["logo"][0, 0].tolist() == [0, 80, 200]


def test_composite_broadcast_frame_with_capture_resolves_screen_region():
    from app.broadcast_capture_backend import composite_broadcast_frame_with_captures

    screen = np.zeros((2, 3, 3), dtype=np.uint8)
    screen[:, :] = [20, 120, 240]
    scene = {
        "canvas": {"width": 3, "height": 2, "background": [0, 0, 0, 255]},
        "sources": [
            {
                "id": "screen",
                "type": "display_capture",
                "settings": {"region": {"left": 10, "top": 20, "width": 3, "height": 2}},
                "transform": {"x": 0, "y": 0, "width": 3, "height": 2},
            }
        ],
    }

    out, diag = composite_broadcast_frame_with_captures(
        scene,
        screen_grabber=lambda region: screen,
    )

    assert diag["ok"] is True
    assert diag["capture"]["resolved_source_count"] == 1
    assert diag["composite"]["rendered_source_count"] == 1
    assert out[0, 0].tolist() == [20, 120, 240]


def test_resolve_broadcast_frame_map_reports_missing_required_camera():
    from app.broadcast_capture_backend import resolve_broadcast_frame_map

    scene = {"sources": [{"id": "cam", "type": "camera", "settings": {"device_index": 0}}]}
    _frames, diag = resolve_broadcast_frame_map(
        scene,
        camera_reader=lambda _camera_id: np.zeros((0, 0, 3), dtype=np.uint8),
    )

    assert diag["ok"] is False
    assert diag["missing_source_count"] == 1
    assert "camera source failed" in diag["warnings"][0]
