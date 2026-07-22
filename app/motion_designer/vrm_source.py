"""Qt-free Motion Designer source contract for VRM/MToon avatars."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.vtuber.source_framing import vrm_visibility_policy_for_source_exposure
from app.vtuber.video_face_driver import idle_motion_frame
from app.vtuber.vrm_profile import inspect_vrm_profile
from app.vtuber.vrm_renderer import VRM_RENDERER_FAMILY, VRM_RENDERER_GPU

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer, SourceRef


VRM_SOURCE_KIND = "vrm_actor"


def _animated(default: Any, value_type: str = "scalar") -> dict[str, Any]:
    return AnimatedProperty(value_type=value_type, default=default).to_dict()


def _value(value: Any, time_ms: float, fallback: Any, value_type: str = "scalar") -> Any:
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        prop = AnimatedProperty.from_dict(value, value_type=value_type)
        if prop.default is None:
            prop.default = fallback
        return evaluate_property(prop, time_ms)
    return fallback if value is None else value


def _number(value: Any, fallback: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(fallback)
    return max(minimum, min(maximum, number))


def _deep_merge(target: dict[str, Any], changes: Mapping[str, Any]) -> None:
    for key, value in changes.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[str(key)] = value


def inspect_vrm_source(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    profile = inspect_vrm_profile(source)
    result = {
        "ok": bool(profile.get("ok")),
        "path": str(source),
        "file_size": int(source.stat().st_size) if source.is_file() else 0,
        "profile": profile,
        "renderer": VRM_RENDERER_GPU,
        "renderer_family": VRM_RENDERER_FAMILY,
    }
    if not result["ok"]:
        result["error"] = "; ".join(str(value) for value in profile.get("errors", []) or []) or "VRM source is not loadable"
    return result


def default_vrm_params(
    path: str | Path,
    *,
    width: int,
    height: int,
    source_info: Mapping[str, Any],
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    visibility = vrm_visibility_policy_for_source_exposure(
        "full_body", requested_preset="full_body",
    )
    return {
        "asset": {"avatar_vrm": str(source)},
        "pose": {
            "yaw_deg": _animated(0.0),
            "pitch_deg": _animated(0.0),
            "roll_deg": _animated(0.0),
            "shoulder_roll_deg": _animated(0.0),
            "mouth_open": _animated(0.0),
            "blink_l": _animated(0.0),
            "blink_r": _animated(0.0),
            "idle_strength": _animated(1.0),
        },
        "placement": {
            "source_exposure": "full_body",
            "framing_preset": "full_body",
            "allow_narrower_than_source": False,
            "target_width_ratio": _animated(0.72),
            "target_height_ratio": _animated(0.94),
            "output_center_x": _animated(0.50),
            "output_bottom_y": _animated(0.985),
            "visibility_policy": visibility,
        },
        "lighting": {
            "light_azimuth": _animated(28.0),
            "light_elevation": _animated(42.0),
            "direct_strength": _animated(0.65),
            "ibl_exposure": _animated(1.15),
            "shadow_strength": _animated(0.42),
            "hdri_id": "studio_small_09",
        },
        "playback": {
            "loop": True,
            "rate": _animated(1.0),
            "idle_motion": True,
            "preview_cache_fps": 30.0,
        },
        "render": {
            "width": int(width),
            "height": int(height),
            "renderer": VRM_RENDERER_GPU,
            "renderer_family": VRM_RENDERER_FAMILY,
            "render_profile": "vrm_mtoon",
            "premultiplied_alpha": True,
            "texture_max_size": 512,
            "fit_padding": 0.03,
            "gpu_warmup_frames": 1,
            "reuse_gpu_widget": True,
            "enable_shadow_map": False,
        },
        "catalog": dict(source_info),
    }


def create_vrm_layer(
    path: str | Path,
    *,
    width: int,
    height: int,
    duration_ms: int,
    name: str = "",
    start_ms: int = 0,
    end_ms: int = 0,
    params: Mapping[str, Any] | None = None,
) -> MotionLayer:
    source = Path(path).expanduser().resolve()
    info = inspect_vrm_source(source)
    if not info.get("ok"):
        raise ValueError(str(info.get("error") or f"VRM source is not loadable: {source}"))
    values = default_vrm_params(source, width=width, height=height, source_info=info)
    if params:
        _deep_merge(values, params)
    asset = values.get("asset") if isinstance(values.get("asset"), Mapping) else {}
    resolved = Path(str(asset.get("avatar_vrm") or source)).expanduser().resolve()
    resolved_info = inspect_vrm_source(resolved)
    if not resolved_info.get("ok"):
        raise ValueError(str(resolved_info.get("error") or f"VRM source is not loadable: {resolved}"))
    values["asset"] = {"avatar_vrm": str(resolved)}
    values["catalog"] = resolved_info
    start = max(0, int(start_ms))
    layer = MotionLayer(
        name=str(name or resolved.stem),
        layer_type=VRM_SOURCE_KIND,
        source=SourceRef(kind=VRM_SOURCE_KIND, uri=str(resolved), params=values),
        in_ms=start,
        out_ms=max(start + 1, int(end_ms or duration_ms)),
        metadata={
            "actor_renderer": VRM_RENDERER_GPU,
            "renderer_family": VRM_RENDERER_FAMILY,
            "program_output_role": "avatar_target",
        },
    )
    layer.transform.position.default = [float(width) * 0.5, float(height) * 0.5]
    return layer


@dataclass(slots=True)
class MotionVRMFrame:
    source: dict[str, Any]
    sample_time_ms: float
    diagnostics: dict[str, Any] = field(default_factory=dict)


def evaluate_vrm_frame(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
) -> MotionVRMFrame:
    if layer.layer_type != VRM_SOURCE_KIND and layer.source.kind != VRM_SOURCE_KIND:
        raise ValueError(f"Layer is not VRM: {layer.id}")
    params = layer.source.params
    asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
    pose = params.get("pose") if isinstance(params.get("pose"), Mapping) else {}
    placement = params.get("placement") if isinstance(params.get("placement"), Mapping) else {}
    lighting = params.get("lighting") if isinstance(params.get("lighting"), Mapping) else {}
    playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
    render = params.get("render") if isinstance(params.get("render"), Mapping) else {}
    rate = _number(_value(playback.get("rate"), time_ms, 1.0), 1.0, 0.05, 8.0)
    sample_time = max(0.0, float(time_ms) * rate)
    duration = max(1.0, float(layer.out_ms - layer.in_ms) * rate)
    if bool(playback.get("loop", True)):
        sample_time %= duration

    idle_strength = _number(_value(pose.get("idle_strength"), time_ms, 1.0), 1.0, 0.0, 2.0)
    idle = idle_motion_frame(int(round(sample_time + 150.0))) if bool(playback.get("idle_motion", True)) else idle_motion_frame(150)
    idle_scale = idle_strength if bool(playback.get("idle_motion", True)) else 0.0
    motion_frame = {
        "time_ms": int(round(sample_time)),
        "yaw_deg": _number(_value(pose.get("yaw_deg"), time_ms, 0.0), 0.0, -45.0, 45.0) + idle.yaw_deg * idle_scale,
        "pitch_deg": _number(_value(pose.get("pitch_deg"), time_ms, 0.0), 0.0, -35.0, 35.0) + idle.pitch_deg * idle_scale,
        "roll_deg": _number(_value(pose.get("roll_deg"), time_ms, 0.0), 0.0, -30.0, 30.0) + idle.roll_deg * idle_scale,
        "shoulder_roll_deg": _number(_value(pose.get("shoulder_roll_deg"), time_ms, 0.0), 0.0, -25.0, 25.0),
        "mouth_open": _number(_value(pose.get("mouth_open"), time_ms, 0.0), 0.0, 0.0, 1.0),
        "blink_l": max(_number(_value(pose.get("blink_l"), time_ms, 0.0), 0.0, 0.0, 1.0), idle.blink_l * idle_scale),
        "blink_r": max(_number(_value(pose.get("blink_r"), time_ms, 0.0), 0.0, 0.0, 1.0), idle.blink_r * idle_scale),
        "confidence": 1.0,
        "source": "motion_designer_explicit_pose",
    }
    source_exposure = str(placement.get("source_exposure") or "full_body")
    requested_framing = str(placement.get("framing_preset") or "full_body")
    policy = vrm_visibility_policy_for_source_exposure(
        source_exposure,
        requested_preset=requested_framing,
        allow_narrower=bool(placement.get("allow_narrower_than_source", False)),
        method="motion_designer_explicit",
        confidence=1.0,
    )
    selected_framing = str(policy.get("selected_framing_preset") or "full_body")
    evaluated_placement = {
        "framing": selected_framing,
        "target_width_ratio": _number(_value(placement.get("target_width_ratio"), time_ms, 0.72), 0.72, 0.1, 1.5),
        "target_height_ratio": _number(_value(placement.get("target_height_ratio"), time_ms, 0.94), 0.94, 0.1, 1.5),
        "output_center_x": _number(_value(placement.get("output_center_x"), time_ms, 0.5), 0.5, -0.5, 1.5),
        "output_bottom_y": _number(_value(placement.get("output_bottom_y"), time_ms, 0.985), 0.985, 0.0, 1.5),
    }
    evaluated_lighting = {
        key: _number(_value(lighting.get(key), time_ms, fallback), fallback, minimum, maximum)
        for key, fallback, minimum, maximum in (
            ("light_azimuth", 28.0, -180.0, 180.0),
            ("light_elevation", 42.0, -89.0, 89.0),
            ("direct_strength", 0.65, 0.0, 4.0),
            ("ibl_exposure", 1.15, 0.0, 4.0),
            ("shadow_strength", 0.42, 0.0, 1.0),
        )
    }
    evaluated_lighting["hdri_id"] = str(lighting.get("hdri_id") or "studio_small_09")
    settings = {
        "avatar_vrm": str(asset.get("avatar_vrm") or layer.source.uri),
        "motion_frame": motion_frame,
        "upper_body_mode": "seated" if selected_framing != "full_body" else "standing",
        "framing_preset": selected_framing,
        "placement": evaluated_placement,
        "lighting": evaluated_lighting,
        "target_fps": max(1.0, float(playback.get("preview_cache_fps", 30.0) or 30.0)),
        "texture_max_size": int(render.get("texture_max_size", 512) or 512),
        "fit_padding": float(render.get("fit_padding", 0.03) or 0.03),
        "gpu_warmup_frames": max(1, int(render.get("gpu_warmup_frames", 1) or 1)),
        "reuse_gpu_widget": bool(render.get("reuse_gpu_widget", True)),
        "enable_shadow_map": bool(render.get("enable_shadow_map", False)),
    }
    return MotionVRMFrame(
        source={"id": layer.id, "settings": settings},
        sample_time_ms=sample_time,
        diagnostics={
            "renderer": VRM_RENDERER_GPU,
            "renderer_family": VRM_RENDERER_FAMILY,
            "render_profile": "vrm_mtoon",
            "source_exposure": source_exposure,
            "visibility_policy": policy,
            "selected_framing_preset": selected_framing,
            "selected_motion": motion_frame,
            "composition_time_ms": float(time_ms if composition_time_ms is None else composition_time_ms),
            "composition_revision": int(getattr(composition, "revision", 0) or 0),
        },
    )


def update_vrm_params(layer: MotionLayer, changes: Mapping[str, Any]) -> None:
    if layer.layer_type != VRM_SOURCE_KIND:
        raise ValueError(f"Layer is not VRM: {layer.id}")
    asset_changes = changes.get("asset") if isinstance(changes.get("asset"), Mapping) else {}
    refreshed: dict[str, Any] | None = None
    if "avatar_vrm" in asset_changes:
        candidate = str(asset_changes.get("avatar_vrm") or "")
        refreshed = inspect_vrm_source(candidate)
        if not refreshed.get("ok"):
            raise ValueError(str(refreshed.get("error") or "VRM source is not loadable"))
    def apply(target: dict[str, Any], values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            current = target.get(key)
            if isinstance(current, Mapping) and ({"default", "keyframes"} & set(current)):
                if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
                    target[str(key)] = dict(value)
                else:
                    prop = AnimatedProperty.from_dict(current)
                    prop.default = value
                    target[str(key)] = prop.to_dict()
            elif isinstance(current, dict) and isinstance(value, Mapping):
                apply(current, value)
            else:
                target[str(key)] = value

    apply(layer.source.params, changes)
    if refreshed is not None:
        resolved = str(refreshed.get("path") or "")
        layer.source.uri = resolved
        layer.source.params["asset"] = {"avatar_vrm": resolved}
        layer.source.params["catalog"] = refreshed


__all__ = [
    "MotionVRMFrame", "VRM_SOURCE_KIND", "create_vrm_layer", "default_vrm_params",
    "evaluate_vrm_frame", "inspect_vrm_source", "update_vrm_params",
]
