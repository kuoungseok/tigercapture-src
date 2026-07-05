"""Physics backend contracts for the MMD pose evaluator."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from typing import Protocol

import numpy as np

from .pmx import MMDModel


SECONDARY_ROTATION_HINT_SCALE = 0.12
SECONDARY_ROTATION_INFLUENCE_LIMIT = 0.65
SPRING_PHYSICS_RESPONSE = 0.60


@dataclass(frozen=True)
class MMDPhysicsPoseDelta:
    """Physics offsets that can be applied before skinning.

    Older call sites unpack ``offsets_for`` as ``translation_offsets, count``.
    ``__iter__`` keeps that compatible while newer pose evaluation can also
    consume lightweight rotation hints for secondary bones.
    """

    translation_offsets: dict[int, np.ndarray]
    active_count: int
    rotation_offsets: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)

    def __iter__(self):
        yield self.translation_offsets
        yield self.active_count


def _coerce_physics_delta(result) -> MMDPhysicsPoseDelta:
    if isinstance(result, MMDPhysicsPoseDelta):
        return result
    offsets, count = result
    return MMDPhysicsPoseDelta(
        translation_offsets={
            int(k): np.asarray(v, dtype=np.float32)
            for k, v in dict(offsets or {}).items()
        },
        active_count=int(count),
    )


def _int_attr(obj, name: str, default: int = 0) -> int:
    value = getattr(obj, name, default)
    if value is None:
        return int(default)
    try:
        return int(value)
    except Exception:
        return int(default)


def _quat_normalize(q: tuple[float, float, float, float] | np.ndarray) -> tuple[float, float, float, float]:
    x, y, z, w = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 0.000001:
        return 0.0, 0.0, 0.0, 1.0
    return x / length, y / length, z / length, w / length


def _quat_slerp(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    t: float,
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = _quat_normalize(a)
    bx, by, bz, bw = _quat_normalize(b)
    dot = ax * bx + ay * by + az * bz + aw * bw
    if dot < 0.0:
        bx, by, bz, bw = -bx, -by, -bz, -bw
        dot = -dot
    t = max(0.0, min(1.0, float(t)))
    if dot > 0.9995:
        return _quat_normalize((ax + (bx - ax) * t, ay + (by - ay) * t, az + (bz - az) * t, aw + (bw - aw) * t))
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    sin_theta_0 = math.sin(theta_0)
    s0 = math.cos(theta) - dot * sin_theta / max(0.000001, sin_theta_0)
    s1 = sin_theta / max(0.000001, sin_theta_0)
    return _quat_normalize((ax * s0 + bx * s1, ay * s0 + by * s1, az * s0 + bz * s1, aw * s0 + bw * s1))


def _quat_multiply(
    a: tuple[float, float, float, float] | np.ndarray,
    b: tuple[float, float, float, float] | np.ndarray,
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = _quat_normalize(a)
    bx, by, bz, bw = _quat_normalize(b)
    return _quat_normalize((
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ))


def _quat_inverse(q: tuple[float, float, float, float] | np.ndarray) -> tuple[float, float, float, float]:
    x, y, z, w = _quat_normalize(q)
    return -x, -y, -z, w


def _quat_angle(q: tuple[float, float, float, float] | np.ndarray) -> float:
    x, y, z, w = _quat_normalize(q)
    return 2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w))


def _quat_scaled(q: tuple[float, float, float, float] | np.ndarray, scale: float) -> tuple[float, float, float, float]:
    return _quat_slerp((0.0, 0.0, 0.0, 1.0), _quat_normalize(q), max(0.0, min(1.0, float(scale))))


def _quat_from_euler(euler: tuple[float, float, float] | np.ndarray) -> tuple[float, float, float, float]:
    rx, ry, rz = (float(euler[0]), float(euler[1]), float(euler[2]))
    cx, sx = math.cos(rx * 0.5), math.sin(rx * 0.5)
    cy, sy = math.cos(ry * 0.5), math.sin(ry * 0.5)
    cz, sz = math.cos(rz * 0.5), math.sin(rz * 0.5)
    return _quat_normalize((
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    ))


def _quat_rotate(q: tuple[float, float, float, float] | np.ndarray, vector: np.ndarray) -> np.ndarray:
    x, y, z, w = _quat_normalize(q)
    u = np.asarray((x, y, z), dtype=np.float32)
    v = np.asarray(vector, dtype=np.float32)
    return np.asarray(
        2.0 * float(np.dot(u, v)) * u
        + (w * w - float(np.dot(u, u))) * v
        + 2.0 * w * np.cross(u, v),
        dtype=np.float32,
    )


def _normalize_vec(v: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(v))
    if length <= 0.000001:
        return np.zeros((3,), dtype=np.float32)
    return np.asarray(v, dtype=np.float32) / length


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
    return _quat_normalize((float(axis[0] * math.sin(half)), float(axis[1] * math.sin(half)), float(axis[2] * math.sin(half)), math.cos(half)))


def _matrix_to_quat(mat: np.ndarray) -> tuple[float, float, float, float]:
    m = np.asarray(mat, dtype=np.float32)
    trace = float(m[0, 0] + m[1, 1] + m[2, 2])
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        return _quat_normalize(((m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s, 0.25 * s))
    if m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(max(0.0, 1.0 + float(m[0, 0] - m[1, 1] - m[2, 2]))) * 2.0
        return _quat_normalize((0.25 * s, (m[0, 1] + m[1, 0]) / max(s, 0.000001), (m[0, 2] + m[2, 0]) / max(s, 0.000001), (m[2, 1] - m[1, 2]) / max(s, 0.000001)))
    if m[1, 1] > m[2, 2]:
        s = math.sqrt(max(0.0, 1.0 + float(m[1, 1] - m[0, 0] - m[2, 2]))) * 2.0
        return _quat_normalize(((m[0, 1] + m[1, 0]) / max(s, 0.000001), 0.25 * s, (m[1, 2] + m[2, 1]) / max(s, 0.000001), (m[0, 2] - m[2, 0]) / max(s, 0.000001)))
    s = math.sqrt(max(0.0, 1.0 + float(m[2, 2] - m[0, 0] - m[1, 1]))) * 2.0
    return _quat_normalize(((m[0, 2] + m[2, 0]) / max(s, 0.000001), (m[1, 2] + m[2, 1]) / max(s, 0.000001), 0.25 * s, (m[1, 0] - m[0, 1]) / max(s, 0.000001)))


class MMDPhysicsBackend(Protocol):
    """Interface used by animation evaluation before skinning.

    Backends receive the post-VMD/post-IK bone globals and return temporary
    local translation offsets keyed by bone index. Bullet-compatible backends
    can later implement the same contract without changing the renderer.
    """

    def reset(self) -> None:
        ...

    def offsets_for(
        self,
        model: MMDModel,
        globals_: list[np.ndarray],
        frame: float,
    ) -> MMDPhysicsPoseDelta | tuple[dict[int, np.ndarray], int]:
        ...


@dataclass
class NoPhysicsBackend:
    """Explicit no-op backend for deterministic timeline seeking or tests."""

    def reset(self) -> None:
        return

    def offsets_for(
        self,
        model: MMDModel,
        globals_: list[np.ndarray],
        frame: float,
    ) -> MMDPhysicsPoseDelta:
        return MMDPhysicsPoseDelta({}, 0)


@dataclass
class SpringPhysicsBackend:
    """Lightweight deterministic secondary-motion backend for PMX rigid bodies.

    This is not a Bullet replacement. It preserves the PMX rigid-body graph and
    gives physics-controlled bones damped follow-through until a native physics
    backend is introduced.
    """

    particles: dict[int, tuple[np.ndarray, np.ndarray]] = field(default_factory=dict)
    last_frame: float | None = None
    spring_response: float = SPRING_PHYSICS_RESPONSE
    secondary_rotation_scale: float = SECONDARY_ROTATION_HINT_SCALE
    secondary_rotation_influence_limit: float = SECONDARY_ROTATION_INFLUENCE_LIMIT

    def reset(self) -> None:
        self.particles.clear()
        self.last_frame = None

    @staticmethod
    def _body_target(model: MMDModel, globals_: list[np.ndarray], bone_idx: int, body_position) -> np.ndarray:
        body_pos = np.asarray(body_position, dtype=np.float32)
        if not (0 <= bone_idx < len(model.bones)):
            return body_pos
        rest_bone = np.asarray(model.bones[bone_idx].position, dtype=np.float32)
        local_offset = body_pos - rest_bone
        transform = np.asarray(globals_[bone_idx], dtype=np.float32)
        return np.asarray(transform[:3, :3] @ local_offset + transform[:3, 3], dtype=np.float32)

    @staticmethod
    def _max_displacement(body) -> float:
        size = np.asarray(body.size, dtype=np.float32)
        radius = float(np.linalg.norm(np.maximum(size, 0.0001)))
        return max(0.025, min(0.22, radius * 0.28))

    @staticmethod
    def _secondary_rotation_settings(
        body,
        bone,
        *,
        rotation_scale: float | None = None,
        influence_limit: float | None = None,
    ) -> tuple[float, float, float]:
        name = " ".join(
            str(value or "")
            for value in (
                getattr(body, "name", ""),
                getattr(body, "english_name", ""),
                getattr(bone, "name", ""),
                getattr(bone, "english_name", ""),
            )
        ).casefold()
        scale = max(0.0, min(0.5, float(SECONDARY_ROTATION_HINT_SCALE if rotation_scale is None else rotation_scale)))
        influence = max(
            0.0,
            min(1.0, float(SECONDARY_ROTATION_INFLUENCE_LIMIT if influence_limit is None else influence_limit)),
        )
        skirt_tokens = ("skirt", "dress", "cloth", "cape", "sleeve", "スカ", "スカート", "裙", "衣", "裾")
        hair_tokens = ("hair", "tail", "ribbon", "髪")
        if any(token.casefold() in name for token in skirt_tokens):
            return 1.65 * scale, influence, 0.42 * scale
        if any(token.casefold() in name for token in hair_tokens):
            return 1.25 * scale, influence, 0.42 * scale
        if int(getattr(body, "physics_mode", 0) or 0) == 1:
            return 0.65 * scale, influence, 0.24 * scale
        if int(getattr(body, "physics_mode", 0) or 0) == 2:
            return 0.35 * scale, influence, 0.24 * scale
        return 0.0, 0.0, 0.0

    @staticmethod
    def _secondary_rotation_gain(body, bone, *, rotation_scale: float | None = None) -> float:
        gain, _influence_limit, _max_angle = SpringPhysicsBackend._secondary_rotation_settings(
            body,
            bone,
            rotation_scale=rotation_scale,
        )
        return gain

    @staticmethod
    def _rotation_hint_for_body(
        model: MMDModel,
        globals_: list[np.ndarray],
        bone_idx: int,
        body,
        target: np.ndarray,
        delta: np.ndarray,
        *,
        rotation_scale: float | None = None,
        influence_limit: float | None = None,
    ) -> tuple[float, float, float, float] | None:
        if not (0 <= bone_idx < len(model.bones) and bone_idx < len(globals_)):
            return None
        bone = model.bones[bone_idx]
        gain, influence_limit, max_angle = SpringPhysicsBackend._secondary_rotation_settings(
            body,
            bone,
            rotation_scale=rotation_scale,
            influence_limit=influence_limit,
        )
        if gain <= 0.0:
            return None
        bone_global = np.asarray(globals_[bone_idx], dtype=np.float32)
        bone_pos = np.asarray(bone_global[:3, 3], dtype=np.float32)
        base_world = np.asarray(target, dtype=np.float32) - bone_pos
        base_len = float(np.linalg.norm(base_world))
        if base_len <= 0.025:
            return None
        delta = np.asarray(delta, dtype=np.float32)
        delta_len = float(np.linalg.norm(delta))
        if delta_len <= 0.0005:
            return None
        influence = max(0.0, min(float(influence_limit), delta_len / max(0.08, base_len)))
        desired_world = base_world + delta * gain * influence
        if float(np.linalg.norm(desired_world)) <= 0.0001:
            return None
        bone_rot = bone_global[:3, :3]
        base_local = base_world @ bone_rot
        desired_local = desired_world @ bone_rot
        quat = _quat_between(base_local, desired_local, max_angle=max_angle)
        if abs(quat[0]) + abs(quat[1]) + abs(quat[2]) <= 0.00001:
            return None
        return quat

    def offsets_for(
        self,
        model: MMDModel,
        globals_: list[np.ndarray],
        frame: float,
    ) -> MMDPhysicsPoseDelta:
        valid_entries: dict[int, dict[str, object]] = {}
        active_indices: list[int] = []
        for body_index, body in enumerate(model.rigid_bodies):
            bone_idx = int(body.bone_index)
            if not (0 <= bone_idx < len(globals_)):
                continue
            target = self._body_target(model, globals_, bone_idx, body.position)
            active = int(body.physics_mode) in {1, 2}
            valid_entries[body_index] = {
                "body": body,
                "bone_idx": bone_idx,
                "target": target,
                "active": active,
                "pos": np.asarray(target, dtype=np.float32),
                "vel": np.zeros((3,), dtype=np.float32),
            }
            if active:
                active_indices.append(body_index)
        if not active_indices:
            self.last_frame = float(frame)
            return MMDPhysicsPoseDelta({}, 0)
        if self.last_frame is None or frame < self.last_frame or abs(frame - self.last_frame) > 12.0:
            self.particles.clear()
        previous_frame = float(self.last_frame) if self.last_frame is not None else float(frame)
        dt = max(0.0, min(1.0 / 15.0, (float(frame) - previous_frame) / 30.0))
        gravity = np.asarray((0.0, -1.15, 0.0), dtype=np.float32)
        for body_index in active_indices:
            entry = valid_entries[body_index]
            body = entry["body"]
            target = np.asarray(entry["target"], dtype=np.float32)
            pos, vel = self.particles.get(
                body_index,
                (np.array(target, dtype=np.float32, copy=True), np.zeros((3,), dtype=np.float32)),
            )
            if dt > 0.0:
                mass = max(0.05, float(body.mass or 1.0))
                damping = max(0.0, min(0.98, float(body.linear_damping or 0.0)))
                angular_damping = max(0.0, min(0.98, float(body.angular_damping or 0.0)))
                friction = max(0.0, min(1.0, float(body.friction or 0.0)))
                restitution = max(0.0, min(1.0, float(body.restitution or 0.0)))
                mode_follow = 1.35 if int(body.physics_mode) == 2 else 1.0
                response = max(0.15, min(1.5, float(self.spring_response or 1.0)))
                spring = (28.0 + friction * 18.0) * mode_follow * response / (1.0 + mass * 0.35)
                vel = vel + (target - pos) * spring * dt + gravity * dt * min(1.25, mass)
                vel = vel * (1.0 - damping * 0.48) * (1.0 - angular_damping * 0.22)
                pos = pos + vel * dt
                delta = pos - target
                length = float(np.linalg.norm(delta))
                max_delta = self._max_displacement(body)
                if length > max_delta:
                    delta = delta / max(0.0001, length) * max_delta
                    pos = target + delta
                    vel *= 0.35 + restitution * 0.25
            entry["pos"] = np.asarray(pos, dtype=np.float32)
            entry["vel"] = np.asarray(vel, dtype=np.float32)

        if dt > 0.0 and model.joints:
            for joint in model.joints:
                a_idx = int(joint.rigid_body_a)
                b_idx = int(joint.rigid_body_b)
                if a_idx not in valid_entries or b_idx not in valid_entries:
                    continue
                a = valid_entries[a_idx]
                b = valid_entries[b_idx]
                if not (a["active"] or b["active"]):
                    continue
                target_delta = np.asarray(b["target"], dtype=np.float32) - np.asarray(a["target"], dtype=np.float32)
                current_delta = np.asarray(b["pos"], dtype=np.float32) - np.asarray(a["pos"], dtype=np.float32)
                correction = target_delta - current_delta
                corr_len = float(np.linalg.norm(correction))
                if corr_len <= 0.00001:
                    continue
                linear_spring = float(np.linalg.norm(np.asarray(joint.linear_spring, dtype=np.float32)))
                angular_spring = float(np.linalg.norm(np.asarray(joint.angular_spring, dtype=np.float32)))
                strength = max(0.04, min(0.38, 0.08 + linear_spring * 0.0015 + angular_spring * 0.0008))
                correction = correction * strength
                a_active = bool(a["active"])
                b_active = bool(b["active"])
                if a_active and b_active:
                    a["pos"] = np.asarray(a["pos"], dtype=np.float32) - correction * 0.5
                    b["pos"] = np.asarray(b["pos"], dtype=np.float32) + correction * 0.5
                    a["vel"] = np.asarray(a["vel"], dtype=np.float32) - correction / max(dt, 0.0001) * 0.08
                    b["vel"] = np.asarray(b["vel"], dtype=np.float32) + correction / max(dt, 0.0001) * 0.08
                elif a_active:
                    a["pos"] = np.asarray(a["pos"], dtype=np.float32) - correction
                    a["vel"] = np.asarray(a["vel"], dtype=np.float32) - correction / max(dt, 0.0001) * 0.08
                elif b_active:
                    b["pos"] = np.asarray(b["pos"], dtype=np.float32) + correction
                    b["vel"] = np.asarray(b["vel"], dtype=np.float32) + correction / max(dt, 0.0001) * 0.08

        bone_offsets: dict[int, list[np.ndarray]] = {}
        bone_rotations: dict[int, list[tuple[float, float, float, float]]] = {}
        for body_index in active_indices:
            entry = valid_entries[body_index]
            body = entry["body"]
            target = np.asarray(entry["target"], dtype=np.float32)
            pos = np.asarray(entry["pos"], dtype=np.float32)
            vel = np.asarray(entry["vel"], dtype=np.float32)
            delta = pos - target
            length = float(np.linalg.norm(delta))
            max_delta = self._max_displacement(body)
            if length > max_delta:
                delta = delta / max(0.0001, length) * max_delta
                pos = target + delta
                vel *= 0.45
            self.particles[body_index] = (np.asarray(pos, dtype=np.float32), np.asarray(vel, dtype=np.float32))
            bone_idx = int(entry["bone_idx"])
            bone_offsets.setdefault(bone_idx, []).append(np.asarray(delta, dtype=np.float32))
            rotation_hint = self._rotation_hint_for_body(
                model,
                globals_,
                bone_idx,
                body,
                target,
                delta,
                rotation_scale=self.secondary_rotation_scale,
                influence_limit=self.secondary_rotation_influence_limit,
            )
            if rotation_hint is not None:
                bone_rotations.setdefault(bone_idx, []).append(rotation_hint)
        offsets = {
            bone_idx: np.asarray(np.mean(values, axis=0), dtype=np.float32)
            for bone_idx, values in bone_offsets.items()
            if values
        }
        rotation_offsets = {}
        identity = (0.0, 0.0, 0.0, 1.0)
        for bone_idx, values in bone_rotations.items():
            if not values:
                continue
            blended = identity
            weight = 1.0 / max(1, len(values))
            for quat in values:
                blended = _quat_slerp(blended, quat, weight)
            rotation_offsets[int(bone_idx)] = blended
        self.last_frame = float(frame)
        return MMDPhysicsPoseDelta(offsets, len(active_indices), rotation_offsets)


@dataclass
class PyBulletPhysicsBackend:
    """Optional pybullet-backed secondary motion backend.

    The project does not require pybullet at install time. When pybullet is not
    importable this backend delegates to ``SpringPhysicsBackend`` so MMD preview
    remains functional. When available, PMX active rigid bodies are represented
    as lightweight Bullet bodies connected back to animated bone targets.
    """

    fallback: SpringPhysicsBackend = field(default_factory=SpringPhysicsBackend)
    client_id: int | None = None
    body_ids: dict[int, int] = field(default_factory=dict)
    shape_ids: dict[int, int] = field(default_factory=dict)
    shape_type_counts: dict[str, int] = field(default_factory=dict)
    constraint_ids: dict[int, int] = field(default_factory=dict)
    constraint_max_forces: dict[int, float] = field(default_factory=dict)
    last_frame: float | None = None
    last_joint_limit_correction_count: int = 0
    last_joint_spring_correction_count: int = 0
    last_orientation_feedback_count: int = 0
    last_solver_iterations: int = 0
    last_solver_substeps: int = 0
    last_solver_fixed_time_step: float = 0.0
    last_solver_active_body_count: int = 0
    last_solver_joint_count: int = 0
    last_capsule_axis_fix_count: int = 0
    solver_fixed_time_step: float = 1.0 / 120.0
    solver_contact_erp: float = 0.18
    solver_joint_erp: float = 0.22
    solver_friction_erp: float = 0.20
    _pybullet_missing: bool = False

    def _pybullet(self):
        if self._pybullet_missing:
            return None
        try:
            import pybullet as pb  # type: ignore

            return pb
        except Exception:
            self._pybullet_missing = True
            return None

    def available(self) -> bool:
        return self._pybullet() is not None

    def reset(self) -> None:
        self.fallback.reset()
        pb = self._pybullet()
        if pb is not None and self.client_id is not None:
            try:
                pb.resetSimulation(physicsClientId=self.client_id)
                pb.setGravity(0.0, -9.8, 0.0, physicsClientId=self.client_id)
                self._configure_solver(pb, active_body_count=0, joint_count=0)
            except Exception:
                pass
        self.body_ids.clear()
        self.shape_ids.clear()
        self.shape_type_counts.clear()
        self.constraint_ids.clear()
        self.constraint_max_forces.clear()
        self.last_frame = None
        self.last_joint_limit_correction_count = 0
        self.last_joint_spring_correction_count = 0
        self.last_orientation_feedback_count = 0
        self.last_solver_iterations = 0
        self.last_solver_substeps = 0
        self.last_solver_fixed_time_step = 0.0
        self.last_solver_active_body_count = 0
        self.last_solver_joint_count = 0
        self.last_capsule_axis_fix_count = 0

    def _ensure_client(self):
        pb = self._pybullet()
        if pb is None:
            return None
        if self.client_id is None:
            try:
                self.client_id = int(pb.connect(pb.DIRECT))
                pb.setGravity(0.0, -9.8, 0.0, physicsClientId=self.client_id)
                self._configure_solver(pb, active_body_count=0, joint_count=0)
            except Exception:
                self._pybullet_missing = True
                return None
        return pb

    @staticmethod
    def _solver_iterations_for(active_body_count: int, joint_count: int) -> int:
        bodies = max(0, int(active_body_count))
        joints = max(0, int(joint_count))
        iterations = 24
        if joints >= 128 or bodies >= 96:
            iterations = 36
        if joints >= 384 or bodies >= 256:
            iterations = 48
        if joints >= 560 or bodies >= 360:
            iterations = 56
        return max(16, min(80, iterations))

    def _configure_solver(self, pb, *, active_body_count: int, joint_count: int) -> None:
        if self.client_id is None:
            return
        fixed_time_step = max(1.0 / 240.0, min(1.0 / 60.0, float(self.solver_fixed_time_step)))
        iterations = self._solver_iterations_for(active_body_count, joint_count)
        try:
            pb.setTimeStep(fixed_time_step, physicsClientId=self.client_id)
        except Exception:
            pass
        try:
            pb.setPhysicsEngineParameter(
                fixedTimeStep=fixed_time_step,
                numSubSteps=0,
                numSolverIterations=iterations,
                contactERP=max(0.02, min(0.80, float(self.solver_contact_erp))),
                erp=max(0.02, min(0.80, float(self.solver_joint_erp))),
                frictionERP=max(0.02, min(0.80, float(self.solver_friction_erp))),
                deterministicOverlappingPairs=1,
                physicsClientId=self.client_id,
            )
        except Exception:
            try:
                pb.setPhysicsEngineParameter(
                    fixedTimeStep=fixed_time_step,
                    numSolverIterations=iterations,
                    physicsClientId=self.client_id,
                )
            except Exception:
                pass
        self.last_solver_iterations = int(iterations)
        self.last_solver_fixed_time_step = float(fixed_time_step)
        self.last_solver_active_body_count = int(active_body_count)
        self.last_solver_joint_count = int(joint_count)

    @staticmethod
    def _shape_radius(body) -> float:
        size = np.asarray(getattr(body, "size", (0.1, 0.1, 0.1)), dtype=np.float32)
        return max(0.025, min(0.35, float(np.linalg.norm(np.maximum(size, 0.001))) * 0.35))

    @staticmethod
    def _shape_type_name(shape_type: int) -> str:
        if int(shape_type) == 1:
            return "box"
        if int(shape_type) == 2:
            return "capsule"
        return "sphere"

    @staticmethod
    def _capsule_axis_orientation() -> tuple[float, float, float, float]:
        return _quat_from_euler((-math.pi * 0.5, 0.0, 0.0))

    @staticmethod
    def _collision_group_mask(body) -> tuple[int, int]:
        group_index = max(0, min(15, int(getattr(body, "collision_group", 0) or 0)))
        group = 1 << group_index
        no_collision_mask = int(getattr(body, "collision_mask", 0) or 0) & 0xFFFF
        collides_with = (~no_collision_mask) & 0xFFFF
        return int(group), int(collides_with)

    @staticmethod
    def _body_mass(body) -> float:
        if int(getattr(body, "physics_mode", 0) or 0) == 0:
            return 0.0
        return max(0.001, float(getattr(body, "mass", 1.0) or 1.0))

    def _body_orientation(self, pb, body) -> tuple[float, float, float, float]:
        try:
            rot = tuple(float(v) for v in getattr(body, "rotation", (0.0, 0.0, 0.0))[:3])
            quat = pb.getQuaternionFromEuler(rot)
            return _quat_normalize((quat[0], quat[1], quat[2], quat[3]))
        except Exception:
            return 0.0, 0.0, 0.0, 1.0

    def _body_target_orientation(
        self,
        pb,
        globals_: list[np.ndarray],
        bone_idx: int,
        body,
    ) -> tuple[float, float, float, float]:
        body_quat = self._body_orientation(pb, body)
        if not (0 <= int(bone_idx) < len(globals_)):
            return body_quat
        bone_quat = _matrix_to_quat(np.asarray(globals_[int(bone_idx)], dtype=np.float32)[:3, :3])
        return _quat_multiply(bone_quat, body_quat)

    def _create_collision_shape(self, pb, body_index: int, body) -> int | None:
        if self.client_id is None:
            return None
        if body_index in self.shape_ids:
            return self.shape_ids[body_index]
        try:
            size = np.asarray(getattr(body, "size", (0.1, 0.1, 0.1)), dtype=np.float32)
            size = np.maximum(size, 0.001)
            shape_type = int(getattr(body, "shape", 0) or 0)
            if shape_type == 1:
                shape_id = pb.createCollisionShape(
                    pb.GEOM_BOX,
                    halfExtents=[float(size[0]), float(size[1]), float(size[2])],
                    physicsClientId=self.client_id,
                )
            elif shape_type == 2:
                capsule_orientation = self._capsule_axis_orientation()
                shape_id = pb.createCollisionShape(
                    pb.GEOM_CAPSULE,
                    radius=float(size[0]),
                    height=float(max(size[1] * 2.0, size[0] * 2.0)),
                    collisionFrameOrientation=[
                        float(capsule_orientation[0]),
                        float(capsule_orientation[1]),
                        float(capsule_orientation[2]),
                        float(capsule_orientation[3]),
                    ],
                    physicsClientId=self.client_id,
                )
                self.last_capsule_axis_fix_count += 1
            else:
                shape_id = pb.createCollisionShape(
                    pb.GEOM_SPHERE,
                    radius=float(max(size[0], 0.001)),
                    physicsClientId=self.client_id,
                )
            self.shape_ids[body_index] = int(shape_id)
            shape_name = self._shape_type_name(shape_type)
            self.shape_type_counts[shape_name] = int(self.shape_type_counts.get(shape_name, 0)) + 1
            return int(shape_id)
        except Exception:
            return None

    def _ensure_body(
        self,
        pb,
        body_index: int,
        body,
        target: np.ndarray,
        *,
        target_orientation: tuple[float, float, float, float] | None = None,
        active: bool = True,
    ) -> int | None:
        if body_index in self.body_ids:
            return self.body_ids[body_index]
        if self.client_id is None:
            return None
        try:
            shape = self._create_collision_shape(pb, body_index, body)
            if shape is None:
                return None
            mass = self._body_mass(body) if active else 0.0
            orientation = _quat_normalize(target_orientation or self._body_orientation(pb, body))
            body_id = pb.createMultiBody(
                baseMass=mass,
                baseCollisionShapeIndex=shape,
                basePosition=[float(target[0]), float(target[1]), float(target[2])],
                baseOrientation=[float(orientation[0]), float(orientation[1]), float(orientation[2]), float(orientation[3])],
                physicsClientId=self.client_id,
            )
            damping = max(0.0, min(0.99, float(getattr(body, "linear_damping", 0.25) or 0.0)))
            pb.changeDynamics(
                body_id,
                -1,
                linearDamping=damping,
                angularDamping=max(0.0, min(0.99, float(getattr(body, "angular_damping", 0.25) or 0.0))),
                lateralFriction=max(0.0, min(2.0, float(getattr(body, "friction", 0.5) or 0.0))),
                restitution=max(0.0, min(1.0, float(getattr(body, "restitution", 0.0) or 0.0))),
                physicsClientId=self.client_id,
            )
            group, mask = self._collision_group_mask(body)
            try:
                pb.setCollisionFilterGroupMask(
                    body_id,
                    -1,
                    collisionFilterGroup=group,
                    collisionFilterMask=mask,
                    physicsClientId=self.client_id,
                )
            except TypeError:
                pb.setCollisionFilterGroupMask(body_id, -1, group, mask, physicsClientId=self.client_id)
            self.body_ids[body_index] = int(body_id)
            return int(body_id)
        except Exception:
            return None

    def _reset_body_to_target(
        self,
        pb,
        body_id: int,
        body,
        target: np.ndarray,
        target_orientation: tuple[float, float, float, float] | None = None,
    ) -> None:
        if self.client_id is None:
            return
        try:
            orientation = _quat_normalize(target_orientation or self._body_orientation(pb, body))
            pb.resetBasePositionAndOrientation(
                body_id,
                [float(target[0]), float(target[1]), float(target[2])],
                [float(orientation[0]), float(orientation[1]), float(orientation[2]), float(orientation[3])],
                physicsClientId=self.client_id,
            )
        except Exception:
            pass

    @staticmethod
    def _joint_orientation(joint) -> tuple[float, float, float, float]:
        return _quat_from_euler(np.asarray(getattr(joint, "rotation", (0.0, 0.0, 0.0)), dtype=np.float32))

    @staticmethod
    def _joint_pivot_local(
        body_target: np.ndarray,
        body_orientation: tuple[float, float, float, float],
        joint_position: np.ndarray,
    ) -> np.ndarray:
        pivot_world = np.asarray(joint_position, dtype=np.float32) - np.asarray(body_target, dtype=np.float32)
        return _quat_rotate(_quat_inverse(body_orientation), pivot_world)

    def _ensure_joint_constraint(
        self,
        pb,
        joint_index: int,
        joint,
        entries: dict[int, tuple[int, object, np.ndarray, tuple[float, float, float, float], bool]],
    ) -> None:
        if self.client_id is None or joint_index in self.constraint_ids:
            return
        a_idx = _int_attr(joint, "rigid_body_a", -1)
        b_idx = _int_attr(joint, "rigid_body_b", -1)
        if a_idx not in entries or b_idx not in entries:
            return
        a_body_id = self.body_ids.get(a_idx)
        b_body_id = self.body_ids.get(b_idx)
        if a_body_id is None or b_body_id is None:
            return
        _a_bone, _a_body, a_target, a_orientation, _a_active = entries[a_idx]
        _b_bone, _b_body, b_target, b_orientation, _b_active = entries[b_idx]
        joint_pos = np.asarray(getattr(joint, "position", (0.0, 0.0, 0.0)), dtype=np.float32)
        pivot_a = self._joint_pivot_local(a_target, a_orientation, joint_pos)
        pivot_b = self._joint_pivot_local(b_target, b_orientation, joint_pos)
        try:
            constraint_id = pb.createConstraint(
                a_body_id,
                -1,
                b_body_id,
                -1,
                pb.JOINT_POINT2POINT,
                [0.0, 0.0, 0.0],
                [float(pivot_a[0]), float(pivot_a[1]), float(pivot_a[2])],
                [float(pivot_b[0]), float(pivot_b[1]), float(pivot_b[2])],
                physicsClientId=self.client_id,
            )
            max_force = self._joint_constraint_max_force(joint, _a_body, _b_body)
            try:
                pb.changeConstraint(int(constraint_id), maxForce=max_force, physicsClientId=self.client_id)
            except Exception:
                pass
            self.constraint_ids[joint_index] = int(constraint_id)
            self.constraint_max_forces[joint_index] = float(max_force)
        except Exception:
            return

    def _joint_constraint_max_force(self, joint, body_a=None, body_b=None) -> float:
        linear_spring = float(np.linalg.norm(np.asarray(getattr(joint, "linear_spring", (0.0, 0.0, 0.0)), dtype=np.float32)))
        angular_spring = float(np.linalg.norm(np.asarray(getattr(joint, "angular_spring", (0.0, 0.0, 0.0)), dtype=np.float32)))
        masses = []
        for body in (body_a, body_b):
            if body is None:
                continue
            try:
                mass = float(getattr(body, "mass", 0.0) or 0.0)
            except Exception:
                mass = 0.0
            if mass > 0.0:
                masses.append(mass)
        avg_mass = float(sum(masses) / len(masses)) if masses else 1.0
        spring_force = linear_spring * 0.045 + angular_spring * 0.030
        mass_force = min(32.0, avg_mass * 2.5)
        if spring_force <= 0.00001:
            return max(8.0, min(80.0, 18.0 + mass_force))
        return max(12.0, min(260.0, 16.0 + spring_force + mass_force))

    def _apply_position_correction(
        self,
        pb,
        body_id: int,
        position: np.ndarray,
        orientation: tuple[float, float, float, float],
    ) -> None:
        if self.client_id is None:
            return
        try:
            pb.resetBasePositionAndOrientation(
                body_id,
                [float(position[0]), float(position[1]), float(position[2])],
                [float(orientation[0]), float(orientation[1]), float(orientation[2]), float(orientation[3])],
                physicsClientId=self.client_id,
            )
        except Exception:
            pass

    @staticmethod
    def _joint_linear_bounds(joint) -> tuple[np.ndarray, np.ndarray]:
        lower = np.asarray(getattr(joint, "linear_lower", (0.0, 0.0, 0.0)), dtype=np.float32)
        upper = np.asarray(getattr(joint, "linear_upper", (0.0, 0.0, 0.0)), dtype=np.float32)
        return np.minimum(lower, upper), np.maximum(lower, upper)

    @staticmethod
    def _joint_angular_bounds(joint) -> tuple[np.ndarray, np.ndarray]:
        lower = np.asarray(getattr(joint, "angular_lower", (0.0, 0.0, 0.0)), dtype=np.float32)
        upper = np.asarray(getattr(joint, "angular_upper", (0.0, 0.0, 0.0)), dtype=np.float32)
        return np.minimum(lower, upper), np.maximum(lower, upper)

    def _apply_joint_limit_corrections(
        self,
        pb,
        joints,
        entries: dict[int, tuple[int, object, np.ndarray, tuple[float, float, float, float], bool]],
        dt: float,
    ) -> None:
        if self.client_id is None or dt <= 0.0:
            return
        for joint in joints:
            a_idx = _int_attr(joint, "rigid_body_a", -1)
            b_idx = _int_attr(joint, "rigid_body_b", -1)
            if a_idx not in entries or b_idx not in entries:
                continue
            a_id = self.body_ids.get(a_idx)
            b_id = self.body_ids.get(b_idx)
            if a_id is None or b_id is None:
                continue
            _a_bone, _a_body, a_target, a_target_orn, a_active = entries[a_idx]
            _b_bone, _b_body, b_target, b_target_orn, b_active = entries[b_idx]
            if not (a_active or b_active):
                continue
            try:
                a_pos_raw, a_orn_raw = pb.getBasePositionAndOrientation(a_id, physicsClientId=self.client_id)
                b_pos_raw, b_orn_raw = pb.getBasePositionAndOrientation(b_id, physicsClientId=self.client_id)
            except Exception:
                continue
            a_pos = np.asarray(a_pos_raw, dtype=np.float32)
            b_pos = np.asarray(b_pos_raw, dtype=np.float32)
            a_orn = _quat_normalize(a_orn_raw)
            b_orn = _quat_normalize(b_orn_raw)
            joint_pos = np.asarray(getattr(joint, "position", (0.0, 0.0, 0.0)), dtype=np.float32)
            joint_orientation = self._joint_orientation(joint)
            a_pivot_local = self._joint_pivot_local(a_target, a_target_orn, joint_pos)
            b_pivot_local = self._joint_pivot_local(b_target, b_target_orn, joint_pos)
            a_anchor = a_pos + _quat_rotate(a_orn, a_pivot_local)
            b_anchor = b_pos + _quat_rotate(b_orn, b_pivot_local)
            rel_local = _quat_rotate(_quat_inverse(joint_orientation), b_anchor - a_anchor)
            lower, upper = self._joint_linear_bounds(joint)
            clamped = np.minimum(np.maximum(rel_local, lower), upper)
            correction_local = rel_local - clamped
            linear_spring = np.asarray(getattr(joint, "linear_spring", (0.0, 0.0, 0.0)), dtype=np.float32)
            if float(np.linalg.norm(linear_spring)) > 0.00001:
                spring_strength = np.minimum(np.maximum(linear_spring * 0.0008, 0.0), 0.18)
                correction_local = correction_local + rel_local * spring_strength
                if float(np.linalg.norm(rel_local)) > 0.00001:
                    self.last_joint_spring_correction_count += 1
            correction = _quat_rotate(joint_orientation, correction_local)
            corr_len = float(np.linalg.norm(correction))
            if corr_len > 0.00001:
                correction = correction * min(0.65, max(0.08, 0.20 + corr_len * 1.5))
                if a_active and b_active:
                    a_pos = a_pos + correction * 0.5
                    b_pos = b_pos - correction * 0.5
                elif a_active:
                    a_pos = a_pos + correction
                elif b_active:
                    b_pos = b_pos - correction
                self.last_joint_limit_correction_count += 1

            q_target_rel = _quat_multiply(_quat_inverse(a_target_orn), b_target_orn)
            q_current_rel = _quat_multiply(_quat_inverse(a_orn), b_orn)
            q_error = _quat_multiply(_quat_inverse(q_target_rel), q_current_rel)
            q_error_joint = _quat_multiply(_quat_multiply(_quat_inverse(joint_orientation), q_error), joint_orientation)
            angular_lower, angular_upper = self._joint_angular_bounds(joint)
            angular_spring = np.asarray(getattr(joint, "angular_spring", (0.0, 0.0, 0.0)), dtype=np.float32)
            angular_strength = 0.0
            correction_q: tuple[float, float, float, float] | None = None
            try:
                euler = np.asarray(pb.getEulerFromQuaternion(q_error_joint), dtype=np.float32)
                outside = np.maximum(euler - angular_upper, 0.0) + np.minimum(euler - angular_lower, 0.0)
                if float(np.linalg.norm(outside)) > 0.00001:
                    angular_strength = max(angular_strength, min(0.28, 0.05 + float(np.linalg.norm(outside)) * 0.25))
                    correction_local_q = _quat_from_euler(-outside)
                    correction_q = _quat_multiply(
                        _quat_multiply(joint_orientation, _quat_scaled(correction_local_q, angular_strength)),
                        _quat_inverse(joint_orientation),
                    )
                if float(np.linalg.norm(angular_spring)) > 0.00001 and _quat_angle(q_error) > 0.0005:
                    angular_strength = max(angular_strength, min(0.20, float(np.linalg.norm(angular_spring)) * 0.00055))
                    self.last_joint_spring_correction_count += 1
            except Exception:
                if _quat_angle(q_error) > 0.25:
                    angular_strength = 0.08
            if angular_strength > 0.0001:
                if correction_q is None:
                    correction_q = _quat_scaled(_quat_inverse(q_error), angular_strength)
                if a_active and b_active:
                    half_q = _quat_scaled(correction_q, 0.5)
                    a_orn = _quat_multiply(a_orn, _quat_inverse(half_q))
                    b_orn = _quat_multiply(half_q, b_orn)
                elif a_active:
                    a_orn = _quat_multiply(a_orn, _quat_inverse(correction_q))
                elif b_active:
                    b_orn = _quat_multiply(correction_q, b_orn)
                self.last_joint_limit_correction_count += 1

            if a_active:
                self._apply_position_correction(pb, a_id, a_pos, a_orn)
            if b_active:
                self._apply_position_correction(pb, b_id, b_pos, b_orn)

    def _orientation_feedback_for_body(
        self,
        pb,
        model: MMDModel,
        globals_: list[np.ndarray],
        bone_idx: int,
        body,
        target_orientation: tuple[float, float, float, float],
        current_orientation: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float] | None:
        if not (0 <= bone_idx < len(model.bones) and bone_idx < len(globals_)):
            return None
        bone = model.bones[bone_idx]
        gain, influence_limit, max_angle = SpringPhysicsBackend._secondary_rotation_settings(
            body,
            bone,
            rotation_scale=self.fallback.secondary_rotation_scale,
            influence_limit=self.fallback.secondary_rotation_influence_limit,
        )
        if gain <= 0.0:
            return None
        q_error_world = _quat_multiply(current_orientation, _quat_inverse(target_orientation))
        angle = _quat_angle(q_error_world)
        if angle <= 0.001:
            return None
        if max_angle > 0.0 and angle > max_angle:
            q_error_world = _quat_scaled(q_error_world, max_angle / max(angle, 0.000001))
            angle = max_angle
        bone_world = _matrix_to_quat(np.asarray(globals_[bone_idx], dtype=np.float32)[:3, :3])
        local_error = _quat_multiply(_quat_multiply(_quat_inverse(bone_world), q_error_world), bone_world)
        influence = min(float(influence_limit), max(0.02, angle / max(max_angle, 0.05))) if max_angle > 0.0 else 0.10
        hint = _quat_scaled(local_error, min(0.45, gain * influence))
        if _quat_angle(hint) <= 0.0005:
            return None
        self.last_orientation_feedback_count += 1
        return hint

    def offsets_for(
        self,
        model: MMDModel,
        globals_: list[np.ndarray],
        frame: float,
    ) -> MMDPhysicsPoseDelta:
        pb = self._ensure_client()
        if pb is None or self.client_id is None:
            return _coerce_physics_delta(self.fallback.offsets_for(model, globals_, frame))

        entries: dict[int, tuple[int, object, np.ndarray, tuple[float, float, float, float], bool]] = {}
        for body_index, body in enumerate(model.rigid_bodies):
            bone_idx = _int_attr(body, "bone_index", -1)
            target = SpringPhysicsBackend._body_target(model, globals_, bone_idx, body.position)
            target_orientation = self._body_target_orientation(pb, globals_, bone_idx, body)
            active = bool(int(getattr(body, "physics_mode", 0) or 0) in {1, 2} and 0 <= bone_idx < len(globals_))
            entries[body_index] = (bone_idx, body, target, target_orientation, active)
        active_entries = [
            (body_index, bone_idx, body, target, target_orientation)
            for body_index, (bone_idx, body, target, target_orientation, active) in entries.items()
            if active
        ]
        if not active_entries:
            self.last_frame = float(frame)
            return MMDPhysicsPoseDelta({}, 0)
        if self.last_frame is None or frame < self.last_frame or abs(float(frame) - float(self.last_frame)) > 12.0:
            self.reset()
            pb = self._ensure_client()
            if pb is None or self.client_id is None:
                return _coerce_physics_delta(self.fallback.offsets_for(model, globals_, frame))
        self._configure_solver(pb, active_body_count=len(active_entries), joint_count=len(model.joints))
        previous = float(self.last_frame) if self.last_frame is not None else float(frame)
        dt = max(0.0, min(1.0 / 15.0, (float(frame) - previous) / 30.0))
        fixed_step = self.last_solver_fixed_time_step or self.solver_fixed_time_step
        substeps = max(1, min(10, int(round(dt / max(0.0001, fixed_step))))) if dt > 0.0 else 1
        self.last_solver_substeps = int(substeps if dt > 0.0 else 0)
        self.last_joint_limit_correction_count = 0
        self.last_joint_spring_correction_count = 0
        self.last_orientation_feedback_count = 0
        offsets_by_bone: dict[int, list[np.ndarray]] = {}
        rotations_by_bone: dict[int, list[tuple[float, float, float, float]]] = {}
        for body_index, (_bone_idx, body, target, target_orientation, active) in entries.items():
            body_id = self._ensure_body(
                pb,
                body_index,
                body,
                target,
                target_orientation=target_orientation,
                active=active,
            )
            if body_id is None:
                continue
            if not active or dt <= 0.0:
                self._reset_body_to_target(pb, body_id, body, target, target_orientation)
                continue
        for joint_index, joint in enumerate(model.joints):
            self._ensure_joint_constraint(pb, joint_index, joint, entries)
        for body_index, bone_idx, body, target, _target_orientation in active_entries:
            body_id = self.body_ids.get(body_index)
            if body_id is None:
                continue
            try:
                pos, _orn = pb.getBasePositionAndOrientation(body_id, physicsClientId=self.client_id)
                current = np.asarray(pos, dtype=np.float32)
                mass = max(0.05, float(getattr(body, "mass", 1.0) or 1.0))
                mode_follow = 1.35 if int(getattr(body, "physics_mode", 0) or 0) == 2 else 1.0
                force = (target - current) * (42.0 * mode_follow / mass)
                force[1] += -0.65 * mass
                pb.applyExternalForce(
                    body_id,
                    -1,
                    [float(force[0]), float(force[1]), float(force[2])],
                    [float(current[0]), float(current[1]), float(current[2])],
                    pb.WORLD_FRAME,
                    physicsClientId=self.client_id,
                )
            except Exception:
                continue
        for _ in range(substeps):
            try:
                pb.stepSimulation(physicsClientId=self.client_id)
            except Exception:
                break
            if model.joints:
                self._apply_joint_limit_corrections(pb, model.joints, entries, dt)
        for body_index, bone_idx, body, target, target_orientation in active_entries:
            body_id = self.body_ids.get(body_index)
            if body_id is None:
                continue
            try:
                pos, orn = pb.getBasePositionAndOrientation(body_id, physicsClientId=self.client_id)
            except Exception:
                continue
            delta = np.asarray(pos, dtype=np.float32) - target
            length = float(np.linalg.norm(delta))
            max_delta = SpringPhysicsBackend._max_displacement(body)
            if length > max_delta:
                delta = delta / max(0.0001, length) * max_delta
                corrected = target + delta
                try:
                    corrected_orientation = _quat_normalize(orn)
                    pb.resetBasePositionAndOrientation(
                        body_id,
                        [float(corrected[0]), float(corrected[1]), float(corrected[2])],
                        [
                            float(corrected_orientation[0]),
                            float(corrected_orientation[1]),
                            float(corrected_orientation[2]),
                            float(corrected_orientation[3]),
                        ],
                        physicsClientId=self.client_id,
                    )
                except Exception:
                    pass
            offsets_by_bone.setdefault(bone_idx, []).append(np.asarray(delta, dtype=np.float32))
            rotation_hint = SpringPhysicsBackend._rotation_hint_for_body(
                model,
                globals_,
                bone_idx,
                body,
                target,
                delta,
                rotation_scale=self.fallback.secondary_rotation_scale,
                influence_limit=self.fallback.secondary_rotation_influence_limit,
            )
            if rotation_hint is not None:
                rotations_by_bone.setdefault(bone_idx, []).append(rotation_hint)
            orientation_hint = self._orientation_feedback_for_body(
                pb,
                model,
                globals_,
                bone_idx,
                body,
                target_orientation,
                _quat_normalize(orn),
            )
            if orientation_hint is not None:
                rotations_by_bone.setdefault(bone_idx, []).append(orientation_hint)
        self.last_frame = float(frame)
        offsets = {
            bone_idx: np.asarray(np.mean(values, axis=0), dtype=np.float32)
            for bone_idx, values in offsets_by_bone.items()
            if values
        }
        rotation_offsets = {}
        identity = (0.0, 0.0, 0.0, 1.0)
        for bone_idx, values in rotations_by_bone.items():
            blended = identity
            weight = 1.0 / max(1, len(values))
            for quat in values:
                blended = _quat_slerp(blended, quat, weight)
            rotation_offsets[int(bone_idx)] = blended
        return MMDPhysicsPoseDelta(offsets, len(active_entries), rotation_offsets)


@dataclass
class DecimatedPhysicsBackend:
    """Reuse and smooth physics offsets between solver ticks.

    The wrapped backend still owns the stateful simulation. This layer keeps
    playback responsive by sampling that backend at a lower cadence, then
    easing visible offsets toward the latest solver result instead of popping
    cloth/hair bones to the new value in one frame.
    """

    backend: MMDPhysicsBackend
    update_interval_frames: float = 2.0
    smoothing_response: float = 0.88
    last_update_frame: float | None = None
    last_offsets: dict[int, np.ndarray] = field(default_factory=dict)
    target_offsets: dict[int, np.ndarray] = field(default_factory=dict)
    last_rotation_offsets: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    target_rotation_offsets: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    last_count: int = 0

    def reset(self) -> None:
        self.backend.reset()
        self.last_update_frame = None
        self.last_offsets.clear()
        self.target_offsets.clear()
        self.last_rotation_offsets.clear()
        self.target_rotation_offsets.clear()
        self.last_count = 0

    @staticmethod
    def _copy_offsets(offsets: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
        return {
            int(k): np.asarray(v, dtype=np.float32)
            for k, v in offsets.items()
        }

    @staticmethod
    def _blend_offsets(
        previous: dict[int, np.ndarray],
        target: dict[int, np.ndarray],
        response: float,
    ) -> dict[int, np.ndarray]:
        alpha = max(0.0, min(1.0, float(response)))
        if alpha >= 0.999:
            return DecimatedPhysicsBackend._copy_offsets(target)
        out: dict[int, np.ndarray] = {}
        zero = np.zeros((3,), dtype=np.float32)
        for key in set(previous) | set(target):
            prev = np.asarray(previous.get(key, zero), dtype=np.float32)
            nxt = np.asarray(target.get(key, zero), dtype=np.float32)
            value = prev + (nxt - prev) * alpha
            if float(np.linalg.norm(value)) > 0.00001 or key in target:
                out[int(key)] = np.asarray(value, dtype=np.float32)
        return out

    @staticmethod
    def _copy_rotations(rotations: dict[int, tuple[float, float, float, float]]) -> dict[int, tuple[float, float, float, float]]:
        return {
            int(k): _quat_normalize(v)
            for k, v in dict(rotations or {}).items()
        }

    @staticmethod
    def _blend_rotations(
        previous: dict[int, tuple[float, float, float, float]],
        target: dict[int, tuple[float, float, float, float]],
        response: float,
    ) -> dict[int, tuple[float, float, float, float]]:
        alpha = max(0.0, min(1.0, float(response)))
        if alpha >= 0.999:
            return DecimatedPhysicsBackend._copy_rotations(target)
        identity = (0.0, 0.0, 0.0, 1.0)
        out: dict[int, tuple[float, float, float, float]] = {}
        for key in set(previous) | set(target):
            prev = previous.get(key, identity)
            nxt = target.get(key, identity)
            value = _quat_slerp(prev, nxt, alpha)
            if abs(value[0]) + abs(value[1]) + abs(value[2]) > 0.00001 or key in target:
                out[int(key)] = value
        return out

    def offsets_for(
        self,
        model: MMDModel,
        globals_: list[np.ndarray],
        frame: float,
    ) -> MMDPhysicsPoseDelta:
        current = float(frame)
        interval = max(1.0, float(self.update_interval_frames))
        discontinuity = (
            self.last_update_frame is None
            or current < self.last_update_frame
            or abs(current - self.last_update_frame) > 12.0
        )
        should_update = (
            discontinuity
            or current - self.last_update_frame >= interval
        )
        if should_update:
            result = _coerce_physics_delta(self.backend.offsets_for(model, globals_, current))
            self.target_offsets = self._copy_offsets(result.translation_offsets)
            self.target_rotation_offsets = self._copy_rotations(result.rotation_offsets)
            if discontinuity or not self.last_offsets:
                self.last_offsets = self._copy_offsets(self.target_offsets)
                self.last_rotation_offsets = self._copy_rotations(self.target_rotation_offsets)
            else:
                self.last_offsets = self._blend_offsets(
                    self.last_offsets,
                    self.target_offsets,
                    self.smoothing_response,
                )
                self.last_rotation_offsets = self._blend_rotations(
                    self.last_rotation_offsets,
                    self.target_rotation_offsets,
                    self.smoothing_response,
                )
            self.last_count = int(result.active_count)
            self.last_update_frame = current
        return MMDPhysicsPoseDelta(
            {
                int(k): np.asarray(v, dtype=np.float32)
                for k, v in self.last_offsets.items()
            },
            int(self.last_count),
            self._copy_rotations(self.last_rotation_offsets),
        )


def mmd_physics_backend_diagnostics(backend: MMDPhysicsBackend | None) -> dict[str, object]:
    """Return text/JSON friendly state for the selected physics backend."""
    if backend is None:
        return {
            "physics_backend": "none",
            "physics_backend_class": "",
            "physics_backend_available": False,
            "physics_backend_fallback": False,
        }
    out: dict[str, object] = {
        "physics_backend_class": type(backend).__name__,
    }
    inner = getattr(backend, "backend", None)
    if inner is not None:
        out["physics_decimated_backend"] = True
        out["physics_update_interval_frames"] = float(getattr(backend, "update_interval_frames", 0.0) or 0.0)
        out["physics_smoothing_response"] = float(getattr(backend, "smoothing_response", 0.0) or 0.0)
        out.update(mmd_physics_backend_diagnostics(inner))
        out["physics_backend_wrapper_class"] = type(backend).__name__
        return out
    if isinstance(backend, NoPhysicsBackend):
        out.update(
            {
                "physics_backend": "none",
                "physics_backend_available": True,
                "physics_backend_fallback": False,
            }
        )
    elif isinstance(backend, PyBulletPhysicsBackend):
        available = bool(backend.available())
        constraint_forces = list(getattr(backend, "constraint_max_forces", {}).values())
        avg_constraint_force = float(sum(constraint_forces) / len(constraint_forces)) if constraint_forces else 0.0
        max_constraint_force = float(max(constraint_forces)) if constraint_forces else 0.0
        out.update(
            {
                "physics_backend": "pybullet" if available else "spring",
                "physics_backend_requested": "pybullet",
                "physics_backend_available": available,
                "physics_backend_fallback": not available,
                "physics_backend_body_count": int(len(backend.body_ids)),
                "physics_backend_shape_count": int(len(backend.shape_ids)),
                "physics_backend_shape_sphere_count": int(getattr(backend, "shape_type_counts", {}).get("sphere", 0)),
                "physics_backend_shape_box_count": int(getattr(backend, "shape_type_counts", {}).get("box", 0)),
                "physics_backend_shape_capsule_count": int(getattr(backend, "shape_type_counts", {}).get("capsule", 0)),
                "physics_backend_capsule_axis_fix_count": int(backend.last_capsule_axis_fix_count),
                "physics_backend_constraint_count": int(len(backend.constraint_ids)),
                "physics_backend_joint_frame_constraint_count": int(len(backend.constraint_ids)),
                "physics_backend_joint_limit_correction_count": int(backend.last_joint_limit_correction_count),
                "physics_backend_joint_spring_correction_count": int(backend.last_joint_spring_correction_count),
                "physics_backend_orientation_feedback_count": int(backend.last_orientation_feedback_count),
                "physics_backend_solver_iterations": int(backend.last_solver_iterations),
                "physics_backend_solver_substeps": int(backend.last_solver_substeps),
                "physics_backend_solver_fixed_time_step": float(backend.last_solver_fixed_time_step),
                "physics_backend_solver_active_body_count": int(backend.last_solver_active_body_count),
                "physics_backend_solver_joint_count": int(backend.last_solver_joint_count),
                "physics_backend_solver_contact_erp": float(backend.solver_contact_erp),
                "physics_backend_solver_joint_erp": float(backend.solver_joint_erp),
                "physics_backend_solver_friction_erp": float(backend.solver_friction_erp),
                "physics_backend_constraint_force_avg": avg_constraint_force,
                "physics_backend_constraint_force_max": max_constraint_force,
            }
        )
    elif isinstance(backend, SpringPhysicsBackend):
        out.update(
            {
                "physics_backend": "spring",
                "physics_backend_available": True,
                "physics_backend_fallback": False,
                "physics_backend_particle_count": int(len(backend.particles)),
            }
        )
    else:
        out.update(
            {
                "physics_backend": type(backend).__name__,
                "physics_backend_available": True,
                "physics_backend_fallback": False,
            }
        )
    return out


def configure_mmd_physics_backend(
    backend: MMDPhysicsBackend,
    *,
    spring_response: float | None = None,
    secondary_rotation_scale: float | None = None,
) -> MMDPhysicsBackend:
    if spring_response is not None and hasattr(backend, "spring_response"):
        setattr(backend, "spring_response", max(0.15, min(1.5, float(spring_response))))
    if secondary_rotation_scale is not None and hasattr(backend, "secondary_rotation_scale"):
        setattr(backend, "secondary_rotation_scale", max(0.0, min(0.5, float(secondary_rotation_scale))))
    inner = getattr(backend, "backend", None)
    if inner is not None:
        configure_mmd_physics_backend(
            inner,
            spring_response=spring_response,
            secondary_rotation_scale=secondary_rotation_scale,
        )
    fallback = getattr(backend, "fallback", None)
    if fallback is not None:
        configure_mmd_physics_backend(
            fallback,
            spring_response=spring_response,
            secondary_rotation_scale=secondary_rotation_scale,
        )
    return backend


def create_mmd_physics_backend(
    prefer: str | None = None,
    *,
    spring_response: float = SPRING_PHYSICS_RESPONSE,
    secondary_rotation_scale: float = SECONDARY_ROTATION_HINT_SCALE,
) -> MMDPhysicsBackend:
    choice = str(prefer or os.environ.get("TIGERCAPTURE_MMD_PHYSICS_BACKEND", "auto")).strip().casefold()
    if choice in {"none", "off", "disabled", "0"}:
        return NoPhysicsBackend()
    if choice == "spring":
        return SpringPhysicsBackend(
            spring_response=spring_response,
            secondary_rotation_scale=secondary_rotation_scale,
        )
    if choice in {"auto", "bullet", "pybullet"}:
        backend = PyBulletPhysicsBackend(
            fallback=SpringPhysicsBackend(
                spring_response=spring_response,
                secondary_rotation_scale=secondary_rotation_scale,
            )
        )
        if choice == "auto" and not backend.available():
            return backend.fallback
        return backend
    return SpringPhysicsBackend(
        spring_response=spring_response,
        secondary_rotation_scale=secondary_rotation_scale,
    )


MMDPhysicsState = SpringPhysicsBackend
