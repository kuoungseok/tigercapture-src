from app.vtuber.video_face_driver import FaceMotionFrame


def test_framing_user_offset_preserves_automatic_and_changes_final_view():
    from app.vtuber.source_framing import solve_source_framing
    from app.vtuber.source_framing_control import apply_framing_user_offset

    auto = solve_source_framing(FaceMotionFrame(time_ms=120, face_box=(266, 94, 190, 94)), (640, 360))
    controlled = apply_framing_user_offset(
        auto,
        {
            "pan_x": 0.1,
            "pan_y": -0.2,
            "zoom_scale": 1.1,
            "lower_occlusion_y_delta": -0.05,
        },
    )

    assert controlled["schema"] == "tigerstudio.vtuber.source_framing_control.v1"
    assert controlled["automatic"]["model_view"]["pan_x"] == auto.model_view["pan_x"]
    assert controlled["final"]["model_view"]["pan_x"] > auto.model_view["pan_x"]
    assert controlled["final"]["model_view"]["pan_y"] < auto.model_view["pan_y"]
    assert controlled["final"]["model_view"]["zoom"] > auto.model_view["zoom"]
    assert controlled["final"]["model_view"]["lower_occlusion_y"] < auto.model_view["lower_occlusion_y"]


def test_source_framing_plan_includes_final_framing_with_user_offset():
    from app.vtuber.source_framing_plan import build_source_framing_plan

    frames = [FaceMotionFrame(time_ms=0, face_box=(266, 94, 190, 94))]
    plan = build_source_framing_plan(frames, (640, 360), slots="neutral", user_offset={"pan_x": 0.2})

    selected = plan["selected_frames"][0]
    assert selected["framing"]["model_view"]["pan_x"] != selected["final_framing"]["model_view"]["pan_x"]
    assert selected["framing_control"]["user_offset"]["pan_x"] == 0.2


def test_live_framing_dead_zone_keeps_small_camera_jitter_stable():
    from app.vtuber.source_framing_control import update_live_source_framing

    first = update_live_source_framing(
        FaceMotionFrame(time_ms=0, face_box=(266, 94, 190, 94)),
        (640, 360),
        config={"min_update_interval_ms": 0, "dead_zone_pan": 0.05},
    )
    second = update_live_source_framing(
        FaceMotionFrame(time_ms=80, face_box=(268, 94, 190, 94)),
        (640, 360),
        previous_state=first["state"],
        config={"min_update_interval_ms": 0, "dead_zone_pan": 0.05},
    )

    assert second["schema"] == "tigerstudio.vtuber.source_framing_live.v1"
    assert second["state"]["model_view"]["pan_x"] == first["state"]["model_view"]["pan_x"]


def test_live_framing_lock_keeps_previous_view_but_applies_new_user_offset():
    from app.vtuber.source_framing_control import update_live_source_framing

    first = update_live_source_framing(
        FaceMotionFrame(time_ms=0, face_box=(266, 94, 190, 94)),
        (640, 360),
        config={"min_update_interval_ms": 0},
    )
    locked = update_live_source_framing(
        FaceMotionFrame(time_ms=120, face_box=(420, 70, 190, 94)),
        (640, 360),
        previous_state=first["state"],
        user_offset={"pan_x": 0.15},
        config={"lock_framing": True, "min_update_interval_ms": 0},
    )

    assert locked["state"]["locked"] is True
    assert locked["state"]["model_view"]["pan_x"] == first["state"]["model_view"]["pan_x"]
    assert locked["final"]["model_view"]["pan_x"] > first["state"]["model_view"]["pan_x"]


def test_live_framing_throttles_updates_before_interval():
    from app.vtuber.source_framing_control import update_live_source_framing

    first = update_live_source_framing(FaceMotionFrame(time_ms=100, face_box=(266, 94, 190, 94)), (640, 360))
    throttled = update_live_source_framing(
        FaceMotionFrame(time_ms=110, face_box=(420, 70, 190, 94)),
        (640, 360),
        previous_state=first["state"],
        config={"min_update_interval_ms": 33},
    )

    assert throttled["state"]["update_throttled"] is True
    assert throttled["state"]["model_view"]["pan_x"] == first["state"]["model_view"]["pan_x"]
