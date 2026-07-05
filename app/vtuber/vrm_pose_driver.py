"""Map VTuber motion frames to VRM-compatible pose diagnostics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from app.vtuber.vmc_protocol import build_vmc_messages_from_face_frame, summarize_vmc_messages


VRM_POSE_DRIVER_SCHEMA = "tigerstudio.vtuber.vrm_pose_driver.v1"


@dataclass(frozen=True)
class VrmPoseFrame:
    time_ms: int
    bones: dict[str, dict[str, Any]]
    blends: dict[str, float]
    source: str = "vrm_pose_driver"

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": int(self.time_ms),
            "bones": self.bones,
            "blends": self.blends,
            "source": self.source,
        }


def vrm_pose_from_motion_frame(frame: Any) -> VrmPoseFrame:
    """Convert a face-motion frame into the VMC pose VSeeFace expects."""
    messages = build_vmc_messages_from_face_frame(frame)
    summary = summarize_vmc_messages(messages)
    return VrmPoseFrame(
        time_ms=int(_frame_value(frame, "time_ms", 0)),
        bones=dict(summary.get("bones") or {}),
        blends={str(key): float(value) for key, value in dict(summary.get("blends") or {}).items()},
    )


def build_vrm_pose_frames(frames: Iterable[Any]) -> tuple[VrmPoseFrame, ...]:
    return tuple(vrm_pose_from_motion_frame(frame) for frame in frames)


def summarize_vrm_pose_frames(frames: Iterable[VrmPoseFrame]) -> dict[str, Any]:
    data = tuple(frames)
    if not data:
        return {
            "schema": VRM_POSE_DRIVER_SCHEMA,
            "ok": False,
            "frame_count": 0,
            "animated": False,
            "animated_bones": [],
            "animated_blends": [],
        }
    bone_names = sorted({name for frame in data for name in frame.bones.keys()})
    blend_names = sorted({name for frame in data for name in frame.blends.keys()})
    animated_bones = [
        name
        for name in bone_names
        if _bone_rotation_range(data, name) > 0.0001
    ]
    animated_blends = [
        name
        for name in blend_names
        if _blend_range(data, name) > 0.0001 or max(frame.blends.get(name, 0.0) for frame in data) > 0.0001
    ]
    return {
        "schema": VRM_POSE_DRIVER_SCHEMA,
        "ok": True,
        "frame_count": len(data),
        "time_min_ms": min(frame.time_ms for frame in data),
        "time_max_ms": max(frame.time_ms for frame in data),
        "animated": bool(animated_bones or animated_blends),
        "bone_count": len(bone_names),
        "blend_count": len(blend_names),
        "bones": bone_names,
        "blends": blend_names,
        "animated_bones": animated_bones,
        "animated_blends": animated_blends,
        "head_rotation_range": _bone_rotation_range(data, "Head"),
    }


def _bone_rotation_range(frames: tuple[VrmPoseFrame, ...], name: str) -> float:
    rotations = []
    for frame in frames:
        bone = frame.bones.get(name) or {}
        rotation = bone.get("rotation") or []
        if len(rotation) >= 4:
            rotations.append(tuple(float(value) for value in rotation[:4]))
    if len(rotations) < 2:
        return 0.0
    return max(
        max(component) - min(component)
        for component in zip(*rotations)
    )


def _blend_range(frames: tuple[VrmPoseFrame, ...], name: str) -> float:
    values = [float(frame.blends.get(name, 0.0)) for frame in frames]
    return max(values) - min(values) if values else 0.0


def _frame_value(frame: Any, name: str, default: Any) -> Any:
    if isinstance(frame, dict):
        return frame.get(name, default)
    return getattr(frame, name, default)
