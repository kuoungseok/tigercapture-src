"""Motion-blur controls for AR/PBR rendering."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


DEFAULT_MOTION_BLUR_MODE = "off"
DEFAULT_MOTION_BLUR_SAMPLE_COUNT = 1
DEFAULT_SHUTTER_ANGLE = 180.0
DEFAULT_FRAME_DURATION_MS = 1000.0 / 60.0
MOTION_BLUR_CONTAINER_KEYS = (
    "motion_blur_rendering",
    "motion_blur",
    "camera_motion_blur",
    "shutter",
    "final_motion_blur",
)
MOTION_BLUR_REQUEST_KEYS = {
    "motion_blur_mode",
    "motion_blur_enabled",
    "motion_blur_samples",
    "motion_blur_shutter_angle",
    "motion_blur_shutter_fraction",
    "motion_blur_shutter_ms",
    "motion_blur_strength",
    "sample_count",
    "samples",
    "shutter_samples",
    "shutter_angle",
    "shutter_fraction",
    "shutter_ms",
    "exposure_ms",
    "strength",
    "amount",
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "final", "camera", "motion", "motion_blur"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "none"}:
        return False
    return bool(default)


def _float_value(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def _int_value(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        out = int(value)
    except Exception:
        out = int(default)
    return max(int(lo), min(int(hi), out))


def _vec2(value: Any) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else [0.0, 0.0]
    out: list[float] = []
    for idx in range(2):
        try:
            out.append(max(-256.0, min(256.0, float(source[idx]))))
        except Exception:
            out.append(0.0)
    return out


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in MOTION_BLUR_CONTAINER_KEYS:
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _has_motion_blur_request(data: Mapping[str, Any]) -> bool:
    for key in MOTION_BLUR_CONTAINER_KEYS:
        nested = data.get(key)
        if isinstance(nested, Mapping) and bool(nested):
            return True
    return any(key in data for key in MOTION_BLUR_REQUEST_KEYS)


def _frame_duration_ms(data: Mapping[str, Any]) -> float:
    direct = _first_value(
        _nested(data, "frame_duration_ms", "frame_ms"),
        data.get("frame_duration_ms"),
        data.get("motion_blur_frame_duration_ms"),
    )
    if direct is not None:
        return _float_value(direct, DEFAULT_FRAME_DURATION_MS, 1.0, 1000.0)
    fps = _first_value(_nested(data, "fps", "frame_rate"), data.get("fps"), data.get("frame_rate"))
    try:
        fps_value = float(fps)
    except Exception:
        fps_value = 60.0
    return 1000.0 / max(1.0, min(240.0, fps_value))


def normalize_motion_blur_settings(value: Any) -> dict[str, Any]:
    """Normalize final-render shutter/sample motion blur controls."""
    data = _as_mapping(value)
    has_request = _has_motion_blur_request(data)
    raw_mode = _first_value(
        _nested(data, "mode", "motion_blur_mode"),
        data.get("motion_blur_mode"),
        DEFAULT_MOTION_BLUR_MODE,
    )
    mode = str(raw_mode or DEFAULT_MOTION_BLUR_MODE).strip().casefold().replace("-", "_").replace(" ", "_")
    if mode in {"render", "final_render", "shutter", "camera"}:
        mode = "final"
    if mode not in {"off", "final"}:
        mode = DEFAULT_MOTION_BLUR_MODE

    sample_count = _int_value(
        _first_value(
            _nested(data, "sample_count", "samples", "motion_blur_samples", "shutter_samples"),
            data.get("motion_blur_samples"),
        ),
        DEFAULT_MOTION_BLUR_SAMPLE_COUNT,
        1,
        32,
    )
    shutter_angle = _float_value(
        _first_value(
            _nested(data, "shutter_angle", "angle"),
            data.get("shutter_angle"),
            data.get("motion_blur_shutter_angle"),
        ),
        DEFAULT_SHUTTER_ANGLE,
        0.0,
        360.0,
    )
    frame_duration = _frame_duration_ms(data)
    shutter_fraction = _float_value(
        _first_value(
            _nested(data, "shutter_fraction", "fraction"),
            data.get("motion_blur_shutter_fraction"),
        ),
        shutter_angle / 360.0 if shutter_angle > 0.0 else 0.0,
        0.0,
        1.0,
    )
    shutter_ms = _float_value(
        _first_value(
            _nested(data, "shutter_ms", "exposure_ms"),
            data.get("motion_blur_shutter_ms"),
        ),
        frame_duration * shutter_fraction,
        0.0,
        1000.0,
    )
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "motion_blur_strength"),
            data.get("motion_blur_strength"),
        ),
        1.0,
        0.0,
        2.0,
    )
    camera_motion_px = _vec2(_first_value(
        _nested(data, "camera_motion_px", "camera_velocity_px", "camera_pan_px"),
        data.get("camera_motion_px"),
        data.get("camera_velocity_px"),
    ))
    enabled = _bool_value(
        _first_value(
            _nested(data, "enabled", "motion_blur_enabled"),
            data.get("motion_blur_enabled"),
        ),
        has_request and (mode != "off" or sample_count > 1 or shutter_ms > 0.0),
    )
    if enabled and mode == "off":
        mode = "final"
    if not enabled or strength <= 0.0 or shutter_ms <= 0.0:
        mode = "off"
        enabled = False
        sample_count = 1
        shutter_ms = 0.0
    elif sample_count < 2:
        sample_count = 2

    return {
        "schema": "tigerstudio.ar_pbr.motion_blur.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "sample_count": int(sample_count),
        "shutter_angle": float(shutter_angle),
        "shutter_fraction": float(shutter_fraction),
        "shutter_ms": float(shutter_ms),
        "frame_duration_ms": float(frame_duration),
        "strength": float(strength),
        "camera_motion_px": camera_motion_px,
        "sampling_model": "centered_shutter_multi_sample_accumulation",
        "camera_motion_model": "optional_intrinsics_center_shift_per_shutter_sample",
        "packet_policy": "final_export_rebuilds_preview_packets_per_sample",
        "viewport_policy": "live_preview_contract_only_single_sample",
        "full_gpu_policy": "helper_contract_until_native_velocity_or_multisample_service_path",
        "render_pass_policy": "beauty_pass_blurred_data_passes_use_center_sample",
        "render_pass_safe": True,
    }


def flatten_motion_blur_settings(value: Any) -> dict[str, Any]:
    settings = normalize_motion_blur_settings(value)
    return {
        "motion_blur_mode": settings["mode"],
        "motion_blur_enabled": settings["enabled"],
        "motion_blur_samples": settings["sample_count"],
        "motion_blur_shutter_angle": settings["shutter_angle"],
        "motion_blur_shutter_fraction": settings["shutter_fraction"],
        "motion_blur_shutter_ms": settings["shutter_ms"],
        "motion_blur_frame_duration_ms": settings["frame_duration_ms"],
        "motion_blur_strength": settings["strength"],
        "camera_motion_px": list(settings["camera_motion_px"]),
    }


def motion_blur_sample_offsets_ms(settings: Mapping[str, Any]) -> list[float]:
    cfg = normalize_motion_blur_settings(settings)
    if not bool(cfg["enabled"]) or int(cfg["sample_count"]) <= 1:
        return [0.0]
    count = int(cfg["sample_count"])
    shutter = float(cfg["shutter_ms"]) * float(cfg["strength"])
    if shutter <= 0.0:
        return [0.0]
    if count == 2:
        return [-shutter * 0.5, shutter * 0.5]
    return [
        -shutter * 0.5 + shutter * (float(idx) / float(count - 1))
        for idx in range(count)
    ]


def camera_solution_for_motion_sample(
    camera_solution: Mapping[str, Any] | None,
    settings: Mapping[str, Any],
    offset_ms: float,
) -> Mapping[str, Any] | None:
    cfg = normalize_motion_blur_settings(settings)
    motion = cfg.get("camera_motion_px") if isinstance(cfg.get("camera_motion_px"), list) else [0.0, 0.0]
    if abs(float(motion[0])) <= 1.0e-6 and abs(float(motion[1])) <= 1.0e-6:
        return camera_solution
    shutter = max(1.0e-6, float(cfg.get("shutter_ms", 0.0) or 0.0) * float(cfg.get("strength", 1.0) or 1.0))
    ratio = max(-0.5, min(0.5, float(offset_ms) / shutter))
    data = deepcopy(camera_solution) if isinstance(camera_solution, Mapping) else {}
    intr = data.get("intrinsics") if isinstance(data.get("intrinsics"), Mapping) else {}
    data["intrinsics"] = dict(intr)
    data["intrinsics"]["cx"] = float(data["intrinsics"].get("cx", 0.0) or 0.0) + float(motion[0]) * ratio
    data["intrinsics"]["cy"] = float(data["intrinsics"].get("cy", 0.0) or 0.0) + float(motion[1]) * ratio
    return data


def merge_motion_blur_settings(global_settings: Mapping[str, Any] | None, source: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(source or {})
    global_data = _as_mapping(global_settings)
    for key in (
        "frame_duration_ms",
        "fps",
        "frame_rate",
        "motion_blur_frame_duration_ms",
        "camera_motion_px",
        "camera_velocity_px",
    ):
        if key in global_data and key not in data:
            data[key] = global_data[key]
    return normalize_motion_blur_settings(data)
