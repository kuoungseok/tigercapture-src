"""Spine 2D animation data model — Spine runtime-compatible transforms.

World transform algorithm matches spine-csharp Bone.UpdateWorldTransform(),
including all 5 transform modes and shear support.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

# Transform mode constants (matches Spine TransformMode enum)
TM_NORMAL               = 0
TM_ONLY_TRANSLATION     = 1
TM_NO_ROTATION          = 2   # NoRotationOrReflection
TM_NO_SCALE             = 3
TM_NO_SCALE_OR_REFLECT  = 4

_TRANSFORM_MODE_NAMES = {
    "normal":                 TM_NORMAL,
    "onlytranslation":        TM_ONLY_TRANSLATION,
    "norotationorreflection": TM_NO_ROTATION,
    "noscale":                TM_NO_SCALE,
    "noscaleorreflection":    TM_NO_SCALE_OR_REFLECT,
}


def _parse_transform_mode(s: str) -> int:
    return _TRANSFORM_MODE_NAMES.get((s or "").lower().replace(" ", ""), TM_NORMAL)


def _cos(deg: float) -> float:
    return math.cos(math.radians(deg))

def _sin(deg: float) -> float:
    return math.sin(math.radians(deg))


@dataclass
class Bone:
    name: str
    parent: Optional[str] = None
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    shear_x: float = 0.0
    shear_y: float = 0.0
    length: float = 60.0
    transform_mode: int = TM_NORMAL

    # Bind pose — saved after parsing, reset to each frame
    bind_rotation: float = 0.0
    bind_x: float = 0.0
    bind_y: float = 0.0
    bind_scale_x: float = 1.0
    bind_scale_y: float = 1.0
    bind_shear_x: float = 0.0
    bind_shear_y: float = 0.0

    # World transform (computed by update_world_transforms)
    world_x: float = 0.0
    world_y: float = 0.0
    # 2x2 world matrix: [a b ; c d]
    # vertex_world = bone.a*vx + bone.b*vy + bone.world_x
    #                bone.c*vx + bone.d*vy + bone.world_y
    a: float = 1.0   # m00
    b: float = 0.0   # m01
    c: float = 0.0   # m10
    d: float = 1.0   # m11

    # Legacy aliases kept for renderer compatibility
    @property
    def m00(self) -> float: return self.a
    @property
    def m01(self) -> float: return self.b
    @property
    def m10(self) -> float: return self.c
    @property
    def m11(self) -> float: return self.d

    def tip_pos(self) -> tuple[float, float]:
        """World position of bone tip (for editor visualisation)."""
        world_rot = math.atan2(self.c, self.a)
        return (
            self.world_x + math.cos(world_rot) * self.length,
            self.world_y + math.sin(world_rot) * self.length,
        )

    def world_matrix(self) -> np.ndarray:
        return np.array([
            [self.a, self.b, self.world_x],
            [self.c, self.d, self.world_y],
            [0.0,    0.0,    1.0],
        ], dtype=np.float64)


@dataclass
class Slot:
    name: str
    bone: str
    attachment: Optional[str] = None
    color: str = "ffffffff"
    bind_attachment: Optional[str] = None


@dataclass
class RegionAttachment:
    """A rectangular image region (or mesh) attached to a slot."""
    name: str
    path: str = ""
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    width: float = 100.0
    height: float = 100.0
    mesh_weights: list = field(default_factory=list)
    mesh_uvs: list = field(default_factory=list)
    mesh_triangles: list = field(default_factory=list)


@dataclass
class BoneKeyframe:
    time: float
    value: float
    curve: str = "linear"


@dataclass
class BoneTimeline:
    bone: str
    property: str   # rotate | translateX | translateY | scaleX | scaleY | shearX | shearY
    keyframes: list[BoneKeyframe] = field(default_factory=list)

    def value_at(self, time: float) -> float:
        if not self.keyframes:
            return 0.0
        if time <= self.keyframes[0].time:
            return self.keyframes[0].value
        if time >= self.keyframes[-1].time:
            return self.keyframes[-1].value
        for i in range(len(self.keyframes) - 1):
            k0, k1 = self.keyframes[i], self.keyframes[i + 1]
            if k0.time <= time <= k1.time:
                t = (time - k0.time) / max(k1.time - k0.time, 1e-9)
                if k0.curve == "stepped":
                    return k0.value
                return k0.value + (k1.value - k0.value) * t
        return 0.0


@dataclass
class DeformKeyframe:
    time: float
    vertices: list[float] = field(default_factory=list)
    curve: str = "linear"


@dataclass
class DeformTimeline:
    slot: str
    attachment: str
    keyframes: list[DeformKeyframe] = field(default_factory=list)

    def value_at(self, time: float) -> list[float]:
        if not self.keyframes:
            return []
        if time <= self.keyframes[0].time:
            return list(self.keyframes[0].vertices)
        if time >= self.keyframes[-1].time:
            return list(self.keyframes[-1].vertices)
        for i in range(len(self.keyframes) - 1):
            k0, k1 = self.keyframes[i], self.keyframes[i + 1]
            if k0.time <= time <= k1.time:
                if k0.curve == "stepped":
                    return list(k0.vertices)
                denom = max(k1.time - k0.time, 1e-9)
                alpha = (time - k0.time) / denom
                n = min(len(k0.vertices), len(k1.vertices))
                return [
                    k0.vertices[j] + (k1.vertices[j] - k0.vertices[j]) * alpha
                    for j in range(n)
                ]
        return []


@dataclass
class IKConstraint:
    name: str
    bones: list[str] = field(default_factory=list)
    target: str = ""
    order: int = 0
    mix: float = 1.0
    compress: bool = False
    stretch: bool = False
    uniform: bool = False


@dataclass
class IKKeyframe:
    time: float
    mix: float = 1.0
    curve: str = "linear"


@dataclass
class IKTimeline:
    name: str
    keyframes: list[IKKeyframe] = field(default_factory=list)

    def value_at(self, time: float) -> float:
        if not self.keyframes:
            return 1.0
        if time <= self.keyframes[0].time:
            return self.keyframes[0].mix
        if time >= self.keyframes[-1].time:
            return self.keyframes[-1].mix
        for i in range(len(self.keyframes) - 1):
            k0, k1 = self.keyframes[i], self.keyframes[i + 1]
            if k0.time <= time <= k1.time:
                if k0.curve == "stepped":
                    return k0.mix
                denom = max(k1.time - k0.time, 1e-9)
                alpha = (time - k0.time) / denom
                return k0.mix + (k1.mix - k0.mix) * alpha
        return self.keyframes[-1].mix


@dataclass
class SlotAttachmentKeyframe:
    time: float
    attachment: Optional[str] = None


@dataclass
class SlotAttachmentTimeline:
    slot: str
    keyframes: list[SlotAttachmentKeyframe] = field(default_factory=list)

    def value_at(self, time: float) -> Optional[str]:
        if not self.keyframes:
            return None
        current = self.keyframes[0].attachment
        for keyframe in self.keyframes:
            if time < keyframe.time:
                break
            current = keyframe.attachment
        return current


@dataclass
class Animation:
    name: str
    duration: float = 1.0
    timelines: list = field(default_factory=list)


@dataclass
class SpineSkeleton:
    name: str = "skeleton"
    width: float = 500.0
    height: float = 800.0
    bones: list[Bone] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)
    skins: dict = field(default_factory=dict)
    animations: dict[str, Animation] = field(default_factory=dict)
    active_deforms: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    ik_constraints: list[IKConstraint] = field(default_factory=list)
    active_ik_mixes: dict[str, float] = field(default_factory=dict)

    def bone(self, name: str) -> Optional[Bone]:
        return next((b for b in self.bones if b.name == name), None)

    def store_bind_pose(self) -> None:
        for b in self.bones:
            b.bind_rotation  = b.rotation
            b.bind_x         = b.x
            b.bind_y         = b.y
            b.bind_scale_x   = b.scale_x
            b.bind_scale_y   = b.scale_y
            b.bind_shear_x   = b.shear_x
            b.bind_shear_y   = b.shear_y
        for s in self.slots:
            s.bind_attachment = s.attachment

    def _update_world_transforms_raw(self) -> None:
        """Recompute world transforms — matches spine-csharp Bone.UpdateWorldTransform.

        All 5 transform modes supported. Shear is included in the 2x2 matrix.
        Bones must be ordered parent-before-child (as Spine exports them).
        """
        sx_skel = 1.0   # skeleton global scale (always 1 for us)
        sy_skel = 1.0

        for bone in self.bones:
            rot  = bone.rotation
            hx   = bone.shear_x
            hy   = bone.shear_y
            sclx = bone.scale_x
            scly = bone.scale_y
            lx   = bone.x
            ly   = bone.y

            rot_y = rot + 90.0 + hy
            la = _cos(rot + hx) * sclx
            lb = _cos(rot_y)    * scly
            lc = _sin(rot + hx) * sclx
            ld = _sin(rot_y)    * scly

            parent = self.bone(bone.parent) if bone.parent else None

            if parent is None:
                bone.world_x = lx * sx_skel
                bone.world_y = ly * sy_skel
                bone.a = la * sx_skel
                bone.b = lb * sx_skel
                bone.c = lc * sy_skel
                bone.d = ld * sy_skel
                continue

            pa, pb, pc, pd = parent.a, parent.b, parent.c, parent.d
            bone.world_x = pa * lx + pb * ly + parent.world_x
            bone.world_y = pc * lx + pd * ly + parent.world_y

            mode = bone.transform_mode

            if mode == TM_NORMAL:
                bone.a = pa * la + pb * lc
                bone.b = pa * lb + pb * ld
                bone.c = pc * la + pd * lc
                bone.d = pc * lb + pd * ld

            elif mode == TM_ONLY_TRANSLATION:
                bone.a = la
                bone.b = lb
                bone.c = lc
                bone.d = ld

            elif mode == TM_NO_ROTATION:
                s = pa * pa + pc * pc
                prx: float
                if s > 1e-4:
                    s   = abs(pa * pd - pb * pc) / s
                    pb2 = pc * s
                    pd2 = pa * s
                    prx = math.degrees(math.atan2(pc, pa))
                else:
                    pa  = 0.0
                    pc  = 0.0
                    prx = 90.0 - math.degrees(math.atan2(pd, pb))
                    pb2 = pb
                    pd2 = pd
                rx = rot + hx  - prx
                ry = rot + hy  - prx + 90.0
                bone.a = _cos(rx) * sclx * pa  - _cos(ry) * scly * pb2
                bone.b = _cos(rx) * sclx * pb2 + _cos(ry) * scly * pd2  # approximation
                bone.c = _sin(rx) * sclx * pc  + _sin(ry) * scly * pd2
                bone.d = _sin(rx) * sclx * pb2 + _sin(ry) * scly * pd2
                # Proper no-rotation-or-reflection (spine-csharp)
                _la = _cos(rx) * sclx
                _lb = _cos(ry) * scly
                _lc = _sin(rx) * sclx
                _ld = _sin(ry) * scly
                bone.a = pa * _la - pb2 * _lc
                bone.b = pa * _lb - pb2 * _ld
                bone.c = pc * _la + pd2 * _lc
                bone.d = pc * _lb + pd2 * _ld

            elif mode in (TM_NO_SCALE, TM_NO_SCALE_OR_REFLECT):
                cos_r = _cos(rot)
                sin_r = _sin(rot)
                za = (pa * cos_r + pb * sin_r) / sx_skel
                zc = (pc * cos_r + pd * sin_r) / sy_skel
                s  = math.sqrt(za * za + zc * zc)
                if s > 1e-5:
                    s = 1.0 / s
                za *= s
                zc *= s
                s = math.sqrt(za * za + zc * zc)
                # Reflection handling
                if (mode == TM_NO_SCALE and
                        ((pa * pd - pb * pc < 0) !=
                         ((sx_skel < 0) != (sy_skel < 0)))):
                    s = -s
                r  = math.pi / 2.0 + math.atan2(zc, za)
                zb = math.cos(r) * s
                zd = math.sin(r) * s
                nla = _cos(hx) * sclx
                nlb = _cos(90.0 + hy) * scly
                nlc = _sin(hx) * sclx
                nld = _sin(90.0 + hy) * scly
                bone.a = za * nla + zb * nlc
                bone.b = za * nlb + zb * nld
                bone.c = zc * nla + zd * nlc
                bone.d = zc * nlb + zd * nld

            else:   # fallback
                bone.a, bone.b, bone.c, bone.d = pa, pb, pc, pd

    def update_world_transforms(self, apply_constraints: bool = False) -> None:
        self._update_world_transforms_raw()
        if not apply_constraints or not self.ik_constraints:
            return
        for con in sorted(self.ik_constraints, key=lambda c: c.order):
            mix = self.active_ik_mixes.get(con.name, con.mix)
            if mix <= 1e-5:
                continue
            if self._apply_one_bone_ik(con, mix):
                self._update_world_transforms_raw()

    def _apply_one_bone_ik(self, con: IKConstraint, mix: float) -> bool:
        if len(con.bones) != 1:
            return False
        bone = self.bone(con.bones[0])
        target = self.bone(con.target)
        if bone is None or target is None:
            return False
        parent = self.bone(bone.parent) if bone.parent else None
        if parent is None:
            pa, pb, pc, pd = 1.0, 0.0, 0.0, 1.0
            pwx = pwy = 0.0
        else:
            pa, pb, pc, pd = parent.a, parent.b, parent.c, parent.d
            pwx, pwy = parent.world_x, parent.world_y

        rotation_ik = -bone.shear_x - bone.rotation
        tx = ty = 0.0
        if bone.transform_mode == TM_ONLY_TRANSLATION:
            tx = target.world_x - bone.world_x
            ty = target.world_y - bone.world_y
        else:
            if bone.transform_mode == TM_NO_ROTATION:
                s = abs(pa * pd - pb * pc) / max(0.0001, pa * pa + pc * pc)
                sa = pa
                sc = pc
                pb = -sc * s
                pd = sa * s
                rotation_ik += math.degrees(math.atan2(sc, sa))
            x = target.world_x - pwx
            y = target.world_y - pwy
            det = pa * pd - pb * pc
            if abs(det) > 0.0001:
                tx = (x * pd - y * pb) / det - bone.x
                ty = (y * pa - x * pc) / det - bone.y

        rotation_ik += math.degrees(math.atan2(ty, tx))
        if bone.scale_x < 0:
            rotation_ik += 180.0
        rotation_ik = (rotation_ik + 180.0) % 360.0 - 180.0

        alpha = max(0.0, min(1.0, mix))
        sx = bone.scale_x
        sy = bone.scale_y
        if con.compress or con.stretch:
            if bone.transform_mode in (TM_NO_SCALE, TM_NO_SCALE_OR_REFLECT):
                tx = target.world_x - bone.world_x
                ty = target.world_y - bone.world_y
            reach = bone.length * sx
            dist = math.sqrt(tx * tx + ty * ty)
            if ((con.compress and dist < reach) or
                    (con.stretch and dist > reach and abs(reach) > 0.0001)):
                scale = (dist / reach - 1.0) * alpha + 1.0
                sx *= scale
                if con.uniform:
                    sy *= scale

        bone.rotation += rotation_ik * alpha
        bone.scale_x = sx
        bone.scale_y = sy
        return True

    def apply_animation(self, anim: Animation, time: float) -> None:
        """Reset to bind pose then apply animation keyframes."""
        self.active_deforms.clear()
        self.active_ik_mixes = {c.name: c.mix for c in self.ik_constraints}
        for slot in self.slots:
            slot.attachment = slot.bind_attachment

        for bone in self.bones:
            bone.rotation = bone.bind_rotation
            bone.x        = bone.bind_x
            bone.y        = bone.bind_y
            bone.scale_x  = bone.bind_scale_x
            bone.scale_y  = bone.bind_scale_y
            bone.shear_x  = bone.bind_shear_x
            bone.shear_y  = bone.bind_shear_y

        for tl in anim.timelines:
            if isinstance(tl, SlotAttachmentTimeline):
                attachment = tl.value_at(time)
                slot = next((s for s in self.slots if s.name == tl.slot), None)
                if slot is not None:
                    slot.attachment = attachment
                continue

            if isinstance(tl, DeformTimeline):
                value = tl.value_at(time)
                if value:
                    self.active_deforms[(tl.slot, tl.attachment)] = value
                continue

            if isinstance(tl, IKTimeline):
                self.active_ik_mixes[tl.name] = tl.value_at(time)
                continue

            # Skip slot timelines (prefixed with __slot_)
            if tl.bone.startswith("__slot_"):
                continue
            bone = self.bone(tl.bone)
            if bone is None:
                continue
            v = tl.value_at(time)
            p = tl.property
            if   p == "rotate":      bone.rotation += v          # additive
            elif p == "translateX":  bone.x        += v          # additive
            elif p == "translateY":  bone.y        += v          # additive
            elif p == "scaleX":      bone.scale_x  += v - 1.0   # bind + (v-1)
            elif p == "scaleY":      bone.scale_y  += v - 1.0
            elif p == "shearX":      bone.shear_x  += v
            elif p == "shearY":      bone.shear_y  += v

        self.update_world_transforms(apply_constraints=True)

    def to_json(self) -> dict:
        return {
            "skeleton": {"name": self.name, "width": self.width, "height": self.height},
            "bones": [
                {k: v for k, v in {
                    "name": b.name, "parent": b.parent,
                    "x": b.x, "y": b.y, "rotation": b.rotation,
                    "scaleX": b.scale_x if b.scale_x != 1 else None,
                    "scaleY": b.scale_y if b.scale_y != 1 else None,
                    "length": b.length,
                }.items() if v is not None}
                for b in self.bones
            ],
            "slots": [
                {"name": s.name, "bone": s.bone, "attachment": s.attachment}
                for s in self.slots
            ],
        }


def make_humanoid_skeleton(name: str = "character") -> SpineSkeleton:
    skel = SpineSkeleton(name=name, width=400, height=600)
    skel.bones = [
        Bone("root"),
        Bone("hip",   parent="root",  x=0,  y=100, length=40),
        Bone("spine", parent="hip",   x=0,  y=40,  length=80,  rotation=90),
        Bone("chest", parent="spine", x=80, y=0,   length=60),
        Bone("head",  parent="chest", x=90, y=0,   length=60),
        Bone("arm_L", parent="chest", x=20, y=40,  length=80,  rotation=180),
        Bone("arm_R", parent="chest", x=20, y=-40, length=80),
        Bone("leg_L", parent="hip",   x=0,  y=30,  length=120, rotation=270),
        Bone("leg_R", parent="hip",   x=0,  y=-30, length=120, rotation=270),
    ]
    skel.update_world_transforms()
    return skel
