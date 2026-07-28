"""Validation for Motion Designer documents."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

from .schema import AnimatedProperty, MotionComposition


VECTOR_BOOLEAN_OPERATIONS = {"union", "subtract", "intersect", "exclude", "xor"}
VECTOR_ANIMATED_PARAMS = {
    "path", "width", "height", "radius", "sides", "inner_ratio", "shape_rotation",
    "fill", "stroke", "stroke_width", "gradient", "stroke_gradient", "dash",
    "dash_offset", "stroke_taper", "trim", "offset_path", "repeater",
}
TYPOGRAPHY_ANIMATED_PARAMS = {
    "text", "font_family", "font_size", "font_weight", "font_axes", "fill",
    "stroke", "stroke_width", "letter_spacing", "line_height", "text_animation",
    "text_animators", "text_path", "text_path_offset",
}
AR_PBR_ANIMATED_GROUPS = {
    "object": {"position", "rotation", "scale"},
    "material": {"override_strength", "roughness", "metallic", "reflectance", "clearcoat", "clearcoat_roughness"},
    "render": {
        "ibl_exposure", "ibl_rotation", "shadow_strength", "self_shadow_strength",
        "shadow_pcf_radius", "ao_strength", "bloom_strength", "depth_of_field_strength",
    },
}
CAMERA_ANIMATED_PARAMS = {"position", "rotation", "target", "fov", "focus_distance", "focus_range"}
LIGHT_ANIMATED_PARAMS = {"azimuth", "elevation", "color", "intensity", "enabled"}
ACTOR_ANIMATED_PARAMS = {"position", "scale", "opacity"}
MMD_ANIMATED_GROUPS = {
    "view": {"yaw", "pitch", "roll", "zoom", "offset_x", "offset_y"},
    "lighting": {"key_intensity", "fill_intensity", "rim_intensity", "ambient_intensity", "shadow_strength"},
    "material": {"skin_warmth", "hair_highlight", "eye_highlight", "lip_specular", "matcap_specular", "emissive"},
}
VRM_ANIMATED_GROUPS = {
    "pose": {
        "yaw_deg", "pitch_deg", "roll_deg", "shoulder_roll_deg",
        "mouth_open", "blink_l", "blink_r", "idle_strength",
    },
    "placement": {"target_width_ratio", "target_height_ratio", "output_center_x", "output_bottom_y"},
    "lighting": {"light_azimuth", "light_elevation", "direct_strength", "ibl_exposure", "shadow_strength"},
}


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str = ""
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path, "severity": self.severity}


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "issues": [issue.to_dict() for issue in self.issues]}


def _default_value(value: Any) -> Any:
    if isinstance(value, Mapping) and ("default" in value or "keyframes" in value):
        return value.get("default")
    return value


def _valid_point(value: Any) -> bool:
    return (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        and len(value) >= 2
        and all(isinstance(item, (int, float)) and isfinite(float(item)) for item in value[:2])
    )


def _validate_vector_path(data: Any, path: str, issues: list[ValidationIssue], *, closed_minimum: int = 2) -> None:
    if not isinstance(data, Mapping):
        issues.append(ValidationIssue("invalid_vector_path", "Vector path must be an object.", path))
        return
    points = data.get("points")
    minimum = 3 if bool(data.get("closed", True)) else closed_minimum
    if not isinstance(points, list) or len(points) < minimum:
        issues.append(ValidationIssue(
            "invalid_vector_path", f"Vector path requires at least {minimum} points.", f"{path}.points",
        ))
        return
    for index, point in enumerate(points):
        point_path = f"{path}.points[{index}]"
        if not isinstance(point, Mapping) or not _valid_point(point.get("position")):
            issues.append(ValidationIssue("invalid_vector_point", "Vector point position must be finite x/y.", point_path))
            continue
        for tangent in ("in", "out"):
            if tangent in point and not _valid_point(point.get(tangent)):
                issues.append(ValidationIssue(
                    "invalid_vector_tangent", "Vector tangent must be finite x/y.", f"{point_path}.{tangent}",
                ))


def _validate_vector_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type != "shape":
        return
    params = layer.source.params
    shape = str(_default_value(params.get("shape", "rectangle")) or "rectangle").lower()
    if shape not in {"rectangle", "ellipse", "polygon", "star", "path"}:
        issues.append(ValidationIssue("invalid_vector_primitive", f"Unsupported vector primitive: {shape}", f"{path}.source.params.shape"))
    if "path" in params:
        _validate_vector_path(_default_value(params.get("path")), f"{path}.source.params.path", issues)
        animated_path = params.get("path")
        if isinstance(animated_path, Mapping) and "keyframes" in animated_path:
            from .path_morph import path_topology_signature

            morph_paths = [animated_path.get("default")]
            morph_paths.extend(
                keyframe.get("value")
                for keyframe in animated_path.get("keyframes", [])
                if isinstance(keyframe, Mapping)
            )
            signatures = [
                path_topology_signature(value)
                for value in morph_paths
                if isinstance(value, Mapping)
            ]
            if signatures and any(
                signature != signatures[0] for signature in signatures[1:]
            ):
                issues.append(ValidationIssue(
                    "path_morph_topology_mismatch",
                    "Path Morph keyframes must share point count, closure, and fill rule.",
                    f"{path}.source.params.path.keyframes",
                ))
    path_morph = layer.metadata.get("path_morph")
    if path_morph is not None:
        from .path_morph import PATH_MORPH_CONTRACT

        if (
            not isinstance(path_morph, Mapping)
            or path_morph.get("contract") != PATH_MORPH_CONTRACT
        ):
            issues.append(ValidationIssue(
                "invalid_path_morph_contract",
                "Path Morph metadata uses an unsupported contract.",
                f"{path}.metadata.path_morph",
            ))
    if shape in {"polygon", "star"}:
        sides = _default_value(params.get("sides", 5))
        if not isinstance(sides, (int, float)) or not 3 <= int(sides) <= 128:
            issues.append(ValidationIssue("invalid_vector_sides", "Polygon/star sides must be between 3 and 128.", f"{path}.source.params.sides"))
    boolean = _default_value(params.get("boolean"))
    if boolean is not None:
        if not isinstance(boolean, Mapping):
            issues.append(ValidationIssue("invalid_vector_boolean", "Vector Boolean must be an object.", f"{path}.source.params.boolean"))
        else:
            operation = str(boolean.get("operation") or "union").lower()
            if operation not in VECTOR_BOOLEAN_OPERATIONS:
                issues.append(ValidationIssue("invalid_vector_boolean", f"Unsupported Boolean operation: {operation}", f"{path}.source.params.boolean.operation"))
            for index, item in enumerate(boolean.get("paths", [])):
                _validate_vector_path(item, f"{path}.source.params.boolean.paths[{index}]", issues, closed_minimum=3)
    trim = _default_value(params.get("trim"))
    if trim is not None:
        if not isinstance(trim, Mapping):
            issues.append(ValidationIssue("invalid_vector_trim", "Vector trim must be an object.", f"{path}.source.params.trim"))
        else:
            for key, default in (("start", 0.0), ("end", 1.0)):
                value = trim.get(key, default)
                if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                    issues.append(ValidationIssue("invalid_vector_trim", f"Trim {key} must be between 0 and 1.", f"{path}.source.params.trim.{key}"))
    offset_path = _default_value(params.get("offset_path"))
    if offset_path is not None:
        if not isinstance(offset_path, Mapping):
            issues.append(ValidationIssue(
                "invalid_offset_path",
                "Offset Paths settings must be an object.",
                f"{path}.source.params.offset_path",
            ))
        else:
            amount = offset_path.get("amount", 0.0)
            join = str(offset_path.get("join") or "round")
            if not isinstance(amount, (int, float)) or not isfinite(float(amount)):
                issues.append(ValidationIssue(
                    "invalid_offset_path",
                    "Offset Paths amount must be finite.",
                    f"{path}.source.params.offset_path.amount",
                ))
            if join not in {"round", "miter", "bevel"}:
                issues.append(ValidationIssue(
                    "invalid_offset_path",
                    "Offset Paths join must be round, miter, or bevel.",
                    f"{path}.source.params.offset_path.join",
                ))
    taper = _default_value(params.get("stroke_taper"))
    if taper is not None:
        if not isinstance(taper, Mapping):
            issues.append(ValidationIssue(
                "invalid_stroke_taper",
                "Stroke taper must be an object.",
                f"{path}.source.params.stroke_taper",
            ))
        else:
            for name in ("start", "end"):
                value = taper.get(name, 1.0)
                if (
                    not isinstance(value, (int, float))
                    or not isfinite(float(value))
                    or float(value) < 0.0
                ):
                    issues.append(ValidationIssue(
                        "invalid_stroke_taper",
                        "Stroke taper factors must be finite and non-negative.",
                        f"{path}.source.params.stroke_taper.{name}",
                    ))
            profile = taper.get("profile")
            if profile is not None and (
                not isinstance(profile, list)
                or any(
                    not isinstance(value, (int, float)) or float(value) < 0.0
                    for value in profile
                )
            ):
                issues.append(ValidationIssue(
                    "invalid_stroke_taper",
                    "Variable-width stroke profile must contain non-negative numbers.",
                    f"{path}.source.params.stroke_taper.profile",
                ))
    repeater = _default_value(params.get("repeater"))
    if repeater is not None:
        count = repeater.get("count", 1) if isinstance(repeater, Mapping) else None
        if not isinstance(count, (int, float)) or not 1 <= int(count) <= 512:
            issues.append(ValidationIssue("invalid_vector_repeater", "Repeater count must be between 1 and 512.", f"{path}.source.params.repeater.count"))
    for name in VECTOR_ANIMATED_PARAMS:
        value = params.get(name)
        if not isinstance(value, Mapping) or not ("default" in value or "keyframes" in value):
            continue
        prop = AnimatedProperty.from_dict(value)
        key_path = f"{path}.source.params.{name}"
        times = [key.time_ms for key in prop.keyframes]
        if times != sorted(times):
            issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
        key_ids = [key.id for key in prop.keyframes]
        if len(key_ids) != len(set(key_ids)):
            issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))


def _validate_typography_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type != "text":
        return
    from app.typo_animations import REGISTRY

    params = layer.source.params
    font_size = _default_value(params.get("font_size", 72))
    if not isinstance(font_size, (int, float)) or float(font_size) <= 0:
        issues.append(ValidationIssue(
            "invalid_typography_font_size", "Typography font size must be positive.",
            f"{path}.source.params.font_size",
        ))
    axes = _default_value(params.get("font_axes", {}))
    if axes is not None and not isinstance(axes, Mapping):
        issues.append(ValidationIssue(
            "invalid_typography_axes", "Variable font axes must be an object.",
            f"{path}.source.params.font_axes",
        ))
    elif isinstance(axes, Mapping):
        for name, value in axes.items():
            if len(str(name)) != 4 or not isinstance(value, (int, float)) or not isfinite(float(value)):
                issues.append(ValidationIssue(
                    "invalid_typography_axis", "Variable font axis tags require four characters and a finite value.",
                    f"{path}.source.params.font_axes.{name}",
                ))
    text_path = _default_value(params.get("text_path"))
    if text_path is not None:
        _validate_vector_path(text_path, f"{path}.source.params.text_path", issues, closed_minimum=2)
    animation = _default_value(params.get("text_animation", {}))
    if animation is not None and not isinstance(animation, Mapping):
        issues.append(ValidationIssue(
            "invalid_typography_animation", "Typography animation must be an object.",
            f"{path}.source.params.text_animation",
        ))
    elif isinstance(animation, Mapping):
        for phase in ("in", "hold", "out"):
            animation_id = str(animation.get(phase) or "none")
            if animation_id not in REGISTRY:
                issues.append(ValidationIssue(
                    "invalid_typography_animation", f"Unknown typography animation: {animation_id}",
                    f"{path}.source.params.text_animation.{phase}",
                ))
        unit = str(animation.get("unit") or "character")
        if unit not in {"character", "word", "line"}:
            issues.append(ValidationIssue(
                "invalid_typography_selector", f"Unsupported typography selector unit: {unit}",
                f"{path}.source.params.text_animation.unit",
            ))
        start = animation.get("selector_start", 0.0)
        end = animation.get("selector_end", 1.0)
        if not all(isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in (start, end)) or float(start) > float(end):
            issues.append(ValidationIssue(
                "invalid_typography_selector", "Typography selector range must satisfy 0 <= start <= end <= 1.",
                f"{path}.source.params.text_animation",
            ))
        for name in ("in_duration_ms", "out_duration_ms", "stagger_ms"):
            value = animation.get(name, 0)
            if not isinstance(value, (int, float)) or float(value) < 0:
                issues.append(ValidationIssue(
                    "invalid_typography_timing", f"Typography {name} must be non-negative.",
                    f"{path}.source.params.text_animation.{name}",
                ))
    animators = _default_value(params.get("text_animators"))
    animator_path = f"{path}.source.params.text_animators"
    if animators is not None and not isinstance(animators, list):
        issues.append(ValidationIssue(
            "invalid_text_animator_stack",
            "Text Animator stack must be an array.",
            animator_path,
        ))
    elif isinstance(animators, list):
        if len(animators) > 32:
            issues.append(ValidationIssue(
                "invalid_text_animator_stack",
                "Text Animator stack is limited to 32 entries.",
                animator_path,
            ))
        ids: set[str] = set()
        for index, animator in enumerate(animators):
            item_path = f"{animator_path}[{index}]"
            if not isinstance(animator, Mapping):
                issues.append(ValidationIssue(
                    "invalid_text_animator",
                    "Each Text Animator must be an object.",
                    item_path,
                ))
                continue
            animator_id = str(animator.get("id") or "")
            if animator_id and animator_id in ids:
                issues.append(ValidationIssue(
                    "duplicate_text_animator_id",
                    "Text Animator ids must be unique.",
                    f"{item_path}.id",
                ))
            ids.add(animator_id)
            unit = str(animator.get("unit") or "character")
            if unit not in {"character", "word", "line"}:
                issues.append(ValidationIssue(
                    "invalid_typography_selector",
                    f"Unsupported typography selector unit: {unit}",
                    f"{item_path}.unit",
                ))
            start = animator.get("selector_start", 0.0)
            end = animator.get("selector_end", 1.0)
            if not all(
                isinstance(value, (int, float)) and 0.0 <= float(value) <= 1.0
                for value in (start, end)
            ) or float(start) > float(end):
                issues.append(ValidationIssue(
                    "invalid_typography_selector",
                    "Text Animator range must satisfy 0 <= start <= end <= 1.",
                    item_path,
                ))
            smoothness = animator.get("smoothness", 0.0)
            if not isinstance(smoothness, (int, float)) or not 0.0 <= float(smoothness) <= 1.0:
                issues.append(ValidationIssue(
                    "invalid_typography_selector",
                    "Text Animator smoothness must be between 0 and 1.",
                    f"{item_path}.smoothness",
                ))
            selector_shape = str(animator.get("selector_shape") or "square")
            if selector_shape not in {
                "square", "ramp_up", "ramp_down", "triangle", "round",
            }:
                issues.append(ValidationIssue(
                    "invalid_typography_selector",
                    f"Unsupported Text Animator selector shape: {selector_shape}",
                    f"{item_path}.selector_shape",
                ))
    for name in TYPOGRAPHY_ANIMATED_PARAMS:
        value = params.get(name)
        if not isinstance(value, Mapping) or not ("default" in value or "keyframes" in value):
            continue
        prop = AnimatedProperty.from_dict(value)
        key_path = f"{path}.source.params.{name}"
        times = [key.time_ms for key in prop.keyframes]
        if times != sorted(times):
            issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
        key_ids = [key.id for key in prop.keyframes]
        if len(key_ids) != len(set(key_ids)):
            issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))


def _validate_animated_source_param(value: Any, path: str, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, Mapping) or not ({"default", "keyframes"} & set(value)):
        return
    prop = AnimatedProperty.from_dict(value)
    times = [key.time_ms for key in prop.keyframes]
    if times != sorted(times):
        issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", path))
    ids = [key.id for key in prop.keyframes]
    if len(ids) != len(set(ids)):
        issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", path))


def _validate_ar_pbr_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type == "ar_pbr":
        from app.ar_pbr.schema import is_supported_asset_path

        if not layer.source.uri:
            issues.append(ValidationIssue("missing_ar_pbr_asset", "AR/PBR layer requires an asset path.", f"{path}.source.uri"))
        elif not is_supported_asset_path(layer.source.uri):
            issues.append(ValidationIssue("unsupported_ar_pbr_asset", "AR/PBR layer asset format is unsupported.", f"{path}.source.uri"))
        for group_name, names in AR_PBR_ANIMATED_GROUPS.items():
            group = layer.source.params.get(group_name)
            if not isinstance(group, Mapping):
                issues.append(ValidationIssue("invalid_ar_pbr_group", f"AR/PBR {group_name} must be an object.", f"{path}.source.params.{group_name}"))
                continue
            for name in names:
                _validate_animated_source_param(group.get(name), f"{path}.source.params.{group_name}.{name}", issues)
    elif layer.layer_type == "camera":
        for name in CAMERA_ANIMATED_PARAMS:
            _validate_animated_source_param(layer.source.params.get(name), f"{path}.source.params.{name}", issues)
    elif layer.layer_type == "light":
        for name in LIGHT_ANIMATED_PARAMS:
            _validate_animated_source_param(layer.source.params.get(name), f"{path}.source.params.{name}", issues)


def _validate_actor_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    from app.motion_designer.actor_source import ACTOR_SOURCE_KINDS, LIVE2D_SOURCE_KIND

    if layer.layer_type not in ACTOR_SOURCE_KINDS:
        return
    if not layer.source.uri:
        issues.append(ValidationIssue("missing_actor_asset", "Actor layer requires an asset path.", f"{path}.source.uri"))
        return
    try:
        from pathlib import Path
        from app.actor_compat_repair import repair_actor_model_path

        source = Path(layer.source.uri)
        if not source.exists():
            issues.append(ValidationIssue("missing_actor_asset", "Actor asset does not exist.", f"{path}.source.uri"))
            return
        repair_kind = "live2d" if layer.layer_type == LIVE2D_SOURCE_KIND else "spine"
        repair = repair_actor_model_path(repair_kind, str(source))
        warnings = [str(value).lower() for value in repair.get("warnings", []) or []]
        if not repair.get("ok") or any("unsupported" in value or "invalid or missing" in value for value in warnings):
            issues.append(ValidationIssue("unsupported_actor_asset", "Actor asset cannot be loaded by the current runtime.", f"{path}.source.uri"))
        if repair_kind == "spine" and not str((repair.get("metadata") or {}).get("atlas_path") or ""):
            issues.append(ValidationIssue("missing_spine_atlas", "Spine actor requires a matching atlas file.", f"{path}.source.params.asset.atlas_path"))
    except Exception as exc:
        issues.append(ValidationIssue("actor_probe_failed", f"Actor compatibility check failed: {exc}", f"{path}.source.uri"))
    actor = layer.source.params.get("actor")
    if not isinstance(actor, Mapping):
        issues.append(ValidationIssue("invalid_actor_group", "Actor controls must be an object.", f"{path}.source.params.actor"))
    else:
        for name in ACTOR_ANIMATED_PARAMS:
            _validate_animated_source_param(actor.get(name), f"{path}.source.params.actor.{name}", issues)
    playback = layer.source.params.get("playback")
    if not isinstance(playback, Mapping):
        issues.append(ValidationIssue("invalid_actor_playback", "Actor playback controls must be an object.", f"{path}.source.params.playback"))
    else:
        _validate_animated_source_param(playback.get("rate"), f"{path}.source.params.playback.rate", issues)


def _validate_mmd_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    from pathlib import Path

    from app.mmd.schema import is_supported_model_path, is_supported_motion_path
    from app.motion_designer.mmd_source import MMD_SOURCE_KIND

    if layer.layer_type != MMD_SOURCE_KIND and layer.source.kind != MMD_SOURCE_KIND:
        return
    params = layer.source.params
    asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
    model_path = str(asset.get("model_path") or layer.source.uri or "")
    motion_path = str(asset.get("motion_path") or "")
    if not model_path:
        issues.append(ValidationIssue("missing_mmd_model", "MMD layer requires a model path.", f"{path}.source.uri"))
    elif not is_supported_model_path(model_path):
        issues.append(ValidationIssue("unsupported_mmd_model", "MMD model must be PMX, PMD, or PBX.", f"{path}.source.uri"))
    elif not Path(model_path).is_file():
        issues.append(ValidationIssue("missing_mmd_model", "MMD model does not exist.", f"{path}.source.uri"))
    if motion_path:
        if not is_supported_motion_path(motion_path):
            issues.append(ValidationIssue("unsupported_mmd_motion", "MMD motion must be VMD.", f"{path}.source.params.asset.motion_path"))
        elif not Path(motion_path).is_file():
            issues.append(ValidationIssue("missing_mmd_motion", "MMD motion does not exist.", f"{path}.source.params.asset.motion_path"))
    else:
        issues.append(ValidationIssue(
            "mmd_static_pose", "No VMD motion is assigned; the MMD layer renders its static model pose.",
            f"{path}.source.params.asset.motion_path", severity="warning",
        ))
    catalog = params.get("catalog") if isinstance(params.get("catalog"), Mapping) else {}
    model_info = catalog.get("model") if isinstance(catalog.get("model"), Mapping) else {}
    motion_info = catalog.get("motion") if isinstance(catalog.get("motion"), Mapping) else {}
    if motion_path and int(motion_info.get("camera_frames", 0) or 0) <= 0:
        issues.append(ValidationIssue(
            "mmd_auto_frame_camera_fallback",
            "The VMD has no camera frames; model bounds auto-framing is used.",
            f"{path}.source.params.playback.use_vmd_camera", severity="info",
        ))
    if int(model_info.get("sdef_vertices", 0) or 0) > 0:
        issues.append(ValidationIssue(
            "mmd_sdef_precision_path",
            "SDEF vertices use the precision CPU deformation path while compatible vertices remain GPU skinned.",
            f"{path}.source.params.playback.gpu_skinning", severity="info",
        ))
    view = params.get("view")
    render = params.get("render")
    playback = params.get("playback")
    if not isinstance(view, Mapping):
        issues.append(ValidationIssue("invalid_mmd_view", "MMD view controls must be an object.", f"{path}.source.params.view"))
    else:
        for name in MMD_ANIMATED_GROUPS["view"]:
            _validate_animated_source_param(view.get(name), f"{path}.source.params.view.{name}", issues)
    if not isinstance(render, Mapping):
        issues.append(ValidationIssue("invalid_mmd_render", "MMD render controls must be an object.", f"{path}.source.params.render"))
    else:
        _validate_animated_source_param(render.get("bloom_strength"), f"{path}.source.params.render.bloom_strength", issues)
        for group_name in ("lighting", "material"):
            group = render.get(group_name)
            if not isinstance(group, Mapping):
                issues.append(ValidationIssue(
                    "invalid_mmd_render_group", f"MMD {group_name} controls must be an object.",
                    f"{path}.source.params.render.{group_name}",
                ))
                continue
            for name in MMD_ANIMATED_GROUPS[group_name]:
                _validate_animated_source_param(
                    group.get(name), f"{path}.source.params.render.{group_name}.{name}", issues,
                )
    if not isinstance(playback, Mapping):
        issues.append(ValidationIssue("invalid_mmd_playback", "MMD playback controls must be an object.", f"{path}.source.params.playback"))
    else:
        _validate_animated_source_param(playback.get("rate"), f"{path}.source.params.playback.rate", issues)


def _validate_vrm_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    from pathlib import Path

    from app.motion_designer.vrm_source import VRM_SOURCE_KIND
    from app.vtuber.source_framing import vrm_visibility_policy_for_source_exposure
    from app.vtuber.vrm_profile import inspect_vrm_profile
    from app.vtuber.vrm_renderer import VRM_RENDERER_GPU

    if layer.layer_type != VRM_SOURCE_KIND and layer.source.kind != VRM_SOURCE_KIND:
        return
    params = layer.source.params
    asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
    avatar_path = str(asset.get("avatar_vrm") or layer.source.uri or "")
    if not avatar_path:
        issues.append(ValidationIssue("missing_vrm_avatar", "VRM layer requires an avatar path.", f"{path}.source.uri"))
    elif Path(avatar_path).suffix.casefold() != ".vrm":
        issues.append(ValidationIssue("unsupported_vrm_avatar", "VRM avatar must use the .vrm format.", f"{path}.source.uri"))
    elif not Path(avatar_path).is_file():
        issues.append(ValidationIssue("missing_vrm_avatar", "VRM avatar does not exist.", f"{path}.source.uri"))
    else:
        profile = inspect_vrm_profile(avatar_path)
        if not profile.get("ok"):
            issues.append(ValidationIssue(
                "invalid_vrm_profile", "VRM profile metadata could not be parsed.", f"{path}.source.uri",
            ))
        elif str(profile.get("profile") or "") == "VRM1":
            issues.append(ValidationIssue(
                "vrm1_internal_only", "VRM1 is available to the internal renderer but not the optional VSeeFace bridge.",
                f"{path}.source.uri", severity="info",
            ))
    render = params.get("render") if isinstance(params.get("render"), Mapping) else {}
    if str(render.get("renderer") or VRM_RENDERER_GPU) != VRM_RENDERER_GPU:
        issues.append(ValidationIssue(
            "invalid_vrm_renderer", "Motion VRM layers must use vrm_mtoon_gpu; software and generic PBR routes are disabled.",
            f"{path}.source.params.render.renderer",
        ))
    for group_name, names in VRM_ANIMATED_GROUPS.items():
        group = params.get(group_name)
        if not isinstance(group, Mapping):
            issues.append(ValidationIssue(
                "invalid_vrm_group", f"VRM {group_name} controls must be an object.",
                f"{path}.source.params.{group_name}",
            ))
            continue
        for name in names:
            _validate_animated_source_param(group.get(name), f"{path}.source.params.{group_name}.{name}", issues)
    placement = params.get("placement") if isinstance(params.get("placement"), Mapping) else {}
    policy = vrm_visibility_policy_for_source_exposure(
        placement.get("source_exposure"),
        requested_preset=str(placement.get("framing_preset") or "auto"),
        allow_narrower=bool(placement.get("allow_narrower_than_source", False)),
    )
    if policy.get("upgraded_from_requested"):
        issues.append(ValidationIssue(
            "vrm_framing_upgraded_to_source_visibility",
            str(policy.get("reason") or "VRM framing is widened to match source visibility."),
            f"{path}.source.params.placement.framing_preset", severity="info",
        ))
    playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
    _validate_animated_source_param(playback.get("rate"), f"{path}.source.params.playback.rate", issues)


def _validate_particle_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    from pathlib import Path

    from .particles import (
        EMITTER_KINDS, MAX_PARTICLES_HARD_LIMIT, PARTICLE_BLEND_MODES, PARTICLE_SHAPES,
        PARTICLE_SOURCE_KIND,
    )

    if layer.layer_type != PARTICLE_SOURCE_KIND and layer.source.kind != PARTICLE_SOURCE_KIND:
        return
    params = layer.source.params
    emitter = _default_value(params.get("emitter", {}))
    if not isinstance(emitter, Mapping):
        issues.append(ValidationIssue("invalid_particle_emitter", "Particle emitter must be an object.", f"{path}.source.params.emitter"))
    elif str(emitter.get("kind") or "point").lower() not in EMITTER_KINDS:
        issues.append(ValidationIssue("invalid_particle_emitter", "Particle emitter kind must be point, box, circle, or path.", f"{path}.source.params.emitter.kind"))
    maximum = _default_value(params.get("max_particles", 2000))
    if not isinstance(maximum, (int, float)) or not 0 <= int(maximum) <= MAX_PARTICLES_HARD_LIMIT:
        issues.append(ValidationIssue("invalid_particle_limit", f"Particle limit must be between 0 and {MAX_PARTICLES_HARD_LIMIT}.", f"{path}.source.params.max_particles"))
    lifetime = _default_value(params.get("lifetime_ms", 1000))
    if not isinstance(lifetime, (int, float)) or float(lifetime) <= 0:
        issues.append(ValidationIssue("invalid_particle_lifetime", "Particle lifetime must be positive.", f"{path}.source.params.lifetime_ms"))
    particle = _default_value(params.get("particle", {}))
    if not isinstance(particle, Mapping):
        issues.append(ValidationIssue("invalid_particle_appearance", "Particle appearance must be an object.", f"{path}.source.params.particle"))
    else:
        shape = str(particle.get("shape") or "circle").lower()
        if shape not in PARTICLE_SHAPES:
            issues.append(ValidationIssue("invalid_particle_shape", f"Unsupported particle shape: {shape}", f"{path}.source.params.particle.shape"))
        if shape == "sprite":
            sprite_uri = str(particle.get("sprite_uri") or "")
            if not sprite_uri or not Path(sprite_uri).is_file():
                issues.append(ValidationIssue("missing_particle_sprite", "Sprite particles require an existing image.", f"{path}.source.params.particle.sprite_uri"))
    if layer.blend_mode not in PARTICLE_BLEND_MODES:
        issues.append(ValidationIssue("invalid_particle_blend", "Particle blend mode must be normal, add, or screen.", f"{path}.blend_mode"))


def _validate_button_component(layer, path: str, issues: list[ValidationIssue]) -> None:
    raw = layer.metadata.get("interactive_component")
    if raw is None:
        return
    if not isinstance(raw, Mapping) or str(raw.get("type") or "") != "button":
        issues.append(ValidationIssue(
            "invalid_interactive_component",
            "Interactive component must be a button object.",
            f"{path}.metadata.interactive_component",
        ))
        return
    from .interactive_button import BUTTON_EASINGS, BUTTON_STATES

    active_state = str(raw.get("active_state") or "normal")
    if active_state not in BUTTON_STATES:
        issues.append(ValidationIssue(
            "invalid_button_state",
            "Button active state is unsupported.",
            f"{path}.metadata.interactive_component.active_state",
        ))
    transition = raw.get("transition")
    if isinstance(transition, Mapping):
        easing = str(transition.get("easing") or "ease_out")
        if easing not in BUTTON_EASINGS:
            issues.append(ValidationIssue(
                "invalid_button_easing",
                "Button transition easing is unsupported.",
                f"{path}.metadata.interactive_component.transition.easing",
            ))
    states = raw.get("states")
    if not isinstance(states, Mapping) or any(state not in states for state in BUTTON_STATES):
        issues.append(ValidationIssue(
            "invalid_button_states",
            "Button component must define every standard state.",
            f"{path}.metadata.interactive_component.states",
        ))


def _validate_generator_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type != "generator":
        return
    from .generators import GENERATOR_KINDS

    params = layer.source.params
    kind = str(params.get("kind") or "")
    if layer.source.kind != "generator" or kind not in GENERATOR_KINDS:
        issues.append(ValidationIssue(
            "invalid_generator_kind",
            f"Unsupported Motion generator: {kind or layer.source.kind}",
            f"{path}.source.params.kind",
        ))
    for key in ("width", "height"):
        try:
            value = int(params.get(key, 0) or 0)
        except (TypeError, ValueError):
            value = 0
        if not 1 <= value <= 16384:
            issues.append(ValidationIssue(
                "invalid_generator_size",
                "Generator dimensions must be between 1 and 16384.",
                f"{path}.source.params.{key}",
            ))
    try:
        scale = float(params.get("scale", 96.0) or 0.0)
    except (TypeError, ValueError):
        scale = 0.0
    if not 2.0 <= scale <= 4096.0:
        issues.append(ValidationIssue(
            "invalid_generator_scale",
            "Generator scale must be between 2 and 4096.",
            f"{path}.source.params.scale",
        ))


def _validate_rigs(composition: MotionComposition, issues: list[ValidationIssue]) -> None:
    from .rigging import (
        RIG_CONSTRAINT_TWO_BONE_IK,
        RIG_KIND_CUTOUT_2D,
        composition_rigs,
    )
    from .schema import AnimatedProperty

    rigs = composition_rigs(composition)
    rig_ids = [rig.id for rig in rigs]
    for rig_id in sorted({value for value in rig_ids if rig_ids.count(value) > 1}):
        issues.append(ValidationIssue(
            "duplicate_rig_id", f"Duplicate rig id: {rig_id}", "metadata.rigs",
        ))
    layer_ids = {layer.id for layer in composition.layers}
    for rig_index, rig in enumerate(rigs):
        path = f"metadata.rigs[{rig_index}]"
        if rig.kind != RIG_KIND_CUTOUT_2D:
            issues.append(ValidationIssue(
                "unsupported_rig_kind", f"Unsupported rig kind: {rig.kind}", f"{path}.kind",
            ))
        bone_ids = [bone.id for bone in rig.bones]
        bone_id_set = set(bone_ids)
        for bone_id in sorted({value for value in bone_ids if bone_ids.count(value) > 1}):
            issues.append(ValidationIssue(
                "duplicate_rig_bone_id", f"Duplicate rig bone id: {bone_id}", f"{path}.bones",
            ))
        if not rig.bones:
            issues.append(ValidationIssue(
                "empty_rig", "A motion rig requires at least one bone.", f"{path}.bones",
            ))
        if rig.root_bone_id not in bone_id_set:
            issues.append(ValidationIssue(
                "missing_rig_root", "Rig root_bone_id must reference a bone.", f"{path}.root_bone_id",
            ))
        parent_by_id = {bone.id: bone.parent_id for bone in rig.bones}
        for bone_index, bone in enumerate(rig.bones):
            bone_path = f"{path}.bones[{bone_index}]"
            if bone.side not in {"left", "right", "center"}:
                issues.append(ValidationIssue(
                    "invalid_rig_bone_side",
                    "Rig bone side must be left, right, or center.",
                    f"{bone_path}.side",
                ))
            if bone.parent_id and bone.parent_id not in bone_id_set:
                issues.append(ValidationIssue(
                    "missing_rig_bone_parent",
                    f"Unknown rig bone parent: {bone.parent_id}",
                    f"{bone_path}.parent_id",
                ))
            if not all(isfinite(float(value)) for value in bone.rest_position):
                issues.append(ValidationIssue(
                    "invalid_rig_bone_position",
                    "Rig bone rest position must contain finite x/y values.",
                    f"{bone_path}.rest_position",
                ))
            if not all(isfinite(float(value)) for value in (
                bone.rest_rotation, bone.rotation_min, bone.rotation_max,
            )):
                issues.append(ValidationIssue(
                    "invalid_rig_bone_rotation",
                    "Rig bone rotation values must be finite.",
                    bone_path,
                ))
            elif bone.rotation_min > bone.rotation_max:
                issues.append(ValidationIssue(
                    "invalid_rig_bone_limit",
                    "Rig bone rotation_min must not exceed rotation_max.",
                    bone_path,
                ))
            for property_name, prop in (
                ("rotation", bone.rotation),
                ("translation", bone.translation),
            ):
                property_path = f"{bone_path}.{property_name}"
                times = [key.time_ms for key in prop.keyframes]
                if times != sorted(times):
                    issues.append(ValidationIssue(
                        "unsorted_rig_keyframes",
                        "Rig bone keyframes must be time sorted.",
                        property_path,
                    ))
                key_ids = [key.id for key in prop.keyframes]
                if len(key_ids) != len(set(key_ids)):
                    issues.append(ValidationIssue(
                        "duplicate_rig_keyframe_id",
                        "Rig bone keyframe ids must be unique.",
                        property_path,
                    ))
            seen: set[str] = set()
            node = bone.id
            while node:
                if node in seen:
                    issues.append(ValidationIssue(
                        "rig_bone_cycle",
                        f"Rig bone parent cycle includes: {node}",
                        f"{bone_path}.parent_id",
                    ))
                    break
                seen.add(node)
                node = parent_by_id.get(node, "")
        bound_layers: set[str] = set()
        for binding_index, binding in enumerate(rig.bindings):
            binding_path = f"{path}.bindings[{binding_index}]"
            if binding.layer_id not in layer_ids:
                issues.append(ValidationIssue(
                    "missing_rig_binding_layer",
                    f"Unknown rig binding layer: {binding.layer_id}",
                    f"{binding_path}.layer_id",
                ))
            if binding.bone_id not in bone_id_set:
                issues.append(ValidationIssue(
                    "missing_rig_binding_bone",
                    f"Unknown rig binding bone: {binding.bone_id}",
                    f"{binding_path}.bone_id",
                ))
            if binding.layer_id in bound_layers:
                issues.append(ValidationIssue(
                    "duplicate_rig_layer_binding",
                    f"Layer is bound more than once in this rig: {binding.layer_id}",
                    f"{binding_path}.layer_id",
                ))
            bound_layers.add(binding.layer_id)
        constraint_ids: set[str] = set()
        for constraint_index, constraint in enumerate(rig.constraints):
            constraint_path = f"{path}.constraints[{constraint_index}]"
            constraint_id = str(constraint.get("id") or "")
            if not constraint_id or constraint_id in constraint_ids:
                issues.append(ValidationIssue(
                    "invalid_rig_constraint_id",
                    "Rig constraint ids must be non-empty and unique.",
                    f"{constraint_path}.id",
                ))
            constraint_ids.add(constraint_id)
            if str(constraint.get("kind") or "") != RIG_CONSTRAINT_TWO_BONE_IK:
                issues.append(ValidationIssue(
                    "unsupported_rig_constraint",
                    f"Unsupported rig constraint: {constraint.get('kind')}",
                    f"{constraint_path}.kind",
                ))
                continue
            root_id = str(constraint.get("root_bone_id") or "")
            mid_id = str(constraint.get("mid_bone_id") or "")
            end_id = str(constraint.get("end_bone_id") or "")
            if any(value not in bone_id_set for value in (root_id, mid_id, end_id)):
                issues.append(ValidationIssue(
                    "missing_rig_constraint_bone",
                    "IK constraint root, mid, and end must reference rig bones.",
                    constraint_path,
                ))
            elif (
                parent_by_id.get(mid_id) != root_id
                or parent_by_id.get(end_id) != mid_id
            ):
                issues.append(ValidationIssue(
                    "invalid_rig_constraint_chain",
                    "IK constraint bones must form a direct root -> mid -> end chain.",
                    constraint_path,
                ))
            for property_name, value_type in (
                ("target", "vector2"),
                ("pole", "vector2"),
                ("weight", "scalar"),
            ):
                try:
                    prop = AnimatedProperty.from_dict(
                        constraint.get(property_name), value_type=value_type,
                    )
                    samples = [prop.default, *(row.value for row in prop.keyframes)]
                    if value_type == "vector2":
                        valid = all(_valid_point(sample) for sample in samples)
                    else:
                        valid = all(isfinite(float(sample)) for sample in samples)
                    if not valid:
                        raise ValueError
                except (TypeError, ValueError):
                    issues.append(ValidationIssue(
                        "invalid_rig_constraint_property",
                        f"IK constraint {property_name} contains invalid values.",
                        f"{constraint_path}.{property_name}",
                    ))


def _validate_puppet_mesh(
    layer,
    path: str,
    issues: list[ValidationIssue],
    composition: MotionComposition,
) -> None:
    from .puppet_mesh import (
        PUPPET_PIN_KINDS,
        layer_puppet_mesh,
        puppet_mesh_diagnostics,
    )

    mesh = layer_puppet_mesh(layer)
    if mesh is None:
        return
    if layer.layer_type != "image":
        issues.append(ValidationIssue(
            "invalid_puppet_layer_type",
            "Puppet meshes currently require an image layer.",
            f"{path}.metadata.puppet_mesh",
        ))
    vertex_ids = [vertex.id for vertex in mesh.vertices]
    if len(mesh.vertices) < 4 or len(vertex_ids) != len(set(vertex_ids)):
        issues.append(ValidationIssue(
            "invalid_puppet_vertices",
            "Puppet mesh requires at least four uniquely identified vertices.",
            f"{path}.metadata.puppet_mesh.vertices",
        ))
    if not mesh.triangles:
        issues.append(ValidationIssue(
            "empty_puppet_mesh",
            "Puppet mesh requires at least one visible triangle.",
            f"{path}.metadata.puppet_mesh.triangles",
        ))
    if any(
        not 0.0 <= coordinate <= 1.0
        for vertex in mesh.vertices
        for coordinate in vertex.uv
    ):
        issues.append(ValidationIssue(
            "invalid_puppet_uv",
            "Puppet mesh UV coordinates must be normalized.",
            f"{path}.metadata.puppet_mesh.vertices",
        ))
    pin_ids: set[str] = set()
    for index, pin in enumerate(mesh.pins):
        pin_path = f"{path}.metadata.puppet_mesh.pins[{index}]"
        if not pin.id or pin.id in pin_ids:
            issues.append(ValidationIssue(
                "invalid_puppet_pin_id",
                "Puppet pin ids must be non-empty and unique.",
                f"{pin_path}.id",
            ))
        pin_ids.add(pin.id)
        if pin.kind not in PUPPET_PIN_KINDS:
            issues.append(ValidationIssue(
                "invalid_puppet_pin_kind",
                f"Unsupported puppet pin kind: {pin.kind}",
                f"{pin_path}.kind",
            ))
        if not 0.001 <= pin.radius <= 2.0 or not 0.0 <= pin.strength <= 2.0:
            issues.append(ValidationIssue(
                "invalid_puppet_pin_influence",
                "Puppet pin radius and strength are outside supported bounds.",
                pin_path,
            ))
        driver = pin.metadata.get("rig_driver")
        if isinstance(driver, Mapping):
            from .rigging import composition_rigs

            rig = next(
                (
                    row
                    for row in composition_rigs(composition)
                    if row.id == str(driver.get("rig_id") or "")
                ),
                None,
            )
            if rig is None or not any(
                bone.id == str(driver.get("bone_id") or "")
                for bone in rig.bones
            ):
                issues.append(ValidationIssue(
                    "missing_puppet_rig_driver",
                    "Puppet pin rig driver must reference an existing rig bone.",
                    f"{pin_path}.metadata.rig_driver",
                ))
    diagnostics = puppet_mesh_diagnostics(mesh)
    if diagnostics["degenerate_triangle_count"]:
        issues.append(ValidationIssue(
            "invalid_puppet_triangles",
            "Puppet mesh contains invalid or degenerate triangles.",
            f"{path}.metadata.puppet_mesh.triangles",
        ))


def _validate_precomposition(
    layer,
    path: str,
    issues: list[ValidationIssue],
    composition: MotionComposition,
) -> None:
    if layer.layer_type != "precomp":
        return
    from .precomposition import (
        PRECOMP_CONTRACT,
        PRECOMP_SOURCE_KIND,
        embedded_composition,
    )

    source_path = f"{path}.source"
    if layer.source.kind != PRECOMP_SOURCE_KIND:
        issues.append(ValidationIssue(
            "invalid_precomp_source",
            "Pre-composition layers require a motion_composition source.",
            f"{source_path}.kind",
        ))
        return
    if layer.source.params.get("contract") != PRECOMP_CONTRACT:
        issues.append(ValidationIssue(
            "invalid_precomp_contract",
            "Pre-composition source contract is missing or unsupported.",
            f"{source_path}.params.contract",
        ))
    child = embedded_composition(layer)
    if child is None:
        issues.append(ValidationIssue(
            "missing_precomp_document",
            "Pre-composition layer requires an embedded composition snapshot.",
            f"{source_path}.params.composition",
        ))
        return
    if child.id == composition.id:
        issues.append(ValidationIssue(
            "precomp_cycle",
            "A composition cannot directly contain itself.",
            f"{source_path}.params.composition.id",
        ))
        return
    child_report = validate_composition(child)
    for issue in child_report.issues:
        issues.append(ValidationIssue(
            issue.code,
            f"Nested composition: {issue.message}",
            f"{source_path}.params.composition.{issue.path}",
            severity=issue.severity,
        ))


def _validate_time_remap(
    layer,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    raw = layer.metadata.get("time_remap")
    if raw is None:
        return
    if not isinstance(raw, Mapping):
        issues.append(ValidationIssue(
            "invalid_time_remap",
            "Time Remap metadata must be an object.",
            f"{path}.metadata.time_remap",
        ))
        return
    if not raw.get("enabled", True):
        return
    from .time_remap import TIME_REMAP_CONTRACT, layer_time_remap

    prop = layer_time_remap(layer)
    if raw.get("contract") != TIME_REMAP_CONTRACT or prop is None:
        issues.append(ValidationIssue(
            "invalid_time_remap",
            "Time Remap requires the supported contract and animated property.",
            f"{path}.metadata.time_remap",
        ))
        return
    if not prop.keyframes:
        issues.append(ValidationIssue(
            "empty_time_remap",
            "Time Remap requires at least one source-time keyframe.",
            f"{path}.metadata.time_remap.property.keyframes",
        ))
    if any(float(row.value) < 0.0 for row in prop.keyframes):
        issues.append(ValidationIssue(
            "negative_time_remap",
            "Time Remap source-time values cannot be negative.",
            f"{path}.metadata.time_remap.property.keyframes",
        ))


def _validate_frame_blending(
    layer,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    raw = layer.metadata.get("frame_blending")
    if raw is None:
        return
    from .frame_blending import FRAME_BLENDING_CONTRACT, FRAME_BLEND_MODES

    if not isinstance(raw, Mapping):
        issues.append(ValidationIssue(
            "invalid_frame_blending",
            "Frame Blending metadata must be an object.",
            f"{path}.metadata.frame_blending",
        ))
        return
    if (
        raw.get("contract") != FRAME_BLENDING_CONTRACT
        or str(raw.get("mode") or "off") not in FRAME_BLEND_MODES
    ):
        issues.append(ValidationIssue(
            "invalid_frame_blending",
            "Frame Blending requires a supported contract and mode.",
            f"{path}.metadata.frame_blending",
        ))
    try:
        source_fps = float(raw.get("source_fps", 0.0) or 0.0)
    except (TypeError, ValueError):
        source_fps = -1.0
    if source_fps < 0.0:
        issues.append(ValidationIssue(
            "invalid_frame_blending_fps",
            "Frame Blending source FPS cannot be negative.",
            f"{path}.metadata.frame_blending.source_fps",
        ))


def validate_composition(composition: MotionComposition) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if composition.width <= 0 or composition.height <= 0:
        issues.append(ValidationIssue("invalid_size", "Composition dimensions must be positive.", "viewport"))
    if composition.fps <= 0:
        issues.append(ValidationIssue("invalid_fps", "Composition fps must be positive.", "fps"))
    if composition.duration_ms <= 0:
        issues.append(ValidationIssue("invalid_duration", "Composition duration must be positive.", "duration_ms"))
    tracking_assets = [
        item
        for item in composition.metadata.get("tracking_assets", [])
        if isinstance(item, Mapping)
    ]
    tracking_ids = [str(item.get("id") or "") for item in tracking_assets]
    for duplicate_id in sorted({
        track_id for track_id in tracking_ids
        if track_id and tracking_ids.count(track_id) > 1
    }):
        issues.append(ValidationIssue(
            "duplicate_tracking_asset_id",
            f"Duplicate Motion tracking asset id: {duplicate_id}",
            "metadata.tracking_assets",
        ))
    from .tracking_workflow import normalize_track_asset

    for track_index, asset in enumerate(tracking_assets):
        try:
            normalize_track_asset(asset)
        except (TypeError, ValueError) as exc:
            issues.append(ValidationIssue(
                "invalid_tracking_asset",
                str(exc),
                f"metadata.tracking_assets[{track_index}]",
            ))
    _validate_rigs(composition, issues)

    ids = [layer.id for layer in composition.layers]
    duplicate_ids = {layer_id for layer_id in ids if ids.count(layer_id) > 1}
    for layer_id in sorted(duplicate_ids):
        issues.append(ValidationIssue("duplicate_layer_id", f"Duplicate layer id: {layer_id}", "layers"))

    id_set = set(ids)
    layers_by_id = {layer.id: layer for layer in composition.layers}
    boolean_operands: dict[str, list[str]] = {}
    for index, layer in enumerate(composition.layers):
        boolean = _default_value(layer.source.params.get("boolean"))
        if not isinstance(boolean, Mapping):
            continue
        refs = [str(value or "") for value in boolean.get("operand_layer_ids", []) if str(value or "")]
        boolean_operands[layer.id] = refs
        for operand_index, operand_id in enumerate(refs):
            operand_path = f"layers[{index}].source.params.boolean.operand_layer_ids[{operand_index}]"
            if operand_id == layer.id:
                issues.append(ValidationIssue(
                    "vector_boolean_self_reference", "A Boolean layer cannot consume itself.", operand_path,
                ))
            elif operand_id not in id_set:
                issues.append(ValidationIssue(
                    "missing_vector_boolean_operand", f"Unknown Boolean operand: {operand_id}", operand_path,
                ))
            elif layers_by_id[operand_id].layer_type != "shape":
                issues.append(ValidationIssue(
                    "invalid_vector_boolean_operand", "Boolean operands must be shape layers.", operand_path,
                ))

    cycle_nodes: set[str] = set()

    def visit_boolean(node: str, stack: tuple[str, ...]) -> None:
        if node in stack:
            cycle_nodes.update((*stack[stack.index(node):], node))
            return
        for operand_id in boolean_operands.get(node, []):
            if operand_id in boolean_operands:
                visit_boolean(operand_id, (*stack, node))

    for layer_id in boolean_operands:
        visit_boolean(layer_id, ())
    for layer_id in sorted(cycle_nodes):
        issues.append(ValidationIssue(
            "vector_boolean_cycle", f"Boolean operand cycle includes: {layer_id}", "layers",
        ))
    parent_by_id: dict[str, str] = {}
    for layer in composition.layers:
        parent_by_id.setdefault(layer.id, layer.parent_id)
    for index, layer in enumerate(composition.layers):
        path = f"layers[{index}]"
        _validate_puppet_mesh(layer, path, issues, composition)
        _validate_precomposition(layer, path, issues, composition)
        _validate_time_remap(layer, path, issues)
        _validate_frame_blending(layer, path, issues)
        if layer.out_ms <= layer.in_ms:
            issues.append(ValidationIssue("invalid_layer_range", "Layer out_ms must be after in_ms.", path))
        if layer.parent_id and layer.parent_id not in id_set:
            issues.append(ValidationIssue("missing_parent", f"Unknown parent: {layer.parent_id}", f"{path}.parent_id"))
        applied_track = layer.transform.metadata.get("tracking")
        if isinstance(applied_track, Mapping):
            applied_track_id = str(applied_track.get("track_id") or "")
            if applied_track_id and applied_track_id not in set(tracking_ids):
                issues.append(ValidationIssue(
                    "missing_applied_tracking_asset",
                    f"Unknown applied Motion track: {applied_track_id}",
                    f"{path}.transform.metadata.tracking.track_id",
                ))
        matte_id = str(layer.metadata.get("matte_layer_id") or "")
        if matte_id == layer.id:
            issues.append(ValidationIssue(
                "track_matte_self_reference",
                "A layer cannot use itself as a track matte.",
                f"{path}.metadata.matte_layer_id",
            ))
        elif matte_id and matte_id not in id_set:
            issues.append(ValidationIssue(
                "missing_track_matte",
                f"Unknown track matte: {matte_id}",
                f"{path}.metadata.matte_layer_id",
            ))
        matte_mode = str(layer.metadata.get("matte_mode") or "alpha").lower()
        if matte_mode not in {"alpha", "luma", "alpha_inverted", "luma_inverted"}:
            issues.append(ValidationIssue(
                "invalid_track_matte_mode",
                "Track matte mode must be alpha, luma, alpha_inverted, or luma_inverted.",
                f"{path}.metadata.matte_mode",
            ))
        try:
            depth_z = float(layer.metadata.get("depth_z", 0.0) or 0.0)
        except (TypeError, ValueError):
            depth_z = 99.0
        if not -8.0 <= depth_z <= 8.0:
            issues.append(ValidationIssue(
                "invalid_2_5d_depth",
                "2.5D layer depth must be between -8 and 8.",
                f"{path}.metadata.depth_z",
            ))
        three_d = layer.metadata.get("three_d")
        if isinstance(three_d, Mapping):
            projection_model = str(
                three_d.get("projection_model") or "affine_card_2_5d"
            )
            if projection_model != "affine_card_2_5d":
                issues.append(ValidationIssue(
                    "invalid_3d_layer_projection_model",
                    "2.5D layers currently require affine_card_2_5d projection.",
                    f"{path}.metadata.three_d.projection_model",
                ))
            for key in ("rotation_x", "rotation_y"):
                try:
                    angle = float(_default_value(three_d.get(key, 0.0)) or 0.0)
                except (TypeError, ValueError):
                    angle = 999.0
                if not -180.0 <= angle <= 180.0:
                    issues.append(ValidationIssue(
                        "invalid_3d_layer_rotation",
                        "2.5D card rotations must be between -180 and 180 degrees.",
                        f"{path}.metadata.three_d.{key}",
                    ))
            for key, minimum, maximum in (
                ("shadow_strength", 0.0, 1.0),
                ("shadow_softness", 0.0, 32.0),
            ):
                try:
                    value = float(_default_value(three_d.get(key, minimum)) or 0.0)
                except (TypeError, ValueError):
                    value = maximum + 1.0
                if not minimum <= value <= maximum:
                    issues.append(ValidationIssue(
                        "invalid_3d_layer_shadow",
                        f"2.5D card {key} must be between {minimum:g} and {maximum:g}.",
                        f"{path}.metadata.three_d.{key}",
                    ))
        replicator = layer.metadata.get("replicator")
        if isinstance(replicator, Mapping):
            arrangement = str(replicator.get("arrangement") or "line").lower()
            if arrangement not in {"line", "grid", "radial"}:
                issues.append(ValidationIssue(
                    "invalid_layer_replicator_arrangement",
                    "Replicator arrangement must be line, grid, or radial.",
                    f"{path}.metadata.replicator.arrangement",
                ))
            try:
                repeat_count = int(_default_value(replicator.get("count", 1)) or 1)
                columns = int(_default_value(replicator.get("columns", 1)) or 1)
            except (TypeError, ValueError):
                repeat_count, columns = 0, 0
            if not 1 <= repeat_count <= 256:
                issues.append(ValidationIssue(
                    "invalid_layer_replicator",
                    "Generic layer Replicator count must be between 1 and 256.",
                    f"{path}.metadata.replicator.count",
                ))
            if not 1 <= columns <= 256:
                issues.append(ValidationIssue(
                    "invalid_layer_replicator_columns",
                    "Replicator columns must be between 1 and 256.",
                    f"{path}.metadata.replicator.columns",
                ))
        blur = layer.metadata.get("motion_blur")
        if isinstance(blur, Mapping):
            try:
                samples = int(blur.get("samples", 8) or 8)
                shutter = float(blur.get("shutter", 0.65) or 0.0)
            except (TypeError, ValueError):
                samples, shutter = 0, -1.0
            if not 2 <= samples <= 32 or not 0.0 <= shutter <= 2.0:
                issues.append(ValidationIssue(
                    "invalid_motion_blur",
                    "Motion blur requires 2-32 samples and a shutter between 0 and 2.",
                    f"{path}.metadata.motion_blur",
                ))
        seen: set[str] = set()
        node = layer.id
        while node:
            if node in seen:
                issues.append(ValidationIssue("parent_cycle", f"Parent cycle includes: {node}", f"{path}.parent_id"))
                break
            seen.add(node)
            node = parent_by_id.get(node, "")
        for prop_name, prop in layer.transform.properties().items():
            times = [key.time_ms for key in prop.keyframes]
            if times != sorted(times):
                issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", f"{path}.transform.{prop_name}"))
            key_ids = [key.id for key in prop.keyframes]
            if len(key_ids) != len(set(key_ids)):
                issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", f"{path}.transform.{prop_name}"))
        for collection_name, items in (("effects", layer.effects), ("masks", layer.masks)):
            item_ids = [item.id for item in items]
            if len(item_ids) != len(set(item_ids)):
                issues.append(ValidationIssue(
                    f"duplicate_{collection_name[:-1]}_id",
                    f"{collection_name.title()} ids must be unique.",
                    f"{path}.{collection_name}",
                ))
            for item_index, item in enumerate(items):
                if collection_name == "effects" and item.kind in {
                    "chroma_key", "luma_key", "difference_key",
                }:
                    key_path = f"{path}.effects[{item_index}]"
                    if item.kind == "difference_key":
                        reference = item.params.get("reference_uri")
                        reference_uri = (
                            str(reference.default or "")
                            if reference is not None
                            else ""
                        )
                        if not reference_uri:
                            issues.append(ValidationIssue(
                                "difference_key_reference_missing",
                                "Difference Key requires a reference frame URI.",
                                f"{key_path}.params.reference_uri",
                            ))
                for param_name, prop in item.params.items():
                    key_path = f"{path}.{collection_name}[{item_index}].params.{param_name}"
                    times = [key.time_ms for key in prop.keyframes]
                    if times != sorted(times):
                        issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
                    key_ids = [key.id for key in prop.keyframes]
                    if len(key_ids) != len(set(key_ids)):
                        issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))
                if collection_name == "masks":
                    tracking = item.metadata.get("tracking_cache")
                    if isinstance(tracking, Mapping):
                        track_path = f"{path}.masks[{item_index}].metadata.tracking_cache"
                        mode = str(tracking.get("mode") or "point")
                        if mode not in {"point", "planar"}:
                            issues.append(ValidationIssue(
                                "invalid_mask_tracking_mode",
                                "Mask tracking mode must be point or planar.",
                                f"{track_path}.mode",
                            ))
                        samples = [row for row in tracking.get("samples", []) if isinstance(row, Mapping)]
                        times = [int(row.get("time_ms", 0) or 0) for row in samples]
                        if times != sorted(times):
                            issues.append(ValidationIssue(
                                "unsorted_mask_tracking_samples",
                                "Mask tracking samples must be time sorted.",
                                f"{track_path}.samples",
                            ))
                        if tracking.get("enabled", True) and not samples:
                            issues.append(ValidationIssue(
                                "empty_mask_tracking_cache",
                                "Mask tracking is enabled but has no cached samples.",
                                f"{track_path}.samples",
                                severity="warning",
                            ))
                        corrections = [
                            row for row in tracking.get("corrections", [])
                            if isinstance(row, Mapping)
                        ]
                        correction_times = [
                            int(row.get("time_ms", 0) or 0)
                            for row in corrections
                        ]
                        if correction_times != sorted(correction_times):
                            issues.append(ValidationIssue(
                                "unsorted_matte_corrections",
                                "Matte correction keyframes must be time sorted.",
                                f"{track_path}.corrections",
                            ))
                        if tracking.get("frozen", False) and not samples:
                            issues.append(ValidationIssue(
                                "empty_frozen_matte_cache",
                                "A frozen matte cache must contain propagation samples.",
                                f"{track_path}.samples",
                            ))
        _validate_vector_layer(layer, path, issues)
        _validate_typography_layer(layer, path, issues)
        _validate_ar_pbr_layer(layer, path, issues)
        _validate_actor_layer(layer, path, issues)
        _validate_mmd_layer(layer, path, issues)
        _validate_vrm_layer(layer, path, issues)
        _validate_particle_layer(layer, path, issues)
        _validate_button_component(layer, path, issues)
        _validate_generator_layer(layer, path, issues)
    from .expressions import expression_issues

    layer_index = {layer.id: index for index, layer in enumerate(composition.layers)}
    for issue in expression_issues(composition):
        index = layer_index.get(issue.layer_id, 0)
        issues.append(ValidationIssue(
            issue.code, issue.message,
            f"layers[{index}].metadata.expressions.{issue.property_name}".rstrip("."),
        ))
    from .ui_motion_binding import validate_ui_motion_bindings

    ui_motion_report = validate_ui_motion_bindings(composition)
    for severity, rows in (
        ("error", ui_motion_report["errors"]),
        ("warning", ui_motion_report["warnings"]),
    ):
        for row in rows:
            issues.append(ValidationIssue(
                str(row["code"]),
                str(row["message"]),
                str(row["path"]),
                severity=severity,
            ))
    return ValidationReport(issues)


def validate_all(compositions: Iterable[MotionComposition]) -> ValidationReport:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for index, composition in enumerate(compositions):
        if composition.id in seen:
            issues.append(ValidationIssue("duplicate_composition_id", composition.id, f"motion_compositions[{index}]"))
        seen.add(composition.id)
        for issue in validate_composition(composition).issues:
            issue.path = f"motion_compositions[{index}].{issue.path}".rstrip(".")
            issues.append(issue)
    return ValidationReport(issues)
