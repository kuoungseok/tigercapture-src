def test_choose_subject_candidate_prefers_box_containing_face_head_band():
    from app.vtuber.source_subject import choose_subject_candidate

    face = (270, 90, 100, 90)
    candidates = [
        (20, 20, 120, 260, 0.95, "opencv_hog_people"),
        (220, 30, 260, 320, 0.40, "opencv_haar_upperbody"),
    ]

    selected = choose_subject_candidate(candidates, (640, 360), face)

    assert selected is not None
    assert selected[:4] == (220, 30, 260, 320)


def test_subject_detector_falls_back_to_face_estimate_when_video_missing(tmp_path):
    from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames
    from app.vtuber.video_face_driver import FaceMotionFrame

    result = detect_subject_boxes_for_motion_frames(
        tmp_path / "missing.mp4",
        [FaceMotionFrame(time_ms=0, face_box=(260, 90, 120, 90))],
        source_frame_size=(640, 360),
    )

    assert result.ok is False
    assert result.frames[0].subject_box is not None
    assert result.frames[0].source == "estimated_from_face"
    assert "video_missing" in result.diagnostics["errors"]


def test_source_framing_sequence_accepts_detected_subject_boxes():
    from app.vtuber.source_framing import solve_source_framing_sequence
    from app.vtuber.video_face_driver import FaceMotionFrame

    frames = [FaceMotionFrame(time_ms=0, face_box=(270, 105, 100, 70))]
    solved = solve_source_framing_sequence(
        frames,
        (640, 360),
        subject_boxes=[(180, 20, 300, 330)],
    )

    assert solved[0].diagnostics["subject_source"] == "provided"
    assert solved[0].diagnostics["subject_box"] == [180, 20, 300, 330]


def test_foreground_subject_detector_finds_synthetic_upper_body():
    import pytest

    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.vtuber.source_subject import _detect_foreground_subject_box

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :] = (48, 56, 62)
    frame[70:335, 210:455] = (110, 82, 72)
    frame[80:180, 270:370] = (186, 150, 130)

    box = _detect_foreground_subject_box(cv2, frame, (270, 80, 100, 100))

    assert box is not None
    assert box[0] <= 215
    assert box[2] >= 220
    assert box[3] >= 240


def test_grabcut_subject_detector_finds_synthetic_upper_body():
    import pytest

    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.vtuber.source_subject import _detect_grabcut_subject_box

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :] = (44, 52, 58)
    frame[55:345, 215:455] = (30, 70, 120)
    frame[80:180, 270:370] = (190, 155, 132)
    frame[210:330, 175:250] = (220, 195, 180)
    frame[210:330, 420:495] = (220, 195, 180)

    box = _detect_grabcut_subject_box(cv2, frame, (270, 80, 100, 100))

    assert box is not None
    assert box[0] <= 220
    assert box[2] >= 200
    assert box[3] >= 250


def test_shoulder_roll_estimator_reads_slanted_upper_body_line():
    import pytest

    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.vtuber.source_subject import _estimate_shoulder_roll_from_frame

    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:, :] = (42, 48, 54)
    cv2.line(frame, (210, 178), (455, 222), (210, 220, 230), 8)

    roll = _estimate_shoulder_roll_from_frame(cv2, frame, (270, 80, 100, 100), (180, 20, 300, 330))

    assert roll is not None
    assert roll > 4.0


def test_subject_detector_can_limit_detection_to_selected_indices(tmp_path, monkeypatch):
    import pytest

    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from app.vtuber import source_subject
    from app.vtuber.video_face_driver import FaceMotionFrame

    video_path = tmp_path / "subject_scope.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (160, 90))
    for _ in range(3):
        writer.write(np.full((90, 160, 3), 52, dtype=np.uint8))
    writer.release()

    calls = []

    def fake_detect(cv2_mod, cap, time_ms, face_box, *, hog, upper_cascade, full_cascade):
        calls.append(time_ms)
        return (40, 8, 80, 76), "grabcut_subject", 0.68

    monkeypatch.setattr(source_subject, "_detect_subject_box_at_time", fake_detect)
    frames = [
        FaceMotionFrame(time_ms=0, face_box=(58, 18, 42, 30)),
        FaceMotionFrame(time_ms=100, face_box=(58, 18, 42, 30)),
        FaceMotionFrame(time_ms=200, face_box=(58, 18, 42, 30)),
    ]

    result = source_subject.detect_subject_boxes_for_motion_frames(
        video_path,
        frames,
        source_frame_size=(160, 90),
        detect_indices=[1],
    )

    assert calls == [100]
    assert result.frames[0].source == "estimated_from_face"
    assert result.frames[1].source == "grabcut_subject"
    assert result.frames[2].source == "held_previous_detection"
    assert result.diagnostics["detect_indices"] == [1]
