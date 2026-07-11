from app.vtuber.video_face_driver import FaceMotionFrame


def _frames():
    return [
        FaceMotionFrame(time_ms=0, face_box=(250, 90, 120, 90), yaw_deg=0.0, mouth_open=0.1, confidence=0.9, chin_offset_x_norm=-0.12),
        FaceMotionFrame(time_ms=100, face_box=(260, 94, 120, 90), yaw_deg=8.0, roll_deg=2.0, mouth_open=0.2, confidence=0.9, chin_offset_x_norm=-0.18),
        FaceMotionFrame(time_ms=200, face_box=(262, 96, 120, 90), yaw_deg=1.0, mouth_open=0.8, confidence=0.9, chin_offset_x_norm=-0.14),
    ]


def test_source_framing_plan_selects_requested_slots():
    from app.vtuber.source_framing_plan import build_source_framing_plan

    plan = build_source_framing_plan(_frames(), (640, 360), slots="neutral,head,mouth")

    assert plan["ok"] is True
    assert plan["schema"] == "tigerstudio.vtuber.source_framing_plan.v1"
    assert plan["selected_indices"] == [0, 1, 2]
    assert [frame["slot"] for frame in plan["selected_frames"]] == ["neutral", "head", "mouth"]
    assert plan["selected_frames"][1]["framing"]["model_view"]["auto_fit"] is False
    assert plan["selected_frames"][1]["motion"]["chin_offset_x_norm"] == -0.18


def test_source_framing_plan_matches_chest_up_source_visibility():
    from app.vtuber.source_framing_plan import build_source_framing_plan

    plan = build_source_framing_plan(_frames(), (640, 360), preset="bust_up", slots="neutral")

    assert plan["preset"] == "bust_up"
    assert plan["requested_preset"] == "bust_up"
    assert plan["source_exposure"]["source_exposure"] == "chest_up"
    assert plan["visibility_policy"]["ai_rule"] == "match_source_person_exposure_to_vrm_visibility"
    assert plan["visibility_policy"]["minimum_framing_preset"] == "bust_up"
    assert plan["visibility_policy"]["selected_framing_preset"] == "bust_up"
    assert plan["visibility_policy"]["upgraded_from_requested"] is False
    assert plan["selected_frames"][0]["framing"]["preset"] == "bust_up"
    assert plan["selected_frames"][0]["visibility_policy"]["selected_avatar_visibility"] == "head_to_mid_chest"


def test_source_framing_plan_keeps_true_upper_body_wide_enough():
    from app.vtuber.source_framing_plan import build_source_framing_plan

    plan = build_source_framing_plan(
        _frames(),
        (640, 360),
        preset="bust_up",
        slots="neutral",
        source_exposure="upper_body",
    )

    assert plan["preset"] == "half_body"
    assert plan["source_exposure"]["source_exposure"] == "upper_body"
    assert plan["visibility_policy"]["minimum_framing_preset"] == "half_body"
    assert plan["visibility_policy"]["selected_framing_preset"] == "half_body"


def test_source_framing_plan_reports_empty_motion_frames():
    from app.vtuber.source_framing_plan import build_source_framing_plan

    plan = build_source_framing_plan([], (640, 360))

    assert plan["ok"] is False
    assert "motion_frames_empty" in plan["diagnostics"]["errors"]


def test_source_framing_plan_summarizes_missing_video_fallback(tmp_path):
    from app.vtuber.source_framing_plan import build_source_framing_plan

    plan = build_source_framing_plan(_frames(), (640, 360), video_path=tmp_path / "missing.mp4")

    assert plan["ok"] is True
    assert plan["source_subject"]["ok"] is False
    assert "video_missing" in plan["source_subject"]["errors"]
    assert plan["selected_frames"][0]["framing"]["diagnostics"]["subject_source"] == "estimated_from_face"
