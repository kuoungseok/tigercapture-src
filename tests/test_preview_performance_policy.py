from __future__ import annotations


def test_preview_policy_marks_4k60_for_scaled_auto_decode():
    from app.preview_performance_policy import preview_performance_policy_from_metadata

    policy = preview_performance_policy_from_metadata(
        width=3840,
        height=2160,
        fps=60.0,
        codec="av1",
        path="4k60.mp4",
    )

    assert policy["decoder_auto"] is True
    assert policy["needs_monitoring_scale"] is True
    assert policy["needs_proxy"] is True
    assert policy["preview_height"] == 540
    assert policy["frame_drop_allowed"] is True
    assert policy["export_uses_original"] is True
    assert "high_resolution" in policy["reasons"]
    assert "high_fps" in policy["reasons"]


def test_preview_policy_uses_720p_monitoring_for_4k30():
    from app.preview_performance_policy import preview_performance_policy_from_metadata

    policy = preview_performance_policy_from_metadata(
        width=3840,
        height=2160,
        fps=29.97,
        codec="h264",
    )

    assert policy["decoder_auto"] is True
    assert policy["needs_monitoring_scale"] is True
    assert policy["needs_proxy"] is False
    assert policy["preview_height"] == 720
    assert policy["export_uses_original"] is True


def test_preview_policy_respects_explicit_preview_height():
    from app.preview_performance_policy import preview_performance_policy_from_metadata

    policy = preview_performance_policy_from_metadata(
        width=3840,
        height=2160,
        fps=60.0,
        codec="hevc",
        requested_preview_height=360,
    )

    assert policy["preview_height"] == 360
    assert policy["needs_monitoring_scale"] is True
    assert "monitoring_scale:360p" in policy["reasons"]


def test_preview_policy_quality_modes_control_monitoring_height_and_drop():
    from app.preview_performance_policy import preview_performance_policy_from_metadata

    performance = preview_performance_policy_from_metadata(
        width=3840,
        height=2160,
        fps=60.0,
        quality_mode="performance",
    )
    quality = preview_performance_policy_from_metadata(
        width=3840,
        height=2160,
        fps=60.0,
        quality_mode="quality",
    )

    assert performance["quality_mode"] == "performance"
    assert performance["preview_height"] == 540
    assert performance["frame_drop_allowed"] is True
    assert quality["quality_mode"] == "quality"
    assert quality["preview_height"] == 0
    assert quality["needs_monitoring_scale"] is False
    assert quality["frame_drop_allowed"] is False
