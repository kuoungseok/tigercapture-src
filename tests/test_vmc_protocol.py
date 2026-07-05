import struct


def test_vseeface_vmc_ports_match_vseeface_defaults():
    from app.vtuber.vmc_protocol import VMC_VSEEFACE_RECEIVER_PORT, VMC_VSEEFACE_SENDER_PORT, VmcEndpoint

    assert VMC_VSEEFACE_RECEIVER_PORT == 39539
    assert VMC_VSEEFACE_SENDER_PORT == 39540
    assert VmcEndpoint().port == 39539


def test_osc_message_encodes_address_typetags_and_arguments():
    from app.vtuber.vmc_protocol import osc_message

    packet = osc_message("/VMC/Ext/Blend/Val", "A", 0.5)

    assert packet.startswith(b"/VMC/Ext/Blend/Val\0")
    assert b",sf\0" in packet
    assert packet.endswith(struct.pack(">f", 0.5))


def test_euler_quaternion_identity():
    from app.vtuber.vmc_protocol import euler_deg_to_quaternion

    qx, qy, qz, qw = euler_deg_to_quaternion(0.0, 0.0, 0.0)

    assert qx == 0.0
    assert qy == 0.0
    assert qz == 0.0
    assert qw == 1.0


def test_build_vmc_messages_from_face_frame_carries_pose_and_blends():
    from app.vtuber.video_face_driver import FaceMotionFrame
    from app.vtuber.vmc_protocol import build_vmc_messages_from_face_frame

    frame = FaceMotionFrame(time_ms=1500, yaw_deg=12.0, pitch_deg=-4.0, roll_deg=2.0, mouth_open=0.7, blink_l=0.1, blink_r=0.2)

    messages = build_vmc_messages_from_face_frame(frame)

    addresses = [message.address for message in messages]
    assert "/VMC/Ext/OK" in addresses
    assert "/VMC/Ext/Bone/Pos" in addresses
    assert "/VMC/Ext/Blend/Val" in addresses
    assert "/VMC/Ext/Blend/Apply" in addresses
    assert "/VMC/Ext/T" in addresses
    bone_names = [message.args[0] for message in messages if message.address == "/VMC/Ext/Bone/Pos"]
    assert "Head" in bone_names
    assert "LeftUpperArm" in bone_names
    assert "RightLowerArm" in bone_names
    blends = {message.args[0]: message.args[1] for message in messages if message.address == "/VMC/Ext/Blend/Val"}
    assert blends["A"] == 0.7
    assert blends["Blink_L"] == 0.1
    assert blends["Blink_R"] == 0.2


def test_build_vmc_messages_counter_rolls_head_against_shoulder_roll():
    from app.vtuber.video_face_driver import FaceMotionFrame
    from app.vtuber.vmc_protocol import build_vmc_messages_from_face_frame, summarize_vmc_messages

    frame = FaceMotionFrame(time_ms=100, roll_deg=0.0, shoulder_roll_deg=12.0)

    summary = summarize_vmc_messages(build_vmc_messages_from_face_frame(frame))

    head_rotation = summary["bones"]["Head"]["rotation"]
    chest_rotation = summary["bones"]["Chest"]["rotation"]
    assert head_rotation[2] < 0.0
    assert abs(chest_rotation[2]) > 0.001


def test_parse_osc_message_round_trips_bridge_packets():
    from app.vtuber.vmc_protocol import osc_message, parse_osc_message

    packet = osc_message("/VMC/Ext/Blend/Val", "Blink_L", 0.25)
    message = parse_osc_message(packet)

    assert message.address == "/VMC/Ext/Blend/Val"
    assert message.args[0] == "Blink_L"
    assert abs(message.args[1] - 0.25) < 0.0001


def test_summarize_vmc_messages_collects_receiver_state():
    from app.vtuber.video_face_driver import FaceMotionFrame
    from app.vtuber.vmc_protocol import build_vmc_messages_from_face_frame, parse_osc_message, summarize_vmc_messages

    frame = FaceMotionFrame(time_ms=2500, yaw_deg=6.0, pitch_deg=3.0, roll_deg=-2.0, mouth_open=0.45, blink_l=0.2, blink_r=0.8)
    messages = [
        parse_osc_message(message.to_bytes())
        for message in build_vmc_messages_from_face_frame(frame)
    ]
    summary = summarize_vmc_messages(messages)

    assert summary["message_count"] == len(messages)
    assert "Head" in summary["bones"]
    assert "LeftHand" in summary["bones"]
    assert "RightUpperArm" in summary["bones"]
    assert abs(summary["blends"]["A"] - 0.45) < 0.0001
    assert abs(summary["blends"]["Blink_L"] - 0.2) < 0.0001
    assert abs(summary["blends"]["Blink_R"] - 0.8) < 0.0001
    assert summary["timestamp_max"] == 2.5
