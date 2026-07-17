"""Animation sequence contracts for the Action Sequencer owner preview."""
from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any, Mapping


ACTION_SEQUENCE_SCHEMA = "tigerstudio.action_sequencer.animation_sequence.v1"
ACTION_SEQUENCE_REFERENCE_PIPELINE = "UAssetInspector SamplePalette -> Bones UBO -> skinned shader"
DEFAULT_ANIMATION_PREVIEW_BACKEND = "uasset_inspector_gpu_bone_palette"


def build_owner_animation_sequence(
    clip: Mapping[str, Any] | None,
    *,
    animation_path: str | Path | None = None,
    play_once: bool = True,
    apply_frame_ms: int = 0,
    backend: str = DEFAULT_ANIMATION_PREVIEW_BACKEND,
) -> dict[str, Any]:
    """Normalize an exported Unreal animation clip into a preview playback plan.

    This intentionally does not enable AR/PBR skeletal deformation yet. The plan
    is the stable handoff to the GPU bone-palette renderer so selecting an
    AnimSequence never falls back to the old fragile static-mesh deformation path.
    """

    clip_data = dict(clip or {})
    curves = _mapping(clip_data.get("model_curves"))
    bone_names = _bone_names(clip_data, curves)
    sample_times = _sample_times_from_curves(curves)

    duration_ms = _float(clip_data.get("duration_ms"), 0.0)
    if duration_ms <= 0.0 and sample_times:
        duration_ms = max(sample_times)

    if not sample_times:
        sample_times = _sample_times_from_counts(clip_data, duration_ms)
    if duration_ms <= 0.0 and sample_times:
        duration_ms = max(sample_times)

    clamped_apply_ms = _clamp(float(apply_frame_ms), 0.0, max(duration_ms, 0.0))
    selected_sample_ms = _nearest_sample(sample_times, clamped_apply_ms)
    animated_bone_count = sum(1 for curve in curves.values() if _curve_has_samples(curve))
    diagnostics: list[str] = []
    if not curves:
        diagnostics.append("No model_curves were exported for this AnimSequence.")
    if not sample_times:
        diagnostics.append("No sampled frames are available for playback.")
    if not bone_names and curves:
        diagnostics.append("Bone names were not exported; curve keys are used as fallback names.")

    path_text = str(animation_path or clip_data.get("source_asset_path") or clip_data.get("asset_path") or "")
    clip_id = str(clip_data.get("id") or clip_data.get("name") or (Path(path_text).stem if path_text else "animation"))

    plan = {
        "schema": ACTION_SEQUENCE_SCHEMA,
        "status": "ready" if sample_times else "diagnostic_only",
        "source": {
            "id": clip_id,
            "name": str(clip_data.get("name") or clip_id),
            "animation_path": path_text,
            "source_mode": str(clip_data.get("source_mode") or "unknown"),
            "export_path": str(clip_data.get("_export_path") or clip_data.get("export_path") or ""),
        },
        "playback": {
            "mode": "play_once" if play_once else "hold_frame",
            "duration_ms": round(duration_ms, 3),
            "apply_frame_ms": round(clamped_apply_ms, 3),
            "selected_sample_ms": round(selected_sample_ms, 3) if selected_sample_ms is not None else None,
            "sample_count": len(sample_times),
            "sample_times_ms": [round(value, 3) for value in sample_times],
        },
        "bone_palette": {
            "backend": backend,
            "bone_count": len(bone_names),
            "animated_bone_count": animated_bone_count,
            "bone_names": bone_names,
        },
        "root_motion": _root_motion_summary(curves),
        "ar_pbr_deformation_enabled": False,
        "requires_gpu_palette_renderer": True,
        "preview_backend": backend,
        "reference_pipeline": ACTION_SEQUENCE_REFERENCE_PIPELINE,
        "diagnostics": diagnostics,
    }
    return plan


def animation_sequence_summary(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(plan or {})
    playback = _mapping(data.get("playback"))
    palette = _mapping(data.get("bone_palette"))
    return {
        "status": str(data.get("status") or "unknown"),
        "duration_ms": playback.get("duration_ms", 0.0),
        "sample_count": int(playback.get("sample_count") or 0),
        "bone_count": int(palette.get("bone_count") or 0),
        "animated_bone_count": int(palette.get("animated_bone_count") or 0),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, low: float, high: float) -> float:
    if high < low:
        high = low
    return max(low, min(high, value))


def _bone_names(clip: Mapping[str, Any], curves: Mapping[str, Any]) -> list[str]:
    raw_names = clip.get("bone_names")
    if isinstance(raw_names, (list, tuple)):
        names = [str(name) for name in raw_names if str(name)]
        if names:
            return names
    names = []
    for key, value in curves.items():
        curve = _mapping(value)
        names.append(str(curve.get("bone_name") or key))
    return names


def _sample_times_from_counts(clip: Mapping[str, Any], duration_ms: float) -> list[float]:
    count = int(_float(clip.get("sampled_frame_count") or clip.get("frame_count"), 0.0))
    if count <= 0:
        return []
    if count == 1 or duration_ms <= 0.0:
        return [0.0]
    step = duration_ms / float(count - 1)
    return [step * index for index in range(count)]


def _sample_times_from_curves(curves: Mapping[str, Any]) -> list[float]:
    times: set[float] = set()
    for value in curves.values():
        curve = _mapping(value)
        for channel in ("translation", "rotation_quat", "scale"):
            block = _mapping(curve.get(channel))
            for samples in block.values():
                if not isinstance(samples, (list, tuple)):
                    continue
                for sample in samples:
                    if isinstance(sample, (list, tuple)) and sample:
                        times.add(_float(sample[0], 0.0))
    return sorted(times)


def _curve_has_samples(value: Any) -> bool:
    curve = _mapping(value)
    for channel in ("translation", "rotation_quat", "scale"):
        block = _mapping(curve.get(channel))
        for samples in block.values():
            if isinstance(samples, (list, tuple)) and samples:
                return True
    return False


def _nearest_sample(sample_times: list[float], time_ms: float) -> float | None:
    if not sample_times:
        return None
    return min(sample_times, key=lambda sample: abs(sample - time_ms))


def _root_motion_summary(curves: Mapping[str, Any]) -> dict[str, Any]:
    root_key, root_curve = _root_curve(curves)
    if root_curve is None:
        return {
            "root_bone": "",
            "translation_start": [0.0, 0.0, 0.0],
            "translation_end": [0.0, 0.0, 0.0],
            "translation_delta": [0.0, 0.0, 0.0],
            "horizontal_distance": 0.0,
        }

    start = _vec3_endpoint(root_curve, first=True)
    end = _vec3_endpoint(root_curve, first=False)
    delta = [round(end[index] - start[index], 6) for index in range(3)]
    horizontal = sqrt(delta[0] * delta[0] + delta[1] * delta[1])
    return {
        "root_bone": str(_mapping(root_curve).get("bone_name") or root_key),
        "translation_start": [round(value, 6) for value in start],
        "translation_end": [round(value, 6) for value in end],
        "translation_delta": delta,
        "horizontal_distance": round(horizontal, 6),
    }


def _root_curve(curves: Mapping[str, Any]) -> tuple[str, Mapping[str, Any] | None]:
    preferred = {"root", "pelvis", "hips", "bone_0"}
    fallback_key = ""
    fallback_curve: Mapping[str, Any] | None = None
    for key, value in curves.items():
        curve = _mapping(value)
        name = str(curve.get("bone_name") or key)
        if fallback_curve is None:
            fallback_key = str(key)
            fallback_curve = curve
        if name.casefold() in preferred or str(key).casefold() in preferred:
            return str(key), curve
    return fallback_key, fallback_curve


def _vec3_endpoint(curve: Mapping[str, Any], *, first: bool) -> list[float]:
    translation = _mapping(_mapping(curve).get("translation"))
    values = []
    for axis in ("x", "y", "z"):
        samples = translation.get(axis)
        if isinstance(samples, (list, tuple)) and samples:
            sample = samples[0 if first else -1]
            if isinstance(sample, (list, tuple)) and len(sample) >= 2:
                values.append(_float(sample[1], 0.0))
            else:
                values.append(0.0)
        else:
            values.append(0.0)
    return values


__all__ = [
    "ACTION_SEQUENCE_REFERENCE_PIPELINE",
    "ACTION_SEQUENCE_SCHEMA",
    "DEFAULT_ANIMATION_PREVIEW_BACKEND",
    "animation_sequence_summary",
    "build_owner_animation_sequence",
]
