from __future__ import annotations


def test_ar_pbr_gizmo_module_projects_rotated_axes() -> None:
    from app.ar_pbr.gizmo import gizmo_geometry

    track = {
        "id": "ar_pbr_gizmo",
        "placement": {"image_point": [0.5, 0.5]},
        "transform": {
            "position": [0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "scale": [1.0, 1.0, 1.0],
        },
    }

    base = gizmo_geometry(track, 1000, 800)
    base_x = base["axes"]["x"]["vec"]

    track["transform"]["rotation"] = [0.0, 0.0, 90.0]
    rotated = gizmo_geometry(track, 1000, 800)
    rotated_x = rotated["axes"]["x"]["vec"]

    assert base_x[0] > 0.95
    assert abs(base_x[1]) < 0.05
    assert abs(rotated_x[0]) < 0.08
    assert rotated_x[1] < -0.95
    assert all(len(rotated["rings"][axis]) >= 36 for axis in ("x", "y", "z"))


def test_ar_pbr_depth_interaction_cue_restores_track_state() -> None:
    from app.ar_pbr.gizmo import begin_depth_interaction_cue, restore_depth_interaction_cue

    track = {
        "id": "ar_pbr_001",
        "occlusion": False,
        "render": {
            "lighting": {
                "depth_edge_glow_enabled": False,
                "depth_edge_glow_strength": 0.12,
                "depth_edge_glow_radius_px": 3.0,
                "depth_edge_glow_color": [0.1, 0.2, 0.3],
            },
        },
    }
    restore: dict[str, dict] = {}

    begin_depth_interaction_cue(track, restore)

    assert track["occlusion"] is True
    assert track["render"]["lighting"]["depth_edge_glow_enabled"] is True
    assert track["render"]["lighting"]["depth_edge_glow_strength"] >= 0.65
    assert track["render"]["lighting"]["depth_edge_glow_radius_px"] >= 7.0

    saved = restore.pop("ar_pbr_001")
    restore_depth_interaction_cue(track, saved)

    assert track["occlusion"] is False
    assert track["render"]["lighting"]["depth_edge_glow_enabled"] is False
    assert track["render"]["lighting"]["depth_edge_glow_strength"] == 0.12
    assert track["render"]["lighting"]["depth_edge_glow_radius_px"] == 3.0
    assert track["render"]["lighting"]["depth_edge_glow_color"] == [0.1, 0.2, 0.3]
