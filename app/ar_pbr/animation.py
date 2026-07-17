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
    unit_scale = _animation_unit_scale(descriptor)
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
    reference_pose_skinned = _apply_reference_pose_skin_animation(
        vertices,
        geometry=geometry,
        descriptor=descriptor,
        model_curves_by_id=model_curves_by_id,
        models=models,
        unit_scale=unit_scale,
        local_ms=local_ms,
    )
    if reference_pose_skinned is not None:
        return reference_pose_skinned
    parent_by_id = _model_parent_map(descriptor)
    bind_poses: dict[str, dict[str, list[float]]] = {}
    anim_poses: dict[str, dict[str, list[float]]] = {}
    out: list[list[float]] = []
    changed = False
    for idx, raw_vertex in enumerate(vertices):
        v = _vec3(raw_vertex, (0.0, 0.0, 0.0))
        rows = _normalized_weight_rows(weights[idx] if idx < len(weights) else [])
        delta = [0.0, 0.0, 0.0]
        for row in rows[:8]:
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


def _apply_reference_pose_skin_animation(
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
    if not isinstance(weights, list) or not weights:
        return None
    try:
        import numpy as np
    except Exception:
        return None

    vertices_np = np.asarray(vertices, dtype=np.float64)
    if vertices_np.ndim != 2 or vertices_np.shape[1] != 3:
        return None
    joint_keys, joint_indices, weight_values = _skin_weight_arrays(geometry, len(vertices_np))
    if not joint_keys:
        return None

    parent_by_id = _model_parent_map(descriptor)
    identity = np.eye(4, dtype=np.float64)
    skin_mats: list[Any] = []
    animated_matrix_count = 0
    for joint_id in joint_keys:
        try:
            bind = _global_matrix(
                joint_id,
                models=models,
                parent_by_id=parent_by_id,
                model_curves_by_id=model_curves_by_id,
                unit_scale=unit_scale,
                local_ms=local_ms,
                animated=False,
            )
            anim = _global_matrix(
                joint_id,
                models=models,
                parent_by_id=parent_by_id,
                model_curves_by_id=model_curves_by_id,
                unit_scale=unit_scale,
                local_ms=local_ms,
                animated=True,
            )
            mat = anim @ np.linalg.inv(bind)
        except Exception:
            mat = identity
        if not np.allclose(mat, identity, atol=1.0e-8):
            animated_matrix_count += 1
        skin_mats.append(mat)
    if animated_matrix_count <= 0:
        return list(vertices)

    hv = np.concatenate(
        [vertices_np, np.ones((len(vertices_np), 1), dtype=np.float64)],
        axis=1,
    )
    accum = np.zeros((len(vertices_np), 4), dtype=np.float64)
    total = np.zeros((len(vertices_np),), dtype=np.float64)
    slot_count = joint_indices.shape[1]
    for slot in range(slot_count):
        ids = joint_indices[:, slot]
        ws = weight_values[:, slot].astype(np.float64, copy=False)
        valid = (ids >= 0) & (ws > 1.0e-8)
        if not np.any(valid):
            continue
        for joint_index_raw in np.unique(ids[valid]):
            joint_index = int(joint_index_raw)
            mat = skin_mats[joint_index]
            mask = valid & (ids == joint_index)
            transformed = hv[mask] @ mat.T
            accum[mask] += transformed * ws[mask, None]
            total[mask] += ws[mask]

    out = vertices_np.copy()
    valid_total = total > 1.0e-8
    if np.any(valid_total):
        skinned = accum[valid_total]
        w = skinned[:, 3:4]
        nonzero_w = np.abs(w[:, 0]) > 1.0e-8
        skinned_xyz = skinned[:, :3]
        skinned_xyz[nonzero_w] = skinned_xyz[nonzero_w] / w[nonzero_w]
        out[valid_total] = skinned_xyz
    if not np.any(np.abs(out - vertices_np) > 1.0e-8):
        return list(vertices)
    return out.astype(float).tolist()


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
        rows = _normalized_weight_rows(weights[idx] if idx < len(weights) else [])
        accum = np.zeros(4, dtype=np.float64)
        total = 0.0
        for row in rows[:8]:
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


def _animation_unit_scale(descriptor: Mapping[str, Any]) -> float:
    """Return the transform scale to use for animation bone translations.

    Unreal skeletal exports already store vertex and reference-bone positions in
    Tiger Studio runtime meters. The `units.scale_to_meters` field still records
    the original source unit, so applying it again folds the Manny skeleton down
    to 1/100 scale during animation.
    """

    schema = str(descriptor.get("schema") or "")
    source_format = str(descriptor.get("source_format") or "")
    if schema == "tigerstudio.ar_pbr.unreal_skeletal_mesh_export.v1" or source_format == "unreal_skeletal_mesh":
        return 1.0
    units = descriptor.get("units") if isinstance(descriptor.get("units"), Mapping) else {}
    return _float(units.get("scale_to_meters"), 1.0)


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
    out = {
        str(model.get("id") or ""): model
        for model in descriptor.get("models", []) or []
        if isinstance(model, Mapping)
    }
    for bone in descriptor.get("bones", []) or []:
        if not isinstance(bone, Mapping):
            continue
        bone_id = str(bone.get("id") or "")
        if bone_id and bone_id not in out:
            out[bone_id] = bone
    return out


def _model_parent_map(descriptor: Mapping[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for model in descriptor.get("models", []) or []:
        if not isinstance(model, Mapping):
            continue
        model_id = str(model.get("id") or "")
        parent_id = str(model.get("parent_id") or "")
        if model_id and parent_id:
            out[model_id] = parent_id
    bones = [bone for bone in descriptor.get("bones", []) or [] if isinstance(bone, Mapping)]
    bone_id_by_index = {
        _int(bone.get("index"), -1): str(bone.get("id") or "")
        for bone in bones
        if str(bone.get("id") or "")
    }
    for bone in bones:
        bone_id = str(bone.get("id") or "")
        parent_id = str(bone.get("parent_id") or "")
        if not parent_id:
            parent_index = _int(bone.get("parent_index"), -1)
            parent_id = bone_id_by_index.get(parent_index, "")
        if bone_id and parent_id:
            out[bone_id] = parent_id
    return out


def _normalized_weight_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        joints = value.get("joints")
        weights = value.get("weights")
        if isinstance(joints, (list, tuple)) and isinstance(weights, (list, tuple)):
            rows: list[Mapping[str, Any]] = []
            for idx, joint in enumerate(joints):
                weight = weights[idx] if idx < len(weights) else 0.0
                rows.append({"bone_id": f"bone_{_int(joint, 0)}", "weight": weight})
            return rows
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _skin_weight_arrays(
    geometry: Mapping[str, Any],
    vertex_count: int,
    *,
    max_influences: int = 8,
):
    try:
        import numpy as np
    except Exception:
        return [], None, None
    cache_key = "_runtime_skin_weight_arrays_v1"
    if isinstance(geometry, dict):
        cache = geometry.get(cache_key)
        if isinstance(cache, dict) and cache.get("vertex_count") == vertex_count and cache.get("max_influences") == max_influences:
            return cache.get("joint_keys") or [], cache.get("joint_indices"), cache.get("weights")
    weights_raw = geometry.get("skin_weights")
    if not isinstance(weights_raw, list):
        return [], None, None

    joint_keys: list[str] = []
    joint_index_by_key: dict[str, int] = {}
    joint_indices = np.full((vertex_count, max_influences), -1, dtype=np.int32)
    weight_values = np.zeros((vertex_count, max_influences), dtype=np.float32)

    for vertex_index in range(min(vertex_count, len(weights_raw))):
        rows = _normalized_weight_rows(weights_raw[vertex_index])
        slot = 0
        for row in rows:
            if slot >= max_influences:
                break
            bone_id = str(row.get("bone_id") or row.get("model_id") or "")
            if not bone_id:
                continue
            try:
                weight = float(row.get("weight", 0.0) or 0.0)
            except Exception:
                weight = 0.0
            if weight <= 1.0e-8:
                continue
            if bone_id not in joint_index_by_key:
                joint_index_by_key[bone_id] = len(joint_keys)
                joint_keys.append(bone_id)
            joint_indices[vertex_index, slot] = joint_index_by_key[bone_id]
            weight_values[vertex_index, slot] = max(0.0, min(1.0, weight))
            slot += 1

    totals = weight_values.sum(axis=1, keepdims=True)
    valid = totals[:, 0] > 1.0e-8
    weight_values[valid] = weight_values[valid] / totals[valid]
    if isinstance(geometry, dict):
        geometry[cache_key] = {
            "vertex_count": vertex_count,
            "max_influences": max_influences,
            "joint_keys": joint_keys,
            "joint_indices": joint_indices,
            "weights": weight_values,
        }
    return joint_keys, joint_indices, weight_values


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
    base_q = _vec4(model.get("rotation_quat"), (0.0, 0.0, 0.0, 1.0))
    curves = model_curves_by_id.get(model_id) if animated else None
    if isinstance(curves, Mapping):
        q = _sample_quat(curves.get("rotation_quat"), local_ms, base_q)
        if not isinstance(curves.get("rotation_quat"), Mapping):
            q = _quat_from_euler_deg(*_sample_vec3(curves.get("rotation"), local_ms, base_r))
        return {
            "translation": _sample_vec3(curves.get("translation"), local_ms, base_t),
            "rotation": _sample_vec3(curves.get("rotation"), local_ms, base_r),
            "rotation_quat": q,
            "scale": _sample_vec3(curves.get("scale"), local_ms, base_s),
        }
    return {"translation": base_t, "rotation": base_r, "rotation_quat": base_q, "scale": base_s}


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
    local_q = list(local.get("rotation_quat") or _quat_from_euler_deg(local_r[0], local_r[1], local_r[2]))
    local_s = list(local["scale"])
    parent_id = str(parent_by_id.get(model_id) or "")
    if not parent_id or parent_id in stack:
        return {"translation": local_t, "rotation": local_r, "rotation_quat": local_q, "scale": local_s}
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
    parent_q = list(parent.get("rotation_quat") or _quat_from_euler_deg(parent_r[0], parent_r[1], parent_r[2]))
    scaled_t = (
        local_t[0] * parent_s[0],
        local_t[1] * parent_s[1],
        local_t[2] * parent_s[2],
    )
    rotated_t = _mat_mul_vec(_quat_to_mat3(parent_q), scaled_t)
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
        "rotation_quat": _quat_multiply(parent_q, local_q),
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
    bind_q = _vec4(bind_pose.get("rotation_quat"), tuple(_quat_from_euler_deg(bind_r[0], bind_r[1], bind_r[2])))
    anim_q = _vec4(anim_pose.get("rotation_quat"), tuple(_quat_from_euler_deg(anim_r[0], anim_r[1], anim_r[2])))
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
    if bind_pose.get("rotation_quat") is not None or anim_pose.get("rotation_quat") is not None:
        delta_q = _quat_multiply(anim_q, _quat_conjugate(bind_q))
        rotated = _mat_mul_vec(_quat_to_mat3(delta_q), local)
    else:
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


def _quat_multiply(left: Sequence[Any], right: Sequence[Any]) -> list[float]:
    ax, ay, az, aw = _normalize_quat(left)
    bx, by, bz, bw = _normalize_quat(right)
    return _normalize_quat([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def _quat_conjugate(value: Sequence[Any]) -> list[float]:
    x, y, z, w = _normalize_quat(value)
    return [-x, -y, -z, w]


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
