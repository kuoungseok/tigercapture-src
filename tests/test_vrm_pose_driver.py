def test_vrm_pose_driver_maps_face_motion_to_humanoid_bones_and_blends():
    from app.vtuber.video_face_driver import FaceMotionFrame
    from app.vtuber.vrm_pose_driver import build_vrm_pose_frames, summarize_vrm_pose_frames

    frames = [
        FaceMotionFrame(time_ms=0, yaw_deg=0, pitch_deg=0, roll_deg=0, mouth_open=0.0, blink_l=0.0, blink_r=0.0),
        FaceMotionFrame(time_ms=100, yaw_deg=15, pitch_deg=-4, roll_deg=2, mouth_open=0.5, blink_l=0.2, blink_r=0.6),
    ]

    pose_frames = build_vrm_pose_frames(frames)
    summary = summarize_vrm_pose_frames(pose_frames)

    assert len(pose_frames) == 2
    assert "Head" in pose_frames[0].bones
    assert "Neck" in pose_frames[0].bones
    assert "LeftUpperArm" in pose_frames[0].bones
    assert "RightLowerArm" in pose_frames[0].bones
    assert pose_frames[1].blends["A"] == 0.5
    assert pose_frames[1].blends["Blink_R"] == 0.6
    assert summary["animated"] is True
    assert "Head" in summary["animated_bones"]
    assert "LeftUpperArm" in summary["animated_bones"]
    assert "A" in summary["animated_blends"]
    assert summary["head_rotation_range"] > 0
