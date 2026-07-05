"""Runtime animation helpers for AR/PBR asset descriptors."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


FBX_TICKS_PER_SECOND = 46_186_158_000


def ticks_to_ms(value: Any) -> float:
    try:
        return float(value) * 1000.0 / float(FBX_TICKS_PER_SECOND)
    except Exception:
        return 0.0


def normalize_animation_settings(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, Mapping) else {}

    def _bool(key: str, default: bool) -> bool:
        raw = data.get(key)
        if isinstance(raw, bool):
            return raw
        if raw is None:
            return bool(default)
        text = str(raw).strip().casefold()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
        return bool(default)

    def _float(key: str, default: float, lo: float, hi: float) -> float:
        try:
            return max(lo, min(hi, float(data.get(key, default))))
        except Exception:
            return float(default)

    return {
        "auto_play": _bool("auto_play", True),
        "loop": _bool("loop", True),
        "clip": str(data.get("clip") or data.get("clip_id") or ""),
        "speed": _float("speed", 1.0, -8.0, 8.0),
        "start_offset_ms": _float("start_offset_ms", 0.0, 0.0, 24.0 * 60.0 * 60.0 * 1000.0),
    }


def animation_time_ms(track: Mapping[str, Any], timeline_ms: int, clip: Mapping[str, Any]) -> float | None:
    settings = normalize_animation_settings(track.get("animation") if isinstance(track, Mapping) else {})
    if not settings.get("auto_play", True):
        return None
    speed = float(settings.get("speed", 1.0) or 0.0)
    start_ms = _int(track.get("start_ms"), 0)
    local = (float(timeline_ms) - float(start_ms)) * speed + float(settings.get("start_offset_ms", 0.0) or 0.0)
    duration = _float(clip.get("duration_ms"), 0.0)
    if duration > 0.0 and bool(settings.get("loop", True)):
        local = local % duration
    return max(0.0, local)


def select_animation_clip(descriptor: Mapping[str, Any], track: Mapping[str, Any]) -> Mapping[str, Any] | None:
    clips = descriptor.get("animation_clips")
    if not isinstance(clips, list) or not clips:
        return None
    settings = normalize_animation_settings(track.get("animation") if isinstance(track, Mapping) else {})
    wanted = str(settings.get("clip") or "").strip()
    if wanted:
        for clip in clips:
            if not isinstance(clip, Mapping):
                continue
            if wanted in {str(clip.get("id") or ""), str(clip.get("name") or "")}:
                return clip
    return next((clip for clip in clips if isinstance(clip, Mapping)), None)


def animated_vertices_for_geometry(
    vertices: Sequence[Any],
    *,
    geometry: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    track: Mapping[str, Any],
    time_ms: int,
) -> list[Any] | Sequence[Any]:
    clip = select_animation_clip(descriptor, track)
    if clip is None:
        return vertices
    local_ms = animation_time_ms(track, int(time_ms), clip)
    if local_ms is None:
        return vertices
    model_id = str(geometry.get("model_id") or "")
    curves = clip.get("model_curves") if isinstance(clip.get("model_curves"), Mapping) else {}
    model_curves = curves.get(model_id) if model_id else None

    model = _model_by_id(descriptor).get(model_id, {})
    models = _model_by_id(descriptor)
    units = descriptor.get("units") if isinstance(descriptor.get("units"), Mapping) else {}
    unit_scale = _float(units.get("scale_to_meters"), 1.0)
    center = _bounds_center(geometry.get("bounds"))
    out_vertices: Sequence[Any] | list[Any] = vertices

    if isinstance(model_curves, Mapping):
        out_vertices = _apply_model_animation(
            out_vertices,
            model_curves=model_curves,
            model=model,
            unit_scale=unit_scale,
            center=center,
            local_ms=local_ms,
        )

    out_vertices = _apply_skin_animation(
        out_vertices,
        geometry=geometry,
        descriptor=descriptor,
        model_curves_by_id=curves,
        models=models,
        unit_scale=unit_scale,
        local_ms=local_ms,
    )
    return out_vertices


def _apply_model_animation(
    vertices: Sequence[Any],
    *,
    model_curves: Mapping[str, Any],
    model: Mapping[str, Any],
    unit_scale: float,
    center: list[float],
    local_ms: float,
) -> list[list[float]] | Sequence[Any]:
    base_t = _vec3(model.get("translation"), (0.0, 0.0, 0.0))
    base_r = _vec3(model.get("rotation"), (0.0, 0.0, 0.0))
    base_s = _vec3(model.get("scale"), (1.0, 1.0, 1.0))
    anim_t = _sample_vec3(model_curves.get("translation"), local_ms, base_t)
    anim_r = _sample_vec3(model_curves.get("rotation"), local_ms, base_r)
    anim_s = _sample_vec3(model_curves.get("scale"), local_ms, base_s)
    delta_t = [(anim_t[idx] - base_t[idx]) * unit_scale for idx in range(3)]
    delta_r = [anim_r[idx] - base_r[idx] for idx in range(3)]
    ratio_s = [
        anim_s[idx] / base_s[idx] if abs(base_s[idx]) > 1e-8 else 1.0
        for idx in range(3)
    ]
    if (
        max(abs(v) for v in delta_t) <= 1e-8
        and max(abs(v) for v in delta_r) <= 1e-8
        and max(abs(v - 1.0) for v in ratio_s) <= 1e-8
    ):
        return vertices

    rot = _rotation_matrix(delta_r[0], delta_r[1], delta_r[2])
    out: list[list[float]] = []
    for raw in vertices:
        v = _vec3(raw, (0.0, 0.0, 0.0))
        local = (
            (v[0] - center[0]) * ratio_s[0],
            (v[1] - center[1]) * ratio_s[1],
            (v[2] - center[2]) * ratio_s[2],
        )
        rotated = _mat_mul_vec(rot, local)
        out.append([
            center[0] + rotated[0] + delta_t[0],
            center[1] + rotated[1] + delta_t[1],
            center[2] + rotated[2] + delta_t[2],
        ])
    return out


def _apply_skin_animation(
    vertices: Sequence[Any],
    *,
    geometry: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    model_curves_by_id: Mapping[str, Any],
    models: Mapping[str, Mapping[str, Any]],
    unit_scale: float,
    local_ms: float,
) -> list[list[float]] | Sequence[Any]:
    weights = geometry.get("skin_weights")
    if not isinstance(weights, list) or not weights:
        return vertices
    matrix_skinned = _apply_matrix_skin_animation(
        vertices,
        geometry=geometry,
        descriptor=descriptor,
        model_curves_by_id=model_curves_by_id,
        models=models,
        unit_scale=unit_scale,
        local_ms=local_ms,
    )
    if matrix_skinned is not None:
        return matrix_skinned
    parent_by_id = _model_parent_map(descriptor)
    bind_poses: dict[str, dict[str, list[float]]] = {}
    anim_poses: dict[str, dict[str, list[float]]] = {}
    out: list[list[float]] = []
    changed = False
    for idx, raw_vertex in enumerate(vertices):
        v = _vec3(raw_vertex, (0.0, 0.0, 0.0))
        rows = weights[idx] if idx < len(weights) else []
        if not isinstance(rows, list):
            rows = []
        delta = [0.0, 0.0, 0.0]
        for row in rows[:8]:
            if not isinstance(row, Mapping):
                continue
            bone_id = str(row.get("bone_id") or row.get("model_id") or "")
            try:
                weight = max(0.0, min(1.0, float(row.get("weight", 0.0) or 0.0)))
            except Exception:
                weight = 0.0
            if not bone_id or weight <= 0.0:
                continue
            bone_curves = model_curves_by_id.get(bone_id)
            if not isinstance(bone_curves, Mapping):
                continue
            if bone_id not in bind_poses:
                bind_poses[bone_id] = _global_pose(
                    bone_id,
                    models=models,
                    parent_by_id=parent_by_id,
                    model_curves_by_id=model_curves_by_id,
                    unit_scale=unit_scale,
                    local_ms=local_ms,
                    animated=False,
                )
            if bone_id not in anim_poses:
                anim_poses[bone_id] = _global_pose(
                    bone_id,
                    models=models,
                    parent_by_id=parent_by_id,
                    model_curves_by_id=model_curves_by_id,
                    unit_scale=unit_scale,
                    local_ms=local_ms,
                    animated=True,
                )
            deformed = _deform_by_pose_delta(v, bind_poses[bone_id], anim_poses[bone_id])
            for axis in range(3):
                delta[axis] += (deformed[axis] - v[axis]) * weight
        if max(abs(value) for value in delta) > 1e-8:
            changed = True
            out.append([v[0] + delta[0], v[1] + delta[1], v[2] + delta[2]])
        else:
            out.append(v)
    return out if changed else vertices


def _apply_matrix_skin_animation(
    vertices: Sequence[Any],
    *,
    geometry: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    model_curves_by_id: Mapping[str, Any],
    models: Mapping[str, Mapping[str, Any]],
    unit_scale: float,
    local_ms: float,
) -> list[list[float]] | None:
    weights = geometry.get("skin_weights")
    joint_ids = geometry.get("skin_joint_ids")
    inverse_bind = geometry.get("skin_inverse_bind_matrices")
    if not isinstance(weights, list) or not isinstance(joint_ids, list) or not isinstance(inverse_bind, list):
        return None
    if not joint_ids or not inverse_bind:
        return None
    try:
        import numpy as np
    except Exception:
        return None

    parent_by_id = _model_parent_map(descriptor)
    skin_mats: dict[str, Any] = {}
    identity = np.eye(4, dtype=np.float64)
    for slot, joint_id_raw in enumerate(joint_ids):
        joint_id = str(joint_id_raw or "")
        if not joint_id:
            continue
        try:
            ibm = np.asarray(inverse_bind[slot], dtype=np.float64).reshape((4, 4))
        except Exception:
            ibm = identity
        skin_mats[joint_id] = _global_matrix(
            joint_id,
            models=models,
            parent_by_id=parent_by_id,
            model_curves_by_id=model_curves_by_id,
            unit_scale=unit_scale,
            local_ms=local_ms,
            animated=True,
        ) @ ibm
    if not skin_mats:
        return None

    out: list[list[float]] = []
    changed = False
    for idx, raw_vertex in enumerate(vertices):
        v = _vec3(raw_vertex, (0.0, 0.0, 0.0))
        hv = np.asarray([v[0], v[1], v[2], 1.0], dtype=np.float64)
        rows = weights[idx] if idx < len(weights) else []
        if not isinstance(rows, list):
            rows = []
        accum = np.zeros(4, dtype=np.float64)
        total = 0.0
        for row in rows[:8]:
            if not isinstance(row, Mapping):
                continue
            bone_id = str(row.get("bone_id") or row.get("model_id") or "")
            mat = skin_mats.get(bone_id)
            if mat is None:
                continue
            try:
                weight = max(0.0, min(1.0, float(row.get("weight", 0.0) or 0.0)))
            except Exception:
                weight = 0.0
            if weight <= 1.0e-6:
                continue
            accum += (mat @ hv) * weight
            total += weight
        if total > 1.0e-6:
            if abs(float(accum[3])) > 1.0e-8:
                accum = accum / float(accum[3])
            result = [float(accum[0]), float(accum[1]), float(accum[2])]
            if max(abs(result[axis] - v[axis]) for axis in range(3)) > 1.0e-8:
                changed = True
            out.append(result)
        else:
            out.append(v)
    return out if changed else list(vertices)


def descriptor_animation_diagnostics(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    clips = [clip for clip in descriptor.get("animation_clips", []) or [] if isinstance(clip, Mapping)]
    bones = [bone for bone in descriptor.get("bones", []) or [] if isinstance(bone, Mapping)]
    return {
        "animation_count": len(clips),
        "skeleton_bone_count": len(bones),
        "skeletal_mesh_count": int(descriptor.get("skeletal_mesh_count", 0) or 0),
        "has_static_mesh_animation": any(bool((clip.get("model_curves") or {})) for clip in clips),
        "has_skeletal_animation": bool(bones) and bool(clips),
    }


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _vec3(value: Any, default: tuple[float, float, float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        raw = source[idx] if idx < len(source) else default[idx]
        out.append(_float(raw, default[idx]))
    return out


def _vec4(value: Any, default: tuple[float, float, float, float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(4):
        raw = source[idx] if idx < len(source) else default[idx]
        out.append(_float(raw, default[idx]))
    return _normalize_quat(out)


def _normalize_quat(value: Sequence[Any]) -> list[float]:
    vals = [_float(value[idx] if idx < len(value) else 0.0, 0.0) for idx in range(4)]
    length = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / length for v in vals]


def _bounds_center(value: Any) -> list[float]:
    if isinstance(value, Mapping):
        center = value.get("center")
        if isinstance(center, (list, tuple)) and len(center) >= 3:
            return _vec3(center, (0.0, 0.0, 0.0))
    return [0.0, 0.0, 0.0]


def _model_by_id(descriptor: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(model.get("id") or ""): model
        for model in descriptor.get("models", []) or []
        if isinstance(model, Mapping)
    }


def _model_parent_map(descriptor: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for model in descriptor.get("models", []) or []:
        if not isinstance(model, Mapping):
            continue
        model_id = str(model.get("id") or "")
        parent_id = str(model.get("parent_id") or "")
        if model_id and parent_id:
            out[model_id] = parent_id
    for bone in descriptor.get("bones", []) or []:
        if not isinstance(bone, Mapping):
            continue
        bone_id = str(bone.get("id") or "")
        parent_id = str(bone.get("parent_id") or "")
        if bone_id and parent_id:
            out[bone_id] = parent_id
    return out


def _local_pose(
    model_id: str,
    *,
    models: Mapping[str, Mapping[str, Any]],
    model_curves_by_id: Mapping[str, Any],
    local_ms: float,
    animated: bool,
) -> dict[str, list[float]]:
    model = models.get(model_id, {})
    base_t = _vec3(model.get("translation"), (0.0, 0.0, 0.0))
    base_r = _vec3(model.get("rotation"), (0.0, 0.0, 0.0))
    base_s = _vec3(model.get("scale"), (1.0, 1.0, 1.0))
    curves = model_curves_by_id.get(model_id) if animated else None
    if isinstance(curves, Mapping):
        return {
            "translation": _sample_vec3(curves.get("translation"), local_ms, base_t),
            "rotation": _sample_vec3(curves.get("rotation"), local_ms, base_r),
            "scale": _sample_vec3(curves.get("scale"), local_ms, base_s),
        }
    return {"translation": base_t, "rotation": base_r, "scale": base_s}


def _local_matrix(
    model_id: str,
    *,
    models: Mapping[str, Mapping[str, Any]],
    model_curves_by_id: Mapping[str, Any],
    unit_scale: float,
    local_ms: float,
    animated: bool,
):
    import numpy as np

    model = models.get(model_id, {})
    base_t = _vec3(model.get("translation"), (0.0, 0.0, 0.0))
    base_s = _vec3(model.get("scale"), (1.0, 1.0, 1.0))
    base_q = _vec4(model.get("rotation_quat"), (0.0, 0.0, 0.0, 1.0))
    curves = model_curves_by_id.get(model_id) if animated else None
    if isinstance(curves, Mapping):
        t = _sample_vec3(curves.get("translation"), local_ms, base_t)
        s = _sample_vec3(curves.get("scale"), local_ms, base_s)
        q = _sample_quat(curves.get("rotation_quat"), local_ms, base_q)
        if not isinstance(curves.get("rotation_quat"), Mapping):
            euler_default = _vec3(model.get("rotation"), (0.0, 0.0, 0.0))
            euler = _sample_vec3(curves.get("rotation"), local_ms, euler_default)
            q = _quat_from_euler_deg(euler[0], euler[1], euler[2])
    else:
        t = base_t
        s = base_s
        q = base_q

    mat = np.eye(4, dtype=np.float64)
    mat[:3, :3] = _quat_to_mat3(q) @ np.diag(np.asarray(s, dtype=np.float64))
    mat[:3, 3] = np.asarray([t[0] * unit_scale, t[1] * unit_scale, t[2] * unit_scale], dtype=np.float64)
    return mat


def _global_matrix(
    model_id: str,
    *,
    models: Mapping[str, Mapping[str, Any]],
    parent_by_id: Mapping[str, str],
    model_curves_by_id: Mapping[str, Any],
    unit_scale: float,
    local_ms: float,
    animated: bool,
    stack: tuple[str, ...] = (),
):
    import numpy as np

    local = _local_matrix(
        model_id,
        models=models,
        model_curves_by_id=model_curves_by_id,
        unit_scale=unit_scale,
        local_ms=local_ms,
        animated=animated,
    )
    parent_id = str(parent_by_id.get(model_id) or "")
    if not parent_id or parent_id in stack:
        return local
    return _global_matrix(
        parent_id,
        models=models,
        parent_by_id=parent_by_id,
        model_curves_by_id=model_curves_by_id,
        unit_scale=unit_scale,
        local_ms=local_ms,
        animated=animated,
        stack=(*stack, model_id),
    ) @ local


def _global_pose(
    model_id: str,
    *,
    models: Mapping[str, Mapping[str, Any]],
    parent_by_id: Mapping[str, str],
    model_curves_by_id: Mapping[str, Any],
    unit_scale: float,
    local_ms: float,
    animated: bool,
    stack: tuple[str, ...] = (),
) -> dict[str, list[float]]:
    local = _local_pose(
        model_id,
        models=models,
        model_curves_by_id=model_curves_by_id,
        local_ms=local_ms,
        animated=animated,
    )
    local_t = [value * unit_scale for value in local["translation"]]
    local_r = list(local["rotation"])
    local_s = list(local["scale"])
    parent_id = str(parent_by_id.get(model_id) or "")
    if not parent_id or parent_id in stack:
        return {"translation": local_t, "rotation": local_r, "scale": local_s}
    parent = _global_pose(
        parent_id,
        models=models,
        parent_by_id=parent_by_id,
        model_curves_by_id=model_curves_by_id,
        unit_scale=unit_scale,
        local_ms=local_ms,
        animated=animated,
        stack=(*stack, model_id),
    )
    parent_s = parent["scale"]
    parent_r = parent["rotation"]
    scaled_t = (
        local_t[0] * parent_s[0],
        local_t[1] * parent_s[1],
        local_t[2] * parent_s[2],
    )
    rotated_t = _mat_mul_vec(_rotation_matrix(parent_r[0], parent_r[1], parent_r[2]), scaled_t)
    return {
        "translation": [
            parent["translation"][0] + rotated_t[0],
            parent["translation"][1] + rotated_t[1],
            parent["translation"][2] + rotated_t[2],
        ],
        "rotation": [
            parent_r[0] + local_r[0],
            parent_r[1] + local_r[1],
            parent_r[2] + local_r[2],
        ],
        "scale": [
            parent_s[0] * local_s[0],
            parent_s[1] * local_s[1],
            parent_s[2] * local_s[2],
        ],
    }


def _deform_by_pose_delta(
    vertex: list[float],
    bind_pose: Mapping[str, list[float]],
    anim_pose: Mapping[str, list[float]],
) -> list[float]:
    bind_t = _vec3(bind_pose.get("translation"), (0.0, 0.0, 0.0))
    anim_t = _vec3(anim_pose.get("translation"), (0.0, 0.0, 0.0))
    bind_r = _vec3(bind_pose.get("rotation"), (0.0, 0.0, 0.0))
    anim_r = _vec3(anim_pose.get("rotation"), (0.0, 0.0, 0.0))
    bind_s = _vec3(bind_pose.get("scale"), (1.0, 1.0, 1.0))
    anim_s = _vec3(anim_pose.get("scale"), (1.0, 1.0, 1.0))
    ratio_s = [
        anim_s[idx] / bind_s[idx] if abs(bind_s[idx]) > 1e-8 else 1.0
        for idx in range(3)
    ]
    delta_r = [anim_r[idx] - bind_r[idx] for idx in range(3)]
    local = (
        (vertex[0] - bind_t[0]) * ratio_s[0],
        (vertex[1] - bind_t[1]) * ratio_s[1],
        (vertex[2] - bind_t[2]) * ratio_s[2],
    )
    rotated = _mat_mul_vec(_rotation_matrix(delta_r[0], delta_r[1], delta_r[2]), local)
    return [
        anim_t[0] + rotated[0],
        anim_t[1] + rotated[1],
        anim_t[2] + rotated[2],
    ]


def _sample_vec3(value: Any, time_ms: float, default: list[float]) -> list[float]:
    if not isinstance(value, Mapping):
        return list(default)
    axes = ("x", "y", "z")
    return [_sample_curve(value.get(axis), time_ms, default[idx]) for idx, axis in enumerate(axes)]


def _sample_quat(value: Any, time_ms: float, default: list[float]) -> list[float]:
    if not isinstance(value, Mapping):
        return _normalize_quat(default)
    rows: list[tuple[float, list[float]]] = []
    axes = ("x", "y", "z", "w")
    raw_axes = [value.get(axis) for axis in axes]
    if not all(isinstance(axis_rows, (list, tuple)) for axis_rows in raw_axes):
        return _normalize_quat(default)
    count = min(len(axis_rows) for axis_rows in raw_axes if isinstance(axis_rows, (list, tuple)))
    for idx in range(count):
        time_value = None
        quat: list[float] = []
        for axis_idx, axis_rows in enumerate(raw_axes):
            row = axis_rows[idx]
            if isinstance(row, Mapping):
                t = _float(row.get("time_ms"), 0.0)
                v = _float(row.get("value"), default[axis_idx])
            elif isinstance(row, (list, tuple)) and len(row) >= 2:
                t = _float(row[0], 0.0)
                v = _float(row[1], default[axis_idx])
            else:
                t = 0.0
                v = float(default[axis_idx])
            if time_value is None:
                time_value = t
            quat.append(v)
        rows.append((float(time_value or 0.0), _normalize_quat(quat)))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return _normalize_quat(default)
    if time_ms <= rows[0][0]:
        return rows[0][1]
    for idx in range(1, len(rows)):
        t0, q0 = rows[idx - 1]
        t1, q1 = rows[idx]
        if time_ms <= t1:
            if t1 <= t0:
                return q1
            ratio = max(0.0, min(1.0, (time_ms - t0) / (t1 - t0)))
            dot = sum(a * b for a, b in zip(q0, q1))
            if dot < 0.0:
                q1 = [-v for v in q1]
            return _normalize_quat([q0[i] * (1.0 - ratio) + q1[i] * ratio for i in range(4)])
    return rows[-1][1]


def _sample_curve(value: Any, time_ms: float, default: float) -> float:
    if not isinstance(value, (list, tuple)) or not value:
        return float(default)
    rows: list[tuple[float, float]] = []
    for row in value:
        if isinstance(row, Mapping):
            rows.append((_float(row.get("time_ms"), 0.0), _float(row.get("value"), default)))
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            rows.append((_float(row[0], 0.0), _float(row[1], default)))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return float(default)
    if time_ms <= rows[0][0]:
        return rows[0][1]
    for idx in range(1, len(rows)):
        t0, v0 = rows[idx - 1]
        t1, v1 = rows[idx]
        if time_ms <= t1:
            if t1 <= t0:
                return v1
            ratio = max(0.0, min(1.0, (time_ms - t0) / (t1 - t0)))
            return v0 + (v1 - v0) * ratio
    return rows[-1][1]


def _rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> tuple[tuple[float, float, float], ...]:
    def mm(a, b):
        return tuple(
            tuple(sum(a[row][k] * b[k][col] for k in range(3)) for col in range(3))
            for row in range(3)
        )

    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    mx = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    my = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    mz = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))
    return mm(mz, mm(my, mx))


def _quat_from_euler_deg(rx_deg: float, ry_deg: float, rz_deg: float) -> list[float]:
    rx = math.radians(rx_deg) * 0.5
    ry = math.radians(ry_deg) * 0.5
    rz = math.radians(rz_deg) * 0.5
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    return _normalize_quat([
        sx * cy * cz - cx * sy * sz,
        cx * sy * cz + sx * cy * sz,
        cx * cy * sz - sx * sy * cz,
        cx * cy * cz + sx * sy * sz,
    ])


def _quat_to_mat3(q: Sequence[Any]):
    import numpy as np

    x, y, z, w = _normalize_quat(q)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.asarray([
        [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
        [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
        [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
    ], dtype=np.float64)


def _mat_mul_vec(m: tuple[tuple[float, float, float], ...], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )
