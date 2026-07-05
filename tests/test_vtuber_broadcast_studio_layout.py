def test_vtuber_broadcast_studio_layout_exposes_program_and_studio_regions():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

    layout = build_vtuber_broadcast_studio_layout(
        source_name="trump_face_source.mp4",
        avatar_name="Milica_v1.3.vrm",
        framing_control={
            "automatic": {"model_view": {"zoom": 6.0}},
            "user_offset": {"pan_x": 0.12, "zoom_scale": 1.05},
            "final": {"model_view": {"zoom": 6.3, "pan_x": 0.12, "lower_occlusion_y": 0.68}},
        },
        tracking={
            "confidence": 0.91,
            "face_box": [266, 94, 190, 94],
            "subject_box": [176, 52, 294, 270],
            "subject_source": "grabcut_subject",
        },
        capture_ready=True,
    )

    assert layout["schema"] == "tigerstudio.vtuber.broadcast_studio_layout.v1"
    assert [region["id"] for region in layout["regions"]] == [
        "program",
        "source_tracking",
        "avatar_mapping",
        "controls",
    ]
    assert layout["regions"][0]["title"] == "Program Output"
    assert layout["program"]["composition"] == "program_background_plus_avatar"
    assert layout["program"]["performance_source_direct_output"] is False
    assert layout["performance_source"]["badge"] == "PERF"
    assert layout["performance_source"]["program_output"] is False
    assert layout["avatar_target"]["kind"] == "vrm_vseeface_bridge"
    assert layout["avatar_target"]["mapping_mode"] == "pose_stream"
    assert layout["avatar_target"]["live_target_output"] is True
    assert layout["live_target"]["target_id"] == "record_file"
    assert layout["live_target"]["label"] == "Local MP4"
    assert layout["live_target"]["performance_source_direct_output"] is False
    assert layout["diagnostics"]["live_target_program_output_only"] is True
    assert layout["diagnostics"]["live_target_consumes_project_player_program_output"] is True
    assert next(action for action in layout["operator_actions"] if action["id"] == "go_live")["label"] == "Start Local MP4"
    assert layout["program"]["lower_occlusion_y"] == 0.68
    assert layout["tracking"]["subject_source"] == "grabcut_subject"
    assert layout["diagnostics"]["automatic_framing_preserved"] is True
    assert layout["diagnostics"]["final_framing_available"] is True
    assert layout["diagnostics"]["performance_source_excluded_from_program"] is True


def test_vtuber_broadcast_studio_controls_keep_user_offset_values():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

    layout = build_vtuber_broadcast_studio_layout(
        source_name="source.mp4",
        avatar_name="avatar.vrm",
        framing_control={
            "user_offset": {"pan_x": -0.2, "pan_y": 0.1, "zoom_scale": 0.9, "lower_occlusion_y_delta": 0.04},
            "final": {"model_view": {"lower_occlusion_y": 0.72}},
        },
    )

    controls = next(region for region in layout["regions"] if region["id"] == "controls")["controls"]
    values = {control["id"]: control["value"] for control in controls}

    assert values["pan_x"] == -0.2
    assert values["pan_y"] == 0.1
    assert values["zoom_scale"] == 0.9
    assert values["lower_occlusion_y_delta"] == 0.04


def test_vtuber_broadcast_studio_uses_green_program_when_only_performance_source_active():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout
    from app.vtuber.performance_source import PROGRAM_BACKGROUND_CHROMA

    layout = build_vtuber_broadcast_studio_layout(
        source_name="trump_face_source.mp4",
        avatar_name="Milica.vrm",
        timeline_tracks=[
            {
                "label": "Performance Source",
                "kind": "vtuber_performance_source",
                "clips": [
                    {
                        "label": "trump_face_source.mp4",
                        "timeline_in_ms": 0,
                        "duration_ms": 10_000,
                        "performance_source": True,
                    }
                ],
            }
        ],
        time_ms=1_500,
    )

    assert layout["program"]["background"]["kind"] == PROGRAM_BACKGROUND_CHROMA
    assert layout["performance_source"]["active"] is True
    assert layout["performance_source"]["name"] == "trump_face_source.mp4"
    assert layout["program"]["performance_source_direct_output"] is False


def test_vtuber_broadcast_studio_marks_internal_vrm_fallback_renderer():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

    layout = build_vtuber_broadcast_studio_layout(
        source_name="trump_face_source.mp4",
        avatar_name="Milica.vrm",
        bridge_status={
            "state": "degraded",
            "ui": {"label": "Black frame"},
            "view": {
                "fallback": {
                    "active": True,
                    "mode": "internal_vrm_renderer",
                    "source_id": "internal_vrm_fallback",
                    "program_output": True,
                }
            },
        },
    )

    assert layout["program"]["renderer"] == "internal_vrm_fallback"
    assert layout["program"]["fallback"]["active"] is True
    assert layout["program"]["fallback"]["source_id"] == "internal_vrm_fallback"
    assert "internal_vrm_fallback" in layout["regions"][0]["sources"]
    assert layout["bridge"]["vseeface_optional"] is True
    assert layout["diagnostics"]["internal_vrm_fallback_active"] is True


def test_vtuber_broadcast_studio_layout_accepts_live_target_summary():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

    layout = build_vtuber_broadcast_studio_layout(
        source_name="face.mp4",
        avatar_name="avatar.vrm",
        live_target={
            "target_id": "youtube_live",
            "label": "YouTube Live",
            "output_kind": "rtmp",
            "stream_key_present": True,
        },
    )

    assert layout["live_target"]["target_id"] == "youtube_live"
    assert layout["live_target"]["label"] == "YouTube Live"
    assert layout["live_target"]["program_output"] is True
    assert layout["live_target"]["stream_key_saved"] is False
    assert next(action for action in layout["operator_actions"] if action["id"] == "go_live")["target_id"] == "youtube_live"


def test_vtuber_broadcast_studio_layout_routes_live2d_target_to_live_target():
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout
    from app.vtuber.performance_source import PROGRAM_BACKGROUND_CHROMA

    layout = build_vtuber_broadcast_studio_layout(
        source_name="upper_body_speech.mp4",
        avatar_name="character.model3.json",
        avatar_target={
            "id": "live2d:0:0",
            "kind": "live2d_actor_clip",
            "label": "Live2D Actor",
            "name": "character.model3.json",
            "path": "C:/models/character/character.model3.json",
            "direct_key_baking": True,
        },
        timeline_tracks=[
            {
                "label": "Performance Source",
                "kind": "vtuber_performance_source",
                "clips": [
                    {
                        "label": "upper_body_speech.mp4",
                        "timeline_in_ms": 0,
                        "duration_ms": 10_000,
                        "performance_source": True,
                    }
                ],
            }
        ],
        time_ms=2_000,
        live_target={"target_id": "record_file", "label": "Local MP4", "output_kind": "recording"},
    )

    assert layout["avatar_target"]["kind"] == "live2d_actor_clip"
    assert layout["avatar_target"]["mapping_mode"] == "direct_key_baking"
    assert layout["avatar_target"]["program_output"] is True
    assert layout["avatar_target"]["live_target_output"] is True
    assert layout["program"]["avatar_target"]["kind"] == "live2d_actor_clip"
    assert layout["program"]["avatar_target"]["live_target_output"] is True
    assert layout["program"]["background"]["kind"] == PROGRAM_BACKGROUND_CHROMA
    assert layout["program"]["performance_source_direct_output"] is False
    assert layout["performance_source"]["active"] is True
    assert layout["performance_source"]["program_output"] is False
    assert layout["live_target"]["label"] == "Local MP4"
    assert layout["diagnostics"]["performance_source_excluded_from_program"] is True
    assert layout["diagnostics"]["live_target_program_output_only"] is True
    assert layout["diagnostics"]["live_target_consumes_project_player_program_output"] is True
    assert layout["diagnostics"]["live2d_live_target_supported"] is True
