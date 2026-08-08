"""2D hierarchical cutout rigs for decomposed full-canvas image layers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import AnimatedProperty, Keyframe, MotionComposition, MotionLayer


@dataclass(frozen=True, slots=True)
class ArmJointLayout:
    shoulder: tuple[float, float]
    elbow: tuple[float, float]
    wrist: tuple[float, float]


def _vector(value: Any, fallback: tuple[float, float]) -> list[float]:
    values = list(value or fallback)
    return [float(values[0]), float(values[1])]


def _size(layer: MotionLayer, composition: MotionComposition) -> tuple[float, float]:
    return (
        float(layer.source.params.get("width", composition.width) or composition.width),
        float(layer.source.params.get("height", composition.height) or composition.height),
    )


def _rotation_curve(rows: list[tuple[int, float]]) -> AnimatedProperty:
    values_by_time = {
        max(0, int(time_ms)): float(value)
        for time_ms, value in rows
    }
    return AnimatedProperty(
        value_type="scalar",
        default=float(rows[0][1]),
        keyframes=[
            Keyframe(
                time_ms=int(time_ms),
                value=float(value),
                interpolation="bezier",
                out_tangent=(0.2, 0.0),
                in_tangent=(0.8, 1.0),
            )
            for time_ms, value in sorted(values_by_time.items())
        ],
    )


def apply_arm_wave_rig(
    composition: MotionComposition,
    *,
    torso: MotionLayer,
    upper_arm: MotionLayer,
    forearm: MotionLayer,
    hand: MotionLayer,
    joints: ArmJointLayout,
    start_ms: int,
    end_ms: int,
    side: str = "right",
    cycles: int = 3,
) -> dict[str, Any]:
    """Parent four aligned RGBA parts and animate an editable waving gesture."""
    duration = max(1, int(composition.duration_ms))
    start = min(duration - 1, max(0, int(start_ms)))
    end = min(duration, max(start + 1, int(end_ms)))
    direction = -1.0 if str(side).lower() == "right" else 1.0
    torso_origin = _vector(
        torso.transform.position.default,
        (composition.width * 0.5, composition.height * 0.5),
    )
    shoulder = _vector(joints.shoulder, (composition.width * 0.5, composition.height * 0.4))
    elbow = _vector(joints.elbow, (shoulder[0], shoulder[1] + 100.0))
    wrist = _vector(joints.wrist, (elbow[0], elbow[1] + 90.0))

    upper_size = _size(upper_arm, composition)
    forearm_size = _size(forearm, composition)
    hand_size = _size(hand, composition)
    upper_arm.parent_id = torso.id
    upper_arm.transform.anchor.default = [
        shoulder[0] / max(1.0, upper_size[0]),
        shoulder[1] / max(1.0, upper_size[1]),
    ]
    upper_arm.transform.position.default = [
        shoulder[0] - torso_origin[0],
        shoulder[1] - torso_origin[1],
    ]
    forearm.parent_id = upper_arm.id
    forearm.transform.anchor.default = [
        elbow[0] / max(1.0, forearm_size[0]),
        elbow[1] / max(1.0, forearm_size[1]),
    ]
    forearm.transform.position.default = [
        elbow[0] - shoulder[0],
        elbow[1] - shoulder[1],
    ]
    hand.parent_id = forearm.id
    hand.transform.anchor.default = [
        wrist[0] / max(1.0, hand_size[0]),
        wrist[1] / max(1.0, hand_size[1]),
    ]
    hand.transform.position.default = [
        wrist[0] - elbow[0],
        wrist[1] - elbow[1],
    ]

    lift_end = start + round((end - start) * 0.22)
    wave_end = start + round((end - start) * 0.78)
    upper_rows = [
        (0, 0.0),
        (start, 0.0),
        (lift_end, direction * 52.0),
        (wave_end, direction * 52.0),
        (end, 0.0),
    ]
    forearm_rows = [
        (0, 0.0),
        (start, 0.0),
        (lift_end, direction * 58.0),
    ]
    hand_rows = [
        (0, 0.0),
        (start, 0.0),
        (lift_end, direction * -8.0),
    ]
    cycle_count = max(1, min(8, int(cycles)))
    samples = cycle_count * 2 + 1
    for index in range(samples):
        progress = index / max(1, samples - 1)
        time_ms = round(lift_end + (wave_end - lift_end) * progress)
        alternating = -1.0 if index % 2 else 1.0
        forearm_rows.append((time_ms, direction * (58.0 + alternating * 19.0)))
        hand_rows.append((time_ms, direction * (-8.0 - alternating * 15.0)))
    forearm_rows.append((end, 0.0))
    hand_rows.append((end, 0.0))
    upper_arm.transform.rotation = _rotation_curve(upper_rows)
    forearm.transform.rotation = _rotation_curve(forearm_rows)
    hand.transform.rotation = _rotation_curve(hand_rows)

    for layer, joint, role in (
        (upper_arm, "shoulder", "upper_arm"),
        (forearm, "elbow", "forearm"),
        (hand, "wrist", "hand"),
    ):
        layer.metadata.update(
            {
                "cutout_rig": "arm_chain_v1",
                "joint": joint,
                "part_role": role,
                "rig_side": str(side).lower(),
                "wave_start_ms": start,
                "wave_end_ms": end,
            }
        )
    return {
        "schema": "tigerstudio.motion.cutout_arm_rig.v1",
        "torso_layer_id": torso.id,
        "upper_arm_layer_id": upper_arm.id,
        "forearm_layer_id": forearm.id,
        "hand_layer_id": hand.id,
        "joints": {
            "shoulder": shoulder,
            "elbow": elbow,
            "wrist": wrist,
        },
        "side": str(side).lower(),
        "start_ms": start,
        "end_ms": end,
        "cycles": cycle_count,
    }


__all__ = ["ArmJointLayout", "apply_arm_wave_rig"]
