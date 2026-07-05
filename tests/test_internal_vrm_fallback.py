import numpy as np


def test_internal_vrm_fallback_missing_assets_returns_transparent_frame(tmp_path):
    from app.vtuber.internal_vrm_fallback import render_internal_vrm_fallback_frame

    image, diagnostics = render_internal_vrm_fallback_frame(
        {
            "id": "internal_vrm_fallback",
            "settings": {
                "avatar_vrm": str(tmp_path / "missing.vrm"),
                "descriptor_path": str(tmp_path / "missing.json"),
                "motion_csv": str(tmp_path / "missing.csv"),
            },
        },
        width=16,
        height=9,
    )

    assert image.size == (16, 9)
    assert diagnostics["ok"] is False
    assert diagnostics["requires_vseeface"] is False
    assert diagnostics["requires_virtual_camera"] is False
    assert diagnostics["quality"]["broadcast_ready"] is False
    assert "render_resolution_below_720p" in diagnostics["quality"]["claim_blockers"]
    assert diagnostics["errors"] == ["missing_internal_vrm_fallback_asset"]


def test_internal_vrm_fallback_quality_policy_marks_full_gpu_hd_as_broadcast_candidate():
    from app.vtuber.internal_vrm_fallback import internal_vrm_fallback_quality_policy

    quality = internal_vrm_fallback_quality_policy(width=1920, height=1080, renderer="full-gpu", settings={"fps": 30})

    assert quality["profile"] == "broadcast_candidate"
    assert quality["broadcast_ready"] is True
    assert quality["claim_blockers"] == []
    assert quality["frame_budget_ms"] == 1000.0 / 30.0


def test_internal_vrm_fallback_composite_suppresses_black_vseeface_source():
    from app.vtuber.internal_vrm_fallback import composite_internal_vrm_fallback_program_frame

    scene = {
        "id": "vseeface_bridge_scene",
        "canvas": {"width": 4, "height": 4, "background": [0, 255, 0, 255]},
        "sources": [
            {"id": "background", "type": "color", "z_index": 0, "settings": {"color": [0, 255, 0, 255]}},
            {
                "id": "internal_vrm_fallback",
                "type": "internal_vrm",
                "z_index": 9,
                "transform": {"x": 0, "y": 0, "width": 4, "height": 4, "fit": "stretch"},
                "settings": {"program_output": True},
            },
            {
                "id": "vseeface",
                "type": "vseeface",
                "z_index": 10,
                "transform": {"x": 0, "y": 0, "width": 4, "height": 4, "fit": "stretch"},
                "settings": {"suppress_black_frame": True},
            },
        ],
    }
    fallback = np.zeros((4, 4, 4), dtype=np.uint8)
    fallback[:, :] = [220, 80, 40, 255]
    black = np.zeros((4, 4, 3), dtype=np.uint8)

    out, diagnostics = composite_internal_vrm_fallback_program_frame(scene, fallback, vseeface_frame=black)

    assert out[1, 1, :3].tolist() == [220, 80, 40]
    rows = {row["id"]: row for row in diagnostics["sources"]}
    assert rows["internal_vrm_fallback"]["rendered"] is True
    assert rows["vseeface"]["rendered"] is False
    assert rows["vseeface"]["suppressed_black_frame"] is True
