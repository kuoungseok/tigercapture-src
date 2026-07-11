from types import SimpleNamespace


def _frame(time_ms: int, *, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0, mouth: float = 0.0, blink: float = 0.0):
    return SimpleNamespace(
        time_ms=time_ms,
        yaw_deg=yaw,
        pitch_deg=pitch,
        roll_deg=roll,
        mouth_open=mouth,
        blink_l=blink,
        blink_r=blink,
    )


def test_milica_vrm_mapping_local_qa_slots_separate_yaw_pitch_blink_and_mouth():
    from tools.render_milica_vrm_trump_mapping import _selected_frame_slots

    frames = (
        _frame(0),
        _frame(100, yaw=12.0),
        _frame(200, pitch=-8.0),
        _frame(300, blink=1.0),
        _frame(400, mouth=0.8),
    )

    selected = _selected_frame_slots(frames, slots="neutral,yaw,pitch,blink,mouth")

    assert selected == [
        ("neutral", 0),
        ("yaw", 1),
        ("pitch", 2),
        ("blink", 3),
        ("mouth", 4),
    ]


def test_milica_vrm_mapping_local_qa_single_slot_keeps_compatibility():
    from tools.render_milica_vrm_trump_mapping import _selected_frame_indices

    frames = (
        _frame(0),
        _frame(100, yaw=4.0),
        _frame(200, pitch=9.0),
    )

    assert _selected_frame_indices(frames, single_slot="pitch") == [2]


def test_vtuber_studio_source_crop_expands_to_single_16x9_box():
    from tools.run_vtuber_studio_trump_live import _box_contains_xywh, _expand_box_to_aspect

    crop, diag = _expand_box_to_aspect((158, 67, 415, 245), (640, 360), target_aspect=16.0 / 9.0)

    assert diag["single_crop_then_resize"] is True
    assert abs(diag["crop_aspect"] - 1.7778) < 0.01
    assert _box_contains_xywh(crop, (290, 119, 151, 100)) is True


def test_vtuber_studio_cached_program_output_bottom_anchors_avatar(monkeypatch):
    from pathlib import Path

    from PIL import Image
    from tools import run_vtuber_studio_trump_live as live

    monkeypatch.setattr(live, "_video_frame", lambda *_args, **_kwargs: Image.new("RGB", (1280, 720), (16, 24, 34)))
    avatar = Image.new("RGBA", (220, 520), (0, 0, 0, 0))
    avatar.alpha_composite(Image.new("RGBA", (160, 440), (255, 255, 255, 255)), (30, 40))

    _image, placement = live._make_cached_program_output_frame(
        Path("unused.mp4"),
        avatar,
        time_ms=0,
        label="test",
    )

    assert placement["program_avatar_grounded"] is True
    assert placement["program_avatar_bottom_gap_ratio"] == 0.0
    assert placement["program_avatar_box"][3] == 720
    assert 0.85 <= placement["program_avatar_height_ratio"] <= 0.97


def test_milica_vrm_pose_animation_inverts_source_pitch_for_vrm_space():
    from tools.render_milica_vrm_trump_mapping import _attach_pose_animation

    frame = _frame(100, pitch=6.0)
    descriptor = _attach_pose_animation({"geometries": []}, (frame,), upper_body_mode="none")
    head_curve = descriptor["animation_clips"][0]["model_curves"]["node_18"]["rotation"]["x"]
    neck_curve = descriptor["animation_clips"][0]["model_curves"]["node_17"]["rotation"]["x"]

    assert head_curve == [[100.0, -18.0]]
    assert neck_curve == [[100.0, -7.56]]
