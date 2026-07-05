"""Text-friendly diagnostics for MMD model, motion, and material QA."""
from __future__ import annotations

from pathlib import Path
import math
import re
from typing import Any, Iterable

import numpy as np

from .animation import evaluate_model_pose
from .gpu_preview import MMD_RENDER_BUCKET_TRANSPARENT, MMD_RENDER_TOON, build_mmd_render_item
from .loader import load_mmd_model
from .physics import MMDPhysicsPoseDelta, NoPhysicsBackend, SpringPhysicsBackend
from .pmx import MMDModel
from .vmd import VMDBezier, VMDMotion, load_vmd, vmd_bezier_is_linear, vmd_bezier_max_linear_delta


_WEIGHT_TYPE_NAMES = {
    0: "bdef1",
    1: "bdef2",
    2: "bdef4",
    3: "sdef",
    4: "qdef",
}


def format_mmd_performance_line(diagnostics: dict[str, Any]) -> str:
    """Return a compact one-line preview performance summary."""
    diag = dict(diagnostics or {})
    refresh_ms = max(0.0, float(diag.get("preview_refresh_ms", 0.0) or 0.0))
    pose_ms = max(0.0, float(diag.get("preview_pose_ms", 0.0) or 0.0))
    build_ms = max(0.0, float(diag.get("preview_render_item_ms", 0.0) or 0.0))
    fps = max(0.0, float(diag.get("preview_estimated_fps", 0.0) or 0.0))
    cache_size = max(0, int(diag.get("pose_cache_size", 0) or 0))
    cache_limit = max(cache_size, int(diag.get("pose_cache_limit", 0) or 0))
    ik = max(0, int(diag.get("adaptive_ik_iterations", diag.get("active_ik_count", 0)) or 0))
    vbo_hits = max(0, int(diag.get("mmd_vbo_cache_hits", 0) or 0))
    vbo_misses = max(0, int(diag.get("mmd_vbo_cache_misses", 0) or 0))
    vbo_binds = max(0, int(diag.get("mmd_vbo_cache_binds", 0) or 0))
    vbo_label = ""
    if vbo_binds > 0:
        vbo_label = f"vbo {vbo_hits}/{vbo_hits + vbo_misses}"
    gpu_active = bool(diag.get("gpu_skinning", False) or diag.get("track_gpu_skinning_active", False))
    gpu_label = "GPU" if gpu_active else "CPU"
    reason = str(
        diag.get("gpu_skinning_fallback_reason")
        or diag.get("track_gpu_skinning_fallback_reason")
        or ""
    )
    if reason == "sdef_cpu_skinning_required":
        gpu_label = "CPU(SDEF)"
    physics_backend = str(
        diag.get("physics_backend")
        or diag.get("track_physics_backend")
        or ""
    )
    physics_label = ""
    if physics_backend:
        physics_label = f"phys {physics_backend}"
        if bool(diag.get("physics_backend_fallback") or diag.get("track_physics_backend_fallback")):
            physics_label += "*"
    if refresh_ms <= 0.0:
        return f"Perf -- | {gpu_label}"
    parts = [
        f"Perf {refresh_ms:.1f}ms {fps:.0f}fps",
        f"pose {pose_ms:.1f}ms",
        f"build {build_ms:.1f}ms",
        f"cache {cache_size}/{cache_limit}",
        f"IK {ik}",
        gpu_label,
    ]
    if vbo_label:
        parts.insert(-1, vbo_label)
    if physics_label:
        parts.insert(-1, physics_label)
    return " | ".join(parts)


def _weight_counts(model: MMDModel) -> dict[str, int]:
    weight_types = np.asarray(model.weights.weight_types, dtype=np.uint8)
    return {
        name: int(np.count_nonzero(weight_types == idx))
        for idx, name in _WEIGHT_TYPE_NAMES.items()
    }


def _weight_error_count(model: MMDModel) -> int:
    weights = np.asarray(model.weights.bone_weights, dtype=np.float32)
    sums = np.sum(np.maximum(weights, 0.0), axis=1)
    return int(np.count_nonzero(np.abs(sums - 1.0) > 0.01))


def _sample_frames(motion: VMDMotion | None, requested: Iterable[float] | None = None) -> list[float]:
    if requested is not None:
        out = [max(0.0, float(value)) for value in requested]
        return sorted(set(round(value, 4) for value in out)) or [0.0]
    if motion is None or motion.max_frame <= 0:
        return [0.0]
    end = float(max(1, motion.max_frame))
    return [0.0, end * 0.25, end * 0.5, end * 0.75, end]


def _is_front_hair_row(row: dict[str, Any]) -> bool:
    if str(row.get("material_class_name") or "") != "hair":
        return False
    blob = f"{row.get('name') or ''} {row.get('english_name') or ''}".casefold()
    compact = "".join(ch for ch in blob if not ch.isspace())
    if any(value in compact for value in ("fronthair", "innerhair", "insidehair")):
        return True
    tokens = set(re.findall(r"[a-z0-9]+", blob))
    if tokens.intersection({"bang", "bangs", "fringe"}):
        return True
    return any(value in compact for value in ("\u524d\u9aea", "\u524d\u9aee", "\u524d\u53d1", "\uc55e\uba38\ub9ac"))


def _material_alpha_policy(render_diag: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(row) for row in list(render_diag.get("material_bucket_rows") or []) if isinstance(row, dict)]
    material_alpha_rows: list[dict[str, Any]] = []
    risk_codes: list[str] = []
    uv_blend_count = 0
    uv_cutout_count = 0
    transparent_front_hair_count = 0
    for row in rows:
        render_bucket = int(row.get("render_bucket", 0) or 0)
        uv_mode = str(row.get("uv_alpha_mode") or "opaque")
        if uv_mode == "blend":
            uv_blend_count += 1
        elif uv_mode == "cutout":
            uv_cutout_count += 1
        if uv_mode != "opaque":
            material_alpha_rows.append(
                {
                    "material_index": int(row.get("material_index", 0) or 0),
                    "name": str(row.get("name") or ""),
                    "material_class_name": str(row.get("material_class_name") or ""),
                    "render_bucket_name": str(row.get("render_bucket_name") or ""),
                    "uv_alpha_mode": uv_mode,
                    "uv_alpha_mid_ratio": float(row.get("uv_alpha_mid_ratio", 0.0) or 0.0),
                    "uv_alpha_mean": float(row.get("uv_alpha_mean", 255.0)),
                    "draw_priority": int(row.get("draw_priority", 0) or 0),
                    "face_layer_priority": int(row.get("face_layer_priority", 0) or 0),
                }
            )
        if uv_mode == "blend" and render_bucket < MMD_RENDER_BUCKET_TRANSPARENT:
            risk_codes.append("mmd_uv_alpha_blend_not_transparent")
        if _is_front_hair_row(row) and render_bucket >= MMD_RENDER_BUCKET_TRANSPARENT:
            transparent_front_hair_count += 1
            if int(row.get("draw_priority", 0) or 0) < 70:
                risk_codes.append("mmd_front_hair_alpha_order_low")
    return {
        "uv_blend_group_count": int(uv_blend_count),
        "uv_cutout_group_count": int(uv_cutout_count),
        "transparent_front_hair_count": int(transparent_front_hair_count),
        "material_alpha_rows": material_alpha_rows,
        "risk_codes": sorted(set(risk_codes)),
    }


def _quat_angle_degrees(quat: tuple[float, float, float, float]) -> float:
    x, y, z, w = (float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3]))
    vec = math.sqrt(x * x + y * y + z * z)
    return math.degrees(2.0 * math.atan2(vec, abs(w)))


def _rest_globals_for_physics_probe(model: MMDModel) -> list[np.ndarray]:
    globals_: list[np.ndarray] = []
    for bone in model.bones:
        mat = np.eye(4, dtype=np.float32)
        mat[:3, 3] = np.asarray(bone.position, dtype=np.float32)
        globals_.append(mat)
    return globals_


def _physics_policy(model: MMDModel) -> dict[str, Any]:
    active_bodies = [
        body
        for body in model.rigid_bodies
        if int(getattr(body, "physics_mode", 0) or 0) in {1, 2}
        and 0 <= int(getattr(body, "bone_index", -1)) < len(model.bones)
    ]
    candidate_count = 0
    for body in active_bodies:
        bone = model.bones[int(body.bone_index)]
        if SpringPhysicsBackend._secondary_rotation_gain(body, bone) > 0.000001:
            candidate_count += 1

    probe_active_count = 0
    probe_translation_count = 0
    probe_rotation_count = 0
    max_translation = 0.0
    max_rotation_degrees = 0.0
    if active_bodies and model.bones:
        backend = SpringPhysicsBackend()
        rest_globals = _rest_globals_for_physics_probe(model)
        moved_globals = [np.array(mat, dtype=np.float32, copy=True) for mat in rest_globals]
        active_bone_indices = {int(body.bone_index) for body in active_bodies}
        for bone_idx in active_bone_indices:
            if 0 <= bone_idx < len(moved_globals):
                moved_globals[bone_idx][:3, 3] += np.asarray((0.0, 0.0, 0.35), dtype=np.float32)
        backend.offsets_for(model, rest_globals, 0.0)
        probe_delta = backend.offsets_for(model, moved_globals, 3.0)
        if isinstance(probe_delta, MMDPhysicsPoseDelta):
            offsets = probe_delta.translation_offsets
            rotations = probe_delta.rotation_offsets
            probe_active_count = int(probe_delta.active_count)
        else:
            offsets, probe_active_count = probe_delta
            rotations = {}
        probe_translation_count = int(len(offsets))
        probe_rotation_count = int(len(rotations))
        if offsets:
            max_translation = max(float(np.linalg.norm(np.asarray(value, dtype=np.float32))) for value in offsets.values())
        if rotations:
            max_rotation_degrees = max(_quat_angle_degrees(tuple(value)) for value in rotations.values())

    risk_codes: list[str] = []
    if active_bodies and probe_active_count <= 0:
        risk_codes.append("mmd_physics_probe_no_active_bodies")
    if candidate_count > 0 and probe_rotation_count <= 0:
        risk_codes.append("mmd_physics_secondary_rotation_missing")
    if candidate_count > 0 and max_rotation_degrees < 0.05:
        risk_codes.append("mmd_physics_secondary_rotation_too_small")

    return {
        "active_rigid_body_count": int(len(active_bodies)),
        "joint_count": int(len(model.joints)),
        "secondary_candidate_count": int(candidate_count),
        "probe_active_count": int(probe_active_count),
        "probe_translation_bone_count": int(probe_translation_count),
        "probe_rotation_bone_count": int(probe_rotation_count),
        "probe_max_translation_offset": float(max_translation),
        "probe_max_rotation_degrees": float(max_rotation_degrees),
        "spring_response": float(SpringPhysicsBackend().spring_response),
        "secondary_rotation_scale": float(SpringPhysicsBackend().secondary_rotation_scale),
        "risk_codes": sorted(set(risk_codes)),
    }


def _motion_curves(motion: VMDMotion | None) -> list[VMDBezier]:
    if motion is None:
        return []
    curves: list[VMDBezier] = []
    for frames in motion.bone_frames.values():
        for frame in frames[1:]:
            curves.extend((frame.interpolation.x, frame.interpolation.y, frame.interpolation.z, frame.interpolation.rotation))
    for frame in motion.camera_frames[1:]:
        curves.extend(
            (
                frame.interpolation.x,
                frame.interpolation.y,
                frame.interpolation.z,
                frame.interpolation.rotation,
                frame.interpolation.distance,
                frame.interpolation.fov,
            )
        )
    return curves


def _motion_policy(motion: VMDMotion | None) -> dict[str, Any]:
    curves = _motion_curves(motion)
    nonlinear = [curve for curve in curves if not vmd_bezier_is_linear(curve)]
    max_delta = max((vmd_bezier_max_linear_delta(curve) for curve in nonlinear), default=0.0)
    return {
        "curve_count": int(len(curves)),
        "nonlinear_curve_count": int(len(nonlinear)),
        "max_linear_delta": float(max_delta),
        "bone_track_count": int(len(motion.bone_frames)) if motion is not None else 0,
        "morph_track_count": int(len(motion.morph_frames)) if motion is not None else 0,
        "camera_frame_count": int(len(motion.camera_frames)) if motion is not None else 0,
    }


def analyze_mmd_model(
    model_or_path: MMDModel | str | Path,
    motion_or_path: VMDMotion | str | Path | None = None,
    *,
    sample_frames: Iterable[float] | None = None,
) -> dict[str, Any]:
    """Return a deterministic diagnostics dict suitable for CLI text output."""
    model = model_or_path if isinstance(model_or_path, MMDModel) else load_mmd_model(model_or_path)
    motion = motion_or_path if isinstance(motion_or_path, VMDMotion) or motion_or_path is None else load_vmd(motion_or_path)
    frames = _sample_frames(motion, sample_frames)
    weights = _weight_counts(model)
    item = build_mmd_render_item(model, render_mode=MMD_RENDER_TOON)
    render_diag = dict(item.get("diagnostics") or {})
    alpha_policy = _material_alpha_policy(render_diag)
    physics_policy = _physics_policy(model)
    motion_policy = _motion_policy(motion)

    no_physics = NoPhysicsBackend()
    spring = SpringPhysicsBackend()
    base_positions = np.asarray(model.positions, dtype=np.float32)
    samples: list[dict[str, Any]] = []
    max_pose_delta = 0.0
    max_physics_delta = 0.0
    max_active_bones = 0
    max_active_ik = 0
    max_active_sdef = 0
    max_physics_bodies = 0
    for frame in frames:
        pose = evaluate_model_pose(model, motion, frame, physics_backend=no_physics)
        physics_pose = evaluate_model_pose(model, motion, frame, physics_backend=spring)
        pose_delta = float(np.max(np.abs(np.asarray(pose.positions) - base_positions))) if base_positions.size else 0.0
        physics_delta = (
            float(np.max(np.abs(np.asarray(physics_pose.positions) - np.asarray(pose.positions))))
            if base_positions.size
            else 0.0
        )
        max_pose_delta = max(max_pose_delta, pose_delta)
        max_physics_delta = max(max_physics_delta, physics_delta)
        max_active_bones = max(max_active_bones, int(pose.active_bone_count))
        max_active_ik = max(max_active_ik, int(pose.active_ik_count))
        max_active_sdef = max(max_active_sdef, int(pose.active_sdef_count))
        max_physics_bodies = max(max_physics_bodies, int(physics_pose.physics_body_count))
        samples.append(
            {
                "frame": float(frame),
                "pose_delta": pose_delta,
                "physics_delta": physics_delta,
                "active_bones": int(pose.active_bone_count),
                "active_ik": int(pose.active_ik_count),
                "active_sdef": int(pose.active_sdef_count),
                "physics_bodies": int(physics_pose.physics_body_count),
            }
        )

    feature_flags: list[str] = []
    risk_codes: list[str] = []
    if weights["sdef"] > 0:
        feature_flags.append("sdef_weights")
        feature_flags.append("sdef_cpu_skinning_required")
        if max_active_sdef <= 0:
            risk_codes.append("mmd_sdef_not_exercised")
    if weights["qdef"] > 0:
        feature_flags.append("qdef_weights")
        risk_codes.append("mmd_qdef_treated_as_bdef4")
    if int(render_diag.get("transparent_group_count", 0) or 0) > 0:
        feature_flags.append("transparent_materials")
        risk_codes.append("mmd_transparency_order_needs_visual_qa")
    if int(alpha_policy.get("uv_blend_group_count", 0) or 0) > 0:
        feature_flags.append("uv_alpha_gradients")
    if int(alpha_policy.get("transparent_front_hair_count", 0) or 0) > 0:
        feature_flags.append("transparent_front_hair")
    if int(render_diag.get("cutout_group_count", 0) or 0) > 0:
        feature_flags.append("cutout_alpha")
    if int(render_diag.get("sphere_texture_group_count", 0) or 0) > 0:
        feature_flags.append("sphere_textures")
    if int(render_diag.get("toon_texture_group_count", 0) or 0) > 0:
        feature_flags.append("toon_textures")
    if len(model.rigid_bodies) or len(model.joints):
        feature_flags.append("pmx_physics_data")
        risk_codes.append("mmd_lightweight_physics_backend")
    if int(physics_policy.get("probe_rotation_bone_count", 0) or 0) > 0:
        feature_flags.append("physics_secondary_rotation")
    if int(physics_policy.get("probe_translation_bone_count", 0) or 0) > 0:
        feature_flags.append("physics_probe_motion")
    if any(bone.ik is not None for bone in model.bones):
        feature_flags.append("ik_bones")
        if max_active_ik <= 0 and motion is not None:
            risk_codes.append("mmd_ik_not_exercised")
    if motion is None:
        risk_codes.append("mmd_no_motion_supplied")
    elif max_active_bones <= 0 and not motion.morph_frames:
        risk_codes.append("mmd_motion_no_matching_bones")
    elif max_pose_delta <= 0.001:
        risk_codes.append("mmd_low_motion_delta")
    if int(motion_policy.get("nonlinear_curve_count", 0) or 0) > 0:
        feature_flags.append("vmd_interpolation_curves")
    if int(render_diag.get("missing_texture_count", 0) or 0) > 0:
        risk_codes.append("mmd_missing_textures")
    risk_codes.extend(str(code) for code in list(alpha_policy.get("risk_codes") or []))
    risk_codes.extend(str(code) for code in list(physics_policy.get("risk_codes") or []))

    ok = not any(code in risk_codes for code in ("mmd_motion_no_matching_bones", "mmd_missing_textures"))
    return {
        "ok": bool(ok),
        "model": {
            "path": str(model.path),
            "name": model.name,
            "vertices": int(model.vertex_count),
            "triangles": int(model.triangle_count),
            "materials": int(len(model.materials)),
            "textures": int(len(model.textures)),
            "bones": int(len(model.bones)),
            "morphs": int(len(model.morphs)),
            "rigid_bodies": int(len(model.rigid_bodies)),
            "joints": int(len(model.joints)),
        },
        "motion": {
            "path": str(motion.path) if motion is not None else "",
            "max_frame": int(motion.max_frame) if motion is not None else 0,
            "bone_tracks": int(len(motion.bone_frames)) if motion is not None else 0,
            "morph_tracks": int(len(motion.morph_frames)) if motion is not None else 0,
            "camera_frames": int(len(motion.camera_frames)) if motion is not None else 0,
        },
        "weights": {
            **weights,
            "weight_error_count": _weight_error_count(model),
        },
        "render": render_diag,
        "alpha_policy": alpha_policy,
        "physics_policy": physics_policy,
        "motion_policy": motion_policy,
        "animation": {
            "sample_count": int(len(samples)),
            "max_pose_delta": max_pose_delta,
            "max_physics_delta": max_physics_delta,
            "max_active_bones": int(max_active_bones),
            "max_active_ik": int(max_active_ik),
            "max_active_sdef": int(max_active_sdef),
            "max_physics_bodies": int(max_physics_bodies),
            "samples": samples,
        },
        "feature_flags": sorted(set(feature_flags)),
        "risk_codes": sorted(set(risk_codes)),
    }


def format_mmd_report(reports: list[dict[str, Any]]) -> str:
    """Format diagnostics like the project's text-first QA commands."""
    ok = all(bool(report.get("ok")) for report in reports)
    lines = [
        f"ok            : {ok}",
        f"run_count     : {len(reports)}",
        "scope         : MMD model/material/animation diagnostics",
        "",
        (
            f"{'name':<10} {'verts':>7} {'tris':>7} {'mats':>5} {'bones':>5} "
            f"{'sdef':>6} {'qdef':>6} {'opaque':>6} {'cutout':>6} {'blend':>5} "
            f"{'uvblend':>7} {'fhairA':>6} {'sdefcpu':>7} {'physrot':>7} {'rotdeg':>7} {'vmdcurv':>7} "
            f"{'pose_delta':>11} {'phys_delta':>11} {'active_bones':>12} {'risks'}"
        ),
    ]
    lines.append("-" * len(lines[-1]))
    for report in reports:
        model = report.get("model") or {}
        weights = report.get("weights") or {}
        render = report.get("render") or {}
        alpha_policy = report.get("alpha_policy") or {}
        physics_policy = report.get("physics_policy") or {}
        motion_policy = report.get("motion_policy") or {}
        animation = report.get("animation") or {}
        name = str(model.get("name") or Path(str(model.get("path") or "")).stem or "model")[:10]
        risks = ",".join(report.get("risk_codes") or [])
        lines.append(
            f"{name:<10} "
            f"{int(model.get('vertices', 0)):>7} "
            f"{int(model.get('triangles', 0)):>7} "
            f"{int(model.get('materials', 0)):>5} "
            f"{int(model.get('bones', 0)):>5} "
            f"{int(weights.get('sdef', 0)):>6} "
            f"{int(weights.get('qdef', 0)):>6} "
            f"{int(render.get('opaque_group_count', 0)):>6} "
            f"{int(render.get('cutout_group_count', 0)):>6} "
            f"{int(render.get('transparent_group_count', 0)):>5} "
            f"{int(alpha_policy.get('uv_blend_group_count', 0)):>7} "
            f"{int(alpha_policy.get('transparent_front_hair_count', 0)):>6} "
            f"{1 if bool(render.get('sdef_cpu_skinning_required', False)) else 0:>7} "
            f"{int(physics_policy.get('probe_rotation_bone_count', 0)):>7} "
            f"{float(physics_policy.get('probe_max_rotation_degrees', 0.0)):>7.2f} "
            f"{int(motion_policy.get('nonlinear_curve_count', 0)):>7} "
            f"{float(animation.get('max_pose_delta', 0.0)):>11.4f} "
            f"{float(animation.get('max_physics_delta', 0.0)):>11.4f} "
            f"{int(animation.get('max_active_bones', 0)):>12} "
            f"{risks}"
        )
    return "\n".join(lines)
