"""Reusable high-level direction presets built from native Motion features."""
from __future__ import annotations

from typing import Iterable

from .ar_pbr_source import create_camera_layer
from .cut_paper import build_cut_paper_rig
from .paper_composite import build_paper_paste_rig
from .paper_crumple import make_crumple_unfold_effect
from .schema import AnimatedProperty, Keyframe, MotionBehaviorRef, MotionComposition, MotionLayer


ADVANCED_PRESETS = {
    "headline_slam",
    "paper_rip_reveal",
    "paper_crumple_unfold",
    "cutout_collage",
    "editorial_camera_push",
    "beat_synced_montage",
}


def _keys(default, rows, value_type="scalar") -> AnimatedProperty:
    return AnimatedProperty(
        value_type=value_type,
        default=default,
        keyframes=[
            Keyframe(
                time_ms=int(time_ms), value=value, interpolation="bezier",
                out_tangent=(0.16, 0.0), in_tangent=(0.78, 1.0),
            )
            for time_ms, value in rows
        ],
    )


def _selected(composition: MotionComposition, layer_ids: Iterable[str]) -> list[MotionLayer]:
    wanted = {str(layer_id) for layer_id in layer_ids if str(layer_id)}
    return [
        layer for layer in composition.layers
        if (not wanted or layer.id in wanted) and layer.layer_type not in {"camera", "light", "group", "null"}
    ]


def apply_advanced_preset(
    composition: MotionComposition,
    preset_id: str,
    *,
    layer_ids: Iterable[str] = (),
    start_ms: int = 0,
    beat_interval_ms: int = 420,
) -> dict:
    preset = str(preset_id or "").strip().lower()
    if preset not in ADVANCED_PRESETS:
        raise ValueError(f"unknown advanced motion preset: {preset_id}")
    layers = _selected(composition, layer_ids)
    start = max(0, int(start_ms))
    added: list[MotionLayer] = []

    if preset == "headline_slam":
        targets = [layer for layer in layers if layer.layer_type == "text"] or layers[:1]
        for index, layer in enumerate(targets):
            cue = start + index * 160
            layer.behaviors.append(MotionBehaviorRef(
                kind="impact", start_ms=cue, end_ms=min(composition.duration_ms, cue + 700),
                params={
                    "scale_overshoot": 0.18, "rotation_kick": -5.0 if index % 2 == 0 else 5.0,
                    "shake": 12.0, "frequency": 5.0, "damping": 7.0, "hold_after": True,
                },
            ))
            layer.metadata["motion_blur"] = {"enabled": True, "samples": 10, "shutter": 0.82}
    elif preset == "paper_rip_reveal":
        if not layers:
            raise ValueError("paper rip reveal requires a source layer")
        source = layers[0]
        width = float(source.source.params.get("width", composition.width) or composition.width)
        height = float(source.source.params.get("height", composition.height) or composition.height)
        rig = build_cut_paper_rig(
            composition, source,
            center_x=width * 0.5, center_y=height * 0.5,
            radius_x=width * 0.28, radius_y=height * 0.36,
            start_ms=start, cut_duration_ms=1300, release_duration_ms=720,
        )
        insert_at = composition.layers.index(source) + 1
        composition.layers[insert_at:insert_at] = rig.layers
        added.extend(rig.layers)
    elif preset == "paper_crumple_unfold":
        if not layers:
            raise ValueError("paper crumple and unfold requires a source layer")
        for index, layer in enumerate(layers):
            effect = make_crumple_unfold_effect(
                start_ms=start + index * 120,
                seed=17.0 + index * 31.0,
            )
            layer.effects.append(effect)
            layer.metadata["motion_blur"] = {
                "enabled": True,
                "samples": 8,
                "shutter": 0.64,
            }
    elif preset == "cutout_collage":
        for index, layer in enumerate(layers):
            layer.metadata["depth_z"] = -1.6 + index * 0.42
            layer.metadata["motion_blur"] = {"enabled": True, "samples": 8, "shutter": 0.68}
            layer.behaviors.append(MotionBehaviorRef(
                kind="impact",
                start_ms=start + index * 150,
                end_ms=min(composition.duration_ms, start + index * 150 + 620),
                params={
                    "scale_overshoot": 0.1, "rotation_kick": (-1 if index % 2 else 1) * 6.0,
                    "shake": 7.0, "frequency": 4.0, "damping": 6.0, "hold_after": True,
                },
            ))
            rig = build_paper_paste_rig(
                composition, layer, start_ms=start + index * 150,
                fold_strength=0.22 + min(0.24, index * 0.025),
            )
            insert_at = composition.layers.index(layer)
            composition.layers[insert_at:insert_at] = [rig.shadow]
            source_index = composition.layers.index(layer)
            composition.layers[source_index + 1:source_index + 1] = rig.layers[1:]
            added.extend(rig.layers)
    elif preset == "editorial_camera_push":
        camera = next((layer for layer in composition.layers if layer.layer_type == "camera"), None)
        if camera is None:
            camera = create_camera_layer(duration_ms=composition.duration_ms, name="Editorial 2.5D Camera")
            composition.layers.append(camera)
            added.append(camera)
        camera.source.params["apply_to_2d"] = True
        camera.source.params["parallax_strength"] = 1.15
        camera.source.params["pixels_per_unit"] = 120.0
        end = min(composition.duration_ms, start + 2600)
        camera.source.params["position"] = _keys(
            [0.0, 0.0, 3.8],
            [(start, [0.0, 0.0, 3.8]), (end, [0.24, -0.10, 3.05])],
            "vector3",
        ).to_dict()
        camera.source.params["rotation"] = _keys(
            [0.0, 0.0, 0.0],
            [(start, [0.0, 0.0, 0.0]), (end, [0.0, 0.0, 1.4])],
            "vector3",
        ).to_dict()
        camera.source.params["fov"] = _keys(48.0, [(start, 48.0), (end, 42.0)]).to_dict()
        for index, layer in enumerate(layers):
            layer.metadata.setdefault("depth_z", -1.2 + index * 0.32)
    elif preset == "beat_synced_montage":
        interval = max(80, int(beat_interval_ms))
        for index, layer in enumerate(layers):
            cue = start + index * interval
            layer.behaviors.append(MotionBehaviorRef(
                kind="impact", start_ms=cue, end_ms=min(composition.duration_ms, cue + interval),
                params={
                    "scale_overshoot": 0.13, "rotation_kick": (-1 if index % 2 else 1) * 3.0,
                    "shake": 6.0, "frequency": 4.5, "damping": 7.0, "hold_after": True,
                },
            ))
            layer.metadata["motion_blur"] = {"enabled": True, "samples": 8, "shutter": 0.7}

    composition.revision += 1
    return {
        "schema": "tigerstudio.motion.advanced_preset_result.v1",
        "preset_id": preset,
        "affected_layer_ids": [layer.id for layer in layers],
        "added_layer_ids": [layer.id for layer in added],
        "revision": composition.revision,
    }


__all__ = ["ADVANCED_PRESETS", "apply_advanced_preset"]
