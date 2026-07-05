"""Schema helpers for MMD model tracks."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.mmd.lighting import resolve_mmd_lighting
from app.mmd.physics import SECONDARY_ROTATION_HINT_SCALE, SPRING_PHYSICS_RESPONSE


SUPPORTED_MODEL_EXTS = frozenset({".pmx", ".pmd"})
SUPPORTED_MOTION_EXTS = frozenset({".vmd"})

DEFAULT_VIEW = {
    "yaw": 0.0,
    "pitch": -4.0,
    "roll": 0.0,
    "zoom": 0.72,
    "offset_x": 0.0,
    "offset_y": 0.02,
}

DEFAULT_RENDER = {
    "mode": "toon",
    "lighting_preset": "studio_soft",
    "lighting": {},
    "bloom_strength": 0.30,
    "material": {
        "skin_warmth": 1.0,
        "hair_highlight": 1.0,
        "eye_highlight": 1.0,
        "lip_specular": 1.0,
        "matcap_specular": 1.0,
        "emissive": 1.0,
    },
}

DEFAULT_PLAYBACK = {
    "motion_start_ms": 0,
    "loop": True,
    "enable_ik": True,
    "enable_physics": True,
    "gpu_skinning": True,
    "gpu_morph_slots": 2,
    "physics_backend": "auto",
    "physics_update_interval_frames": 2.0,
    "physics_smoothing_response": 0.88,
    "physics_rotation_hint_scale": SECONDARY_ROTATION_HINT_SCALE,
    "physics_spring_response": SPRING_PHYSICS_RESPONSE,
    "foot_ik_reach_limit": 0.985,
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _coerce_vec3(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)):
        value = default
    return (
        _coerce_float(value[0] if len(value) > 0 else default[0], default[0]),
        _coerce_float(value[1] if len(value) > 1 else default[1], default[1]),
        _coerce_float(value[2] if len(value) > 2 else default[2], default[2]),
    )


def is_supported_model_path(path: str | Path) -> bool:
    p = Path(path)
    return p.suffix.casefold() in SUPPORTED_MODEL_EXTS or p.name.casefold().endswith(".pbx.json")


def is_supported_motion_path(path: str | Path) -> bool:
    return Path(path).suffix.casefold() in SUPPORTED_MOTION_EXTS


def normalize_view(value: Any) -> dict[str, float]:
    data = _as_mapping(value)
    return {
        "yaw": _clamp(_coerce_float(data.get("yaw"), DEFAULT_VIEW["yaw"]), -180.0, 180.0),
        "pitch": _clamp(_coerce_float(data.get("pitch"), DEFAULT_VIEW["pitch"]), -80.0, 45.0),
        "roll": _clamp(_coerce_float(data.get("roll"), DEFAULT_VIEW["roll"]), -180.0, 180.0),
        "zoom": _clamp(_coerce_float(data.get("zoom"), DEFAULT_VIEW["zoom"]), 0.05, 2.20),
        "offset_x": _clamp(_coerce_float(data.get("offset_x"), DEFAULT_VIEW["offset_x"]), -2.0, 2.0),
        "offset_y": _clamp(_coerce_float(data.get("offset_y"), DEFAULT_VIEW["offset_y"]), -2.0, 2.0),
    }


def normalize_lighting(value: Any, preset: str = "studio_soft") -> dict[str, Any]:
    data = _as_mapping(value)
    overrides: dict[str, Any] = {}
    for key in (
        "key_intensity",
        "fill_intensity",
        "rim_intensity",
        "ambient_intensity",
        "shadow_strength",
        "soft_shadow_strength",
        "contact_shadow_strength",
        "ground_shadow_strength",
        "bloom_strength",
    ):
        if key in data:
            overrides[key] = _coerce_float(data.get(key), 0.0)
    if "key_dir" in data:
        overrides["key_dir"] = _coerce_vec3(data.get("key_dir"), (0.42, -0.76, -0.48))
    return resolve_mmd_lighting(preset, overrides)


def normalize_material(value: Any) -> dict[str, float]:
    data = _as_mapping(value)
    defaults = DEFAULT_RENDER["material"]
    return {
        "skin_warmth": _clamp(_coerce_float(data.get("skin_warmth"), defaults["skin_warmth"]), 0.0, 2.0),
        "hair_highlight": _clamp(_coerce_float(data.get("hair_highlight"), defaults["hair_highlight"]), 0.0, 2.0),
        "eye_highlight": _clamp(_coerce_float(data.get("eye_highlight"), defaults["eye_highlight"]), 0.0, 2.0),
        "lip_specular": _clamp(_coerce_float(data.get("lip_specular"), defaults["lip_specular"]), 0.0, 2.0),
        "matcap_specular": _clamp(_coerce_float(data.get("matcap_specular"), defaults["matcap_specular"]), 0.0, 2.0),
        "emissive": _clamp(_coerce_float(data.get("emissive"), defaults["emissive"]), 0.0, 2.0),
    }


def normalize_render(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    out = deepcopy(DEFAULT_RENDER)
    mode = str(data.get("mode") or data.get("render_mode") or DEFAULT_RENDER["mode"]).strip().casefold()
    out["mode"] = "toon" if mode != "toon" else mode
    out["lighting_preset"] = str(data.get("lighting_preset") or DEFAULT_RENDER["lighting_preset"]).strip().casefold()
    out["bloom_strength"] = _clamp(_coerce_float(data.get("bloom_strength"), DEFAULT_RENDER["bloom_strength"]), 0.0, 2.0)
    lighting = dict(normalize_lighting(data.get("lighting"), out["lighting_preset"]))
    lighting["bloom_enabled"] = out["bloom_strength"] > 0.001
    lighting["bloom_strength"] = out["bloom_strength"]
    out["lighting"] = lighting
    out["material"] = normalize_material(data.get("material"))
    return out


def normalize_playback(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    backend = str(data.get("physics_backend") or DEFAULT_PLAYBACK["physics_backend"]).strip().casefold()
    if backend not in {"auto", "spring", "pybullet", "bullet", "none", "off"}:
        backend = DEFAULT_PLAYBACK["physics_backend"]
    return {
        "motion_start_ms": max(0, _coerce_int(data.get("motion_start_ms"), DEFAULT_PLAYBACK["motion_start_ms"])),
        "loop": _coerce_bool(data.get("loop"), DEFAULT_PLAYBACK["loop"]),
        "enable_ik": _coerce_bool(data.get("enable_ik"), DEFAULT_PLAYBACK["enable_ik"]),
        "enable_physics": _coerce_bool(data.get("enable_physics"), DEFAULT_PLAYBACK["enable_physics"]),
        "gpu_skinning": _coerce_bool(data.get("gpu_skinning"), DEFAULT_PLAYBACK["gpu_skinning"]),
        "gpu_morph_slots": max(
            0,
            min(2, _coerce_int(data.get("gpu_morph_slots"), DEFAULT_PLAYBACK["gpu_morph_slots"])),
        ),
        "physics_backend": backend,
        "physics_update_interval_frames": _clamp(
            _coerce_float(
                data.get("physics_update_interval_frames"),
                DEFAULT_PLAYBACK["physics_update_interval_frames"],
            ),
            1.0,
            6.0,
        ),
        "physics_smoothing_response": _clamp(
            _coerce_float(
                data.get("physics_smoothing_response"),
                DEFAULT_PLAYBACK["physics_smoothing_response"],
            ),
            0.0,
            1.0,
        ),
        "physics_rotation_hint_scale": _clamp(
            _coerce_float(
                data.get("physics_rotation_hint_scale"),
                DEFAULT_PLAYBACK["physics_rotation_hint_scale"],
            ),
            0.0,
            0.30,
        ),
        "physics_spring_response": _clamp(
            _coerce_float(
                data.get("physics_spring_response"),
                DEFAULT_PLAYBACK["physics_spring_response"],
            ),
            0.15,
            1.50,
        ),
        "foot_ik_reach_limit": _clamp(
            _coerce_float(data.get("foot_ik_reach_limit"), DEFAULT_PLAYBACK["foot_ik_reach_limit"]),
            0.70,
            1.0,
        ),
    }


def normalize_mmd_track(value: Any, *, index: int = 0) -> dict[str, Any]:
    data = _as_mapping(value)
    start_ms = max(0, _coerce_int(data.get("start_ms"), 0))
    end_ms = _coerce_int(data.get("end_ms"), start_ms)
    duration_ms = _coerce_int(data.get("duration_ms"), 0)
    if end_ms <= start_ms and duration_ms > 0:
        end_ms = start_ms + duration_ms
    if end_ms <= start_ms:
        end_ms = start_ms + 1000
    motion_library: list[str] = []
    raw_library = data.get("motion_library")
    if isinstance(raw_library, (list, tuple)):
        for raw in raw_library:
            text = str(raw or "").strip()
            if text and text not in motion_library and is_supported_motion_path(text):
                motion_library.append(text)
    return {
        "id": str(data.get("id") or f"mmd_{index + 1:03d}"),
        "type": "mmd_model",
        "model_path": str(data.get("model_path") or data.get("asset_path") or ""),
        "motion_path": str(data.get("motion_path") or data.get("vmd_path") or ""),
        "motion_library": motion_library,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "view": normalize_view(data.get("view")),
        "render": normalize_render(data.get("render")),
        "playback": normalize_playback(data.get("playback")),
    }


def normalize_mmd_tracks(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    return [normalize_mmd_track(row, index=idx) for idx, row in enumerate(values)]


def track_active_at(track: Mapping[str, Any], time_ms: int) -> bool:
    start_ms = _coerce_int(track.get("start_ms"), 0)
    end_ms = _coerce_int(track.get("end_ms"), start_ms)
    return start_ms <= int(time_ms) < end_ms


def track_schema_diagnostics(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    missing_models: list[str] = []
    unsupported_models: list[str] = []
    unsupported_motions: list[str] = []
    for track in tracks:
        track_id = str(track.get("id") or "")
        model_path = str(track.get("model_path") or "")
        motion_path = str(track.get("motion_path") or "")
        if not model_path:
            missing_models.append(track_id)
        elif not is_supported_model_path(model_path):
            unsupported_models.append(model_path)
        if motion_path and not is_supported_motion_path(motion_path):
            unsupported_motions.append(motion_path)
    return {
        "track_count": len(tracks),
        "missing_model_path_count": len(missing_models),
        "unsupported_model_count": len(unsupported_models),
        "unsupported_motion_count": len(unsupported_motions),
        "missing_model_track_ids": missing_models,
        "unsupported_model_paths": unsupported_models,
        "unsupported_motion_paths": unsupported_motions,
    }
