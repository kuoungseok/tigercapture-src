"""Two-bone IK solver for Spine skeletons (law of cosines)."""
from __future__ import annotations
import math
from app.spine_editor.spine_data import SpineSkeleton


def solve_2bone_ik(skel: SpineSkeleton,
                   bone_a: str, bone_b: str,
                   target_x: float, target_y: float,
                   bend_positive: bool = True) -> bool:
    """
    Solve IK for a two-bone chain (bone_a → bone_b) pointing at (target_x, target_y).
    Modifies bone_a.rotation and bone_b.rotation (local), then calls update_world_transforms.
    Returns False if target is unreachable.
    """
    a = skel.bone(bone_a)
    b = skel.bone(bone_b)
    if a is None or b is None:
        return False

    len_a = a.length
    len_b = b.length
    if len_a <= 0 or len_b <= 0:
        return False

    # Root position of the chain
    rx, ry = a.world_x, a.world_y

    # Vector from root to target in world space
    dx = target_x - rx
    dy = target_y - ry
    dist = math.hypot(dx, dy)

    # Clamp to reachable range
    dist_clamped = max(abs(len_a - len_b) + 1e-6,
                       min(dist, len_a + len_b - 1e-6))

    # Angle of line from root to target
    angle_to_target = math.degrees(math.atan2(dy, dx))

    # Law of cosines: angle at root joint
    cos_a = (len_a**2 + dist_clamped**2 - len_b**2) / (2 * len_a * dist_clamped)
    cos_a = max(-1.0, min(1.0, cos_a))
    angle_a = math.degrees(math.acos(cos_a))

    # Elbow direction
    if bend_positive:
        rot_a = angle_to_target - angle_a
    else:
        rot_a = angle_to_target + angle_a

    # b's angle relative to a
    cos_b = (len_a**2 + len_b**2 - dist_clamped**2) / (2 * len_a * len_b)
    cos_b = max(-1.0, min(1.0, cos_b))
    angle_b_world = 180.0 - math.degrees(math.acos(cos_b))

    # Convert world rotation to local (relative to parent)
    parent_a = skel.bone(a.parent) if a.parent else None
    parent_world_rot = parent_a.world_rotation if parent_a else 0.0

    a.rotation = rot_a - parent_world_rot
    b.rotation = (angle_b_world if not bend_positive else -angle_b_world)

    skel.update_world_transforms()
    return True


def apply_ik_constraints(skel: SpineSkeleton) -> None:
    """Apply all IK constraints stored in skel.ik_constraints list."""
    for ik in getattr(skel, "ik_constraints", []):
        if len(ik.get("bones", [])) == 2:
            solve_2bone_ik(
                skel,
                ik["bones"][0], ik["bones"][1],
                ik.get("target_x", 0), ik.get("target_y", 0),
                ik.get("bend_positive", True),
            )
