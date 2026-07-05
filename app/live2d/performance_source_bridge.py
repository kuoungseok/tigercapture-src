"""Bridge VTuber Performance Source framing into Live2D actor clips."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.live2d.actor_track import Live2DKeyframe


LIVE2D_PERFORMANCE_SOURCE_SCHEMA = "tigerstudio.live2d.performance_source_bridge.v1"
LIVE2D_PARAMETER_ALIAS_SCHEMA = "tigerstudio.live2d.parameter_aliases.v1"


LIVE2D_PARAMETER_ALIASES: dict[str, tuple[str, ...]] = {
    "ParamAngleX": (
        "ParamHeadAngleX",
        "ParamFaceAngleX",
        "ParamHeadX",
        "ParamHeadYaw",
        "ParamYaw",
        "HeadAngleX",
        "PARAM_ANGLE_X",
    ),
    "ParamAngleY": (
        "ParamHeadAngleY",
        "ParamFaceAngleY",
        "ParamHeadY",
        "ParamHeadPitch",
        "ParamPitch",
        "HeadAngleY",
        "PARAM_ANGLE_Y",
    ),
    "ParamAngleZ": (
        "ParamHeadAngleZ",
        "ParamFaceAngleZ",
        "ParamHeadZ",
        "ParamHeadRoll",
        "ParamRoll",
        "HeadAngleZ",
        "PARAM_ANGLE_Z",
    ),
    "ParamBodyAngleX": ("ParamBodyX", "ParamBodyAngle", "ParamBodyYaw", "BodyAngleX", "PARAM_BODY_ANGLE_X"),
    "ParamBodyAngleY": ("ParamBodyY", "ParamBodyPitch", "BodyAngleY", "PARAM_BODY_ANGLE_Y"),
    "ParamBodyAngleZ": ("ParamBodyZ", "ParamBodyRoll", "BodyAngleZ", "PARAM_BODY_ANGLE_Z"),
    "ParamBreath": ("ParamBreathing", "ParamBreathY", "ParamBreathLoop", "PARAM_BREATH"),
    "ParamEyeBallX": (
        "ParamEyeX",
        "ParamEyesX",
        "ParamEyeBallLX",
        "ParamEyeBallRX",
        "ParamEyeLookX",
        "ParamGazeX",
        "PARAM_EYE_BALL_X",
    ),
    "ParamEyeBallY": (
        "ParamEyeY",
        "ParamEyesY",
        "ParamEyeBallLY",
        "ParamEyeBallRY",
        "ParamEyeLookY",
        "ParamGazeY",
        "PARAM_EYE_BALL_Y",
    ),
    "ParamMouthOpenY": (
        "ParamMouthOpen",
        "ParamMouthOpenA",
        "ParamMouthA",
        "ParamA",
        "MouthOpen",
        "PARAM_MOUTH_OPEN_Y",
    ),
    "ParamMouthForm": ("ParamMouthSmile", "ParamMouthFormY", "ParamMouthShape", "MouthForm", "PARAM_MOUTH_FORM"),
    "ParamEyeLOpen": (
        "ParamEyeLOpenY",
        "ParamEyeOpenL",
        "ParamEyeOpenLeft",
        "ParamLeftEyeOpen",
        "PARAM_EYE_L_OPEN",
    ),
    "ParamEyeROpen": (
        "ParamEyeROpenY",
        "ParamEyeOpenR",
        "ParamEyeOpenRight",
        "ParamRightEyeOpen",
        "PARAM_EYE_R_OPEN",
    ),
    "ParamEyeOpen": ("ParamEyesOpen", "ParamEyeOpenBoth", "ParamBothEyeOpen", "PARAM_EYE_OPEN"),
    "ParamEyeBlink": ("ParamBlink", "ParamEyesBlink", "ParamEyeClose", "PARAM_EYE_BLINK"),
}


def normalize_performance_subject_type(value: Any = "", payload: Mapping[str, Any] | None = None) -> str:
    """Normalize source shot labels into the public Performance Source subject types."""
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if not text and isinstance(payload, Mapping):
        text = _subject_type_from_payload(payload)
    if text in {"face", "face_only", "face_closeup", "closeup", "talking_head", "head", "head_only"}:
        return "face_only"
    if text in {"upper", "upper_body", "bust", "bust_up", "half_body", "seated", "torso"}:
        return "upper_body"
    if text in {"full", "full_body", "standing", "whole_body", "body"}:
        return "full_body"
    if text in {"unknown", "full_body_or_wide", "wide", "wide_shot", "none"}:
        return "unknown"
    return ""


def live2d_parameter_alias_contract() -> dict[str, Any]:
    """Return canonical Live2D parameter ids and fallback aliases used by mocap."""
    return {
        "schema": LIVE2D_PARAMETER_ALIAS_SCHEMA,
        "canonical_parameters": list(LIVE2D_PARAMETER_ALIASES.keys()),
        "aliases": {key: list(values) for key, values in LIVE2D_PARAMETER_ALIASES.items()},
        "rules": [
            "Canonical Cubism ids are kept.",
            "Alias tracks are copied from canonical tracks when the target model may use alternate ids.",
            "Unknown ids are harmless at render time; the Live2D renderer skips parameters the model does not expose.",
        ],
    }


def expand_live2d_parameter_aliases(
    parameter_tracks: Mapping[str, Any] | None,
    *,
    available_parameter_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Copy canonical mocap tracks to common Live2D parameter aliases."""
    tracks = {str(key): list(value or []) for key, value in dict(parameter_tracks or {}).items()}
    available = {str(row) for row in available_parameter_ids} if available_parameter_ids is not None else None
    added: dict[str, list[str]] = {}
    for canonical, aliases in LIVE2D_PARAMETER_ALIASES.items():
        source = tracks.get(canonical)
        if not source:
            continue
        for alias in aliases:
            if alias in tracks:
                continue
            if available is not None and alias not in available:
                continue
            tracks[alias] = [dict(row) if isinstance(row, Mapping) else row for row in source]
            added.setdefault(canonical, []).append(alias)
    return {
        "schema": LIVE2D_PARAMETER_ALIAS_SCHEMA,
        "parameter_keyframes": tracks,
        "aliases_added": added,
        "alias_count": sum(len(rows) for rows in added.values()),
    }


def apply_live2d_parameter_aliases_to_clip(
    clip: Any,
    *,
    available_parameter_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    if clip is None:
        return {"ok": False, "reason": "missing_clip"}
    result = expand_live2d_parameter_aliases(
        getattr(clip, "mocap_parameter_keyframes", {}) or {},
        available_parameter_ids=available_parameter_ids,
    )
    try:
        clip.mocap_parameter_keyframes = dict(result.get("parameter_keyframes") or {})
        clip.mocap_parameter_aliases = dict(result.get("aliases_added") or {})
    except Exception:
        pass
    return {
        "ok": True,
        "schema": LIVE2D_PARAMETER_ALIAS_SCHEMA,
        "aliases_added": dict(result.get("aliases_added") or {}),
        "alias_count": int(result.get("alias_count", 0) or 0),
        "parameter_track_count": len(dict(result.get("parameter_keyframes") or {})),
    }


def apply_performance_source_framing_to_clip(
    clip: Any,
    framing_payload: Mapping[str, Any],
    *,
    source_path: str | Path = "",
    preset: str = "bust_up",
    replace_transform: bool = True,
    subject_type: str = "",
    position_gain_x: float = 0.18,
    position_gain_y: float = 0.075,
    scale_power: float = 0.72,
) -> dict[str, Any]:
    """Apply source camera/framing guidance to a Live2D actor clip.

    Source framing is a camera contract used by the VTuber/VRM UI. Live2D has no
    equivalent 3D camera here, so the bridge stores the original payload and
    bakes a conservative 2D placement path into pos_x/pos_y/scale keyframes.
    """
    if clip is None:
        return {"ok": False, "reason": "missing_clip"}
    if not isinstance(framing_payload, Mapping) or not framing_payload:
        return {"ok": False, "reason": "missing_framing_payload"}

    samples = _extract_framing_samples(framing_payload)
    if not samples:
        return {"ok": False, "reason": "no_model_view_samples"}

    reference = _reference_values(framing_payload, preset=preset)
    normalized_subject = normalize_performance_subject_type(subject_type, framing_payload) or "unknown"
    has_subject_guidance = bool(str(subject_type or "").strip() or _subject_type_from_payload(framing_payload))
    constraints = _framing_constraints(
        normalized_subject,
        position_gain_x=position_gain_x,
        position_gain_y=position_gain_y,
        scale_power=scale_power,
        guided=has_subject_guidance,
    )
    base_x = _float(getattr(clip, "pos_x", 0.5), 0.5)
    base_y = _float(getattr(clip, "pos_y", 0.55), 0.55)
    base_scale = max(0.001, _float(getattr(clip, "scale", 1.0), 1.0))

    pos_x_keys: list[Live2DKeyframe] = []
    pos_y_keys: list[Live2DKeyframe] = []
    scale_keys: list[Live2DKeyframe] = []
    camera_pitch_keys: list[dict[str, Any]] = []
    lower_occlusion_keys: list[dict[str, Any]] = []
    last_view: dict[str, Any] = {}
    last_rotation: list[float] = []

    for sample in samples:
        time_ms = max(0, _int(sample.get("time_ms"), 0))
        view = dict(sample.get("model_view") or {})
        rotation = [float(v) for v in list(sample.get("track_rotation") or [])[:3]]
        if not view:
            continue
        last_view = view
        if rotation:
            last_rotation = rotation
        pos_x, pos_y, scale = _model_view_to_live2d_transform(
            view,
            base_x=base_x,
            base_y=base_y,
            base_scale=base_scale,
            reference=reference,
            position_gain_x=float(constraints["position_gain_x"]),
            position_gain_y=float(constraints["position_gain_y"]),
            scale_power=float(constraints["scale_power"]),
            actor_transform_locked=bool(constraints["actor_transform_locked"]),
            scale_delta_limit=constraints.get("scale_delta_limit"),
        )
        pos_x_keys.append(Live2DKeyframe(time_ms=time_ms, value=pos_x, curve="smoothstep"))
        pos_y_keys.append(Live2DKeyframe(time_ms=time_ms, value=pos_y, curve="smoothstep"))
        scale_keys.append(Live2DKeyframe(time_ms=time_ms, value=scale, curve="smoothstep"))
        if rotation:
            camera_pitch_keys.append({"time_ms": time_ms, "value": round(float(rotation[0]), 5), "curve": "smoothstep"})
        if "lower_occlusion_y" in view:
            lower_occlusion_keys.append(
                {
                    "time_ms": time_ms,
                    "value": round(_float(view.get("lower_occlusion_y"), 1.0), 5),
                    "curve": "smoothstep",
                }
            )

    if not pos_x_keys:
        return {"ok": False, "reason": "no_transform_keys"}

    if replace_transform:
        clip.kf_pos_x = pos_x_keys
        clip.kf_pos_y = pos_y_keys
        clip.kf_scale = scale_keys
    else:
        clip.kf_pos_x = list(getattr(clip, "kf_pos_x", []) or []) + pos_x_keys
        clip.kf_pos_y = list(getattr(clip, "kf_pos_y", []) or []) + pos_y_keys
        clip.kf_scale = list(getattr(clip, "kf_scale", []) or []) + scale_keys

    payload = dict(framing_payload)
    clip.performance_source_path = str(source_path or payload.get("source_path") or "")
    clip.performance_source_framing_payload = payload
    clip.performance_source_model_view = dict(last_view)
    clip.performance_source_track_rotation = list(last_rotation)
    clip.performance_source_subject_type = normalized_subject
    clip.performance_source_mapping_constraints = dict(constraints)
    clip.performance_source_framing_keyframes = {
        "pos_x": [_key_to_dict(row) for row in pos_x_keys],
        "pos_y": [_key_to_dict(row) for row in pos_y_keys],
        "scale": [_key_to_dict(row) for row in scale_keys],
        "camera_pitch": camera_pitch_keys,
        "lower_occlusion_y": lower_occlusion_keys,
    }

    return {
        "ok": True,
        "schema": LIVE2D_PERFORMANCE_SOURCE_SCHEMA,
        "source_path": clip.performance_source_path,
        "sample_count": len(pos_x_keys),
        "pos_keys": len(pos_x_keys),
        "scale_keys": len(scale_keys),
        "model_view": dict(last_view),
        "track_rotation": list(last_rotation),
        "subject_type": normalized_subject,
        "lower_occlusion_y": last_view.get("lower_occlusion_y"),
        "program_output": False,
        "mapping": {
            "method": "source_model_view_to_live2d_transform_keyframes",
            "reference": dict(reference),
            "position_gain_x": float(constraints["position_gain_x"]),
            "position_gain_y": float(constraints["position_gain_y"]),
            "scale_power": float(constraints["scale_power"]),
            "subject_type": normalized_subject,
            "movement_constraints": dict(constraints),
        },
    }


def _extract_framing_samples(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def _append(row: Mapping[str, Any], *, fallback_time_ms: int = 0) -> None:
        view, rotation = _view_and_rotation(row)
        if not view:
            return
        samples.append(
            {
                "time_ms": _int(row.get("time_ms"), fallback_time_ms),
                "model_view": view,
                "track_rotation": rotation,
            }
        )

    selected = payload.get("selected_frames")
    if isinstance(selected, list):
        for row in selected:
            if isinstance(row, Mapping):
                _append(row, fallback_time_ms=_int(payload.get("time_ms"), 0))
    frames = payload.get("frames")
    if isinstance(frames, list):
        for row in frames:
            if isinstance(row, Mapping):
                _append(row, fallback_time_ms=_int(payload.get("time_ms"), 0))
    _append(payload, fallback_time_ms=_int(payload.get("time_ms"), 0))

    unique: dict[int, dict[str, Any]] = {}
    for sample in samples:
        unique[_int(sample.get("time_ms"), 0)] = sample
    return [unique[key] for key in sorted(unique)]


def _view_and_rotation(row: Mapping[str, Any]) -> tuple[dict[str, Any], list[float]]:
    candidates = [
        row,
        row.get("final") if isinstance(row.get("final"), Mapping) else None,
        row.get("final_framing") if isinstance(row.get("final_framing"), Mapping) else None,
        row.get("framing_control") if isinstance(row.get("framing_control"), Mapping) else None,
        row.get("framing") if isinstance(row.get("framing"), Mapping) else None,
        row.get("automatic") if isinstance(row.get("automatic"), Mapping) else None,
    ]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        nested_final = candidate.get("final")
        if isinstance(nested_final, Mapping):
            view = dict(nested_final.get("model_view") or {})
            rotation = _rotation(nested_final.get("track_rotation"))
            if view:
                return view, rotation
        view = dict(candidate.get("model_view") or {})
        if view:
            return view, _rotation(candidate.get("track_rotation"))
    return {}, []


def _reference_values(payload: Mapping[str, Any], *, preset: str) -> dict[str, float]:
    try:
        from app.vtuber.source_framing import preset_for_name

        cfg = preset_for_name(str(payload.get("preset") or preset or "bust_up"))
        return {"zoom": float(cfg.base_zoom), "pan_x": 0.0, "pan_y": float(cfg.base_pan_y)}
    except Exception:
        return {"zoom": 7.1, "pan_x": 0.0, "pan_y": -1.7}


def _subject_type_from_payload(payload: Mapping[str, Any]) -> str:
    candidates: list[Any] = [
        payload.get("subject_type"),
        payload.get("source_subject_type"),
        payload.get("shot_profile"),
        payload.get("profile"),
    ]
    for key in ("retargeting", "tracking", "source_subject", "shot_classification"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            candidates.extend(
                [
                    nested.get("subject_type"),
                    nested.get("shot_profile"),
                    nested.get("profile"),
                    nested.get("type"),
                ]
            )
    for key in ("final", "final_framing", "framing_control", "framing", "automatic"):
        nested = payload.get(key)
        if isinstance(nested, Mapping):
            nested_type = _subject_type_from_payload(nested)
            if nested_type:
                candidates.append(nested_type)
    for candidate in candidates:
        text = str(candidate or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if text:
            return text
    return ""


def _framing_constraints(
    subject_type: str,
    *,
    position_gain_x: float,
    position_gain_y: float,
    scale_power: float,
    guided: bool,
) -> dict[str, Any]:
    subject = normalize_performance_subject_type(subject_type) or "unknown"
    if subject == "face_only":
        return {
            "subject_type": subject,
            "actor_transform_locked": True,
            "position_gain_x": 0.0,
            "position_gain_y": 0.0,
            "scale_power": 0.0,
            "scale_delta_limit": 0.0,
            "reason": "face_only_uses_face_eye_mouth_parameters_without_actor_drift",
        }
    if subject == "upper_body":
        return {
            "subject_type": subject,
            "actor_transform_locked": False,
            "position_gain_x": float(position_gain_x) * 0.35,
            "position_gain_y": float(position_gain_y) * 0.30,
            "scale_power": float(scale_power) * 0.25,
            "scale_delta_limit": 0.02,
            "reason": "upper_body_damps_actor_translation_and_zoom",
        }
    if subject == "full_body":
        return {
            "subject_type": subject,
            "actor_transform_locked": False,
            "position_gain_x": float(position_gain_x),
            "position_gain_y": float(position_gain_y),
            "scale_power": float(scale_power),
            "scale_delta_limit": None,
            "reason": "full_body_allows_actor_translation_and_zoom",
        }
    if guided:
        return {
            "subject_type": "unknown",
            "actor_transform_locked": False,
            "position_gain_x": float(position_gain_x) * 0.50,
            "position_gain_y": float(position_gain_y) * 0.45,
            "scale_power": float(scale_power) * 0.50,
            "scale_delta_limit": 0.03,
            "reason": "unknown_subject_uses_conservative_actor_transform",
        }
    return {
        "subject_type": "unknown",
        "actor_transform_locked": False,
        "position_gain_x": float(position_gain_x),
        "position_gain_y": float(position_gain_y),
        "scale_power": float(scale_power),
        "scale_delta_limit": None,
        "reason": "subject_type_not_provided_preserves_existing_framing_behavior",
    }


def _model_view_to_live2d_transform(
    view: Mapping[str, Any],
    *,
    base_x: float,
    base_y: float,
    base_scale: float,
    reference: Mapping[str, float],
    position_gain_x: float,
    position_gain_y: float,
    scale_power: float,
    actor_transform_locked: bool = False,
    scale_delta_limit: Any = None,
) -> tuple[float, float, float]:
    if bool(actor_transform_locked):
        return round(base_x, 5), round(base_y, 5), round(base_scale, 5)
    ref_zoom = max(0.001, _float(reference.get("zoom"), 7.1))
    ref_pan_x = _float(reference.get("pan_x"), 0.0)
    ref_pan_y = _float(reference.get("pan_y"), -1.7)
    zoom = max(0.001, _float(view.get("zoom"), ref_zoom))
    pan_x = _float(view.get("pan_x"), ref_pan_x)
    pan_y = _float(view.get("pan_y"), ref_pan_y)
    pos_x = _clamp(base_x + (pan_x - ref_pan_x) * float(position_gain_x), 0.05, 0.95)
    pos_y = _clamp(base_y - (pan_y - ref_pan_y) * float(position_gain_y), 0.05, 0.95)
    scale = base_scale * ((zoom / ref_zoom) ** float(scale_power))
    if scale_delta_limit is not None:
        limit = max(0.0, _float(scale_delta_limit, 0.0))
        scale = _clamp(scale, base_scale * (1.0 - limit), base_scale * (1.0 + limit))
    scale = _clamp(scale, 0.20, 4.0)
    return round(pos_x, 5), round(pos_y, 5), round(scale, 5)


def _rotation(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        out: list[float] = []
        for row in list(value)[:3]:
            out.append(_float(row, 0.0))
        while len(out) < 3:
            out.append(0.0)
        return out
    return []


def _key_to_dict(key: Live2DKeyframe) -> dict[str, Any]:
    return {"time_ms": int(key.time_ms), "value": float(key.value), "curve": str(key.curve)}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))
