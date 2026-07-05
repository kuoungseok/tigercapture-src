def test_openseeface_rows_convert_to_relative_face_motion():
    from app.vtuber.openseeface_motion import frames_from_openseeface_rows, summarize_openseeface_motion

    rows = [
        {
            "Frame": "1",
            "FPS": "10",
            "Success3D": "True",
            "Euler.X": "150",
            "Euler.Y": "0",
            "Euler.Z": "80",
            "AverageConfidence": "0.9",
            "LeftOpen": "1",
            "RightOpen": "1",
            "mouth_open": "0",
            "Landmark[0].X": "10",
            "Landmark[0].Y": "20",
            "Landmark[1].X": "30",
            "Landmark[1].Y": "50",
        },
        {
            "Frame": "2",
            "FPS": "10",
            "Success3D": "True",
            "Euler.X": "154",
            "Euler.Y": "8",
            "Euler.Z": "77",
            "AverageConfidence": "0.95",
            "LeftOpen": "0.2",
            "RightOpen": "0.5",
            "mouth_open": "0.4",
            "Landmark[0].X": "12",
            "Landmark[0].Y": "22",
            "Landmark[1].X": "32",
            "Landmark[1].Y": "52",
        },
    ]

    frames = frames_from_openseeface_rows(rows)
    summary = summarize_openseeface_motion(frames)

    assert len(frames) == 2
    assert frames[0].time_ms == 0
    assert frames[1].time_ms == 100
    assert frames[1].yaw_deg > frames[0].yaw_deg
    assert frames[1].pitch_deg > frames[0].pitch_deg
    assert frames[1].roll_deg < frames[0].roll_deg
    assert frames[1].blink_l == 0.8
    assert frames[1].blink_r == 0.5
    assert frames[1].mouth_open == 0.4
    assert frames[1].face_box == (12, 22, 20, 30)
    assert summary["drives_vrm_pose"] is True
    assert "Head" in summary["driven_channels"]


def test_openseeface_rows_skip_failed_3d_rows():
    from app.vtuber.openseeface_motion import frames_from_openseeface_rows

    frames = frames_from_openseeface_rows([
        {"Success3D": "False", "Euler.X": "1", "Euler.Y": "1", "Euler.Z": "1"},
        {"Success3D": "True", "Euler.X": "1", "Euler.Y": "1", "Euler.Z": "1"},
    ])

    assert len(frames) == 1


def test_openseeface_rows_preserve_optional_shoulder_roll_channel():
    from app.vtuber.openseeface_motion import OpenSeeFaceMotionTuning, frames_from_openseeface_rows, summarize_openseeface_motion

    rows = [
        {"Frame": "1", "FPS": "10", "Success3D": "True", "Euler.X": "0", "Euler.Y": "0", "Euler.Z": "0", "shoulder_roll_deg": "2"},
        {"Frame": "2", "FPS": "10", "Success3D": "True", "Euler.X": "0", "Euler.Y": "0", "Euler.Z": "0", "shoulder_roll_deg": "8"},
    ]

    frames = frames_from_openseeface_rows(rows, tuning=OpenSeeFaceMotionTuning(neutral_frames=1))
    summary = summarize_openseeface_motion(frames)

    assert frames[0].shoulder_roll_deg == 0.0
    assert frames[1].shoulder_roll_deg == 6.0
    assert summary["shoulder_roll_range"] == 6.0
    assert "UpperChest" in summary["driven_channels"]
