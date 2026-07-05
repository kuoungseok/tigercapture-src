from __future__ import annotations


def test_live2d_performance_source_framing_maps_model_view_to_transform():
    from app.live2d.actor_track import Live2DActorClip
    from app.live2d.performance_source_bridge import apply_performance_source_framing_to_clip

    clip = Live2DActorClip(pos_x=0.5, pos_y=0.55, scale=1.0)
    payload = {
        "schema": "tigerstudio.vtuber.source_framing_control.v1",
        "preset": "bust_up",
        "final": {
            "model_view": {
                "zoom": 6.64,
                "pan_x": 0.117,
                "pan_y": -1.70,
                "pan_z": 0.0,
                "camera_z": 3.25,
                "lower_occlusion_y": 0.68,
            },
            "track_rotation": [-5.08, 180.0, 0.0],
        },
    }

    result = apply_performance_source_framing_to_clip(
        clip,
        payload,
        source_path="face.mp4",
    )

    assert result["ok"] is True
    assert result["program_output"] is False
    assert clip.performance_source_path == "face.mp4"
    assert clip.performance_source_model_view["lower_occlusion_y"] == 0.68
    assert clip.performance_source_track_rotation == [-5.08, 180.0, 0.0]
    assert clip.kf_pos_x[0].value > 0.5
    assert clip.kf_pos_y[0].value == 0.55
    assert clip.kf_scale[0].value < 1.0


def test_live2d_performance_source_framing_locks_face_only_transform():
    from app.live2d.actor_track import Live2DActorClip
    from app.live2d.performance_source_bridge import apply_performance_source_framing_to_clip

    clip = Live2DActorClip(pos_x=0.48, pos_y=0.58, scale=1.2)
    payload = {
        "schema": "tigerstudio.vtuber.source_framing_control.v1",
        "subject_type": "face_only",
        "final": {
            "model_view": {
                "zoom": 10.0,
                "pan_x": 0.85,
                "pan_y": -0.40,
                "lower_occlusion_y": 0.68,
            },
        },
    }

    result = apply_performance_source_framing_to_clip(
        clip,
        payload,
        source_path="closeup.mp4",
        subject_type="face_only",
    )

    assert result["ok"] is True
    assert result["subject_type"] == "face_only"
    assert result["mapping"]["movement_constraints"]["actor_transform_locked"] is True
    assert {row.value for row in clip.kf_pos_x} == {0.48}
    assert {row.value for row in clip.kf_pos_y} == {0.58}
    assert {row.value for row in clip.kf_scale} == {1.2}
    assert clip.performance_source_subject_type == "face_only"


def test_live2d_performance_source_framing_damps_upper_body_transform():
    from app.live2d.actor_track import Live2DActorClip
    from app.live2d.performance_source_bridge import apply_performance_source_framing_to_clip

    full_clip = Live2DActorClip(pos_x=0.5, pos_y=0.55, scale=1.0)
    upper_clip = Live2DActorClip(pos_x=0.5, pos_y=0.55, scale=1.0)
    payload = {
        "schema": "tigerstudio.vtuber.source_framing_control.v1",
        "final": {
            "model_view": {
                "zoom": 9.2,
                "pan_x": 0.50,
                "pan_y": -0.80,
            },
        },
    }

    full = apply_performance_source_framing_to_clip(full_clip, payload, subject_type="full_body")
    upper = apply_performance_source_framing_to_clip(upper_clip, payload, subject_type="upper_body")

    assert full["ok"] is True
    assert upper["ok"] is True
    assert full["subject_type"] == "full_body"
    assert upper["subject_type"] == "upper_body"
    assert abs(upper_clip.kf_pos_x[0].value - 0.5) < abs(full_clip.kf_pos_x[0].value - 0.5)
    assert abs(upper_clip.kf_pos_y[0].value - 0.55) < abs(full_clip.kf_pos_y[0].value - 0.55)
    assert upper_clip.performance_source_mapping_constraints["scale_delta_limit"] == 0.02


def test_live2d_parameter_aliases_expand_common_fallback_tracks():
    from app.live2d.actor_track import Live2DActorClip
    from app.live2d.performance_source_bridge import (
        apply_live2d_parameter_aliases_to_clip,
        live2d_parameter_alias_contract,
    )

    clip = Live2DActorClip()
    clip.mocap_parameter_keyframes = {
        "ParamAngleX": [{"time_ms": 0, "value": -12.0, "curve": "smoothstep"}],
        "ParamBodyAngleY": [{"time_ms": 0, "value": 1.5, "curve": "smoothstep"}],
        "ParamBreath": [{"time_ms": 0, "value": 0.55, "curve": "smoothstep"}],
        "ParamMouthOpenY": [{"time_ms": 0, "value": 0.75, "curve": "smoothstep"}],
        "ParamEyeLOpen": [{"time_ms": 0, "value": 0.2, "curve": "smoothstep"}],
        "ParamEyeBlink": [{"time_ms": 0, "value": 0.8, "curve": "smoothstep"}],
    }

    result = apply_live2d_parameter_aliases_to_clip(clip)
    contract = live2d_parameter_alias_contract()

    assert result["ok"] is True
    assert contract["schema"] == "tigerstudio.live2d.parameter_aliases.v1"
    assert clip.mocap_parameter_keyframes["ParamHeadAngleX"][0]["value"] == -12.0
    assert clip.mocap_parameter_keyframes["ParamBodyPitch"][0]["value"] == 1.5
    assert clip.mocap_parameter_keyframes["ParamBreathing"][0]["value"] == 0.55
    assert clip.mocap_parameter_keyframes["ParamMouthOpen"][0]["value"] == 0.75
    assert clip.mocap_parameter_keyframes["ParamEyeOpenL"][0]["value"] == 0.2
    assert clip.mocap_parameter_keyframes["ParamBlink"][0]["value"] == 0.8
    assert "ParamMouthOpenY" in clip.mocap_parameter_aliases


def test_live2d_subject_type_normalization_matches_public_terms():
    from app.live2d.performance_source_bridge import normalize_performance_subject_type

    assert normalize_performance_subject_type("face_closeup") == "face_only"
    assert normalize_performance_subject_type("half-body") == "upper_body"
    assert normalize_performance_subject_type("standing") == "full_body"
    assert normalize_performance_subject_type("full_body_or_wide") == "unknown"
