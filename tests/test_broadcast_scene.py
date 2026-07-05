import numpy as np


def test_broadcast_scene_composites_rgba_avatar_over_background():
    from app.broadcast_scene import composite_broadcast_frame

    avatar = np.zeros((2, 2, 4), dtype=np.uint8)
    avatar[:, :] = [255, 0, 0, 128]
    scene = {
        "canvas": {"width": 4, "height": 3, "background": [0, 0, 255, 255]},
        "sources": [
            {
                "id": "avatar",
                "type": "vseeface",
                "z_index": 1,
                "transform": {"x": 1, "y": 1, "width": 2, "height": 2},
            }
        ],
    }

    out, diag = composite_broadcast_frame(scene, {"avatar": avatar})

    assert out.shape == (3, 4, 3)
    assert diag["rendered_source_count"] == 1
    assert out[0, 0].tolist() == [0, 0, 255]
    assert 120 <= int(out[1, 1, 0]) <= 130
    assert 120 <= int(out[1, 1, 2]) <= 130


def test_broadcast_scene_applies_chroma_key_to_external_source():
    from app.broadcast_scene import composite_broadcast_frame

    frame = np.zeros((2, 3, 3), dtype=np.uint8)
    frame[:, :] = [0, 255, 0]
    frame[0, 1] = [255, 0, 0]
    scene = {
        "canvas": {"width": 3, "height": 2, "background": [10, 20, 30, 255]},
        "sources": [
            {
                "id": "avatar",
                "type": "vseeface",
                "transform": {"x": 0, "y": 0, "width": 3, "height": 2},
                "chroma_key": {
                    "enabled": True,
                    "key_hue": 60,
                    "hue_range": 30,
                    "sat_min": 40,
                    "val_min": 40,
                    "spill_suppress": 0.0,
                },
            }
        ],
    }

    out, diag = composite_broadcast_frame(scene, {"avatar": frame})

    assert diag["rendered_source_count"] == 1
    assert out[1, 0].tolist() == [10, 20, 30]
    assert out[0, 1].tolist() == [255, 0, 0]


def test_broadcast_scene_can_suppress_black_capture_frame():
    from app.broadcast_scene import composite_broadcast_frame

    scene = {
        "canvas": {"width": 3, "height": 2, "background": [20, 40, 80, 255]},
        "sources": [
            {
                "id": "avatar",
                "type": "vseeface",
                "settings": {"suppress_black_frame": True},
                "transform": {"x": 0, "y": 0, "width": 3, "height": 2},
            }
        ],
    }

    out, diag = composite_broadcast_frame(scene, {"avatar": np.zeros((2, 3, 3), dtype=np.uint8)})

    assert diag["rendered_source_count"] == 0
    assert diag["skipped_source_count"] == 1
    assert diag["sources"][0]["suppressed_black_frame"] is True
    assert out[0, 0].tolist() == [20, 40, 80]


def test_broadcast_scene_reports_missing_live_sources():
    from app.broadcast_scene import broadcast_scene_diagnostics

    scene = {
        "canvas": {"width": 1280, "height": 720},
        "sources": [
            {"id": "background", "type": "color", "settings": {"color": "#000000"}},
            {"id": "vseeface", "type": "vseeface"},
            {"id": "game", "type": "window_capture"},
        ],
    }

    diag = broadcast_scene_diagnostics(scene, {"vseeface": np.zeros((1, 1, 4), dtype=np.uint8)})

    assert diag["ok"] is False
    assert diag["has_vseeface_source"] is True
    assert diag["missing_frame_sources"] == ["game"]


def test_broadcast_scene_treats_unready_vseeface_source_as_degraded_not_missing():
    from app.broadcast_scene import broadcast_scene_diagnostics

    scene = {
        "canvas": {"width": 1280, "height": 720},
        "sources": [
            {"id": "background", "type": "color", "settings": {"color": "#000000"}},
            {
                "id": "vseeface",
                "type": "vseeface",
                "settings": {
                    "capture_ready": False,
                    "capture_status": "virtual_camera_black_frame",
                },
            },
        ],
    }

    diag = broadcast_scene_diagnostics(scene, {})

    assert diag["ok"] is True
    assert diag["missing_frame_sources"] == []
    assert diag["degraded_frame_sources"] == ["vseeface"]


def test_default_vseeface_bridge_scene_has_avatar_and_audio_channels():
    from app.broadcast_scene import create_vseeface_bridge_scene

    scene = create_vseeface_bridge_scene(width=1280, height=720, fps=60.0)
    payload = scene.to_dict()

    assert payload["canvas"]["width"] == 1280
    assert payload["canvas"]["height"] == 720
    assert payload["canvas"]["fps"] == 60.0
    assert [source["id"] for source in payload["sources"]] == ["background", "vseeface"]
    assert payload["sources"][1]["settings"]["suppress_black_frame"] is True
    assert [channel["id"] for channel in payload["audio"]] == ["mic", "desktop"]
