"""Qt-free Motion Designer bridge to the existing AR/PBR track contract."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.project_tracks import create_preview_ar_track
from app.ar_pbr.schema import is_supported_asset_path, normalize_ar_track

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer, SourceRef, new_motion_id


AR_PBR_SOURCE_KIND = "ar_pbr"
CAMERA_SOURCE_KIND = "ar_pbr_camera"
LIGHT_SOURCE_KIND = "ar_pbr_light"
DEPTH_GROUP_METADATA_KEY = "ar_pbr_depth_groups"


def _animated(default: Any, value_type: str) -> dict[str, Any]:
    return AnimatedProperty(value_type=value_type, default=default).to_dict()


def _evaluate(value: Any, time_ms: float, default: Any, value_type: str = "scalar") -> Any:
    if value is None:
        return default
    prop = AnimatedProperty.from_dict(value, value_type=value_type)
    if prop.default is None:
        prop.default = default
    return evaluate_property(prop, time_ms)


def _vector(value: Any, size: int, default: list[float]) -> list[float]:
    source = list(value) if isinstance(value, (list, tuple)) else list(default)
    source.extend(default[len(source):size])
    output: list[float] = []
    for index in range(size):
        try:
            output.append(float(source[index]))
        except (TypeError, ValueError, IndexError):
            output.append(float(default[index]))
    return output


def _scalar(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(minimum, min(maximum, number))


def default_ar_pbr_params(*, width: int = 1920, height: int = 1080) -> dict[str, Any]:
    return {
        "width": max(1, int(width)),
        "height": max(1, int(height)),
        "object": {
            "position": _animated([0.0, 0.0, 0.0], "vector3"),
            "rotation": _animated([0.0, 18.0, 0.0], "vector3"),
            "scale": _animated([3.25, 3.25, 3.25], "vector3"),
        },
        "material": {
            "override_strength": _animated(0.0, "scalar"),
            "roughness": _animated(0.45, "scalar"),
            "metallic": _animated(0.0, "scalar"),
            "reflectance": _animated(0.5, "scalar"),
            "clearcoat": _animated(0.0, "scalar"),
            "clearcoat_roughness": _animated(0.18, "scalar"),
        },
        "render": {
            "auto_fit": True,
            "hdri_id": "wide_street_01",
            "hdri_path": "",
            "ibl_exposure": _animated(1.1, "scalar"),
            "ibl_rotation": _animated(0.0, "scalar"),
            "shadow_strength": _animated(0.72, "scalar"),
            "self_shadow_strength": _animated(0.45, "scalar"),
            "shadow_filter": "pcf",
            "shadow_pcf_radius": _animated(1.35, "scalar"),
            "ambient_occlusion_mode": "screen",
            "ao_strength": _animated(0.55, "scalar"),
            "bloom_strength": _animated(0.0, "scalar"),
            "depth_of_field_strength": _animated(0.0, "scalar"),
            "transparent_background": True,
            "draw_ground": False,
        },
        "depth_group_id": "",
    }


def default_camera_params() -> dict[str, Any]:
    return {
        "position": _animated([0.0, 0.0, 3.25], "vector3"),
        "rotation": _animated([0.0, 0.0, 0.0], "vector3"),
        "target": _animated([0.0, 0.0, 0.0], "vector3"),
        "fov": _animated(45.0, "scalar"),
        "focus_distance": _animated(3.25, "scalar"),
        "focus_range": _animated(0.28, "scalar"),
    }


def default_light_params() -> dict[str, Any]:
    return {
        "light_type": "directional",
        "azimuth": _animated(45.0, "scalar"),
        "elevation": _animated(45.0, "scalar"),
        "color": _animated([1.0, 1.0, 1.0], "color3"),
        "intensity": _animated(0.42, "scalar"),
        "enabled": _animated(True, "bool"),
    }


def create_ar_pbr_layer(
    asset_path: str | Path,
    *,
    width: int,
    height: int,
    duration_ms: int,
    name: str = "3D Object",
    start_ms: int = 0,
    end_ms: int | None = None,
    params: Mapping[str, Any] | None = None,
) -> MotionLayer:
    path = Path(asset_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"AR/PBR asset not found: {path}")
    if not is_supported_asset_path(path):
        raise ValueError(f"Unsupported AR/PBR asset: {path.suffix}")
    merged = default_ar_pbr_params(width=width, height=height)
    if isinstance(params, Mapping):
        _deep_update(merged, params)
    start = max(0, int(start_ms))
    finish = max(start + 1, int(end_ms if end_ms is not None else duration_ms))
    layer = MotionLayer(
        name=str(name or path.stem),
        layer_type="ar_pbr",
        source=SourceRef(kind=AR_PBR_SOURCE_KIND, uri=str(path), params=merged),
        in_ms=start,
        out_ms=finish,
    )
    layer.transform.position.default = [0.0, 0.0]
    layer.transform.anchor.default = [0.0, 0.0]
    return layer


def create_camera_layer(*, duration_ms: int, name: str = "Camera", params: Mapping[str, Any] | None = None) -> MotionLayer:
    values = default_camera_params()
    if isinstance(params, Mapping):
        _deep_update(values, params)
    return MotionLayer(
        name=str(name or "Camera"), layer_type="camera",
        source=SourceRef(kind=CAMERA_SOURCE_KIND, params=values), out_ms=max(1, int(duration_ms)),
    )


def create_light_layer(*, duration_ms: int, name: str = "Key Light", params: Mapping[str, Any] | None = None) -> MotionLayer:
    values = default_light_params()
    if isinstance(params, Mapping):
        _deep_update(values, params)
    return MotionLayer(
        name=str(name or "Key Light"), layer_type="light",
        source=SourceRef(kind=LIGHT_SOURCE_KIND, params=values), out_ms=max(1, int(duration_ms)),
    )


def _deep_update(target: dict[str, Any], values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[str(key)] = value


def set_source_defaults(target: dict[str, Any], changes: Mapping[str, Any]) -> None:
    """Update authoring defaults without discarding existing source keyframes."""
    for key, value in changes.items():
        current = target.get(key)
        if isinstance(value, Mapping) and isinstance(current, dict) and not ({"default", "keyframes"} & set(current)):
            set_source_defaults(current, value)
        elif isinstance(current, Mapping) and ({"default", "keyframes"} & set(current)):
            prop = AnimatedProperty.from_dict(current)
            prop.default = value
            target[str(key)] = prop.to_dict()
        else:
            target[str(key)] = value


def _active_layer(composition: MotionComposition | None, layer_type: str, time_ms: float) -> MotionLayer | None:
    if composition is None:
        return None
    return next((
        layer for layer in reversed(composition.layers)
        if layer.layer_type == layer_type and layer.visible and layer.in_ms <= time_ms < layer.out_ms
    ), None)


def _depth_group(composition: MotionComposition | None, group_id: str) -> dict[str, Any]:
    if composition is None or not group_id:
        return {}
    rows = composition.metadata.get(DEPTH_GROUP_METADATA_KEY)
    if not isinstance(rows, Mapping):
        return {}
    row = rows.get(group_id)
    return dict(row) if isinstance(row, Mapping) else {}


@dataclass(slots=True)
class MotionArPbrFrame:
    track: dict[str, Any]
    settings: dict[str, Any]
    depth_frame: Any = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def evaluate_ar_pbr_frame(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
) -> MotionArPbrFrame:
    if layer.layer_type != "ar_pbr" and layer.source.kind != AR_PBR_SOURCE_KIND:
        raise ValueError(f"Layer is not AR/PBR: {layer.id}")
    params = layer.source.params
    object_params = params.get("object") if isinstance(params.get("object"), Mapping) else {}
    material_params = params.get("material") if isinstance(params.get("material"), Mapping) else {}
    render_params = params.get("render") if isinstance(params.get("render"), Mapping) else {}
    global_time = float(time_ms if composition_time_ms is None else composition_time_ms)

    object_position = _vector(_evaluate(object_params.get("position"), time_ms, [0.0, 0.0, 0.0], "vector3"), 3, [0.0, 0.0, 0.0])
    object_rotation = _vector(_evaluate(object_params.get("rotation"), time_ms, [0.0, 18.0, 0.0], "vector3"), 3, [0.0, 18.0, 0.0])
    object_scale = _vector(_evaluate(object_params.get("scale"), time_ms, [3.25, 3.25, 3.25], "vector3"), 3, [3.25, 3.25, 3.25])

    camera_layer = _active_layer(composition, "camera", global_time)
    camera = camera_layer.source.params if camera_layer is not None else default_camera_params()
    camera_position = _vector(_evaluate(camera.get("position"), global_time, [0.0, 0.0, 3.25], "vector3"), 3, [0.0, 0.0, 3.25])
    camera_rotation = _vector(_evaluate(camera.get("rotation"), global_time, [0.0, 0.0, 0.0], "vector3"), 3, [0.0, 0.0, 0.0])
    camera_target = _vector(_evaluate(camera.get("target"), global_time, [0.0, 0.0, 0.0], "vector3"), 3, [0.0, 0.0, 0.0])
    fov = _scalar(_evaluate(camera.get("fov"), global_time, 45.0), 45.0, 10.0, 120.0)
    focus_distance = _scalar(_evaluate(camera.get("focus_distance"), global_time, 3.25), 3.25, 0.01, 100.0)
    focus_range = _scalar(_evaluate(camera.get("focus_range"), global_time, 0.28), 0.28, 0.001, 10.0)
    distance = math.sqrt(sum((camera_position[index] - camera_target[index]) ** 2 for index in range(3)))
    camera_z = max(0.2, min(20.0, distance or 3.25))
    relative_rotation = [object_rotation[index] - camera_rotation[index] for index in range(3)]

    light_layer = _active_layer(composition, "light", global_time)
    light = light_layer.source.params if light_layer is not None else default_light_params()
    light_enabled = bool(_evaluate(light.get("enabled"), global_time, True, "bool"))
    light_color = _vector(_evaluate(light.get("color"), global_time, [1.0, 1.0, 1.0], "color3"), 3, [1.0, 1.0, 1.0])
    light_color = [max(0.0, min(8.0, value)) for value in light_color]
    light_intensity = _scalar(_evaluate(light.get("intensity"), global_time, 0.42), 0.42, 0.0, 4.0) if light_enabled else 0.0
    light_azimuth = _scalar(_evaluate(light.get("azimuth"), global_time, 45.0), 45.0, -180.0, 180.0)
    light_elevation = _scalar(_evaluate(light.get("elevation"), global_time, 45.0), 45.0, -20.0, 89.0)

    override = _scalar(_evaluate(material_params.get("override_strength"), time_ms, 0.0), 0.0, 0.0, 1.0)
    roughness = _scalar(_evaluate(material_params.get("roughness"), time_ms, 0.45), 0.45, 0.04, 1.0)
    metallic = _scalar(_evaluate(material_params.get("metallic"), time_ms, 0.0), 0.0, 0.0, 1.0)
    reflectance = _scalar(_evaluate(material_params.get("reflectance"), time_ms, 0.5), 0.5, 0.0, 1.0)
    clearcoat = _scalar(_evaluate(material_params.get("clearcoat"), time_ms, 0.0), 0.0, 0.0, 1.0)
    clearcoat_roughness = _scalar(_evaluate(material_params.get("clearcoat_roughness"), time_ms, 0.18), 0.18, 0.02, 1.0)

    lighting = {
        "hdri_id": str(render_params.get("hdri_id") or "wide_street_01"),
        "hdri_path": str(render_params.get("hdri_path") or ""),
        "ibl_exposure": _scalar(_evaluate(render_params.get("ibl_exposure"), time_ms, 1.1), 1.1, 0.0, 8.0),
        "ibl_rotation": _scalar(_evaluate(render_params.get("ibl_rotation"), time_ms, 0.0), 0.0, -1.0, 1.0),
        "light_azimuth": light_azimuth,
        "light_elevation": light_elevation,
        "light_color": light_color,
        "direct_strength": light_intensity,
        "shadow_strength": _scalar(_evaluate(render_params.get("shadow_strength"), time_ms, 0.72), 0.72, 0.0, 1.0),
        "self_shadow_strength": _scalar(_evaluate(render_params.get("self_shadow_strength"), time_ms, 0.45), 0.45, 0.0, 1.0),
        "shadow_filter": str(render_params.get("shadow_filter") or "pcf"),
        "shadow_pcf_radius": _scalar(_evaluate(render_params.get("shadow_pcf_radius"), time_ms, 1.35), 1.35, 0.0, 12.0),
        "ambient_occlusion_mode": str(render_params.get("ambient_occlusion_mode") or "screen"),
        "ao_strength": _scalar(_evaluate(render_params.get("ao_strength"), time_ms, 0.55), 0.55, 0.0, 2.0),
        "surface_override_strength": override,
        "surface_roughness": roughness,
        "surface_metallic": metallic,
        "surface_reflectance": reflectance,
        "clearcoat_mode": "clearcoat" if clearcoat > 1.0e-6 else "off",
        "clearcoat_enabled": clearcoat > 1.0e-6,
        "clearcoat_strength": clearcoat,
        "clearcoat_roughness": clearcoat_roughness,
        "depth_of_field_mode": "depth_bands" if _scalar(_evaluate(render_params.get("depth_of_field_strength"), time_ms, 0.0), 0.0, 0.0, 1.0) > 0 else "off",
        "depth_of_field_strength": _scalar(_evaluate(render_params.get("depth_of_field_strength"), time_ms, 0.0), 0.0, 0.0, 1.0),
        "dof_focus_depth": focus_distance,
        "dof_focus_range": focus_range,
        "post_effects_mode": "post_effects" if _scalar(_evaluate(render_params.get("bloom_strength"), time_ms, 0.0), 0.0, 0.0, 4.0) > 0 else "off",
        "bloom_strength": _scalar(_evaluate(render_params.get("bloom_strength"), time_ms, 0.0), 0.0, 0.0, 4.0),
    }
    base_track = create_preview_ar_track(
        layer.source.uri, track_id=layer.id, start_ms=0,
        end_ms=max(1, layer.out_ms - layer.in_ms), scale=1.0,
    )
    base_track.update({
        "transform": {"position": object_position, "rotation": relative_rotation, "scale": object_scale},
        "material": {"roughness": roughness, "metallic": metallic, "reflectance": reflectance},
        "material_override": override > 1.0e-6,
        "render": {"render_profile": "authored", "shadow_quality": "preview", "reflection_quality": "preview", "lighting": lighting},
    })

    group = _depth_group(composition, str(params.get("depth_group_id") or ""))
    depth_path = str(group.get("depth_frame_path") or "")
    occlusion = bool(group.get("occlusion", False) and depth_path)
    base_track["depth_source_id"] = str(group.get("depth_source_id") or "")
    base_track["occlusion"] = occlusion
    track = normalize_ar_track(base_track)
    settings = {
        "renderer": "full_gpu",
        "reuse_gpu_widget": True,
        "enable_shadow_map": True,
        "model_view": {
            "auto_fit": bool(render_params.get("auto_fit", True)),
            "zoom": max(0.03, min(40.0, 1.75 * 45.0 / fov)),
            "camera_z": camera_z,
            "fov_deg": fov,
            "pan_x": max(-20.0, min(20.0, camera_target[0] - camera_position[0])),
            "pan_y": max(-20.0, min(20.0, camera_target[1] - camera_position[1])),
            "pan_z": max(-20.0, min(20.0, camera_target[2])),
            "show_environment_background": False,
            "transparent_background": bool(render_params.get("transparent_background", True)),
            "draw_ground": bool(render_params.get("draw_ground", False)),
        },
    }
    diagnostics = {
        "camera_layer_id": camera_layer.id if camera_layer else "",
        "light_layer_id": light_layer.id if light_layer else "",
        "depth_group_id": str(params.get("depth_group_id") or ""),
        "depth_frame_path": depth_path,
        "depth_occlusion_requested": bool(group.get("occlusion", False)),
        "depth_occlusion_ready": occlusion,
        "renderer": "full_gpu",
        "camera_equivalence": "camera_rotation_is_applied_as_inverse_model_orbit",
        "light_limit": "single_key_light_plus_hdri",
    }
    depth_frame: Any = depth_path if occlusion else None
    return MotionArPbrFrame(track=track, settings=settings, depth_frame=depth_frame, diagnostics=diagnostics)


def set_depth_group(
    composition: MotionComposition,
    *,
    group_id: str = "",
    member_layer_ids: list[str] | tuple[str, ...],
    depth_source_id: str = "",
    depth_frame_path: str = "",
    occlusion: bool = True,
) -> dict[str, Any]:
    members = [str(value) for value in member_layer_ids if str(value)]
    known = {layer.id for layer in composition.layers if layer.layer_type == "ar_pbr"}
    unknown = sorted(set(members) - known)
    if unknown:
        raise ValueError(f"Unknown AR/PBR depth-group layers: {', '.join(unknown)}")
    identifier = str(group_id or new_motion_id("depth_group"))
    rows = dict(composition.metadata.get(DEPTH_GROUP_METADATA_KEY) or {})
    row = {
        "id": identifier,
        "member_layer_ids": members,
        "depth_source_id": str(depth_source_id or ""),
        "depth_frame_path": str(Path(depth_frame_path).expanduser().resolve()) if depth_frame_path else "",
        "occlusion": bool(occlusion),
    }
    rows[identifier] = row
    composition.metadata[DEPTH_GROUP_METADATA_KEY] = rows
    for layer in composition.layers:
        if layer.id in members:
            layer.source.params["depth_group_id"] = identifier
        elif str(layer.source.params.get("depth_group_id") or "") == identifier:
            layer.source.params["depth_group_id"] = ""
    composition.revision += 1
    return row


__all__ = [
    "AR_PBR_SOURCE_KIND", "CAMERA_SOURCE_KIND", "LIGHT_SOURCE_KIND", "DEPTH_GROUP_METADATA_KEY",
    "MotionArPbrFrame", "create_ar_pbr_layer", "create_camera_layer", "create_light_layer",
    "default_ar_pbr_params", "default_camera_params", "default_light_params",
    "evaluate_ar_pbr_frame", "set_depth_group", "set_source_defaults",
]
