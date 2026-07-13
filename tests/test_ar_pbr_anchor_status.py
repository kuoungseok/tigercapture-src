from app.ar_pbr.anchor_status import ar_pbr_anchor_status


def test_ar_pbr_anchor_status_reports_manual_track():
    status = ar_pbr_anchor_status({
        "id": "manual_car",
        "placement": {"mode": "manual", "image_point": [0.5, 0.7]},
    })

    assert status["badge"] == "3D"
    assert status["tone"] == "manual"
    assert status["anchored"] is False
    assert status["tracking_enabled"] is False


def test_ar_pbr_anchor_status_reports_depth_anchor_without_tracking():
    status = ar_pbr_anchor_status({
        "id": "anchored_car",
        "placement": {"mode": "road_plane_anchor", "image_point": [0.5, 0.7]},
    })

    assert status["badge"] == "ANCH"
    assert status["tone"] == "anchored"
    assert status["anchored"] is True
    assert status["tracking_enabled"] is False


def test_ar_pbr_anchor_status_reports_scene_anchor_tracking():
    status = ar_pbr_anchor_status({
        "id": "tracked_car",
        "placement": {
            "mode": "road_plane_anchor",
            "image_point": [0.5, 0.7],
            "tracking": {"enabled": True, "template_size": [24, 24]},
        },
    })

    assert status["badge"] == "TRK"
    assert status["tone"] == "tracking"
    assert status["anchored"] is True
    assert status["tracking_enabled"] is True
