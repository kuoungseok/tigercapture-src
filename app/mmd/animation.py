"""CPU-side PMX pose evaluation for the MMD player MVP."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math

import numpy as np

from .pmx import MMDModel
from .physics import MMDPhysicsBackend, MMDPhysicsPoseDelta, MMDPhysicsState
from .vmd import VMDMotion, bone_pose_at, morph_weights_at


_BONE_TOPOLOGY_CACHE_LIMIT = 16
_BONE_TOPOLOGY_CACHE: OrderedDict[tuple[int, str, int], "_BoneTopology"] = OrderedDict()


@dataclass(frozen=True)
class MMDPoseGeometry:
    positions: np.ndarray
    normals: np.ndarray
    skinned: bool
    active_morph_count: int
    active_bone_count: int
    active_ik_count: int = 0
    physics_body_count: int = 0
    active_sdef_count: int = 0
    bone_matrices: np.ndarray | None = None
    gpu_morph_names: tuple[str, ...] = ()
    gpu_morph_weights: tuple[float, ...] = ()


@dataclass(frozen=True)
class _BoneTopology:
    positions: np.ndarray
    parent_indices: np.ndarray
    base_deltas: np.ndarray
    inherit_indices: np.ndarray
    inherit_weights: np.ndarray
    flags: np.ndarray

    @property
    def bone_count(self) -> int:
        return int(self.positions.shape[0])


def _bone_topology(model: MMDModel) -> _BoneTopology:
    key = (id(model), str(getattr(model, "path", "")), len(model.bones))
    cached = _BONE_TOPOLOGY_CACHE.get(key)
    if cached is not None:
        _BONE_TOPOLOGY_CACHE.move_to_end(key)
        return cached
    positions = np.asarray([bone.position for bone in model.bones], dtype=np.float32)
    parent_indices = np.asarray([int(bone.parent_index) for bone in model.bones], dtype=np.int32)
    inherit_indices = np.asarray([int(bone.inherit_parent_index) for bone in model.bones], dtype=np.int32)
    inherit_weights = np.asarray([float(bone.inherit_weight) for bone in model.bones], dtype=np.float32)
    flags = np.asarray([int(bone.flags) for bone in model.bones], dtype=np.int32)
    base_deltas = np.zeros_like(positions, dtype=np.float32)
    for i, parent in enumerate(parent_indices):
        if 0 <= int(parent) < len(model.bones):
            base_deltas[i] = positions[i] - positions[int(parent)]
        else:
            base_deltas[i] = positions[i]
    topology = _BoneTopology(
        positions=np.ascontiguousarray(positions, dtype=np.float32),
        parent_indices=parent_indices,
        base_deltas=np.ascontiguousarray(base_deltas, dtype=np.float32),
        inherit_indices=inherit_indices,
        inherit_weights=inherit_weights,
        flags=flags,
    )
    _BONE_TOPOLOGY_CACHE[key] = topology
    _BONE_TOPOLOGY_CACHE.move_to_end(key)
    while len(_BONE_TOPOLOGY_CACHE) > _BONE_TOPOLOGY_CACHE_LIMIT:
        _BONE_TOPOLOGY_CACHE.popitem(last=False)
    return topology


def _translation(v: np.ndarray) -> np.ndarray:
    out = np.eye(4, dtype=np.float32)
    out[:3, 3] = np.asarray(v, dtype=np.float32)[:3]
    return out


def _normalize_vec(v: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(v))
    if length <= 0.000001:
        return np.zeros((3,), dtype=np.float32)
    return np.asarray(v, dtype=np.float32) / length


def _quat_normalize(q: tuple[float, float, float, float] | np.ndarray) -> tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 0.000001:
        return 0.0, 0.0, 0.0, 1.0
    return x / length, y / length, z / length, w / length


def _quat_multiply(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return _quat_normalize((
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ))


def _quat_slerp(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    dot = ax * bx + ay * by + az * bz + aw * bw
    if dot < 0.0:
        bx, by, bz, bw = -bx, -by, -bz, -bw
        dot = -dot
    if dot > 0.9995:
        return _quat_normalize((ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t, aw + (bw - aw) * t))
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return (ax * s0 + bx * s1, ay * s0 + by * s1, az * s0 + bz * s1, aw * s0 + bw * s1)


def _quat_between(src: np.ndarray, dst: np.ndarray, max_angle: float | None = None) -> tuple[float, float, float, float]:
    a = _normalize_vec(src)
    b = _normalize_vec(dst)
    if float(np.linalg.norm(a)) <= 0.000001 or float(np.linalg.norm(b)) <= 0.000001:
        return 0.0, 0.0, 0.0, 1.0
    dot = max(-1.0, min(1.0, float(np.dot(a, b))))
    axis = np.cross(a, b)
    axis_len = float(np.linalg.norm(axis))
    if axis_len <= 0.000001:
        if dot > 0.0:
            return 0.0, 0.0, 0.0, 1.0
        axis = _normalize_vec(np.cross(a, np.asarray((1.0, 0.0, 0.0), dtype=np.float32)))
        if float(np.linalg.norm(axis)) <= 0.000001:
            axis = np.asarray((0.0, 1.0, 0.0), dtype=np.float32)
    else:
        axis = axis / axis_len
    angle = math.acos(dot)
    if max_angle is not None:
        angle = max(-abs(max_angle), min(abs(max_angle), angle))
    half = angle * 0.5
    s = math.sin(half)
    return _quat_normalize((float(axis[0] * s), float(axis[1] * s), float(axis[2] * s), math.cos(half)))


def _matrix_to_quat(mat: np.ndarray) -> tuple[float, float, float, float]:
    m = np.asarray(mat, dtype=np.float32)
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return _quat_normalize(((m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s))
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + float(m[0, 0] - m[1, 1] - m[2, 2])) * 2.0
        return _quat_normalize((0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s, (m[2, 1] - m[1, 2]) / s))
    if m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + float(m[1, 1] - m[0, 0] - m[2, 2])) * 2.0
        return _quat_normalize(((m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s, (m[0, 2] - m[2, 0]) / s))
    s = math.sqrt(1.0 + float(m[2, 2] - m[0, 0] - m[1, 1])) * 2.0
    return _quat_normalize(((m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s, (m[1, 0] - m[0, 1]) / s))


def _quat_rotate(q: tuple[float, float, float, float], v: np.ndarray) -> np.ndarray:
    rot = _quat_to_matrix(q)[:3, :3]
    return np.asarray(v, dtype=np.float32) @ rot.T


def _quat_to_matrix(q: tuple[float, float, float, float]) -> np.ndarray:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 0.000001:
        return np.eye(4, dtype=np.float32)
    x, y, z, w = x / length, y / length, z / length, w / length
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    out = np.eye(4, dtype=np.float32)
    out[:3, :3] = np.asarray(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float32,
    )
    return out


def _quat_translation_matrix(q: tuple[float, float, float, float], translation: np.ndarray) -> np.ndarray:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    out = np.empty((4, 4), dtype=np.float32)
    if length <= 0.000001:
        out[:3, :3] = np.eye(3, dtype=np.float32)
    else:
        x, y, z, w = x / length, y / length, z / length, w / length
        xx, yy, zz = x * x, y * y, z * z
        xy, xz, yz = x * y, x * z, y * z
        wx, wy, wz = w * x, w * y, w * z
        out[:3, :3] = np.asarray(
            [
                [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
                [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
                [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
            ],
            dtype=np.float32,
        )
    out[:3, 3] = np.asarray(translation, dtype=np.float32)[:3]
    out[3, :3] = 0.0
    out[3, 3] = 1.0
    return out


def _active_vertex_morphs(model: MMDModel, motion: VMDMotion | None, frame: float):
    weights = morph_weights_at(motion, frame)
    if not weights:
        return []
    morph_by_name = {}
    for morph in model.morphs:
        if morph.vertex_morph is not None:
            morph_by_name[morph.name] = morph
            if morph.english_name:
                morph_by_name[morph.english_name] = morph
    active = []
    for name, weight in weights.items():
        if abs(float(weight)) <= 0.0001:
            continue
        morph = morph_by_name.get(name)
        if morph is None or morph.vertex_morph is None:
            continue
        active.append((str(name), float(weight), morph))
    return active


def _apply_vertex_morphs(model: MMDModel, motion: VMDMotion | None, frame: float) -> tuple[np.ndarray, int]:
    positions = np.array(model.positions, dtype=np.float32, copy=True)
    active_morphs = _active_vertex_morphs(model, motion, frame)
    if not active_morphs:
        return positions, 0
    active = 0
    for _name, weight, morph in active_morphs:
        indices = morph.vertex_morph.indices
        offsets = morph.vertex_morph.offsets
        valid = (indices >= 0) & (indices < positions.shape[0])
        if not np.any(valid):
            continue
        positions[indices[valid]] += offsets[valid] * weight
        active += 1
    return np.ascontiguousarray(positions, dtype=np.float32), active


def _pose_channels(model: MMDModel, motion: VMDMotion | None, frame: float) -> tuple[np.ndarray, list[tuple[float, float, float, float]], int]:
    bones = model.bones
    pose = bone_pose_at(motion, frame)
    translations = np.zeros((len(bones), 3), dtype=np.float32)
    rotations = [(0.0, 0.0, 0.0, 1.0) for _ in bones]
    active = 0
    for i, bone in enumerate(bones):
        bone_pose = pose.get(bone.name) or (pose.get(bone.english_name) if bone.english_name else None)
        if bone_pose is not None:
            translations[i] = np.asarray(bone_pose[0], dtype=np.float32)
            rotations[i] = _quat_normalize(bone_pose[1])
            active += 1
    return translations, rotations, active


def _compute_globals(
    model: MMDModel,
    translations: np.ndarray,
    rotations: list[tuple[float, float, float, float]],
    *,
    bone_count: int | None = None,
    positions: np.ndarray | None = None,
    topology: _BoneTopology | None = None,
    out: list[np.ndarray] | None = None,
) -> list[np.ndarray]:
    bones = model.bones
    topology = topology or _bone_topology(model)
    count = len(bones) if bone_count is None else max(0, min(len(bones), int(bone_count)))
    if positions is None:
        positions = topology.positions
        base_deltas = topology.base_deltas
    else:
        positions = np.asarray(positions, dtype=np.float32)
        base_deltas = None
    if out is None or len(out) < count:
        globals_: list[np.ndarray] = [np.eye(4, dtype=np.float32) for _ in range(count)]
    else:
        globals_ = out
    zero = np.zeros((3,), dtype=np.float32)
    for i in range(count):
        parent = int(topology.parent_indices[i])
        if base_deltas is not None:
            base_delta = base_deltas[i]
        else:
            parent_pos = positions[parent] if 0 <= parent < len(bones) else zero
            base_delta = positions[i] - parent_pos
        local_translation = translations[i]
        local_rotation = rotations[i]
        inherit_idx = int(topology.inherit_indices[i])
        inherit_weight = float(topology.inherit_weights[i])
        if 0 <= inherit_idx < len(bones) and abs(inherit_weight) > 0.00001:
            flags = int(topology.flags[i])
            if flags & 0x0200:
                local_translation = local_translation + translations[inherit_idx] * inherit_weight
            if flags & 0x0100:
                inherited = _quat_slerp((0.0, 0.0, 0.0, 1.0), rotations[inherit_idx], max(0.0, min(1.0, inherit_weight)))
                local_rotation = _quat_multiply(local_rotation, inherited)
        local = _quat_translation_matrix(local_rotation, base_delta + local_translation)
        if 0 <= parent < count:
            np.matmul(globals_[parent], local, out=globals_[i])
        else:
            globals_[i][:] = local
    return globals_ if len(globals_) == count else globals_[:count]


def _clamp_quat_xyz(
    quat: tuple[float, float, float, float],
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    # PMX IK limits are Euler-domain constraints. The MVP solver keeps the
    # common knee/ankle cases stable by clamping a compact XYZ extraction.
    x, y, z, w = _quat_normalize(quat)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    roll = max(float(lower[0]), min(float(upper[0]), roll))
    pitch = max(float(lower[1]), min(float(upper[1]), pitch))
    yaw = max(float(lower[2]), min(float(upper[2]), yaw))
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    return _quat_normalize((
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ))


def _is_primary_x_limit(
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> bool:
    return (
        abs(float(lower[1])) <= 0.0001
        and abs(float(upper[1])) <= 0.0001
        and abs(float(lower[2])) <= 0.0001
        and abs(float(upper[2])) <= 0.0001
        and abs(float(lower[0] - upper[0])) > 0.0001
    )


def _limit_quat_to_x_axis(
    quat: tuple[float, float, float, float],
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    """Keep MMD knee-like IK limits on the local X axis.

    three.js' MMD path treats knee limitations as a primary-axis constraint.
    This avoids Euler decomposition jitter while preserving PMX min/max ranges.
    """
    x, y, z, w = _quat_normalize(quat)
    if w < 0.0:
        x, y, z, w = -x, -y, -z, -w
    if float(upper[0]) <= 0.0 and float(lower[0]) < 0.0:
        sign = -1.0
        min_angle = abs(float(upper[0]))
        max_angle = abs(float(lower[0]))
    elif float(lower[0]) >= 0.0 and float(upper[0]) > 0.0:
        sign = 1.0
        min_angle = abs(float(lower[0]))
        max_angle = abs(float(upper[0]))
    else:
        sign = -1.0 if x < 0.0 else 1.0
        min_angle = 0.0
        max_angle = max(abs(float(lower[0])), abs(float(upper[0])), math.pi)
    angle = 2.0 * math.atan2(abs(x), max(0.000001, float(w)))
    angle = max(min_angle, min(max_angle, angle))
    half = angle * 0.5
    return _quat_normalize((sign * math.sin(half), 0.0, 0.0, math.cos(half)))


def _softened_ik_target(
    target_pos: np.ndarray,
    globals_: list[np.ndarray],
    root_idx: int,
    chain_length: float,
    foot_ik_reach_limit: float | None,
) -> np.ndarray:
    if foot_ik_reach_limit is None:
        return target_pos
    reach_limit = max(0.70, min(1.0, float(foot_ik_reach_limit)))
    if chain_length <= 0.0001 or root_idx >= len(globals_):
        return target_pos
    root_pos = np.asarray(globals_[root_idx][:3, 3], dtype=np.float32)
    vector = np.asarray(target_pos, dtype=np.float32) - root_pos
    distance = float(np.linalg.norm(vector))
    max_distance = max(0.0001, chain_length * reach_limit)
    if distance <= max_distance:
        return target_pos
    return root_pos + (vector / distance) * max_distance


def _ik_chain_metadata(model: MMDModel, topology: _BoneTopology, ik_bone_index: int) -> tuple[int, float]:
    bone = model.bones[ik_bone_index]
    ik = bone.ik
    if ik is None or not ik.links or not (0 <= int(ik.target_index) < topology.bone_count):
        return -1, 0.0
    link_indices = [int(link.bone_index) for link in ik.links if 0 <= int(link.bone_index) < topology.bone_count]
    if len(link_indices) < 2:
        return (link_indices[-1] if link_indices else -1), 0.0
    root_idx = int(link_indices[-1])
    chain_indices = list(reversed(link_indices)) + [int(ik.target_index)]
    chain_length = 0.0
    positions = topology.positions
    for a, b in zip(chain_indices, chain_indices[1:]):
        chain_length += float(np.linalg.norm(positions[b] - positions[a]))
    return root_idx, chain_length


def _apply_ik(
    model: MMDModel,
    translations: np.ndarray,
    rotations: list[tuple[float, float, float, float]],
    *,
    max_iterations: int | None = None,
    foot_ik_reach_limit: float | None = None,
    topology: _BoneTopology | None = None,
) -> tuple[list[np.ndarray], int]:
    if not model.bones:
        return [], 0
    topology = topology or _bone_topology(model)
    eval_count = 0
    ik_entries = []
    for ik_bone_index, bone in enumerate(model.bones):
        ik = bone.ik
        if ik is None:
            continue
        eval_count = max(eval_count, ik_bone_index + 1, int(ik.target_index) + 1)
        for link in ik.links:
            eval_count = max(eval_count, int(link.bone_index) + 1)
        root_idx, chain_length = _ik_chain_metadata(model, topology, ik_bone_index)
        ik_entries.append((ik_bone_index, bone, ik, root_idx, chain_length))
    eval_count = len(model.bones) if eval_count <= 0 else min(len(model.bones), eval_count)
    positions = topology.positions
    globals_ = _compute_globals(model, translations, rotations, bone_count=eval_count, topology=topology)
    globals_dirty = False
    active_ik = 0
    for ik_bone_index, _bone, ik, root_idx, chain_length in ik_entries:
        if ik is None or not ik.links or not (0 <= ik.target_index < eval_count) or ik_bone_index >= eval_count:
            continue
        active_ik += 1
        iteration_limit = 64 if max_iterations is None else max(1, min(64, int(max_iterations)))
        iteration_count = max(1, min(iteration_limit, int(ik.iteration_count)))
        angle_limit = max(0.001, min(math.pi, float(ik.angle_limit or 0.35)))
        for _iteration in range(iteration_count):
            if globals_dirty:
                globals_ = _compute_globals(
                    model,
                    translations,
                    rotations,
                    bone_count=eval_count,
                    topology=topology,
                    out=globals_,
                )
                globals_dirty = False
            target_pos = _softened_ik_target(
                np.asarray(globals_[ik_bone_index][:3, 3], dtype=np.float32),
                globals_,
                root_idx,
                chain_length,
                foot_ik_reach_limit,
            )
            effector_pos = np.asarray(globals_[ik.target_index][:3, 3], dtype=np.float32)
            if float(np.linalg.norm(target_pos - effector_pos)) <= 0.0005:
                break
            for link in ik.links:
                link_idx = int(link.bone_index)
                if not (0 <= link_idx < eval_count):
                    continue
                if globals_dirty:
                    globals_ = _compute_globals(
                        model,
                        translations,
                        rotations,
                        bone_count=eval_count,
                        topology=topology,
                        out=globals_,
                    )
                    globals_dirty = False
                link_global = globals_[link_idx]
                link_rot = link_global[:3, :3]
                link_pos = link_global[:3, 3]
                eff_local = (globals_[ik.target_index][:3, 3] - link_pos) @ link_rot
                target_local = (target_pos - link_pos) @ link_rot
                delta = _quat_between(eff_local, target_local, max_angle=angle_limit)
                rotations[link_idx] = _quat_multiply(rotations[link_idx], delta)
                if link.has_limit:
                    if _is_primary_x_limit(link.limit_min, link.limit_max):
                        rotations[link_idx] = _limit_quat_to_x_axis(rotations[link_idx], link.limit_min, link.limit_max)
                    else:
                        rotations[link_idx] = _clamp_quat_xyz(rotations[link_idx], link.limit_min, link.limit_max)
                globals_dirty = True
    return _compute_globals(model, translations, rotations, topology=topology), active_ik


def _skin_matrices(model: MMDModel, globals_: list[np.ndarray], *, topology: _BoneTopology | None = None) -> np.ndarray:
    topology = topology or _bone_topology(model)
    positions = topology.positions
    matrices = np.zeros((len(model.bones), 4, 4), dtype=np.float32)
    for i, bone_global in enumerate(globals_):
        matrices[i, :3, :3] = bone_global[:3, :3]
        matrices[i, :3, 3] = bone_global[:3, 3] - bone_global[:3, :3] @ positions[i]
        matrices[i, 3, :3] = 0.0
        matrices[i, 3, 3] = 1.0
    return matrices


def _bone_skin_matrices(
    model: MMDModel,
    motion: VMDMotion | None,
    frame: float,
    *,
    physics_backend: MMDPhysicsBackend | None = None,
    enable_ik: bool = True,
    enable_physics: bool = True,
    max_ik_iterations: int | None = None,
    foot_ik_reach_limit: float | None = None,
) -> tuple[np.ndarray | None, int, int, int]:
    bones = model.bones
    if not bones:
        return None, 0, 0, 0
    topology = _bone_topology(model)
    translations, rotations, active = _pose_channels(model, motion, frame)
    if not active and motion is None:
        return None, 0, 0, 0
    if enable_ik:
        globals_, active_ik = _apply_ik(
            model,
            translations,
            rotations,
            max_iterations=max_ik_iterations,
            foot_ik_reach_limit=foot_ik_reach_limit,
            topology=topology,
        )
    else:
        globals_ = _compute_globals(model, translations, rotations, topology=topology)
        active_ik = 0
    physics_count = 0
    if enable_physics and physics_backend is not None:
        physics_delta = physics_backend.offsets_for(model, globals_, frame)
        if isinstance(physics_delta, MMDPhysicsPoseDelta):
            offsets = physics_delta.translation_offsets
            rotation_offsets = physics_delta.rotation_offsets
            physics_count = int(physics_delta.active_count)
        else:
            offsets, physics_count = physics_delta
            rotation_offsets = {}
        if offsets:
            for bone_idx, offset in offsets.items():
                if 0 <= bone_idx < len(translations):
                    translations[bone_idx] += offset
        if rotation_offsets:
            for bone_idx, quat in rotation_offsets.items():
                if 0 <= bone_idx < len(rotations):
                    rotations[bone_idx] = _quat_multiply(rotations[bone_idx], _quat_normalize(quat))
        if offsets or rotation_offsets:
            globals_ = _compute_globals(model, translations, rotations, topology=topology)
    return _skin_matrices(model, globals_, topology=topology), active, active_ik, physics_count


def _apply_sdef_skin(
    model: MMDModel,
    positions: np.ndarray,
    normals: np.ndarray,
    matrices: np.ndarray,
    out_pos: np.ndarray,
    out_norm: np.ndarray,
) -> np.ndarray:
    weight_types = model.weights.weight_types
    bone_indices = model.weights.bone_indices
    bone_weights = model.weights.bone_weights
    sdef_mask = (
        (weight_types == 3)
        & (bone_indices[:, 0] >= 0)
        & (bone_indices[:, 1] >= 0)
        & (bone_indices[:, 0] < matrices.shape[0])
        & (bone_indices[:, 1] < matrices.shape[0])
    )
    if not np.any(sdef_mask):
        return sdef_mask
    for idx in np.where(sdef_mask)[0]:
        b0 = int(bone_indices[idx, 0])
        b1 = int(bone_indices[idx, 1])
        w0 = float(bone_weights[idx, 0])
        w1 = 1.0 - w0
        m0 = matrices[b0]
        m1 = matrices[b1]
        c = model.weights.sdef_c[idx]
        r0 = model.weights.sdef_r0[idx]
        r1 = model.weights.sdef_r1[idx]
        center0 = (np.append(c, 1.0) @ m0.T)[:3]
        center1 = (np.append(c, 1.0) @ m1.T)[:3]
        center = center0 * w0 + center1 * w1
        rest_anchor = r0 * w0 + r1 * w1
        anchor0 = (np.append(r0, 1.0) @ m0.T)[:3]
        anchor1 = (np.append(r1, 1.0) @ m1.T)[:3]
        anchor = anchor0 * w0 + anchor1 * w1
        q0 = _matrix_to_quat(m0[:3, :3])
        q1 = _matrix_to_quat(m1[:3, :3])
        blended = _quat_slerp(q1, q0, w0)
        rotated_anchor = center + _quat_rotate(blended, rest_anchor - c)
        out_pos[idx] = center + _quat_rotate(blended, positions[idx] - c) + (anchor - rotated_anchor)
        out_norm[idx] = _quat_rotate(blended, normals[idx])
    return sdef_mask


def evaluate_model_pose(
    model: MMDModel,
    motion: VMDMotion | None = None,
    frame: float = 0.0,
    *,
    physics_state: MMDPhysicsState | None = None,
    physics_backend: MMDPhysicsBackend | None = None,
    enable_ik: bool = True,
    enable_physics: bool = True,
    max_ik_iterations: int | None = None,
    foot_ik_reach_limit: float | None = None,
    skin_vertices: bool = True,
    gpu_morph_slots: int = 0,
) -> MMDPoseGeometry:
    backend = physics_backend if physics_backend is not None else physics_state
    gpu_morph_names: tuple[str, ...] = ()
    gpu_morph_weights: tuple[float, ...] = ()
    active_vertex_morphs = _active_vertex_morphs(model, motion, float(frame))
    active_morphs = int(len(active_vertex_morphs))
    gpu_slot_limit = max(0, min(4, int(gpu_morph_slots or 0)))
    can_defer_morphs_to_gpu = bool(not skin_vertices and 0 < active_morphs <= gpu_slot_limit)
    if can_defer_morphs_to_gpu:
        morphed_positions = np.ascontiguousarray(model.positions, dtype=np.float32)
        gpu_morph_names = tuple(name for name, _weight, _morph in active_vertex_morphs[:gpu_slot_limit])
        gpu_morph_weights = tuple(float(weight) for _name, weight, _morph in active_vertex_morphs[:gpu_slot_limit])
    elif active_morphs:
        morphed_positions, active_morphs = _apply_vertex_morphs(model, motion, float(frame))
    else:
        morphed_positions = np.ascontiguousarray(model.positions, dtype=np.float32)
    matrices, active_bones, active_ik, physics_count = _bone_skin_matrices(
        model,
        motion,
        float(frame),
        physics_backend=backend,
        enable_ik=enable_ik,
        enable_physics=enable_physics,
        max_ik_iterations=max_ik_iterations,
        foot_ik_reach_limit=foot_ik_reach_limit,
    )
    if matrices is None or active_bones <= 0:
        if can_defer_morphs_to_gpu:
            morphed_positions, active_morphs = _apply_vertex_morphs(model, motion, float(frame))
            gpu_morph_names = ()
            gpu_morph_weights = ()
        return MMDPoseGeometry(
            positions=np.ascontiguousarray(morphed_positions, dtype=np.float32),
            normals=np.ascontiguousarray(model.normals, dtype=np.float32),
            skinned=False,
            active_morph_count=active_morphs,
            active_bone_count=0,
            active_ik_count=0,
            physics_body_count=0,
            active_sdef_count=0,
            bone_matrices=None,
            gpu_morph_names=gpu_morph_names,
            gpu_morph_weights=gpu_morph_weights,
        )

    if not skin_vertices:
        active_sdef_count = int(np.count_nonzero(model.weights.weight_types == 3))
        return MMDPoseGeometry(
            positions=np.ascontiguousarray(morphed_positions, dtype=np.float32),
            normals=np.ascontiguousarray(model.normals, dtype=np.float32),
            skinned=False,
            active_morph_count=active_morphs,
            active_bone_count=active_bones,
            active_ik_count=active_ik,
            physics_body_count=physics_count,
            active_sdef_count=active_sdef_count,
            bone_matrices=np.ascontiguousarray(matrices, dtype=np.float32),
            gpu_morph_names=gpu_morph_names,
            gpu_morph_weights=gpu_morph_weights,
        )

    bone_indices = model.weights.bone_indices
    bone_weights = model.weights.bone_weights
    n_vertices = int(morphed_positions.shape[0])
    out_pos = np.zeros((n_vertices, 3), dtype=np.float32)
    out_norm = np.zeros((n_vertices, 3), dtype=np.float32)
    hp = np.empty((n_vertices, 4), dtype=np.float32)
    hp[:, :3] = morphed_positions
    hp[:, 3] = 1.0
    normals = np.asarray(model.normals, dtype=np.float32)
    sdef_mask = _apply_sdef_skin(model, morphed_positions, normals, matrices, out_pos, out_norm)
    active_sdef_count = int(np.count_nonzero(sdef_mask))
    for channel in range(4):
        idxs = bone_indices[:, channel]
        weights = bone_weights[:, channel]
        valid = (idxs >= 0) & (idxs < matrices.shape[0]) & (weights > 0.00001) & (~sdef_mask)
        if not np.any(valid):
            continue
        gathered = matrices[np.asarray(idxs[valid], dtype=np.int64)]
        w = np.asarray(weights[valid], dtype=np.float32)[:, None]
        out_pos[valid] += np.einsum("ij,ikj->ik", hp[valid], gathered, optimize=True)[:, :3] * w
        out_norm[valid] += np.einsum(
            "ij,ikj->ik",
            normals[valid],
            gathered[:, :3, :3],
            optimize=True,
        ) * w

    missing = np.linalg.norm(out_pos, axis=1) <= 0.000001
    if np.any(missing):
        out_pos[missing] = morphed_positions[missing]
        out_norm[missing] = normals[missing]
    lens = np.linalg.norm(out_norm, axis=1, keepdims=True)
    out_norm = np.divide(out_norm, np.maximum(lens, 0.000001), out=np.array(normals, copy=True), where=lens > 0.000001)
    return MMDPoseGeometry(
        positions=np.ascontiguousarray(out_pos, dtype=np.float32),
        normals=np.ascontiguousarray(out_norm, dtype=np.float32),
        skinned=True,
        active_morph_count=active_morphs,
        active_bone_count=active_bones,
        active_ik_count=active_ik,
        physics_body_count=physics_count,
        active_sdef_count=active_sdef_count,
        bone_matrices=np.ascontiguousarray(matrices, dtype=np.float32),
        gpu_morph_names=(),
        gpu_morph_weights=(),
    )
