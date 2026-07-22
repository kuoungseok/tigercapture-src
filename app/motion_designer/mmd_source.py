"""Qt-free Motion Designer contract for the existing MMD runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from app.mmd.project_tracks import create_preview_mmd_track, mmd_motion_duration_ms
from app.mmd.schema import is_supported_model_path, is_supported_motion_path, normalize_mmd_track

from .keyframes import evaluate_property
from .schema import AnimatedProperty, MotionComposition, MotionLayer, SourceRef


MMD_SOURCE_KIND = "mmd_actor"


def _animated(default: Any, value_type: str = "scalar") -> dict[str, Any]:
    return AnimatedProperty(value_type=value_type, default=default).to_dict()


def _evaluate(value: Any, time_ms: float, default: Any, value_type: str = "scalar") -> Any:
    if value is None:
        return default
    prop = AnimatedProperty.from_dict(value, value_type=value_type)
    if prop.default is None:
        prop.default = default
    return evaluate_property(prop, time_ms)


def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(minimum, min(maximum, number))


def _count(value: Any) -> int:
    try:
        return int(len(value))
    except (TypeError, ValueError):
        return 0


def _deep_merge(target: dict[str, Any], values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            _deep_merge(current, value)
        else:
            target[str(key)] = value


def inspect_mmd_source(model_path: str | Path, motion_path: str | Path | None = None) -> dict[str, Any]:
    model_file = Path(model_path).expanduser().resolve()
    motion_file = Path(motion_path).expanduser().resolve() if motion_path else None
    result: dict[str, Any] = {
        "ok": False,
        "model_path": str(model_file),
        "motion_path": str(motion_file) if motion_file else "",
        "model": {},
        "motion": {},
    }
    if not model_file.is_file():
        result["error"] = f"MMD model not found: {model_file}"
        return result
    if not is_supported_model_path(model_file):
        result["error"] = f"Unsupported MMD model: {model_file.suffix}"
        return result
    if motion_file is not None and (not motion_file.is_file() or not is_supported_motion_path(motion_file)):
        result["error"] = f"MMD motion not found or unsupported: {motion_file}"
        return result
    try:
        import numpy as np

        from app.mmd.loader import load_mmd_model

        model = load_mmd_model(model_file)
        weights = np.asarray(getattr(getattr(model, "weights", None), "weight_types", []))
        result["model"] = {
            "vertices": int(getattr(model, "vertex_count", 0) or _count(getattr(model, "positions", []))),
            "materials": _count(getattr(model, "materials", [])),
            "bones": _count(getattr(model, "bones", [])),
            "morphs": _count(getattr(model, "morphs", [])),
            "rigid_bodies": _count(getattr(model, "rigid_bodies", [])),
            "joints": _count(getattr(model, "joints", [])),
            "sdef_vertices": int(np.count_nonzero(weights == 3)) if weights.size else 0,
        }
        if motion_file is not None:
            from app.mmd.vmd import load_vmd

            motion = load_vmd(motion_file)
            result["motion"] = {
                "max_frame": int(getattr(motion, "max_frame", 0) or 0),
                "duration_ms": int(mmd_motion_duration_ms(motion_file)),
                "bone_tracks": _count(getattr(motion, "bone_frames", {})),
                "morph_tracks": _count(getattr(motion, "morph_frames", {})),
                "camera_frames": _count(getattr(motion, "camera_frames", [])),
            }
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def default_mmd_params(
    model_path: str | Path,
    motion_path: str | Path | None,
    *,
    width: int,
    height: int,
    source_info: Mapping[str, Any],
) -> dict[str, Any]:
    base = create_preview_mmd_track(
        model_path,
        track_id="motion_mmd_source",
        duration_ms=max(1000, int((source_info.get("motion") or {}).get("duration_ms", 0) or 0)),
        motion_path=motion_path,
    )
    view = dict(base.get("view") or {})
    render = dict(base.get("render") or {})
    lighting = dict(render.get("lighting") or {})
    material = dict(render.get("material") or {})
    playback = dict(base.get("playback") or {})
    return {
        "asset": {
            "model_path": str(Path(model_path).expanduser().resolve()),
            "motion_path": str(Path(motion_path).expanduser().resolve()) if motion_path else "",
        },
        "view": {
            "yaw": _animated(float(view.get("yaw", 0.0))),
            "pitch": _animated(float(view.get("pitch", -4.0))),
            "roll": _animated(float(view.get("roll", 0.0))),
            # Motion compositions are presentation canvases; fill the frame more than
            # the standalone MMD viewer while preserving head/toe safe margins.
            "zoom": _animated(max(0.96, float(view.get("zoom", 0.72)))),
            "offset_x": _animated(float(view.get("offset_x", 0.0))),
            "offset_y": _animated(float(view.get("offset_y", 0.02))),
            "auto_frame": True,
        },
        "render": {
            "mode": "toon",
            "width": int(width),
            "height": int(height),
            "lighting_preset": str(render.get("lighting_preset") or "studio_soft"),
            "bloom_strength": _animated(float(render.get("bloom_strength", 0.30))),
            "lighting": {
                key: _animated(float(lighting.get(key, fallback)))
                for key, fallback in (
                    ("key_intensity", 1.0),
                    ("fill_intensity", 0.32),
                    ("rim_intensity", 0.12),
                    ("ambient_intensity", 0.40),
                    ("shadow_strength", 0.64),
                )
            },
            "material": {
                key: _animated(float(material.get(key, 1.0)))
                for key in (
                    "skin_warmth", "hair_highlight", "eye_highlight",
                    "lip_specular", "matcap_specular", "emissive",
                )
            },
            "premultiplied_alpha": True,
        },
        "playback": {
            **playback,
            "rate": _animated(1.0),
            "use_vmd_camera": bool(playback.get("use_vmd_camera", True)),
            "preview_cache_fps": 30.0,
        },
        "catalog": {
            "model": dict(source_info.get("model") or {}),
            "motion": dict(source_info.get("motion") or {}),
        },
    }


def create_mmd_layer(
    model_path: str | Path,
    *,
    width: int,
    height: int,
    duration_ms: int,
    motion_path: str | Path | None = None,
    name: str = "",
    start_ms: int = 0,
    end_ms: int = 0,
    params: Mapping[str, Any] | None = None,
) -> MotionLayer:
    info = inspect_mmd_source(model_path, motion_path)
    if not info.get("ok"):
        raise ValueError(str(info.get("error") or "MMD source is not loadable"))
    values = default_mmd_params(
        model_path, motion_path, width=width, height=height, source_info=info,
    )
    if params:
        _deep_merge(values, params)
    resolved_asset = values.get("asset") if isinstance(values.get("asset"), Mapping) else {}
    resolved_model = str(resolved_asset.get("model_path") or model_path)
    resolved_motion = str(resolved_asset.get("motion_path") or "")
    resolved_info = inspect_mmd_source(resolved_model, resolved_motion or None)
    if not resolved_info.get("ok"):
        raise ValueError(str(resolved_info.get("error") or "MMD source is not loadable"))
    values["asset"] = {"model_path": resolved_model, "motion_path": resolved_motion}
    values["catalog"] = {
        "model": dict(resolved_info.get("model") or {}),
        "motion": dict(resolved_info.get("motion") or {}),
    }
    start = max(0, int(start_ms))
    finish = max(start + 1, int(end_ms or duration_ms))
    layer = MotionLayer(
        name=str(name or Path(model_path).stem),
        layer_type=MMD_SOURCE_KIND,
        source=SourceRef(kind=MMD_SOURCE_KIND, uri=str(Path(model_path).expanduser().resolve()), params=values),
        in_ms=start,
        out_ms=finish,
        metadata={"actor_renderer": "existing_tiger_mmd_opengl_runtime"},
    )
    layer.transform.position.default = [float(width) * 0.5, float(height) * 0.5]
    return layer


@dataclass(slots=True)
class MotionMMDFrame:
    track: dict[str, Any]
    sample_time_ms: float
    diagnostics: dict[str, Any] = field(default_factory=dict)


def evaluate_mmd_frame(
    layer: MotionLayer,
    time_ms: float,
    *,
    composition: MotionComposition | None = None,
    composition_time_ms: float | None = None,
) -> MotionMMDFrame:
    if layer.layer_type != MMD_SOURCE_KIND and layer.source.kind != MMD_SOURCE_KIND:
        raise ValueError(f"Layer is not MMD: {layer.id}")
    params = layer.source.params
    asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
    view = params.get("view") if isinstance(params.get("view"), Mapping) else {}
    render = params.get("render") if isinstance(params.get("render"), Mapping) else {}
    lighting = render.get("lighting") if isinstance(render.get("lighting"), Mapping) else {}
    material = render.get("material") if isinstance(render.get("material"), Mapping) else {}
    playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
    rate = _number(_evaluate(playback.get("rate"), time_ms, 1.0), 1.0, 0.05, 8.0)
    sample_time = max(0.0, float(time_ms) * rate)
    model_path = str(asset.get("model_path") or layer.source.uri)
    motion_path = str(asset.get("motion_path") or "")
    track = {
        "id": layer.id,
        "model_path": model_path,
        "motion_path": motion_path,
        "motion_library": [motion_path] if motion_path else [],
        "start_ms": 0,
        "end_ms": max(1, int(layer.out_ms - layer.in_ms) * 8),
        "view": {
            "yaw": _number(_evaluate(view.get("yaw"), time_ms, 0.0), 0.0, -180.0, 180.0),
            "pitch": _number(_evaluate(view.get("pitch"), time_ms, -4.0), -4.0, -80.0, 45.0),
            "roll": _number(_evaluate(view.get("roll"), time_ms, 0.0), 0.0, -180.0, 180.0),
            "zoom": _number(_evaluate(view.get("zoom"), time_ms, 0.72), 0.72, 0.05, 2.20),
            "offset_x": _number(_evaluate(view.get("offset_x"), time_ms, 0.0), 0.0, -2.0, 2.0),
            "offset_y": _number(_evaluate(view.get("offset_y"), time_ms, 0.02), 0.02, -2.0, 2.0),
        },
        "render": {
            "mode": "toon",
            "lighting_preset": str(render.get("lighting_preset") or "studio_soft"),
            "bloom_strength": _number(_evaluate(render.get("bloom_strength"), time_ms, 0.30), 0.30, 0.0, 2.0),
            "lighting": {
                key: _number(_evaluate(lighting.get(key), time_ms, fallback), fallback, 0.0, 2.0)
                for key, fallback in (
                    ("key_intensity", 1.0),
                    ("fill_intensity", 0.32),
                    ("rim_intensity", 0.12),
                    ("ambient_intensity", 0.40),
                    ("shadow_strength", 0.64),
                )
            },
            "material": {
                key: _number(_evaluate(material.get(key), time_ms, 1.0), 1.0, 0.0, 2.0)
                for key in (
                    "skin_warmth", "hair_highlight", "eye_highlight",
                    "lip_specular", "matcap_specular", "emissive",
                )
            },
        },
        "playback": {
            key: value for key, value in playback.items() if key not in {"rate", "preview_cache_fps"}
        },
    }
    track["playback"]["loop"] = bool(playback.get("loop", True))
    track["playback"]["use_vmd_camera"] = bool(playback.get("use_vmd_camera", True))
    track = normalize_mmd_track(track)
    motion_meta = dict((params.get("catalog") or {}).get("motion") or {})
    return MotionMMDFrame(
        track=track,
        sample_time_ms=sample_time,
        diagnostics={
            "model_path": model_path,
            "motion_path": motion_path,
            "motion_rate": rate,
            "vmd_camera_available": int(motion_meta.get("camera_frames", 0) or 0) > 0,
            "vmd_camera_enabled": bool(track["playback"].get("use_vmd_camera", True)),
            "auto_frame": bool(view.get("auto_frame", True)),
            "composition_time_ms": float(time_ms if composition_time_ms is None else composition_time_ms),
        },
    )


def update_mmd_params(layer: MotionLayer, changes: Mapping[str, Any]) -> None:
    if layer.layer_type != MMD_SOURCE_KIND:
        raise ValueError(f"Layer is not MMD: {layer.id}")

    def apply(target: dict[str, Any], values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            current = target.get(key)
            if isinstance(current, Mapping) and ({"default", "keyframes"} & set(current)):
                prop = AnimatedProperty.from_dict(current)
                prop.default = value
                target[str(key)] = prop.to_dict()
            elif isinstance(current, dict) and isinstance(value, Mapping):
                apply(current, value)
            else:
                target[str(key)] = value

    asset_changes = changes.get("asset") if isinstance(changes.get("asset"), Mapping) else {}
    refreshed_catalog: dict[str, Any] | None = None
    if "motion_path" in asset_changes:
        asset = layer.source.params.get("asset") if isinstance(layer.source.params.get("asset"), Mapping) else {}
        model_path = str(asset.get("model_path") or layer.source.uri)
        motion_path = str(asset_changes.get("motion_path") or "")
        info = inspect_mmd_source(model_path, motion_path or None)
        if not info.get("ok"):
            raise ValueError(str(info.get("error") or "MMD motion is not loadable"))
        refreshed_catalog = {
            "model": dict(info.get("model") or {}),
            "motion": dict(info.get("motion") or {}),
        }
    apply(layer.source.params, changes)
    if refreshed_catalog is not None:
        layer.source.params["catalog"] = refreshed_catalog


__all__ = [
    "MMD_SOURCE_KIND", "MotionMMDFrame", "create_mmd_layer", "default_mmd_params",
    "evaluate_mmd_frame", "inspect_mmd_source", "update_mmd_params",
]
