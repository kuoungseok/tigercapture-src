"""Serializable full-body 2D cutout rig contract and mutations."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import acos, atan2, cos, degrees, hypot, isfinite, sin
from typing import Any, Mapping, Sequence

from .schema import AnimatedProperty, Keyframe, MotionComposition, new_motion_id


RIG_METADATA_KEY = "rigs"
RIG_SCHEMA = "tigerstudio.motion.rig.v1"
RIG_KIND_CUTOUT_2D = "cutout_2d"
RIG_CONSTRAINT_TWO_BONE_IK = "two_bone_ik"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _point(value: Any, fallback: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) >= 2
    ):
        try:
            x, y = float(value[0]), float(value[1])
            if isfinite(x) and isfinite(y):
                return x, y
        except (TypeError, ValueError):
            pass
    return float(fallback[0]), float(fallback[1])


@dataclass(slots=True)
class RigBone:
    id: str = field(default_factory=lambda: new_motion_id("bone"))
    name: str = "Bone"
    role: str = ""
    side: str = "center"
    parent_id: str = ""
    rest_position: tuple[float, float] = (0.0, 0.0)
    rest_rotation: float = 0.0
    rotation: AnimatedProperty = field(
        default_factory=lambda: AnimatedProperty(value_type="scalar", default=0.0)
    )
    translation: AnimatedProperty = field(
        default_factory=lambda: AnimatedProperty(value_type="vector2", default=[0.0, 0.0])
    )
    rotation_min: float = -180.0
    rotation_max: float = 180.0
    translation_locked: bool = False
    rotation_locked: bool = False
    scale_locked: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "side": self.side,
            "parent_id": self.parent_id,
            "rest_position": list(self.rest_position),
            "rest_rotation": float(self.rest_rotation),
            "rotation": self.rotation.to_dict(),
            "translation": self.translation.to_dict(),
            "rotation_min": float(self.rotation_min),
            "rotation_max": float(self.rotation_max),
            "translation_locked": bool(self.translation_locked),
            "rotation_locked": bool(self.rotation_locked),
            "scale_locked": bool(self.scale_locked),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RigBone":
        return cls(
            id=str(value.get("id") or new_motion_id("bone")),
            name=str(value.get("name") or "Bone"),
            role=str(value.get("role") or ""),
            side=str(value.get("side") or "center").lower(),
            parent_id=str(value.get("parent_id") or ""),
            rest_position=_point(value.get("rest_position")),
            rest_rotation=float(value.get("rest_rotation", 0.0) or 0.0),
            rotation=AnimatedProperty.from_dict(
                value.get("rotation", 0.0), value_type="scalar",
            ),
            translation=AnimatedProperty.from_dict(
                value.get("translation", [0.0, 0.0]), value_type="vector2",
            ),
            rotation_min=float(value.get("rotation_min", -180.0) or -180.0),
            rotation_max=float(value.get("rotation_max", 180.0) or 180.0),
            translation_locked=bool(value.get("translation_locked", False)),
            rotation_locked=bool(value.get("rotation_locked", False)),
            scale_locked=bool(value.get("scale_locked", True)),
            metadata=_mapping(value.get("metadata")),
        )


@dataclass(slots=True)
class RigLayerBinding:
    layer_id: str = ""
    bone_id: str = ""
    inherit_rotation: bool = True
    inherit_scale: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "bone_id": self.bone_id,
            "inherit_rotation": bool(self.inherit_rotation),
            "inherit_scale": bool(self.inherit_scale),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RigLayerBinding":
        return cls(
            layer_id=str(value.get("layer_id") or ""),
            bone_id=str(value.get("bone_id") or ""),
            inherit_rotation=bool(value.get("inherit_rotation", True)),
            inherit_scale=bool(value.get("inherit_scale", True)),
            metadata=_mapping(value.get("metadata")),
        )


@dataclass(slots=True)
class MotionRig:
    id: str = field(default_factory=lambda: new_motion_id("rig"))
    name: str = "2D Character Rig"
    kind: str = RIG_KIND_CUTOUT_2D
    root_bone_id: str = ""
    bones: list[RigBone] = field(default_factory=list)
    bindings: list[RigLayerBinding] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    poses: list[dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RIG_SCHEMA,
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "root_bone_id": self.root_bone_id,
            "bones": [bone.to_dict() for bone in self.bones],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "constraints": deepcopy(self.constraints),
            "poses": deepcopy(self.poses),
            "enabled": bool(self.enabled),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MotionRig":
        return cls(
            id=str(value.get("id") or new_motion_id("rig")),
            name=str(value.get("name") or "2D Character Rig"),
            kind=str(value.get("kind") or RIG_KIND_CUTOUT_2D),
            root_bone_id=str(value.get("root_bone_id") or ""),
            bones=[
                RigBone.from_dict(row)
                for row in value.get("bones", [])
                if isinstance(row, Mapping)
            ],
            bindings=[
                RigLayerBinding.from_dict(row)
                for row in value.get("bindings", [])
                if isinstance(row, Mapping)
            ],
            constraints=[
                deepcopy(dict(row))
                for row in value.get("constraints", [])
                if isinstance(row, Mapping)
            ],
            poses=[
                deepcopy(dict(row))
                for row in value.get("poses", [])
                if isinstance(row, Mapping)
            ],
            enabled=bool(value.get("enabled", True)),
            metadata=_mapping(value.get("metadata")),
        )


def composition_rigs(composition: MotionComposition) -> list[MotionRig]:
    rows = composition.metadata.get(RIG_METADATA_KEY, [])
    if not isinstance(rows, list):
        return []
    return [
        MotionRig.from_dict(row)
        for row in rows
        if isinstance(row, Mapping)
    ]


def set_composition_rigs(
    composition: MotionComposition,
    rigs: Sequence[MotionRig | Mapping[str, Any]],
) -> None:
    composition.metadata[RIG_METADATA_KEY] = [
        row.to_dict() if isinstance(row, MotionRig) else MotionRig.from_dict(row).to_dict()
        for row in rigs
    ]


def find_rig(composition: MotionComposition, rig_id: str) -> MotionRig:
    rig = next((row for row in composition_rigs(composition) if row.id == str(rig_id)), None)
    if rig is None:
        raise ValueError(f"Unknown motion rig: {rig_id}")
    return rig


def rig_for_layer(composition: MotionComposition, layer_id: str) -> MotionRig | None:
    target = str(layer_id or "")
    return next(
        (
            rig
            for rig in composition_rigs(composition)
            if any(binding.layer_id == target for binding in rig.bindings)
        ),
        None,
    )


def create_rig(
    composition: MotionComposition,
    *,
    name: str = "2D Character Rig",
    bones: Sequence[Mapping[str, Any]] = (),
    bindings: Sequence[Mapping[str, Any]] = (),
    kind: str = RIG_KIND_CUTOUT_2D,
) -> MotionRig:
    parsed_bones = [RigBone.from_dict(row) for row in bones]
    if not parsed_bones:
        center = (composition.width * 0.5, composition.height * 0.55)
        parsed_bones = [
            RigBone(name="Root", role="root", rest_position=center),
        ]
    root = next((bone for bone in parsed_bones if not bone.parent_id), parsed_bones[0])
    rig = MotionRig(
        name=str(name or "2D Character Rig"),
        kind=str(kind or RIG_KIND_CUTOUT_2D),
        root_bone_id=root.id,
        bones=parsed_bones,
        bindings=[RigLayerBinding.from_dict(row) for row in bindings],
    )
    rows = composition_rigs(composition)
    rows.append(rig)
    set_composition_rigs(composition, rows)
    return rig


def create_humanoid_rig(
    composition: MotionComposition,
    *,
    name: str = "Humanoid Cutout Rig",
    layer_slots: Mapping[str, str] | None = None,
) -> MotionRig:
    width, height = float(composition.width), float(composition.height)
    center_x = width * 0.5
    points = {
        "root": (center_x, height * 0.72),
        "pelvis": (center_x, height * 0.62),
        "torso": (center_x, height * 0.48),
        "neck": (center_x, height * 0.32),
        "head": (center_x, height * 0.22),
        "left_upper_arm": (width * 0.40, height * 0.36),
        "left_forearm": (width * 0.31, height * 0.47),
        "left_hand": (width * 0.24, height * 0.58),
        "right_upper_arm": (width * 0.60, height * 0.36),
        "right_forearm": (width * 0.69, height * 0.47),
        "right_hand": (width * 0.76, height * 0.58),
        "left_thigh": (width * 0.45, height * 0.66),
        "left_shin": (width * 0.44, height * 0.82),
        "left_foot": (width * 0.42, height * 0.96),
        "right_thigh": (width * 0.55, height * 0.66),
        "right_shin": (width * 0.56, height * 0.82),
        "right_foot": (width * 0.58, height * 0.96),
    }
    specs = (
        ("root", "Root", "root", "center", ""),
        ("pelvis", "Pelvis", "pelvis", "center", "root"),
        ("torso", "Torso", "torso", "center", "pelvis"),
        ("neck", "Neck", "neck", "center", "torso"),
        ("head", "Head", "head", "center", "neck"),
        ("left_upper_arm", "Left Upper Arm", "upper_arm", "left", "torso"),
        ("left_forearm", "Left Forearm", "forearm", "left", "left_upper_arm"),
        ("left_hand", "Left Hand", "hand", "left", "left_forearm"),
        ("right_upper_arm", "Right Upper Arm", "upper_arm", "right", "torso"),
        ("right_forearm", "Right Forearm", "forearm", "right", "right_upper_arm"),
        ("right_hand", "Right Hand", "hand", "right", "right_forearm"),
        ("left_thigh", "Left Thigh", "thigh", "left", "pelvis"),
        ("left_shin", "Left Shin", "shin", "left", "left_thigh"),
        ("left_foot", "Left Foot", "foot", "left", "left_shin"),
        ("right_thigh", "Right Thigh", "thigh", "right", "pelvis"),
        ("right_shin", "Right Shin", "shin", "right", "right_thigh"),
        ("right_foot", "Right Foot", "foot", "right", "right_shin"),
    )
    id_by_slot = {slot: new_motion_id("bone") for slot, *_rest in specs}
    bones = [
        RigBone(
            id=id_by_slot[slot],
            name=bone_name,
            role=role,
            side=side,
            parent_id=id_by_slot.get(parent_slot, ""),
            rest_position=points[slot],
            rotation_min=-35.0 if role in {"neck", "head", "foot"} else -120.0,
            rotation_max=35.0 if role in {"neck", "head", "foot"} else 120.0,
            translation_locked=role not in {"root", "pelvis"},
        )
        for slot, bone_name, role, side, parent_slot in specs
    ]
    valid_layers = {layer.id for layer in composition.layers}
    bindings = [
        RigLayerBinding(layer_id=str(layer_id), bone_id=id_by_slot[slot])
        for slot, layer_id in dict(layer_slots or {}).items()
        if slot in id_by_slot and str(layer_id) in valid_layers
    ]
    rig = MotionRig(
        name=str(name or "Humanoid Cutout Rig"),
        root_bone_id=id_by_slot["root"],
        bones=bones,
        bindings=bindings,
        metadata={"preset": "humanoid_17_bone_v1"},
    )
    rows = composition_rigs(composition)
    rows.append(rig)
    set_composition_rigs(composition, rows)
    return rig


def upsert_rig(composition: MotionComposition, rig: MotionRig) -> None:
    rows = composition_rigs(composition)
    index = next((index for index, row in enumerate(rows) if row.id == rig.id), None)
    if index is None:
        rows.append(rig)
    else:
        rows[index] = rig
    set_composition_rigs(composition, rows)


def delete_rig(composition: MotionComposition, rig_id: str) -> bool:
    rows = composition_rigs(composition)
    remaining = [row for row in rows if row.id != str(rig_id)]
    if len(remaining) == len(rows):
        return False
    set_composition_rigs(composition, remaining)
    return True


def add_bone(
    composition: MotionComposition,
    rig_id: str,
    bone_data: Mapping[str, Any],
) -> RigBone:
    rig = find_rig(composition, rig_id)
    bone = RigBone.from_dict(bone_data)
    if any(row.id == bone.id for row in rig.bones):
        bone.id = new_motion_id("bone")
    rig.bones.append(bone)
    if not rig.root_bone_id:
        rig.root_bone_id = bone.id
    upsert_rig(composition, rig)
    return bone


def update_bone(
    composition: MotionComposition,
    rig_id: str,
    bone_id: str,
    changes: Mapping[str, Any],
) -> RigBone:
    rig = find_rig(composition, rig_id)
    index = next((index for index, row in enumerate(rig.bones) if row.id == str(bone_id)), None)
    if index is None:
        raise ValueError(f"Unknown rig bone: {bone_id}")
    data = rig.bones[index].to_dict()
    data.update(deepcopy(dict(changes)))
    data["id"] = rig.bones[index].id
    rig.bones[index] = RigBone.from_dict(data)
    upsert_rig(composition, rig)
    return rig.bones[index]


def mirror_rig_bones(
    composition: MotionComposition,
    rig_id: str,
    *,
    bone_ids: Sequence[str] = (),
    axis_x: float | None = None,
    create_missing: bool = True,
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    selected = {str(value) for value in bone_ids if str(value)}
    sources = [
        bone
        for bone in rig.bones
        if bone.side in {"left", "right"}
        and (not selected or bone.id in selected)
    ]
    if not sources:
        raise ValueError("Bone mirroring requires at least one left or right bone")
    center_x = float(
        axis_x
        if axis_x is not None
        else next(
            (
                bone.rest_position[0]
                for bone in rig.bones
                if bone.id == rig.root_bone_id
            ),
            composition.width * 0.5,
        )
    )
    by_role_side = {
        (bone.role, bone.side): bone
        for bone in rig.bones
        if bone.role and bone.side in {"left", "right"}
    }
    counterpart_by_id: dict[str, str] = {}
    for bone in rig.bones:
        opposite = "left" if bone.side == "right" else "right"
        counterpart = by_role_side.get((bone.role, opposite))
        if counterpart is not None:
            counterpart_by_id[bone.id] = counterpart.id

    def mirror_property(prop: AnimatedProperty, value_type: str) -> AnimatedProperty:
        data = prop.to_dict()

        def mirrored(value: Any) -> Any:
            if value_type == "scalar":
                return -float(value or 0.0)
            point = _point(value)
            return [-point[0], point[1]]

        data["default"] = mirrored(data.get("default"))
        for keyframe in data.get("keyframes", []):
            keyframe["value"] = mirrored(keyframe.get("value"))
        return AnimatedProperty.from_dict(data, value_type=value_type)

    created: list[str] = []
    updated: list[str] = []
    for source in sources:
        opposite = "left" if source.side == "right" else "right"
        target = by_role_side.get((source.role, opposite))
        if target is None and not create_missing:
            continue
        target_id = target.id if target is not None else new_motion_id("bone")
        parent_id = counterpart_by_id.get(source.parent_id, source.parent_id)
        name = source.name
        if source.side == "left":
            name = name.replace("Left", "Right").replace("left", "right")
        else:
            name = name.replace("Right", "Left").replace("right", "left")
        mirrored = RigBone(
            id=target_id,
            name=name,
            role=source.role,
            side=opposite,
            parent_id=parent_id,
            rest_position=(
                center_x * 2.0 - source.rest_position[0],
                source.rest_position[1],
            ),
            rest_rotation=-source.rest_rotation,
            rotation=mirror_property(source.rotation, "scalar"),
            translation=mirror_property(source.translation, "vector2"),
            rotation_min=-source.rotation_max,
            rotation_max=-source.rotation_min,
            translation_locked=source.translation_locked,
            rotation_locked=source.rotation_locked,
            scale_locked=source.scale_locked,
            metadata=deepcopy(source.metadata),
        )
        if target is None:
            rig.bones.append(mirrored)
            by_role_side[(source.role, opposite)] = mirrored
            counterpart_by_id[source.id] = mirrored.id
            created.append(mirrored.id)
        else:
            rig.bones[rig.bones.index(target)] = mirrored
            updated.append(mirrored.id)
    upsert_rig(composition, rig)
    return {
        "rig_id": rig.id,
        "axis_x": center_x,
        "source_bone_ids": [bone.id for bone in sources],
        "created_bone_ids": created,
        "updated_bone_ids": updated,
    }


def delete_bone(composition: MotionComposition, rig_id: str, bone_id: str) -> bool:
    rig = find_rig(composition, rig_id)
    target = str(bone_id)
    if not any(row.id == target for row in rig.bones):
        return False
    parent_id = next(row.parent_id for row in rig.bones if row.id == target)
    rig.bones = [row for row in rig.bones if row.id != target]
    for bone in rig.bones:
        if bone.parent_id == target:
            bone.parent_id = parent_id
    rig.bindings = [row for row in rig.bindings if row.bone_id != target]
    if rig.root_bone_id == target:
        rig.root_bone_id = next((row.id for row in rig.bones if not row.parent_id), "")
    upsert_rig(composition, rig)
    return True


def bind_layer(
    composition: MotionComposition,
    rig_id: str,
    layer_id: str,
    bone_id: str,
    *,
    inherit_rotation: bool = True,
    inherit_scale: bool = True,
) -> RigLayerBinding:
    rig = find_rig(composition, rig_id)
    binding = RigLayerBinding(
        layer_id=str(layer_id),
        bone_id=str(bone_id),
        inherit_rotation=bool(inherit_rotation),
        inherit_scale=bool(inherit_scale),
    )
    rig.bindings = [row for row in rig.bindings if row.layer_id != binding.layer_id]
    rig.bindings.append(binding)
    upsert_rig(composition, rig)
    return binding


def unbind_layer(composition: MotionComposition, rig_id: str, layer_id: str) -> bool:
    rig = find_rig(composition, rig_id)
    rows = [row for row in rig.bindings if row.layer_id != str(layer_id)]
    if len(rows) == len(rig.bindings):
        return False
    rig.bindings = rows
    upsert_rig(composition, rig)
    return True


def remove_layer_bindings(composition: MotionComposition, layer_id: str) -> int:
    target = str(layer_id)
    changed = 0
    rigs = composition_rigs(composition)
    for rig in rigs:
        before = len(rig.bindings)
        rig.bindings = [row for row in rig.bindings if row.layer_id != target]
        changed += before - len(rig.bindings)
    if changed:
        set_composition_rigs(composition, rigs)
    return changed


def _normalize_angle(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def _set_property_value(
    prop: AnimatedProperty,
    value: Any,
    *,
    time_ms: int | None,
) -> None:
    if time_ms is None:
        prop.default = value
        return
    target = max(0, int(time_ms))
    prop.keyframes = [row for row in prop.keyframes if row.time_ms != target]
    prop.keyframes.append(Keyframe(time_ms=target, value=value, interpolation="bezier"))
    prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))


def _solve_two_bone_angles(
    rig: MotionRig,
    *,
    root_bone_id: str,
    mid_bone_id: str,
    end_bone_id: str,
    target: Sequence[float],
    pole: Sequence[float] | None = None,
) -> dict[str, Any]:
    by_id = {bone.id: bone for bone in rig.bones}
    root = by_id.get(str(root_bone_id))
    mid = by_id.get(str(mid_bone_id))
    end = by_id.get(str(end_bone_id))
    if root is None or mid is None or end is None:
        raise ValueError("Two-bone IK requires valid root, mid, and end bones")
    if mid.parent_id != root.id or end.parent_id != mid.id:
        raise ValueError("Two-bone IK bones must form a direct root -> mid -> end chain")
    root_point, mid_point, end_point = (
        root.rest_position,
        mid.rest_position,
        end.rest_position,
    )
    target_point = _point(target, end_point)
    length_a = hypot(mid_point[0] - root_point[0], mid_point[1] - root_point[1])
    length_b = hypot(end_point[0] - mid_point[0], end_point[1] - mid_point[1])
    if length_a <= 1e-5 or length_b <= 1e-5:
        raise ValueError("Two-bone IK requires non-zero bone lengths")
    dx = target_point[0] - root_point[0]
    dy = target_point[1] - root_point[1]
    raw_distance = hypot(dx, dy)
    distance = min(
        length_a + length_b - 1e-5,
        max(abs(length_a - length_b) + 1e-5, raw_distance),
    )
    target_angle = atan2(dy, dx)
    cosine = max(
        -1.0,
        min(
            1.0,
            (
                distance * distance
                + length_a * length_a
                - length_b * length_b
            )
            / (2.0 * distance * length_a),
        ),
    )
    bend = acos(cosine)
    pole_point = _point(pole, mid_point) if pole is not None else mid_point
    cross = (
        dx * (pole_point[1] - root_point[1])
        - dy * (pole_point[0] - root_point[0])
    )
    sign = 1.0 if cross >= 0.0 else -1.0
    desired_a = target_angle + sign * bend
    elbow = (
        root_point[0] + length_a * cos(desired_a),
        root_point[1] + length_a * sin(desired_a),
    )
    desired_b = atan2(
        target_point[1] - elbow[1],
        target_point[0] - elbow[0],
    )
    rest_a = atan2(
        mid_point[1] - root_point[1],
        mid_point[0] - root_point[0],
    )
    rest_b = atan2(
        end_point[1] - mid_point[1],
        end_point[0] - mid_point[0],
    )
    root_delta = _normalize_angle(degrees(desired_a - rest_a))
    mid_delta = _normalize_angle(degrees(desired_b - rest_b) - root_delta)
    unclamped = (root_delta, mid_delta)
    root_delta = max(root.rotation_min, min(root.rotation_max, root_delta))
    mid_delta = max(mid.rotation_min, min(mid.rotation_max, mid_delta))
    return {
        "rig_id": rig.id,
        "chain": [root.id, mid.id, end.id],
        "target": list(target_point),
        "pole": list(pole_point),
        "rotation": {
            root.id: float(root_delta),
            mid.id: float(mid_delta),
        },
        "clamped": bool(
            abs(root_delta - unclamped[0]) > 1e-6
            or abs(mid_delta - unclamped[1]) > 1e-6
        ),
        "reachable": abs(length_a - length_b) <= raw_distance <= length_a + length_b,
    }


def solve_two_bone_ik(
    composition: MotionComposition,
    rig_id: str,
    *,
    root_bone_id: str,
    mid_bone_id: str,
    end_bone_id: str,
    target: Sequence[float],
    pole: Sequence[float] | None = None,
    time_ms: int | None = None,
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    result = _solve_two_bone_angles(
        rig,
        root_bone_id=root_bone_id,
        mid_bone_id=mid_bone_id,
        end_bone_id=end_bone_id,
        target=target,
        pole=pole,
    )
    by_id = {bone.id: bone for bone in rig.bones}
    for bone_id, rotation in result["rotation"].items():
        _set_property_value(by_id[bone_id].rotation, rotation, time_ms=time_ms)
    upsert_rig(composition, rig)
    return result


def set_two_bone_ik_constraint(
    composition: MotionComposition,
    rig_id: str,
    *,
    root_bone_id: str,
    mid_bone_id: str,
    end_bone_id: str,
    target: Sequence[float] | Mapping[str, Any],
    pole: Sequence[float] | Mapping[str, Any] | None = None,
    weight: float | Mapping[str, Any] = 1.0,
    constraint_id: str = "",
    enabled: bool = True,
    lock_end: bool = True,
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    _solve_two_bone_angles(
        rig,
        root_bone_id=root_bone_id,
        mid_bone_id=mid_bone_id,
        end_bone_id=end_bone_id,
        target=_point(
            AnimatedProperty.from_dict(target, value_type="vector2").default
            if isinstance(target, Mapping)
            else target
        ),
        pole=_point(
            AnimatedProperty.from_dict(pole, value_type="vector2").default
            if isinstance(pole, Mapping)
            else pole
        ) if pole is not None else None,
    )
    row = {
        "id": str(constraint_id or new_motion_id("constraint")),
        "kind": RIG_CONSTRAINT_TWO_BONE_IK,
        "enabled": bool(enabled),
        "root_bone_id": str(root_bone_id),
        "mid_bone_id": str(mid_bone_id),
        "end_bone_id": str(end_bone_id),
        "target": AnimatedProperty.from_dict(
            target, value_type="vector2",
        ).to_dict(),
        "pole": AnimatedProperty.from_dict(
            pole if pole is not None else next(
                bone.rest_position
                for bone in rig.bones
                if bone.id == str(mid_bone_id)
            ),
            value_type="vector2",
        ).to_dict(),
        "weight": AnimatedProperty.from_dict(
            weight, value_type="scalar",
        ).to_dict(),
        "lock_end": bool(lock_end),
    }
    rig.constraints = [
        existing
        for existing in rig.constraints
        if str(existing.get("id") or "") != row["id"]
    ]
    rig.constraints.append(row)
    upsert_rig(composition, rig)
    return deepcopy(row)


def remove_rig_constraint(
    composition: MotionComposition,
    rig_id: str,
    constraint_id: str,
) -> bool:
    rig = find_rig(composition, rig_id)
    remaining = [
        row
        for row in rig.constraints
        if str(row.get("id") or "") != str(constraint_id)
    ]
    if len(remaining) == len(rig.constraints):
        return False
    rig.constraints = remaining
    upsert_rig(composition, rig)
    return True


def set_rig_constraint_enabled(
    composition: MotionComposition,
    rig_id: str,
    constraint_id: str,
    enabled: bool,
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    row = next(
        (
            value
            for value in rig.constraints
            if str(value.get("id") or "") == str(constraint_id)
        ),
        None,
    )
    if row is None:
        raise ValueError(f"Unknown rig constraint: {constraint_id}")
    row["enabled"] = bool(enabled)
    upsert_rig(composition, rig)
    return deepcopy(row)


def bake_two_bone_ik_constraint(
    composition: MotionComposition,
    rig_id: str,
    constraint_id: str,
    *,
    start_ms: int = 0,
    end_ms: int | None = None,
    sample_fps: float | None = None,
    disable_after: bool = True,
) -> dict[str, Any]:
    from .keyframes import evaluate_property

    rig = find_rig(composition, rig_id)
    row = next(
        (
            value
            for value in rig.constraints
            if str(value.get("id") or "") == str(constraint_id)
        ),
        None,
    )
    if row is None:
        raise ValueError(f"Unknown rig constraint: {constraint_id}")
    if str(row.get("kind") or "") != RIG_CONSTRAINT_TWO_BONE_IK:
        raise ValueError("Only two-bone IK constraints can be baked")
    start = max(0, int(start_ms))
    end = min(
        composition.duration_ms,
        max(start, int(end_ms if end_ms is not None else composition.duration_ms)),
    )
    fps = max(1.0, min(120.0, float(sample_fps or composition.fps)))
    step = max(1, round(1000.0 / fps))
    times = list(range(start, end + 1, step))
    if not times or times[-1] != end:
        times.append(end)
    target_prop = AnimatedProperty.from_dict(row.get("target"), value_type="vector2")
    pole_prop = AnimatedProperty.from_dict(row.get("pole"), value_type="vector2")
    weight_prop = AnimatedProperty.from_dict(row.get("weight", 1.0), value_type="scalar")
    by_id = {bone.id: bone for bone in rig.bones}
    affected = [str(row.get("root_bone_id") or ""), str(row.get("mid_bone_id") or "")]
    for time_ms in times:
        result = _solve_two_bone_angles(
            rig,
            root_bone_id=affected[0],
            mid_bone_id=affected[1],
            end_bone_id=str(row.get("end_bone_id") or ""),
            target=_point(evaluate_property(target_prop, time_ms)),
            pole=_point(evaluate_property(pole_prop, time_ms)),
        )
        weight_value = max(
            0.0,
            min(1.0, float(evaluate_property(weight_prop, time_ms) or 0.0)),
        )
        for bone_id, ik_rotation in result["rotation"].items():
            bone = by_id[bone_id]
            fk_rotation = float(evaluate_property(bone.rotation, time_ms) or 0.0)
            value = fk_rotation + (float(ik_rotation) - fk_rotation) * weight_value
            _set_property_value(bone.rotation, value, time_ms=time_ms)
    if disable_after:
        row["enabled"] = False
    upsert_rig(composition, rig)
    return {
        "rig_id": rig.id,
        "constraint_id": str(constraint_id),
        "start_ms": start,
        "end_ms": end,
        "sample_count": len(times),
        "affected_bone_ids": affected,
        "constraint_enabled": bool(row.get("enabled", True)),
    }


def save_pose(
    composition: MotionComposition,
    rig_id: str,
    *,
    name: str,
    time_ms: int = 0,
) -> dict[str, Any]:
    from .keyframes import evaluate_property

    rig = find_rig(composition, rig_id)
    pose = {
        "id": new_motion_id("pose"),
        "name": str(name or "Pose"),
        "bones": {
            bone.id: {
                "rotation": float(evaluate_property(bone.rotation, time_ms) or 0.0),
                "translation": list(_point(evaluate_property(bone.translation, time_ms))),
            }
            for bone in rig.bones
        },
    }
    rig.poses.append(pose)
    upsert_rig(composition, rig)
    return deepcopy(pose)


def apply_pose(
    composition: MotionComposition,
    rig_id: str,
    pose_id: str,
    *,
    time_ms: int | None = None,
    mirrored: bool = False,
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    pose = next(
        (row for row in rig.poses if str(row.get("id") or "") == str(pose_id)),
        None,
    )
    if pose is None:
        raise ValueError(f"Unknown rig pose: {pose_id}")
    source_values = _mapping(pose.get("bones"))
    counterpart: dict[str, str] = {}
    if mirrored:
        by_role_side = {
            (bone.role, bone.side): bone.id
            for bone in rig.bones
            if bone.role
        }
        for bone in rig.bones:
            other_side = "left" if bone.side == "right" else "right"
            counterpart[bone.id] = by_role_side.get((bone.role, other_side), bone.id)
    applied: dict[str, Any] = {}
    for bone in rig.bones:
        source_id = counterpart.get(bone.id, bone.id)
        values = _mapping(source_values.get(source_id))
        if not values:
            continue
        rotation = float(values.get("rotation", 0.0) or 0.0)
        translation = _point(values.get("translation"))
        if mirrored:
            rotation = -rotation
            translation = (-translation[0], translation[1])
        rotation = max(bone.rotation_min, min(bone.rotation_max, rotation))
        _set_property_value(bone.rotation, rotation, time_ms=time_ms)
        _set_property_value(
            bone.translation,
            [float(translation[0]), float(translation[1])],
            time_ms=time_ms,
        )
        applied[bone.id] = {
            "rotation": rotation,
            "translation": [float(translation[0]), float(translation[1])],
        }
    upsert_rig(composition, rig)
    return {
        "rig_id": rig.id,
        "pose_id": str(pose_id),
        "time_ms": time_ms,
        "mirrored": bool(mirrored),
        "bones": applied,
    }


def apply_motion_preset(
    composition: MotionComposition,
    rig_id: str,
    preset_id: str,
    *,
    start_ms: int = 0,
    end_ms: int | None = None,
    side: str = "right",
) -> dict[str, Any]:
    rig = find_rig(composition, rig_id)
    preset = str(preset_id or "").lower()
    start = max(0, int(start_ms))
    end = max(start + 1, int(end_ms if end_ms is not None else start + 1200))
    by_role_side = {
        (bone.role, bone.side): bone
        for bone in rig.bones
        if bone.role
    }
    affected: list[str] = []

    def keys(bone: RigBone | None, rows: Sequence[tuple[float, float]]) -> None:
        if bone is None:
            return
        span = end - start
        for progress, value in rows:
            _set_property_value(
                bone.rotation,
                max(bone.rotation_min, min(bone.rotation_max, float(value))),
                time_ms=start + round(span * float(progress)),
            )
        affected.append(bone.id)

    selected_side = "left" if str(side).lower() == "left" else "right"
    if preset == "arm_wave":
        keys(by_role_side.get(("upper_arm", selected_side)), ((0.0, 0), (.2, -55 if selected_side == "right" else 55), (.8, -55 if selected_side == "right" else 55), (1.0, 0)))
        keys(by_role_side.get(("forearm", selected_side)), ((0.0, 0), (.2, -55 if selected_side == "right" else 55), (.4, -78 if selected_side == "right" else 78), (.6, -35 if selected_side == "right" else 35), (.8, -78 if selected_side == "right" else 78), (1.0, 0)))
        keys(by_role_side.get(("hand", selected_side)), ((0.0, 0), (.35, 18), (.55, -18), (.75, 18), (1.0, 0)))
    elif preset == "head_nod":
        keys(by_role_side.get(("head", "center")), ((0.0, 0), (.3, 12), (.55, -5), (.8, 8), (1.0, 0)))
    elif preset == "walk_contact":
        for current_side, phase in (("left", 1.0), ("right", -1.0)):
            keys(by_role_side.get(("thigh", current_side)), ((0.0, 22 * phase), (.5, -22 * phase), (1.0, 22 * phase)))
            keys(by_role_side.get(("shin", current_side)), ((0.0, 8), (.25, 32 if phase > 0 else 5), (.75, 5 if phase > 0 else 32), (1.0, 8)))
            keys(by_role_side.get(("foot", current_side)), ((0.0, -6 * phase), (.5, 8 * phase), (1.0, -6 * phase)))
    else:
        raise ValueError(f"Unknown rig motion preset: {preset_id}")
    if not affected:
        raise ValueError(f"Rig does not contain bones required by preset: {preset_id}")
    upsert_rig(composition, rig)
    return {
        "rig_id": rig.id,
        "preset_id": preset,
        "start_ms": start,
        "end_ms": end,
        "side": selected_side,
        "affected_bone_ids": affected,
    }


def _affine_multiply(parent, child):
    pa, pb, pc, pd, ptx, pty = parent
    ca, cb, cc, cd, ctx, cty = child
    return (
        pa * ca + pc * cb,
        pb * ca + pd * cb,
        pa * cc + pc * cd,
        pb * cc + pd * cd,
        pa * ctx + pc * cty + ptx,
        pb * ctx + pd * cty + pty,
    )


def _affine_inverse(matrix):
    a, b, c, d, tx, ty = matrix
    determinant = a * d - b * c
    if abs(determinant) <= 1e-12:
        return 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
    inverse = 1.0 / determinant
    ia, ib, ic, id_ = d * inverse, -b * inverse, -c * inverse, a * inverse
    return ia, ib, ic, id_, -(ia * tx + ic * ty), -(ib * tx + id_ * ty)


def _joint_matrix(position: tuple[float, float], rotation: float):
    from math import radians

    angle = radians(float(rotation))
    cosine, sine = cos(angle), sin(angle)
    return cosine, sine, -sine, cosine, float(position[0]), float(position[1])


def evaluate_rig_layer_deltas(
    composition: MotionComposition,
    time_ms: float,
) -> dict[str, tuple[float, float, float, float, float, float]]:
    from .keyframes import evaluate_property

    deltas_by_layer: dict[str, tuple[float, float, float, float, float, float]] = {}
    for rig in composition_rigs(composition):
        if not rig.enabled:
            continue
        by_id = {bone.id: bone for bone in rig.bones}
        rotations = {
            bone.id: float(evaluate_property(bone.rotation, time_ms) or 0.0)
            for bone in rig.bones
        }
        for constraint in rig.constraints:
            if (
                not bool(constraint.get("enabled", True))
                or str(constraint.get("kind") or "") != RIG_CONSTRAINT_TWO_BONE_IK
            ):
                continue
            try:
                target = evaluate_property(
                    AnimatedProperty.from_dict(
                        constraint.get("target"), value_type="vector2",
                    ),
                    time_ms,
                )
                pole = evaluate_property(
                    AnimatedProperty.from_dict(
                        constraint.get("pole"), value_type="vector2",
                    ),
                    time_ms,
                )
                weight = max(
                    0.0,
                    min(
                        1.0,
                        float(
                            evaluate_property(
                                AnimatedProperty.from_dict(
                                    constraint.get("weight", 1.0),
                                    value_type="scalar",
                                ),
                                time_ms,
                            )
                            or 0.0
                        ),
                    ),
                )
                solved = _solve_two_bone_angles(
                    rig,
                    root_bone_id=str(constraint.get("root_bone_id") or ""),
                    mid_bone_id=str(constraint.get("mid_bone_id") or ""),
                    end_bone_id=str(constraint.get("end_bone_id") or ""),
                    target=_point(target),
                    pole=_point(pole),
                )
            except (TypeError, ValueError):
                continue
            for bone_id, ik_rotation in solved["rotation"].items():
                fk_rotation = rotations.get(bone_id, 0.0)
                rotations[bone_id] = (
                    fk_rotation + (float(ik_rotation) - fk_rotation) * weight
                )
        delta_cache: dict[str, tuple[float, float, float, float, float, float]] = {}

        def bone_delta(bone: RigBone, stack: set[str] | None = None):
            if bone.id in delta_cache:
                return delta_cache[bone.id]
            stack = set(stack or ())
            if bone.id in stack:
                return 1.0, 0.0, 0.0, 1.0, 0.0, 0.0
            stack.add(bone.id)
            translation = _point(evaluate_property(bone.translation, time_ms))
            rotation = rotations.get(bone.id, 0.0)
            position = (
                bone.rest_position[0] + translation[0],
                bone.rest_position[1] + translation[1],
            )
            current = _joint_matrix(position, rotation)
            parent = by_id.get(bone.parent_id)
            if parent is not None:
                current = _affine_multiply(bone_delta(parent, stack), current)
            rest = _joint_matrix(bone.rest_position, 0.0)
            delta_cache[bone.id] = _affine_multiply(current, _affine_inverse(rest))
            return delta_cache[bone.id]

        for binding in rig.bindings:
            bone = by_id.get(binding.bone_id)
            if bone is not None:
                deltas_by_layer[binding.layer_id] = bone_delta(bone)
    return deltas_by_layer


__all__ = [
    "MotionRig",
    "RIG_KIND_CUTOUT_2D",
    "RIG_CONSTRAINT_TWO_BONE_IK",
    "RIG_METADATA_KEY",
    "RIG_SCHEMA",
    "RigBone",
    "RigLayerBinding",
    "add_bone",
    "apply_motion_preset",
    "apply_pose",
    "bind_layer",
    "bake_two_bone_ik_constraint",
    "composition_rigs",
    "create_rig",
    "create_humanoid_rig",
    "delete_bone",
    "delete_rig",
    "find_rig",
    "evaluate_rig_layer_deltas",
    "mirror_rig_bones",
    "rig_for_layer",
    "remove_layer_bindings",
    "remove_rig_constraint",
    "save_pose",
    "set_composition_rigs",
    "set_rig_constraint_enabled",
    "set_two_bone_ik_constraint",
    "solve_two_bone_ik",
    "unbind_layer",
    "update_bone",
    "upsert_rig",
]
