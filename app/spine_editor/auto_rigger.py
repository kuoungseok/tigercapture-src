"""Auto-rigger: maps PSD layers → humanoid bone hierarchy.

Strategy:
1. Classify each layer by name keywords (language-agnostic patterns).
2. Assign layers to one of 14 body regions.
3. Build a bone hierarchy from the detected layout.
4. Map unclassified layers to the nearest bone.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

from app.spine_editor.psd_importer import LayerInfo
from app.spine_editor.spine_data import Bone, Slot, SpineSkeleton


# ── body-part keyword map ──────────────────────────────────────────────────

_KEYWORDS: dict[str, list[str]] = {
    "head":       ["head", "face", "얼굴", "머리", "顔", "头"],
    "hair":       ["hair", "머리카락", "髪", "发", "ahoge", "前髪", "後髪", "bang"],
    "eye":        ["eye", "눈", "目", "眼", "pupil", "iris", "eyelash", "eyebrow", "eyebrow"],
    "mouth":      ["mouth", "lip", "입", "口", "嘴", "teeth", "tongue"],
    "neck":       ["neck", "목", "首", "颈"],
    "body":       ["body", "torso", "chest", "bust", "몸", "胸", "身体", "上半身"],
    "arm_l":      ["arm_l", "arml", "arm left", "왼팔", "左腕", "左臂", "l_arm", "leftarm"],
    "arm_r":      ["arm_r", "armr", "arm right", "오른팔", "右腕", "右臂", "r_arm", "rightarm"],
    "hand_l":     ["hand_l", "handl", "hand left", "왼손", "左手", "l_hand", "lefthand"],
    "hand_r":     ["hand_r", "handr", "hand right", "오른손", "右手", "r_hand", "righthand"],
    "waist":      ["waist", "hip", "pelvis", "허리", "腰", "hips", "下半身"],
    "leg_l":      ["leg_l", "legl", "leg left", "왼다리", "左足", "左腿", "l_leg", "thigh_l", "shin_l"],
    "leg_r":      ["leg_r", "legr", "leg right", "오른다리", "右足", "右腿", "r_leg", "thigh_r", "shin_r"],
    "foot":       ["foot", "feet", "shoe", "발", "足", "脚"],
    "background": ["bg", "background", "배경", "背景", "back"],
    "shadow":     ["shadow", "그림자", "影"],
    "clothing":   ["cloth", "dress", "skirt", "shirt", "coat", "jacket", "outfit",
                   "clothes", "옷", "服", "衣"],
}

# Priority: more specific before general
_REGION_PRIORITY = [
    "hair", "eye", "mouth", "head", "neck",
    "hand_l", "hand_r", "arm_l", "arm_r",
    "foot", "leg_l", "leg_r",
    "waist", "clothing", "body",
    "shadow", "background",
]


def classify_layer(layer: LayerInfo) -> str:
    """Return a region key for the layer based on its name."""
    name_lower = layer.name.lower()
    for region in _REGION_PRIORITY:
        for kw in _KEYWORDS[region]:
            if kw in name_lower:
                return region
    return "body"  # default fallback


# ── auto-rig entry point ───────────────────────────────────────────────────

@dataclass
class RigResult:
    skeleton: SpineSkeleton
    layer_bone_map: dict[str, str]   # layer_name → bone_name
    canvas_w: int
    canvas_h: int


def auto_rig(layers: list[LayerInfo], canvas_w: int, canvas_h: int,
             skel_name: str = "character") -> RigResult:
    """
    Given a flat list of PSD layers, auto-generate a humanoid Spine skeleton.

    Coordinate convention: Spine uses Y-up with origin at bottom-left.
    PSD uses Y-down with origin at top-left.
    Conversion: spine_y = canvas_h - psd_y
    """
    def to_spine(px: float, py: float) -> tuple[float, float]:
        return px - canvas_w / 2, (canvas_h - py) - canvas_h / 2

    # Classify layers
    classified: dict[str, list[LayerInfo]] = {}
    for layer in layers:
        region = classify_layer(layer)
        classified.setdefault(region, []).append(layer)

    # Helper: average centre of a group of layers in Spine coords
    def group_centre(region: str) -> Optional[tuple[float, float]]:
        grp = classified.get(region)
        if not grp:
            return None
        cx = sum(l.cx for l in grp) / len(grp)
        cy = sum(l.cy for l in grp) / len(grp)
        return to_spine(cx, cy)

    def group_bbox(region: str) -> Optional[tuple[float, float, float, float]]:
        """Returns (min_x, min_y, max_x, max_y) in Spine space."""
        grp = classified.get(region)
        if not grp:
            return None
        all_pts = [(to_spine(l.left, l.top), to_spine(l.right, l.bottom)) for l in grp]
        xs = [p[0][0] for p in all_pts] + [p[1][0] for p in all_pts]
        ys = [p[0][1] for p in all_pts] + [p[1][1] for p in all_pts]
        return min(xs), min(ys), max(xs), max(ys)

    # ── derive key positions ───────────────────────────────────────────────
    head_c = group_centre("head") or group_centre("hair") or (0, canvas_h * 0.35)
    body_c = group_centre("body") or group_centre("clothing") or (0, 0)
    waist_c = group_centre("waist") or (body_c[0], body_c[1] - canvas_h * 0.12)

    arm_l_c = group_centre("arm_l") or (body_c[0] - canvas_w * 0.18, body_c[1] + canvas_h * 0.05)
    arm_r_c = group_centre("arm_r") or (body_c[0] + canvas_w * 0.18, body_c[1] + canvas_h * 0.05)
    hand_l_c = group_centre("hand_l") or (arm_l_c[0] - canvas_w * 0.05, arm_l_c[1] - canvas_h * 0.12)
    hand_r_c = group_centre("hand_r") or (arm_r_c[0] + canvas_w * 0.05, arm_r_c[1] - canvas_h * 0.12)

    leg_l_c = group_centre("leg_l") or (waist_c[0] - canvas_w * 0.07, waist_c[1] - canvas_h * 0.2)
    leg_r_c = group_centre("leg_r") or (waist_c[0] + canvas_w * 0.07, waist_c[1] - canvas_h * 0.2)
    foot_l_c = group_centre("foot") or (leg_l_c[0], leg_l_c[1] - canvas_h * 0.18)
    foot_r_c = (leg_r_c[0], leg_r_c[1] - canvas_h * 0.18)

    # ── build skeleton ─────────────────────────────────────────────────────
    skel = SpineSkeleton(name=skel_name, width=float(canvas_w), height=float(canvas_h))

    def add(name, parent, x, y, length=40, rotation=0.0):
        """Add bone with local coords relative to parent world position."""
        skel.bones.append(Bone(
            name=name, parent=parent,
            x=x, y=y, length=length, rotation=rotation,
        ))

    # Root at waist
    wx, wy = waist_c
    add("root", None, wx, wy, length=0)

    # Hip (same as root for humanoid)
    add("hip", "root", 0, 0, length=30)

    # Spine → chest
    chest_y = body_c[1] - waist_c[1]
    spine_mid_y = chest_y * 0.5
    add("spine", "hip", 0, spine_mid_y, length=abs(spine_mid_y) or 40, rotation=90)
    add("chest", "spine", abs(spine_mid_y) or 40, 0, length=30, rotation=0)

    # Neck → head
    neck_y = (head_c[1] - body_c[1]) * 0.4
    add("neck", "chest", 30, 0, length=max(20, abs(neck_y)), rotation=0)
    head_local_x = max(20, abs(neck_y))
    add("head", "neck", head_local_x, 0, length=50, rotation=0)

    # Left arm (world → local relative to chest)
    al_x = arm_l_c[0] - body_c[0]
    al_y = arm_l_c[1] - body_c[1]
    arm_l_len = math.hypot(al_x - (hand_l_c[0] - body_c[0]), al_y - (hand_l_c[1] - body_c[1]))
    arm_l_len = max(30, arm_l_len * 0.55)
    add("shoulder_L", "chest", al_x, al_y, length=arm_l_len * 0.5, rotation=180)
    add("arm_L", "shoulder_L", arm_l_len * 0.5, 0, length=arm_l_len * 0.5, rotation=0)
    add("hand_L", "arm_L", arm_l_len * 0.5, 0, length=20, rotation=0)

    # Right arm
    ar_x = arm_r_c[0] - body_c[0]
    ar_y = arm_r_c[1] - body_c[1]
    arm_r_len = math.hypot(ar_x - (hand_r_c[0] - body_c[0]), ar_y - (hand_r_c[1] - body_c[1]))
    arm_r_len = max(30, arm_r_len * 0.55)
    add("shoulder_R", "chest", ar_x, ar_y, length=arm_r_len * 0.5, rotation=0)
    add("arm_R", "shoulder_R", arm_r_len * 0.5, 0, length=arm_r_len * 0.5, rotation=0)
    add("hand_R", "arm_R", arm_r_len * 0.5, 0, length=20, rotation=0)

    # Left leg
    ll_x = leg_l_c[0] - waist_c[0]
    ll_y = leg_l_c[1] - waist_c[1]
    leg_l_len = max(40, abs(leg_l_c[1] - foot_l_c[1]) * 0.55)
    add("thigh_L", "hip", ll_x, ll_y, length=leg_l_len, rotation=270)
    add("shin_L", "thigh_L", leg_l_len, 0, length=leg_l_len * 0.9, rotation=0)
    add("foot_L", "shin_L", leg_l_len * 0.9, 0, length=25, rotation=20)

    # Right leg
    lr_x = leg_r_c[0] - waist_c[0]
    lr_y = leg_r_c[1] - waist_c[1]
    leg_r_len = max(40, abs(leg_r_c[1] - foot_r_c[1]) * 0.55)
    add("thigh_R", "hip", lr_x, lr_y, length=leg_r_len, rotation=270)
    add("shin_R", "thigh_R", leg_r_len, 0, length=leg_r_len * 0.9, rotation=0)
    add("foot_R", "shin_R", leg_r_len * 0.9, 0, length=25, rotation=20)

    skel.update_world_transforms()

    # ── build slots and layer→bone mapping ────────────────────────────────
    layer_bone_map: dict[str, str] = {}
    _REGION_TO_BONE = {
        "head": "head", "hair": "head", "eye": "head", "mouth": "head",
        "neck": "neck",
        "body": "chest", "clothing": "chest",
        "arm_l": "arm_L", "hand_l": "hand_L",
        "arm_r": "arm_R", "hand_r": "hand_R",
        "waist": "hip",
        "leg_l": "thigh_L", "leg_r": "thigh_R",
        "foot": "foot_L",
        "shadow": "root", "background": "root",
    }

    for layer in layers:
        region = classify_layer(layer)
        bone_name = _REGION_TO_BONE.get(region, "chest")
        layer_bone_map[layer.name] = bone_name
        skel.slots.append(Slot(
            name=layer.name,
            bone=bone_name,
            attachment=layer.name,
        ))

    return RigResult(
        skeleton=skel,
        layer_bone_map=layer_bone_map,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
    )
