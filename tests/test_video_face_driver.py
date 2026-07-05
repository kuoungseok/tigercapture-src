def test_motion_from_center_face_box_is_neutral():
    from app.vtuber.video_face_driver import motion_from_face_box

    frame = motion_from_face_box((640, 480), (240, 160, 160, 160), time_ms=100)

    assert abs(frame.yaw_deg) < 0.01
    assert abs(frame.pitch_deg) < 0.01
    assert frame.source == "face_box"
    assert frame.confidence > 0.0


def test_motion_from_face_box_tracks_screen_offset():
    from app.vtuber.video_face_driver import motion_from_face_box

    right = motion_from_face_box((640, 480), (400, 160, 160, 160))
    left = motion_from_face_box((640, 480), (80, 160, 160, 160))
    high = motion_from_face_box((640, 480), (240, 60, 160, 160))

    assert right.yaw_deg > 0.0
    assert left.yaw_deg < 0.0
    assert high.pitch_deg > 0.0


def test_motion_from_face_box_maps_eye_count_to_blink():
    from app.vtuber.video_face_driver import motion_from_face_box

    open_eye = motion_from_face_box((640, 480), (240, 160, 160, 160), eye_count=2)
    closed_eye = motion_from_face_box((640, 480), (240, 160, 160, 160), eye_count=0)

    assert open_eye.blink_l == 0.0
    assert closed_eye.blink_l > 0.5
    assert closed_eye.blink_r > 0.5


def test_idle_motion_frame_is_low_confidence_fallback():
    from app.vtuber.video_face_driver import idle_motion_frame

    frame = idle_motion_frame(1000)

    assert frame.source == "idle_fallback"
    assert frame.confidence == 0.0
    assert frame.face_box is None


def test_motion_from_face_landmarks_extracts_mediapipe_style_values():
    from app.vtuber.video_face_driver import motion_from_face_landmarks

    points = [(0.5, 0.5)] * 478
    points[1] = (0.56, 0.50)
    points[13] = (0.50, 0.55)
    points[14] = (0.50, 0.61)
    points[33] = (0.35, 0.43)
    points[263] = (0.65, 0.45)
    points[145] = (0.40, 0.47)
    points[159] = (0.40, 0.455)
    points[374] = (0.60, 0.47)
    points[386] = (0.60, 0.455)
    points[10] = (0.50, 0.22)
    points[152] = (0.50, 0.78)
    points[234] = (0.30, 0.50)
    points[454] = (0.70, 0.50)

    frame = motion_from_face_landmarks((640, 480), points, time_ms=33)

    assert frame.source == "mediapipe_face_mesh"
    assert frame.yaw_deg > 0.0
    assert frame.mouth_open > 0.5
    assert frame.face_box is not None
    assert frame.confidence > 0.8


def test_apply_motion_tuning_calibrates_and_smooths_motion():
    from app.vtuber.video_face_driver import FaceMotionFrame, FaceMotionTuning, apply_motion_tuning

    frames = (
        FaceMotionFrame(time_ms=0, yaw_deg=10.0, pitch_deg=2.0, roll_deg=1.0, shoulder_roll_deg=1.0, mouth_open=0.2),
        FaceMotionFrame(time_ms=1000, yaw_deg=20.0, pitch_deg=4.0, roll_deg=2.0, shoulder_roll_deg=3.0, mouth_open=0.5),
    )

    tuned = apply_motion_tuning(frames, FaceMotionTuning(yaw_scale=2.0, shoulder_roll_scale=2.0, mouth_scale=2.0, smoothing=0.0, calibrate_ms=0))

    assert tuned[0].yaw_deg == 0.0
    assert tuned[1].yaw_deg == 20.0
    assert tuned[1].shoulder_roll_deg == 4.0
    assert tuned[1].mouth_open == 1.0


def test_apply_motion_tuning_can_calibrate_blink_baseline():
    from app.vtuber.video_face_driver import FaceMotionFrame, FaceMotionTuning, apply_motion_tuning

    frames = (
        FaceMotionFrame(time_ms=0, blink_l=0.68, blink_r=0.62, confidence=0.95),
        FaceMotionFrame(time_ms=1000, blink_l=0.78, blink_r=0.72, confidence=0.95),
    )

    tuned = apply_motion_tuning(
        frames,
        FaceMotionTuning(smoothing=0.0, calibrate_ms=0, calibrate_blinks=True, blink_deadzone=0.0),
    )

    assert tuned[0].blink_l == 0.0
    assert tuned[0].blink_r == 0.0
    assert 0.25 < tuned[1].blink_l < 0.35
    assert 0.25 < tuned[1].blink_r < 0.35


def test_motion_from_mediapipe_tasks_result_uses_blendshape_scores():
    from app.vtuber.video_face_driver import motion_from_mediapipe_tasks_result

    class Category:
        def __init__(self, name, score):
            self.category_name = name
            self.score = score

    class Result:
        pass

    points = [(0.5, 0.5)] * 478
    points[1] = (0.50, 0.50)
    points[13] = (0.50, 0.55)
    points[14] = (0.50, 0.57)
    points[33] = (0.35, 0.43)
    points[263] = (0.65, 0.43)
    points[145] = (0.40, 0.47)
    points[159] = (0.40, 0.455)
    points[374] = (0.60, 0.47)
    points[386] = (0.60, 0.455)
    points[10] = (0.50, 0.22)
    points[152] = (0.50, 0.78)
    points[234] = (0.30, 0.50)
    points[454] = (0.70, 0.50)
    result = Result()
    result.face_landmarks = [points]
    result.face_blendshapes = [[
        Category("jawOpen", 0.8),
        Category("eyeBlinkLeft", 0.25),
        Category("eyeBlinkRight", 0.5),
    ]]

    frame = motion_from_mediapipe_tasks_result((640, 480), result, time_ms=80)

    assert frame is not None
    assert frame.source == "mediapipe_tasks_face_landmarker"
    assert frame.mouth_open == 0.8
    assert frame.blink_l == 0.25
    assert frame.blink_r == 0.5


def test_mediapipe_tasks_backend_requires_model_when_forced(tmp_path):
    from app.vtuber.video_face_driver import VideoFaceMotionExtractor

    video = tmp_path / "input.mp4"
    video.write_bytes(b"not a real video")
    extractor = VideoFaceMotionExtractor(backend="mediapipe_tasks", face_landmarker_model=tmp_path / "missing.task")
    result = extractor.extract(video)

    assert result.ok is False
    assert "mediapipe_tasks_unavailable_or_model_missing" in result.diagnostics["errors"]
