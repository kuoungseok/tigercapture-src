from __future__ import annotations


def test_ar_pbr_preview_pipeline_renderer_policy() -> None:
    from app.ar_pbr.preview_pipeline import normalize_preview_renderer_mode, should_use_full_gpu_preview

    assert normalize_preview_renderer_mode("gpu") == "full_gpu"
    assert normalize_preview_renderer_mode("packet_pbr") == "packet"
    assert normalize_preview_renderer_mode("software") == "software_pbr"
    assert normalize_preview_renderer_mode("disabled") == "off"
    assert normalize_preview_renderer_mode("unexpected") == "auto"
    assert should_use_full_gpu_preview("auto", playing=False) is True
    assert should_use_full_gpu_preview("auto", playing=True) is False
    assert should_use_full_gpu_preview("full_gpu", playing=True) is True
    assert should_use_full_gpu_preview("packet", playing=False) is False


def test_ar_pbr_preview_pipeline_triangle_budget_and_cache_key() -> None:
    from app.ar_pbr.preview_pipeline import gpu_packet_cache_key, gpu_preview_triangle_limit

    assert gpu_preview_triangle_limit(
        playing=False,
        preview_limit=120_000,
        playback_limit=1_000,
        preview_env="200000",
    ) == 120_000
    assert gpu_preview_triangle_limit(
        playing=True,
        preview_limit=120_000,
        playback_limit=1_000,
        playback_env="16",
    ) == 64

    descriptor = {
        "id": "asset_static",
        "mesh_count": 1,
        "material_count": 1,
        "animation_count": 0,
        "bounds": {"size": [1, 2, 3]},
    }
    context = {
        "width": 320,
        "height": 180,
        "camera_solution": {"id": "cam"},
        "depth_frame": None,
    }
    track = {"id": "ar_pbr_static", "asset_path": "asset.glb"}
    settings = {
        "asset_descriptors": {
            "ar_pbr_static": descriptor,
        },
        "camera_z": 3.25,
        "shadow_blur": 3.0,
    }

    key = gpu_packet_cache_key(
        playing=True,
        context=context,
        active_tracks=[track],
        settings=settings,
        triangle_limit=1000,
    )

    assert key is not None
    assert key[0] == "ar_pbr_gpu_packet"
    assert gpu_packet_cache_key(
        playing=False,
        context=context,
        active_tracks=[track],
        settings=settings,
        triangle_limit=1000,
    ) is None

    animated = {**descriptor, "animation_clips": [{"name": "Spin"}]}
    assert gpu_packet_cache_key(
        playing=True,
        context=context,
        active_tracks=[track],
        settings={"asset_descriptors": {"ar_pbr_static": animated}},
        triangle_limit=1000,
    ) is None
