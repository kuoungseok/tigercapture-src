def test_source_framing_maps_face_size_to_zoom():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.video_face_driver import FaceMotionFrame

    far = FaceMotionFrame(time_ms=0, face_box=(270, 105, 100, 70))
    near = FaceMotionFrame(time_ms=0, face_box=(220, 75, 200, 140))

    far_solution = solve_source_framing(far, (640, 360))
    near_solution = solve_source_framing(near, (640, 360))

    assert far_solution.ok is True
    assert near_solution.ok is True
    assert near_solution.model_view["zoom"] > far_solution.model_view["zoom"]
    assert near_solution.model_view["auto_fit"] is False
    assert near_solution.diagnostics["subject_source"] == "estimated_from_face"
    assert near_solution.source_subject_size[1] > near_solution.source_face_size[1]


def test_source_framing_tracks_source_screen_offset():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.video_face_driver import FaceMotionFrame

    center = solve_source_framing(FaceMotionFrame(face_box=(270, 105, 100, 70)), (640, 360))
    right_high = solve_source_framing(FaceMotionFrame(face_box=(390, 45, 100, 70)), (640, 360))

    assert right_high.model_view["pan_x"] > center.model_view["pan_x"]
    assert right_high.model_view["pan_y"] > center.model_view["pan_y"]
    assert right_high.track_rotation[0] > center.track_rotation[0]


def test_source_framing_sequence_smooths_large_jumps():
    from app.vtuber.source_framing import solve_source_framing, solve_source_framing_sequence
    from app.vtuber.video_face_driver import FaceMotionFrame

    frames = (
        FaceMotionFrame(time_ms=0, face_box=(270, 105, 100, 70)),
        FaceMotionFrame(time_ms=33, face_box=(430, 45, 180, 130)),
    )

    raw_second = solve_source_framing(frames[1], (640, 360))
    smoothed = solve_source_framing_sequence(frames, (640, 360), smoothing=0.5)

    assert len(smoothed) == 2
    assert smoothed[1].model_view["pan_x"] < raw_second.model_view["pan_x"]
    assert smoothed[1].model_view["zoom"] < raw_second.model_view["zoom"]
    assert smoothed[1].diagnostics["smoothing"] == 0.5


def test_source_framing_uses_provided_subject_box_when_available():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.video_face_driver import FaceMotionFrame

    frame = FaceMotionFrame(face_box=(270, 105, 100, 70))
    estimated = solve_source_framing(frame, (640, 360))
    provided = solve_source_framing(frame, (640, 360), subject_box=(200, 20, 260, 320))

    assert provided.diagnostics["subject_source"] == "provided"
    assert provided.diagnostics["subject_box"] == [200, 20, 260, 320]
    assert provided.source_subject_size[1] > estimated.source_subject_size[1]


def test_source_framing_exposes_lower_occlusion_guidance():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.video_face_driver import FaceMotionFrame

    frame = FaceMotionFrame(face_box=(266, 94, 190, 94))

    bust = solve_source_framing(frame, (640, 360), preset="bust_up")
    full = solve_source_framing(frame, (640, 360), preset="full_body")

    assert 0.5 < bust.model_view["lower_occlusion_y"] < 0.8
    assert full.model_view["lower_occlusion_y"] == 1.0


def test_source_exposure_policy_matches_vrm_visibility():
    from app.vtuber.source_framing import (
        classify_source_exposure_for_framing,
        vrm_visibility_policy_for_source_exposure,
    )
    from app.vtuber.video_face_driver import FaceMotionFrame

    chest = vrm_visibility_policy_for_source_exposure("chest_up", requested_preset="bust_up")
    upper = vrm_visibility_policy_for_source_exposure("upper_body", requested_preset="bust_up")
    full = vrm_visibility_policy_for_source_exposure("full_body", requested_preset="half_body")

    assert chest["ai_rule"] == "match_source_person_exposure_to_vrm_visibility"
    assert chest["minimum_framing_preset"] == "bust_up"
    assert chest["selected_framing_preset"] == "bust_up"
    assert chest["selected_avatar_visibility"] == "head_to_mid_chest"
    assert upper["ai_rule"] == "match_source_person_exposure_to_vrm_visibility"
    assert upper["minimum_framing_preset"] == "half_body"
    assert upper["selected_framing_preset"] == "half_body"
    assert upper["upgraded_from_requested"] is True
    assert full["minimum_framing_preset"] == "full_body"
    assert full["selected_framing_preset"] == "full_body"

    exposure = classify_source_exposure_for_framing(
        [FaceMotionFrame(face_box=(280, 70, 52, 40))],
        (640, 360),
        subject_boxes=[(220, 12, 180, 340)],
    )

    assert exposure["source_exposure"] == "full_body"
    assert exposure["raw_profile"] == "full_body"


def test_estimated_upper_body_box_is_clipped_to_frame():
    from app.vtuber.source_framing import estimate_upper_body_box_from_face_box

    box = estimate_upper_body_box_from_face_box((640, 360), (10, 5, 180, 110))

    assert box[0] == 0
    assert box[1] == 0
    assert box[2] > 180
    assert box[3] <= 360


def test_source_framing_has_stable_fallback_without_face_box():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.video_face_driver import FaceMotionFrame

    solution = solve_source_framing(FaceMotionFrame(time_ms=10), (640, 360))

    assert solution.ok is False
    assert solution.model_view["auto_fit"] is False
    assert solution.diagnostics["reason"] == "face_box_missing"


def test_openseeface_frame_size_from_rows_and_csv(tmp_path):
    from app.vtuber.openseeface_motion import load_openseeface_frame_size_csv
    from app.vtuber.source_framing import frame_size_from_openseeface_rows

    assert frame_size_from_openseeface_rows([{"Width": "640", "Height": "360"}]) == (640, 360)

    csv_path = tmp_path / "face.csv"
    csv_path.write_text("Frame,Width,Height\n1,1280,720\n", encoding="utf-8")

    assert load_openseeface_frame_size_csv(csv_path) == (1280, 720)
