"""Minimal VMC/OSC sender utilities for external VSeeFace control."""
from __future__ import annotations

from dataclasses import dataclass
import math
import socket
import struct
from typing import Any, Iterable, Mapping

from app.vtuber.vrm_motion_mapping import source_pitch_to_vrm_pitch


VMC_DEFAULT_HOST = "127.0.0.1"
VMC_VSEEFACE_RECEIVER_PORT = 39539
VMC_VSEEFACE_SENDER_PORT = 39540


@dataclass(frozen=True)
class VmcEndpoint:
    host: str = VMC_DEFAULT_HOST
    port: int = VMC_VSEEFACE_RECEIVER_PORT

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "VmcEndpoint":
        data = payload or {}
        return cls(
            host=str(data.get("host") or VMC_DEFAULT_HOST),
            port=max(1, min(65535, int(data.get("port", VMC_VSEEFACE_RECEIVER_PORT) or VMC_VSEEFACE_RECEIVER_PORT))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"host": self.host, "port": int(self.port)}


@dataclass(frozen=True)
class VmcOscMessage:
    address: str
    args: tuple[Any, ...] = ()

    def to_bytes(self) -> bytes:
        return osc_message(self.address, *self.args)

    def to_dict(self) -> dict[str, Any]:
        return {"address": self.address, "args": list(self.args)}


def osc_message(address: str, *args: Any) -> bytes:
    """Encode a single OSC message with int, float, and string arguments."""
    if not str(address).startswith("/"):
        raise ValueError("OSC address must start with '/'")
    type_tags = ","
    payload = bytearray()
    for arg in args:
        tag, data = _encode_osc_arg(arg)
        type_tags += tag
        payload += data
    return _osc_string(address) + _osc_string(type_tags) + bytes(payload)


def euler_deg_to_quaternion(pitch_deg: float = 0.0, yaw_deg: float = 0.0, roll_deg: float = 0.0) -> tuple[float, float, float, float]:
    """Return a Unity-style quaternion tuple from pitch/yaw/roll degrees."""
    pitch = math.radians(float(pitch_deg)) * 0.5
    yaw = math.radians(float(yaw_deg)) * 0.5
    roll = math.radians(float(roll_deg)) * 0.5

    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cr, sr = math.cos(roll), math.sin(roll)

    # Yaw(Y) * Pitch(X) * Roll(Z), matching the controls exposed by the bridge.
    qw = cy * cp * cr + sy * sp * sr
    qx = cy * sp * cr + sy * cp * sr
    qy = sy * cp * cr - cy * sp * sr
    qz = cy * cp * sr - sy * sp * cr
    return _normalize_quaternion(qx, qy, qz, qw)


def build_vmc_messages_from_face_frame(
    frame: Any,
    *,
    include_status: bool = True,
    include_body_base: bool = True,
    upper_body_mode: str = "seated",
) -> list[VmcOscMessage]:
    """Build VMC messages that drive a VRM avatar from one face-motion frame."""
    time_ms = _frame_value(frame, "time_ms", 0.0)
    yaw = _clamp(_frame_value(frame, "yaw_deg", 0.0), -45.0, 45.0)
    source_pitch = _clamp(_frame_value(frame, "pitch_deg", 0.0), -35.0, 35.0)
    pitch = _clamp(source_pitch_to_vrm_pitch(source_pitch), -35.0, 35.0)
    roll = _clamp(_frame_value(frame, "roll_deg", 0.0), -25.0, 25.0)
    shoulder_roll = _clamp(_frame_value(frame, "shoulder_roll_deg", 0.0), -25.0, 25.0)
    mouth_open = _clamp01(_frame_value(frame, "mouth_open", 0.0))
    blink_l = _clamp01(_frame_value(frame, "blink_l", 0.0))
    blink_r = _clamp01(_frame_value(frame, "blink_r", 0.0))

    messages: list[VmcOscMessage] = []
    if include_status:
        messages.append(VmcOscMessage("/VMC/Ext/OK", (1, 3, 3, 1)))
    if include_body_base:
        messages.extend(_base_body_pose_messages(pitch, yaw, roll, shoulder_roll=shoulder_roll, upper_body_mode=upper_body_mode))
    else:
        qx, qy, qz, qw = euler_deg_to_quaternion(pitch, yaw, roll)
        messages.append(VmcOscMessage("/VMC/Ext/Bone/Pos", ("Head", 0.0, 1.62, 0.0, qx, qy, qz, qw)))

    messages.extend([
        VmcOscMessage("/VMC/Ext/Blend/Val", ("A", mouth_open)),
        VmcOscMessage("/VMC/Ext/Blend/Val", ("Blink_L", blink_l)),
        VmcOscMessage("/VMC/Ext/Blend/Val", ("Blink_R", blink_r)),
        VmcOscMessage("/VMC/Ext/Blend/Apply", ()),
        VmcOscMessage("/VMC/Ext/T", (float(time_ms) / 1000.0,)),
    ])
    return messages


def send_vmc_messages(messages: Iterable[VmcOscMessage], endpoint: VmcEndpoint) -> int:
    """Send encoded VMC messages over UDP and return the packet count."""
    packets = [message.to_bytes() for message in messages]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for packet in packets:
            sock.sendto(packet, (endpoint.host, endpoint.port))
    return len(packets)


def parse_osc_message(packet: bytes) -> VmcOscMessage:
    """Decode the OSC subset emitted by this bridge: string, int, and float args."""
    data = bytes(packet)
    address, offset = _read_osc_string(data, 0)
    if not address.startswith("/"):
        raise ValueError("OSC address must start with '/'")
    type_tags, offset = _read_osc_string(data, offset)
    if not type_tags.startswith(","):
        raise ValueError("OSC type tag string must start with ','")
    args: list[Any] = []
    for tag in type_tags[1:]:
        if tag == "s":
            value, offset = _read_osc_string(data, offset)
            args.append(value)
        elif tag == "i":
            _require_bytes(data, offset, 4)
            args.append(int.from_bytes(data[offset:offset + 4], "big", signed=True))
            offset += 4
        elif tag == "f":
            _require_bytes(data, offset, 4)
            args.append(float(struct.unpack(">f", data[offset:offset + 4])[0]))
            offset += 4
        else:
            raise ValueError(f"Unsupported OSC type tag: {tag!r}")
    return VmcOscMessage(address, tuple(args))


def summarize_vmc_messages(messages: Iterable[VmcOscMessage]) -> dict[str, Any]:
    """Return a compact receiver-style state summary for VMC smoke tests."""
    bones: dict[str, dict[str, Any]] = {}
    blends: dict[str, float] = {}
    status: tuple[Any, ...] | None = None
    timestamps: list[float] = []
    addresses: dict[str, int] = {}
    for message in messages:
        addresses[message.address] = addresses.get(message.address, 0) + 1
        if message.address == "/VMC/Ext/OK":
            status = message.args
        elif message.address == "/VMC/Ext/Bone/Pos" and len(message.args) >= 8:
            name = str(message.args[0])
            bones[name] = {
                "position": [float(message.args[1]), float(message.args[2]), float(message.args[3])],
                "rotation": [float(message.args[4]), float(message.args[5]), float(message.args[6]), float(message.args[7])],
            }
        elif message.address == "/VMC/Ext/Blend/Val" and len(message.args) >= 2:
            blends[str(message.args[0])] = _clamp01(float(message.args[1]))
        elif message.address == "/VMC/Ext/T" and message.args:
            timestamps.append(float(message.args[0]))
    return {
        "message_count": sum(addresses.values()),
        "addresses": addresses,
        "status": list(status) if status is not None else None,
        "bones": bones,
        "blends": blends,
        "timestamp_min": min(timestamps) if timestamps else None,
        "timestamp_max": max(timestamps) if timestamps else None,
    }


def _base_body_pose_messages(
    pitch: float,
    yaw: float,
    roll: float,
    *,
    shoulder_roll: float = 0.0,
    upper_body_mode: str = "seated",
) -> list[VmcOscMessage]:
    # Keep face roll on Head/Neck while a separately estimated shoulder roll
    # carries upper-body lean from source footage.
    torso_roll = shoulder_roll if abs(float(shoulder_roll)) > 0.001 else roll
    bones = [
        ("Hips", (0.0, 0.95, 0.0), (0.0, 0.0, 0.0)),
        ("Spine", (0.0, 1.15, 0.0), (pitch * 0.08, yaw * 0.08, torso_roll * 0.08)),
        ("Chest", (0.0, 1.34, 0.0), (pitch * 0.18, yaw * 0.18, torso_roll * 0.22)),
        ("Neck", (0.0, 1.52, 0.0), (pitch * 0.42, yaw * 0.38, roll * 0.18 - torso_roll * 0.12)),
        ("Head", (0.0, 1.62, 0.0), (pitch, yaw, roll - torso_roll * 0.18)),
    ]
    if str(upper_body_mode or "").casefold() == "seated":
        bones.extend(_seated_upper_body_pose(pitch, yaw, roll, shoulder_roll=torso_roll))
    messages: list[VmcOscMessage] = []
    for name, pos, rot in bones:
        qx, qy, qz, qw = euler_deg_to_quaternion(rot[0], rot[1], rot[2])
        messages.append(VmcOscMessage("/VMC/Ext/Bone/Pos", (name, pos[0], pos[1], pos[2], qx, qy, qz, qw)))
    return messages


def _seated_upper_body_pose(
    pitch: float,
    yaw: float,
    roll: float,
    *,
    shoulder_roll: float = 0.0,
) -> list[tuple[str, tuple[float, float, float], tuple[float, float, float]]]:
    """Return a pragmatic desk-streamer arm fallback for face-only tracking.

    Most webcam VTuber setups only provide face/head tracking. Leaving the
    humanoid in T-pose makes the avatar unusable, so this fallback relaxes the
    shoulders and bends the arms near a desk while adding very small torso/head
    follow-through. It is intentionally conservative so it does not look like
    full body tracking.
    """
    lean = _clamp(pitch, -18.0, 18.0)
    turn = _clamp(yaw, -20.0, 20.0)
    shoulder_tilt = _clamp(shoulder_roll if abs(float(shoulder_roll)) > 0.001 else roll, -15.0, 15.0)

    left_shoulder = (2.0 + lean * 0.03, -4.0 + turn * 0.03, 5.0 + shoulder_tilt * 0.08)
    right_shoulder = (2.0 + lean * 0.03, 4.0 + turn * 0.03, -5.0 + shoulder_tilt * 0.08)
    left_upper = (-12.0 + lean * 0.10, 8.0 + turn * 0.04, 72.0 + shoulder_tilt * 0.12)
    right_upper = (-12.0 + lean * 0.10, -8.0 + turn * 0.04, -72.0 + shoulder_tilt * 0.12)
    left_lower = (-24.0 + lean * 0.05, 14.0 + turn * 0.03, 52.0)
    right_lower = (-24.0 + lean * 0.05, -14.0 + turn * 0.03, -52.0)
    left_hand = (-6.0, 8.0, 8.0)
    right_hand = (-6.0, -8.0, -8.0)

    return [
        ("LeftShoulder", (-0.08, 1.43, 0.02), left_shoulder),
        ("LeftUpperArm", (-0.23, 1.34, 0.03), left_upper),
        ("LeftLowerArm", (-0.35, 1.15, 0.12), left_lower),
        ("LeftHand", (-0.22, 1.00, 0.20), left_hand),
        ("RightShoulder", (0.08, 1.43, 0.02), right_shoulder),
        ("RightUpperArm", (0.23, 1.34, 0.03), right_upper),
        ("RightLowerArm", (0.35, 1.15, 0.12), right_lower),
        ("RightHand", (0.22, 1.00, 0.20), right_hand),
    ]


def _frame_value(frame: Any, key: str, default: float) -> float:
    if isinstance(frame, Mapping):
        value = frame.get(key, default)
    else:
        value = getattr(frame, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _encode_osc_arg(arg: Any) -> tuple[str, bytes]:
    if isinstance(arg, bool):
        return "i", int(arg).to_bytes(4, "big", signed=True)
    if isinstance(arg, int) and not isinstance(arg, bool):
        return "i", int(arg).to_bytes(4, "big", signed=True)
    if isinstance(arg, float):
        return "f", _pack_float32(arg)
    return "s", _osc_string(str(arg))


def _osc_string(value: Any) -> bytes:
    raw = str(value).encode("utf-8") + b"\0"
    return raw + (b"\0" * ((4 - (len(raw) % 4)) % 4))


def _read_osc_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("Unterminated OSC string")
    raw = data[offset:end]
    next_offset = end + 1
    next_offset += (4 - (next_offset % 4)) % 4
    if next_offset > len(data):
        raise ValueError("OSC string padding exceeds packet length")
    return raw.decode("utf-8"), next_offset


def _require_bytes(data: bytes, offset: int, count: int) -> None:
    if offset + count > len(data):
        raise ValueError("OSC packet ended before argument was complete")


def _pack_float32(value: float) -> bytes:
    return struct.pack(">f", float(value))


def _normalize_quaternion(qx: float, qy: float, qz: float, qw: float) -> tuple[float, float, float, float]:
    mag = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if mag <= 0.000001:
        return 0.0, 0.0, 0.0, 1.0
    return qx / mag, qy / mag, qz / mag, qw / mag


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)
