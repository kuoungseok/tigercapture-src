def test_summarize_motion_frames_reports_core_channels():
    from app.vtuber.motion_quality import summarize_motion_frames
    from app.vtuber.video_face_driver import FaceMotionFrame

    frames = [
        FaceMotionFrame(time_ms=0, yaw_deg=0.0, mouth_open=0.02, blink_l=0.0, blink_r=0.0, confidence=0.95, source="test"),
        FaceMotionFrame(time_ms=500, yaw_deg=6.0, mouth_open=0.42, blink_l=0.0, blink_r=0.8, confidence=0.90, source="test"),
    ]

    summary = summarize_motion_frames(frames)

    assert summary["ok"] is True
    assert summary["frame_count"] == 2
    assert summary["duration_ms"] == 500
    assert summary["source_counts"] == {"test": 2}
    assert summary["channels"]["yaw_deg"]["range"] == 6.0
    assert summary["channels"]["mouth_open"]["max"] == 0.42
    assert summary["checks"]["head_motion"] is True
    assert summary["checks"]["mouth_motion"] is True
    assert summary["checks"]["blink_motion"] is True
    assert summary["checks"]["confidence_ok"] is True


def test_representative_frame_indices_are_stable():
    from app.vtuber.motion_quality import representative_frame_indices

    assert representative_frame_indices(0) == []
    assert representative_frame_indices(1, 3) == [0]
    assert representative_frame_indices(76, 4) == [0, 25, 50, 75]
