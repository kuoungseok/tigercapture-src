from app.actor_mocap import (
    apply_live2d_mocap_payload_to_clip,
    live2d_mocap_payload_from_frames,
    live2d_mocap_user_summary,
)
from app.live2d.actor_track import Live2DActorClip, Live2DActorTrack
from app.project_io import _actor_track_to_dict, _live2d_actor_track_from_dict


def test_live2d_mocap_payload_from_frames_builds_transform_and_parameter_keys():
    frames = [
        {"time_ms": 0, "x_norm": 0.42, "y_norm": 0.50, "w_norm": 0.18, "h_norm": 0.24},
        {"time_ms": 180, "x_norm": 0.50, "y_norm": 0.46, "w_norm": 0.20, "h_norm": 0.26},
        {"time_ms": 360, "x_norm": 0.61, "y_norm": 0.44, "w_norm": 0.25, "h_norm": 0.30},
    ]

    payload = live2d_mocap_payload_from_frames(
        frames,
        source_path="take.mp4",
        duration_ms=500,
    )

    assert payload["ok"] is True
    assert payload["kind"] == "live2d_video_mocap"
    assert payload["source_path"].endswith("take.mp4")
    assert payload["duration_ms"] == 500
    assert payload["capabilities"]["video_file_offline"] is True
    assert payload["transform_keyframes"]["pos_x"]
    assert payload["transform_keyframes"]["pos_y"]
    assert payload["transform_keyframes"]["scale"]
    assert payload["parameter_keyframes"]["ParamAngleX"]
    assert payload["parameter_keyframes"]["ParamAngleY"]
    assert payload["parameter_keyframes"]["ParamBodyAngleY"]
    assert payload["parameter_keyframes"]["ParamBreath"]
    assert payload["capabilities"]["mouth_eye_detail"] is False
    assert payload["retargeting"]["profile"] == "talking_head_stabilized"


def test_live2d_mocap_talking_head_scale_is_stabilized():
    payload = live2d_mocap_payload_from_frames(
        [
            {"time_ms": 0, "x_norm": 0.50, "y_norm": 0.50, "w_norm": 0.19, "h_norm": 0.24},
            {"time_ms": 120, "x_norm": 0.505, "y_norm": 0.49, "w_norm": 0.29, "h_norm": 0.35},
            {"time_ms": 240, "x_norm": 0.495, "y_norm": 0.51, "w_norm": 0.18, "h_norm": 0.23},
            {"time_ms": 360, "x_norm": 0.50, "y_norm": 0.50, "w_norm": 0.30, "h_norm": 0.36},
            {"time_ms": 480, "x_norm": 0.502, "y_norm": 0.50, "w_norm": 0.20, "h_norm": 0.25},
        ],
        source_path="speech.mp4",
        duration_ms=500,
    )

    scale_values = [row["value"] for row in payload["transform_keyframes"]["scale"]]
    pos_x_values = [row["value"] for row in payload["transform_keyframes"]["pos_x"]]
    body_values = [row["value"] for row in payload["parameter_keyframes"]["ParamBodyAngleX"]]

    assert max(scale_values) - min(scale_values) <= 0.01
    assert max(pos_x_values) - min(pos_x_values) <= 0.01
    assert max(abs(value) for value in body_values) <= 1.0


def test_live2d_mocap_face_closeup_locks_actor_transform():
    payload = live2d_mocap_payload_from_frames(
        [
            {"time_ms": 0, "x_norm": 0.35, "y_norm": 0.50, "w_norm": 0.34, "h_norm": 0.42},
            {"time_ms": 160, "x_norm": 0.50, "y_norm": 0.47, "w_norm": 0.36, "h_norm": 0.44},
            {"time_ms": 320, "x_norm": 0.65, "y_norm": 0.53, "w_norm": 0.35, "h_norm": 0.43},
        ],
        source_path="closeup.mp4",
        duration_ms=500,
    )

    retargeting = payload["retargeting"]
    assert retargeting["shot_profile"] == "face_closeup"
    assert retargeting["movement_constraints"]["actor_transform_locked"] is True
    assert retargeting["actor_motion_scale"] == 0.0
    assert retargeting["actor_scale_gain"] == 0.0

    assert {row["value"] for row in payload["transform_keyframes"]["pos_x"]} == {0.5}
    assert {row["value"] for row in payload["transform_keyframes"]["pos_y"]} == {0.55}
    assert {row["value"] for row in payload["transform_keyframes"]["scale"]} == {1.0}
    assert {row["value"] for row in payload["parameter_keyframes"]["ParamBodyAngleX"]} == {0.0}
    assert payload["parameter_keyframes"]["ParamAngleX"]
    assert any(event["kind"] == "shot_profile_classified" for event in payload["events"])

    summary = live2d_mocap_user_summary(payload)
    assert summary["ok"] is True
    assert summary["movement_mode"] == "face_only_locked_transform"
    assert summary["actor_transform_locked"] is True
    assert "actor position/scale locked" in summary["status_line"]
    assert "head angle" in summary["driven_channels"]


def test_live2d_mocap_upper_body_person_box_damps_transform():
    payload = live2d_mocap_payload_from_frames(
        [
            {
                "time_ms": 0,
                "x_norm": 0.34,
                "y_norm": 0.42,
                "w_norm": 0.15,
                "h_norm": 0.20,
                "person_x_norm": 0.48,
                "person_y_norm": 0.45,
                "person_w_norm": 0.42,
                "person_h_norm": 0.58,
            },
            {
                "time_ms": 200,
                "x_norm": 0.50,
                "y_norm": 0.43,
                "w_norm": 0.16,
                "h_norm": 0.21,
                "person_x_norm": 0.50,
                "person_y_norm": 0.46,
                "person_w_norm": 0.43,
                "person_h_norm": 0.59,
            },
            {
                "time_ms": 400,
                "x_norm": 0.66,
                "y_norm": 0.44,
                "w_norm": 0.15,
                "h_norm": 0.20,
                "person_x_norm": 0.52,
                "person_y_norm": 0.46,
                "person_w_norm": 0.42,
                "person_h_norm": 0.58,
            },
        ],
        source_path="upper.mp4",
        duration_ms=500,
    )

    retargeting = payload["retargeting"]
    assert retargeting["shot_profile"] == "upper_body"
    assert retargeting["shot_classification"]["method"] == "face_person_bbox_heuristic"
    assert retargeting["movement_constraints"]["actor_transform_locked"] is False
    assert retargeting["actor_motion_scale"] == 0.028
    assert retargeting["scale_limit"] == 0.02
    assert payload["capabilities"]["person_bbox"] is True

    summary = live2d_mocap_user_summary(payload)
    assert summary["movement_mode"] == "upper_body_damped_transform"
    assert summary["actor_transform_locked"] is False
    assert "actor position/scale" in summary["driven_channels"]


def test_live2d_mocap_full_body_person_box_keeps_transform_profile():
    payload = live2d_mocap_payload_from_frames(
        [
            {
                "time_ms": 0,
                "x_norm": 0.36,
                "y_norm": 0.20,
                "w_norm": 0.08,
                "h_norm": 0.10,
                "person_x_norm": 0.46,
                "person_y_norm": 0.58,
                "person_w_norm": 0.30,
                "person_h_norm": 0.74,
            },
            {
                "time_ms": 200,
                "x_norm": 0.50,
                "y_norm": 0.20,
                "w_norm": 0.08,
                "h_norm": 0.10,
                "person_x_norm": 0.50,
                "person_y_norm": 0.58,
                "person_w_norm": 0.31,
                "person_h_norm": 0.75,
            },
            {
                "time_ms": 400,
                "x_norm": 0.64,
                "y_norm": 0.20,
                "w_norm": 0.08,
                "h_norm": 0.10,
                "person_x_norm": 0.54,
                "person_y_norm": 0.58,
                "person_w_norm": 0.30,
                "person_h_norm": 0.74,
            },
        ],
        source_path="full.mp4",
        duration_ms=500,
    )

    retargeting = payload["retargeting"]
    assert retargeting["shot_profile"] == "full_body"
    assert retargeting["shot_classification"]["method"] == "face_person_bbox_heuristic"
    assert retargeting["movement_constraints"]["actor_transform_locked"] is False
    assert retargeting["movement_constraints"]["reason"] == "full_body_allows_actor_translation_and_zoom"
    assert retargeting["actor_motion_scale"] == 0.08
    assert retargeting["scale_limit"] == 0.04

    summary = live2d_mocap_user_summary(payload)
    assert summary["movement_mode"] == "full_body_transform_enabled"
    assert "Full body" in summary["status_line"]


def test_live2d_mocap_face_detail_drives_gaze_mouth_and_eye_parameters():
    payload = live2d_mocap_payload_from_frames(
        [
            {
                "time_ms": 0,
                "x_norm": 0.50,
                "y_norm": 0.42,
                "w_norm": 0.20,
                "h_norm": 0.26,
                "head_yaw": -1.0,
                "head_pitch": 0.10,
                "head_roll": -0.25,
                "gaze_x": 1.0,
                "gaze_y": -0.20,
                "mouth_open": 0.82,
                "mouth_form": 0.35,
                "eye_l_open": 0.90,
                "eye_r_open": 0.85,
            },
            {
                "time_ms": 200,
                "x_norm": 0.50,
                "y_norm": 0.42,
                "w_norm": 0.20,
                "h_norm": 0.26,
                "head_yaw": -1.0,
                "head_pitch": 0.10,
                "head_roll": -0.25,
                "gaze_x": 1.0,
                "gaze_y": -0.20,
                "mouth_open": 0.82,
                "mouth_form": 0.35,
                "eye_l_open": 0.90,
                "eye_r_open": 0.85,
            },
        ],
        source_path="detail.mp4",
        duration_ms=300,
    )

    params = payload["parameter_keyframes"]
    assert payload["capabilities"]["mouth_eye_detail"] is True
    assert params["ParamAngleX"][0]["value"] == -18.0
    assert params["ParamEyeBallX"][0]["value"] == 1.0
    assert params["ParamEyeBallY"][0]["value"] == -0.2
    assert params["ParamMouthOpenY"][0]["value"] == 0.82
    assert params["ParamMouthForm"][0]["value"] == 0.35
    assert params["ParamEyeLOpen"][0]["value"] == 0.9
    assert params["ParamEyeROpen"][0]["value"] == 0.85
    assert params["ParamEyeOpen"][0]["value"] == 0.875
    assert params["ParamEyeBlink"][0]["value"] == 0.125
    assert params["ParamBreath"]
    assert "ParamEyeBallX" in payload["retargeting"]["detail_parameter_tracks"]
    assert "ParamEyeBlink" in payload["retargeting"]["detail_parameter_tracks"]
    assert any(event["kind"] == "face_detail_parameters_acquired" for event in payload["events"])

    summary = live2d_mocap_user_summary(payload)
    assert "eye gaze" in summary["driven_channels"]
    assert "mouth" in summary["driven_channels"]
    assert "ParamMouthOpenY" in summary["detail_tracks"]


def test_apply_live2d_mocap_payload_to_clip_bakes_exportable_transform_keys():
    payload = live2d_mocap_payload_from_frames(
        [
            {"time_ms": 0, "x_norm": 0.45, "y_norm": 0.49, "w_norm": 0.18, "h_norm": 0.24},
            {"time_ms": 250, "x_norm": 0.62, "y_norm": 0.42, "w_norm": 0.26, "h_norm": 0.32},
        ],
        source_path="source.mov",
        duration_ms=900,
    )
    clip = Live2DActorClip(duration_ms=300)

    result = apply_live2d_mocap_payload_to_clip(clip, payload)

    assert result["ok"] is True
    assert clip.duration_ms == 900
    assert clip.kf_pos_x
    assert clip.kf_pos_y
    assert clip.kf_scale
    assert clip.mocap_source_path.endswith("source.mov")
    assert clip.mocap_backend == "opencv_haar_face"
    assert clip.mocap_payload["kind"] == "live2d_video_mocap"
    assert "ParamAngleX" in clip.mocap_parameter_keyframes


def test_live2d_parameter_values_layer_on_top_of_authored_motion():
    clip = Live2DActorClip(start_ms=1000, duration_ms=2000)
    clip.parameter_keyframes = {
        "ParamEyeLOpen": [
            {"time_ms": 0, "value": 0.1, "curve": "linear"},
            {"time_ms": 1000, "value": 0.9, "curve": "linear"},
        ]
    }
    clip.mocap_parameter_keyframes = {
        "ParamAngleX": [
            {"time_ms": 0, "value": -20.0, "curve": "linear"},
            {"time_ms": 1000, "value": 20.0, "curve": "linear"},
        ],
        "ParamBodyAngleX": [
            {"time_ms": 0, "value": -8.0, "curve": "linear"},
            {"time_ms": 1000, "value": 8.0, "curve": "linear"},
        ],
    }

    values = clip.parameter_values_at(1500)

    assert round(values["ParamEyeLOpen"], 3) == 0.5
    assert round(values["ParamAngleX"], 3) == 0.0
    assert round(values["ParamBodyAngleX"], 3) == 0.0


def test_empty_live2d_mocap_payload_reports_no_face_frames():
    payload = live2d_mocap_payload_from_frames([], source_path="empty.mp4")

    assert payload["ok"] is False
    assert payload["warning"] == "no_face_frames"


def test_live2d_mocap_project_roundtrip_preserves_payload_and_keyframes():
    payload = live2d_mocap_payload_from_frames(
        [
            {"time_ms": 0, "x_norm": 0.40, "y_norm": 0.50, "w_norm": 0.20, "h_norm": 0.22},
            {"time_ms": 300, "x_norm": 0.66, "y_norm": 0.45, "w_norm": 0.22, "h_norm": 0.25},
        ],
        source_path="roundtrip.mp4",
        duration_ms=1000,
    )
    clip = Live2DActorClip(model_path="avatar.model3.json")
    apply_live2d_mocap_payload_to_clip(clip, payload)
    clip.mocap_subject_type = "upper_body"
    clip.mocap_parameter_aliases = {"ParamMouthOpenY": ["ParamMouthOpen"]}
    clip.performance_source_subject_type = "upper_body"
    clip.performance_source_mapping_constraints = {"reason": "upper_body_damps_actor_translation_and_zoom"}
    track = Live2DActorTrack(id=7, label="Live2D mocap", clips=[clip])

    restored = _live2d_actor_track_from_dict(_actor_track_to_dict(track))
    restored_clip = restored.clips[0]

    assert restored.id == 7
    assert restored_clip.model_path == "avatar.model3.json"
    assert restored_clip.mocap_source_path.endswith("roundtrip.mp4")
    assert restored_clip.mocap_payload["sample_count"] == 2
    assert restored_clip.mocap_parameter_keyframes["ParamAngleX"]
    assert restored_clip.mocap_subject_type == "upper_body"
    assert restored_clip.mocap_parameter_aliases["ParamMouthOpenY"] == ["ParamMouthOpen"]
    assert restored_clip.performance_source_subject_type == "upper_body"
    assert restored_clip.performance_source_mapping_constraints["reason"] == "upper_body_damps_actor_translation_and_zoom"
    assert restored_clip.kf_pos_x[0].curve == "smoothstep"
