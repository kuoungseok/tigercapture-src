"""Deterministic stop-motion timing, poses, materials, and audio snapping."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
import random
from typing import Any, Iterable, Mapping, MutableMapping

from .craft_style import make_craft_style_effect
from .schema import Keyframe, MotionComposition, MotionEffectRef, MotionLayer, new_motion_id


STOP_MOTION_SCHEMA = "tigerstudio.motion.stop_motion.v1"
STOP_MOTION_POSE_SCHEMA = "tigerstudio.motion.stop_motion.pose.v1"
STOP_MOTION_KEY = "stop_motion"
STOP_MOTION_POSES_KEY = "stop_motion_poses"

MOTION_STYLES = ("none", "contact_settle", "overshoot", "replacement_pop")
MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "clay": {
        "craft_preset": "handmade",
        "craft": {
            "grain_amount": 0.12,
            "grain_size": 4.8,
            "grain_cadence": 12.0,
            "edge_roughness": 0.07,
            "misregistration": 0.08,
            "warmth": 0.12,
        },
        "boil": 0.28,
        "shadow": {"offset_x": 7.0, "offset_y": 14.0, "radius": 4.0, "opacity": 0.52},
    },
    "felt": {
        "craft_preset": "rough_cut",
        "craft": {
            "grain_amount": 0.24,
            "grain_size": 5.4,
            "grain_cadence": 10.0,
            "edge_roughness": 0.24,
            "misregistration": 0.18,
            "warmth": 0.08,
        },
        "boil": 0.38,
        "shadow": {"offset_x": 6.0, "offset_y": 11.0, "radius": 3.0, "opacity": 0.46},
    },
    "cardboard": {
        "craft_preset": "luxury_paper",
        "craft": {
            "grain_amount": 0.16,
            "grain_size": 6.4,
            "grain_cadence": 8.0,
            "edge_roughness": 0.18,
            "misregistration": 0.32,
            "warmth": 0.19,
        },
        "boil": 0.18,
        "shadow": {"offset_x": 10.0, "offset_y": 16.0, "radius": 2.0, "opacity": 0.58},
    },
    "painted_wood": {
        "craft_preset": "warm_film",
        "craft": {
            "grain_amount": 0.1,
            "grain_size": 3.8,
            "grain_cadence": 8.0,
            "edge_roughness": 0.1,
            "misregistration": 0.14,
            "warmth": 0.24,
        },
        "boil": 0.14,
        "shadow": {"offset_x": 8.0, "offset_y": 13.0, "radius": 3.0, "opacity": 0.55},
    },
}


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _vector(value: Any, fallback: tuple[float, float]) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [_number(value[0], fallback[0]), _number(value[1], fallback[1])]
    return [float(fallback[0]), float(fallback[1])]


def _default_settings(composition: MotionComposition) -> dict[str, Any]:
    return {
        "schema": STOP_MOTION_SCHEMA,
        "enabled": False,
        "exposure_frames": 2,
        "base_fps": float(composition.fps),
        "pose_jitter_px": 0.0,
        "rotation_jitter_deg": 0.0,
        "scale_jitter": 0.0,
        "material_boil": 0.0,
        "seed": 17,
        "motion_style": "none",
        "settle_ms": 520,
        "onion_skin_frames": 1,
        "focus_breathing": 0.0,
        "exposure_flicker": 0.0,
        "gate_weave": 0.0,
    }


def normalize_stop_motion(
    composition: MotionComposition,
    values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = {**_default_settings(composition), **dict(values or {})}
    style = str(source.get("motion_style") or "none").strip().lower()
    if style not in MOTION_STYLES:
        raise ValueError(f"unsupported stop-motion style: {style}")
    return {
        "schema": STOP_MOTION_SCHEMA,
        "enabled": bool(source.get("enabled", False)),
        "exposure_frames": max(1, min(3, int(source.get("exposure_frames", 2) or 2))),
        "base_fps": max(1.0, min(240.0, _number(source.get("base_fps"), composition.fps))),
        "pose_jitter_px": max(0.0, min(64.0, _number(source.get("pose_jitter_px"), 0.0))),
        "rotation_jitter_deg": max(
            0.0,
            min(12.0, _number(source.get("rotation_jitter_deg"), 0.0)),
        ),
        "scale_jitter": max(0.0, min(0.25, _number(source.get("scale_jitter"), 0.0))),
        "material_boil": max(0.0, min(1.0, _number(source.get("material_boil"), 0.0))),
        "seed": max(0, min(2_147_483_647, int(source.get("seed", 17) or 17))),
        "motion_style": style,
        "settle_ms": max(80, min(5000, int(source.get("settle_ms", 520) or 520))),
        "onion_skin_frames": max(0, min(4, int(source.get("onion_skin_frames", 1) or 0))),
        "focus_breathing": max(0.0, min(1.0, _number(source.get("focus_breathing"), 0.0))),
        "exposure_flicker": max(0.0, min(1.0, _number(source.get("exposure_flicker"), 0.0))),
        "gate_weave": max(0.0, min(1.0, _number(source.get("gate_weave"), 0.0))),
    }


def composition_stop_motion(composition: MotionComposition) -> dict[str, Any]:
    raw = composition.metadata.get(STOP_MOTION_KEY)
    return normalize_stop_motion(
        composition,
        raw if isinstance(raw, Mapping) else None,
    )


def effective_stop_motion(
    composition: MotionComposition,
    layer: MotionLayer | None = None,
) -> dict[str, Any]:
    values = composition_stop_motion(composition)
    if layer is not None:
        override = layer.metadata.get(STOP_MOTION_KEY)
        if isinstance(override, Mapping):
            values = normalize_stop_motion(composition, {**values, **dict(override)})
    return values


def set_stop_motion(
    composition: MotionComposition,
    values: Mapping[str, Any],
    *,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    ids = {str(item) for item in layer_ids if str(item)}
    if ids:
        known = {layer.id for layer in composition.layers}
        missing = sorted(ids - known)
        if missing:
            raise KeyError(f"unknown stop-motion layers: {missing}")
        updated: list[str] = []
        for layer in composition.layers:
            if layer.id not in ids:
                continue
            current = effective_stop_motion(composition, layer)
            layer.metadata[STOP_MOTION_KEY] = normalize_stop_motion(
                composition,
                {**current, **dict(values)},
            )
            updated.append(layer.id)
        return {
            "scope": "layers",
            "layer_ids": updated,
            "settings": {
                layer.id: deepcopy(layer.metadata[STOP_MOTION_KEY])
                for layer in composition.layers
                if layer.id in ids
            },
        }
    current = composition_stop_motion(composition)
    settings = normalize_stop_motion(composition, {**current, **dict(values)})
    composition.metadata[STOP_MOTION_KEY] = settings
    return {"scope": "composition", "settings": deepcopy(settings)}


def stop_motion_exposure_ms(
    composition: MotionComposition,
    layer: MotionLayer | None = None,
) -> float:
    settings = effective_stop_motion(composition, layer)
    return 1000.0 / settings["base_fps"] * settings["exposure_frames"]


def stop_motion_sample_time(
    composition: MotionComposition,
    layer: MotionLayer | None,
    time_ms: float,
) -> float:
    settings = effective_stop_motion(composition, layer)
    if not settings["enabled"]:
        return float(time_ms)
    origin = float(layer.in_ms if layer is not None else 0.0)
    exposure = stop_motion_exposure_ms(composition, layer)
    elapsed = max(0.0, float(time_ms) - origin)
    return origin + math.floor((elapsed + 1e-7) / exposure) * exposure


def stop_motion_sample_index(
    composition: MotionComposition,
    layer: MotionLayer | None,
    time_ms: float,
) -> int:
    origin = float(layer.in_ms if layer is not None else 0.0)
    return max(
        0,
        int(
            math.floor(
                (stop_motion_sample_time(composition, layer, time_ms) - origin)
                / max(1e-9, stop_motion_exposure_ms(composition, layer))
                + 1e-7
            )
        ),
    )


def apply_stop_motion_transform(
    composition: MotionComposition,
    layer: MotionLayer,
    values: MutableMapping[str, Any],
    time_ms: float,
) -> MutableMapping[str, Any]:
    settings = effective_stop_motion(composition, layer)
    if not settings["enabled"]:
        return values
    sample = stop_motion_sample_index(composition, layer, time_ms)
    seed = settings["seed"] + int(sha256(layer.id.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed + sample * 104729)
    position = _vector(values.get("position"), (0.0, 0.0))
    scale = _vector(values.get("scale"), (1.0, 1.0))
    jitter = settings["pose_jitter_px"]
    position[0] += rng.uniform(-jitter, jitter)
    position[1] += rng.uniform(-jitter, jitter)
    values["rotation"] = _number(values.get("rotation"), 0.0) + rng.uniform(
        -settings["rotation_jitter_deg"],
        settings["rotation_jitter_deg"],
    )
    scale_noise = rng.uniform(-settings["scale_jitter"], settings["scale_jitter"])
    scale = [scale[0] * (1.0 + scale_noise), scale[1] * (1.0 + scale_noise)]
    style = settings["motion_style"]
    local_ms = max(0.0, stop_motion_sample_time(composition, layer, time_ms) - layer.in_ms)
    if style == "contact_settle":
        phase = min(1.0, local_ms / settings["settle_ms"])
        decay = (1.0 - phase) ** 2
        position[1] -= math.cos(phase * math.pi * 3.0) * 18.0 * decay
        scale_factor = 1.0 + math.sin(phase * math.pi * 2.0) * 0.055 * decay
        scale = [scale[0] * scale_factor, scale[1] * scale_factor]
    elif style == "overshoot":
        phase = min(1.0, local_ms / settings["settle_ms"])
        decay = math.exp(-phase * 4.5)
        values["rotation"] += math.sin(phase * math.pi * 4.0) * 7.0 * decay
        scale_factor = 1.0 + math.sin(phase * math.pi * 3.0) * 0.09 * decay
        scale = [scale[0] * scale_factor, scale[1] * scale_factor]
    elif style == "replacement_pop":
        pop = (rng.random() * 2.0 - 1.0) * 0.045
        scale = [scale[0] * (1.0 + pop), scale[1] * (1.0 + pop)]
    values["position"] = position
    values["scale"] = scale
    return values


def _pose_rows(composition: MotionComposition) -> list[dict[str, Any]]:
    rows = composition.metadata.get(STOP_MOTION_POSES_KEY)
    if not isinstance(rows, list):
        rows = []
        composition.metadata[STOP_MOTION_POSES_KEY] = rows
    return rows


def capture_stop_motion_pose(
    composition: MotionComposition,
    *,
    name: str,
    time_ms: int,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    from .evaluator import evaluate_composition

    ids = {str(item) for item in layer_ids if str(item)}
    states = evaluate_composition(composition, float(time_ms))
    layers = [
        {
            "layer_id": state.id,
            "position": list(state.position),
            "scale": list(state.scale),
            "rotation": state.rotation,
            "opacity": state.opacity,
            "anchor": list(state.anchor),
        }
        for state in states
        if state.active and (not ids or state.id in ids)
    ]
    pose = {
        "schema": STOP_MOTION_POSE_SCHEMA,
        "id": new_motion_id("stop_pose"),
        "name": str(name or "Stop Motion Pose"),
        "time_ms": int(time_ms),
        "sample_time_ms": stop_motion_sample_time(composition, None, time_ms),
        "layers": layers,
    }
    _pose_rows(composition).append(pose)
    return deepcopy(pose)


def _set_hold_keyframe(prop, time_ms: int, value: Any) -> str:
    existing = next((item for item in prop.keyframes if item.time_ms == time_ms), None)
    if existing is not None:
        existing.value = deepcopy(value)
        existing.interpolation = "hold"
        return existing.id
    key = Keyframe(time_ms=int(time_ms), value=deepcopy(value), interpolation="hold")
    prop.keyframes.append(key)
    prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
    return key.id


def apply_stop_motion_pose(
    composition: MotionComposition,
    pose_id: str,
    *,
    time_ms: int | None = None,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    pose = next(
        (item for item in _pose_rows(composition) if str(item.get("id") or "") == pose_id),
        None,
    )
    if pose is None:
        raise KeyError(f"unknown stop-motion pose: {pose_id}")
    selected = {str(item) for item in layer_ids if str(item)}
    layers = {layer.id: layer for layer in composition.layers}
    applied: list[dict[str, Any]] = []
    for row in pose.get("layers", []):
        layer_id = str(row.get("layer_id") or "")
        if selected and layer_id not in selected:
            continue
        layer = layers.get(layer_id)
        if layer is None:
            continue
        values = {
            "position": row.get("position"),
            "scale": row.get("scale"),
            "rotation": row.get("rotation"),
            "opacity": row.get("opacity"),
            "anchor": row.get("anchor"),
        }
        key_ids: dict[str, str] = {}
        for name, value in values.items():
            prop = layer.transform.properties()[name]
            if time_ms is None:
                prop.default = deepcopy(value)
            else:
                key_ids[name] = _set_hold_keyframe(prop, int(time_ms), value)
        applied.append({"layer_id": layer.id, "keyframe_ids": key_ids})
    return {
        "pose_id": pose_id,
        "time_ms": time_ms,
        "applied": applied,
    }


def set_stop_motion_material(
    composition: MotionComposition,
    layer_ids: Iterable[str],
    *,
    preset: str,
    seed: int = 17,
) -> dict[str, Any]:
    preset_id = str(preset or "").strip().lower()
    if preset_id not in MATERIAL_PRESETS:
        raise ValueError(f"unsupported stop-motion material: {preset}")
    ids = {str(item) for item in layer_ids if str(item)}
    settings = MATERIAL_PRESETS[preset_id]
    updated: list[str] = []
    for layer in composition.layers:
        if layer.id not in ids:
            continue
        layer.effects = [
            effect
            for effect in layer.effects
            if not bool(effect.metadata.get("stop_motion_material"))
        ]
        craft = make_craft_style_effect(
            {**settings["craft"], "seed": int(seed), "seed_locked": True},
            preset=str(settings["craft_preset"]),
        )
        craft.metadata["stop_motion_material"] = True
        craft.metadata["material_preset"] = preset_id
        shadow = MotionEffectRef.from_dict({
            "kind": "drop_shadow",
            "params": {
                key: {"default": value}
                for key, value in settings["shadow"].items()
            },
            "metadata": {
                "stop_motion_material": True,
                "material_preset": preset_id,
                "contact_shadow": True,
            },
        })
        layer.effects.extend([shadow, craft])
        layer.metadata["stop_motion_material"] = {
            "schema": STOP_MOTION_SCHEMA,
            "preset": preset_id,
            "seed": int(seed),
            "material_boil": settings["boil"],
            "lighting": "miniature_key_fill_rim",
        }
        current = effective_stop_motion(composition, layer)
        layer.metadata[STOP_MOTION_KEY] = normalize_stop_motion(
            composition,
            {
                **current,
                "enabled": True,
                "material_boil": settings["boil"],
                "seed": int(seed),
            },
        )
        updated.append(layer.id)
    if len(updated) != len(ids):
        missing = sorted(ids - set(updated))
        raise KeyError(f"unknown stop-motion material layers: {missing}")
    return {
        "preset": preset_id,
        "layer_ids": updated,
        "material": deepcopy(settings),
    }


def snap_stop_motion_to_audio(
    composition: MotionComposition,
    *,
    transient_times_ms: Iterable[int],
    layer_ids: Iterable[str] = (),
    threshold_ms: int = 120,
) -> dict[str, Any]:
    transients = sorted({
        max(0, min(composition.duration_ms, int(item)))
        for item in transient_times_ms
    })
    ids = {str(item) for item in layer_ids if str(item)}
    moves: list[dict[str, Any]] = []
    for layer in composition.layers:
        if ids and layer.id not in ids:
            continue
        exposure = stop_motion_exposure_ms(composition, layer)
        for property_name, prop in layer.transform.properties().items():
            occupied = {key.time_ms for key in prop.keyframes}
            for key in prop.keyframes:
                nearest = min(transients, key=lambda item: abs(item - key.time_ms), default=None)
                if nearest is None or abs(nearest - key.time_ms) > int(threshold_ms):
                    continue
                target = int(round(nearest / exposure) * exposure)
                target = max(0, min(composition.duration_ms, target))
                if target in occupied and target != key.time_ms:
                    continue
                before = key.time_ms
                occupied.discard(before)
                key.time_ms = target
                key.interpolation = "hold"
                occupied.add(target)
                moves.append({
                    "layer_id": layer.id,
                    "property": property_name,
                    "keyframe_id": key.id,
                    "before_ms": before,
                    "transient_ms": nearest,
                    "after_ms": target,
                })
            prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
    composition.metadata["stop_motion_audio_snap"] = {
        "schema": STOP_MOTION_SCHEMA,
        "transient_times_ms": transients,
        "threshold_ms": int(threshold_ms),
        "moves": deepcopy(moves),
    }
    return {"moves": moves, "move_count": len(moves)}


def stop_motion_onion_samples(
    composition: MotionComposition,
    *,
    layer_id: str,
    time_ms: float,
    frames: int | None = None,
) -> dict[str, Any]:
    from .evaluator import evaluate_composition

    layer = next((item for item in composition.layers if item.id == layer_id), None)
    if layer is None:
        raise KeyError(f"unknown stop-motion layer: {layer_id}")
    count = (
        effective_stop_motion(composition, layer)["onion_skin_frames"]
        if frames is None
        else max(0, min(4, int(frames)))
    )
    exposure = stop_motion_exposure_ms(composition, layer)
    rows: list[dict[str, Any]] = []
    for offset in range(-count, count + 1):
        sample_time = max(0.0, min(composition.duration_ms, float(time_ms) + offset * exposure))
        state = next(
            item
            for item in evaluate_composition(composition, sample_time)
            if item.id == layer_id
        )
        rows.append({
            "offset": offset,
            "time_ms": sample_time,
            "position": list(state.position),
            "scale": list(state.scale),
            "rotation": state.rotation,
            "opacity": state.opacity,
        })
    return {
        "schema": "tigerstudio.motion.stop_motion.onion.v1",
        "layer_id": layer_id,
        "exposure_ms": exposure,
        "samples": rows,
    }


def preflight_stop_motion(
    composition: MotionComposition,
    *,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    ids = {str(item) for item in layer_ids if str(item)}
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for layer in composition.layers:
        if ids and layer.id not in ids:
            continue
        settings = effective_stop_motion(composition, layer)
        exposure = stop_motion_exposure_ms(composition, layer)
        if not settings["enabled"]:
            issues.append({"code": "stop_motion_disabled", "layer_id": layer.id})
        motion_blur = layer.metadata.get("motion_blur")
        if isinstance(motion_blur, Mapping) and bool(motion_blur.get("enabled")):
            issues.append({"code": "motion_blur_conflicts_with_exposure", "layer_id": layer.id})
        cadence_violations: list[dict[str, Any]] = []
        for property_name, prop in layer.transform.properties().items():
            for key in prop.keyframes:
                nearest = round(key.time_ms / exposure) * exposure
                if abs(key.time_ms - nearest) > 0.51:
                    cadence_violations.append({
                        "property": property_name,
                        "keyframe_id": key.id,
                        "time_ms": key.time_ms,
                    })
        if cadence_violations:
            issues.append({
                "code": "frame_cadence_violation",
                "layer_id": layer.id,
                "keyframes": cadence_violations,
            })
        checks.append({
            "layer_id": layer.id,
            "enabled": settings["enabled"],
            "exposure_frames": settings["exposure_frames"],
            "exposure_ms": exposure,
            "cadence_violation_count": len(cadence_violations),
            "material": deepcopy(layer.metadata.get("stop_motion_material") or {}),
        })
    return {
        "schema": "tigerstudio.motion.stop_motion.preflight.v1",
        "ok": not issues,
        "composition_id": composition.id,
        "settings": composition_stop_motion(composition),
        "checks": checks,
        "issues": issues,
        "summary": {
            "layer_count": len(checks),
            "cadence_violation_count": sum(
                item["cadence_violation_count"] for item in checks
            ),
            "issue_count": len(issues),
        },
    }


def stop_motion_signature(composition: MotionComposition) -> str:
    payload = {
        "settings": composition_stop_motion(composition),
        "layers": {
            layer.id: effective_stop_motion(composition, layer)
            for layer in composition.layers
        },
        "poses": list(composition.metadata.get(STOP_MOTION_POSES_KEY) or []),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


__all__ = [
    "MATERIAL_PRESETS",
    "MOTION_STYLES",
    "STOP_MOTION_KEY",
    "STOP_MOTION_POSES_KEY",
    "STOP_MOTION_POSE_SCHEMA",
    "STOP_MOTION_SCHEMA",
    "apply_stop_motion_pose",
    "apply_stop_motion_transform",
    "capture_stop_motion_pose",
    "composition_stop_motion",
    "effective_stop_motion",
    "normalize_stop_motion",
    "preflight_stop_motion",
    "set_stop_motion",
    "set_stop_motion_material",
    "snap_stop_motion_to_audio",
    "stop_motion_exposure_ms",
    "stop_motion_onion_samples",
    "stop_motion_sample_index",
    "stop_motion_sample_time",
    "stop_motion_signature",
]
