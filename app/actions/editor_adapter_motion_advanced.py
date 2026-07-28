"""Action adapter for advanced Motion Designer compositing and direction tools."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.schema import MotionComposition


class MotionAdvancedAdapterMixin:
    def _motion_advanced_composition(self, composition_id: str) -> MotionComposition:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        return composition

    def _motion_advanced_changed(
        self,
        composition: MotionComposition,
        undo_label: str,
        **result: Any,
    ) -> dict[str, Any]:
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": undo_label,
            "composition_id": composition.id,
            "revision": composition.revision,
            **result,
        }

    def motion_matte_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        matte_layer_id: str,
        mode: str = "alpha",
        inverted: bool = False,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        matte = find_layer(composition, matte_layer_id)
        if matte.id == layer.id:
            raise ValueError("a layer cannot use itself as a track matte")
        mode = str(mode or "alpha").lower()
        if mode not in {"alpha", "luma"}:
            raise ValueError("track matte mode must be alpha or luma")
        layer.metadata.update({
            "matte_layer_id": matte.id,
            "matte_mode": mode,
            "matte_inverted": bool(inverted),
        })
        return self._motion_advanced_changed(
            composition, "Set Motion Track Matte",
            layer_id=layer.id, matte_layer_id=matte.id, mode=mode, inverted=bool(inverted),
        )

    def motion_matte_clear(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        for key in ("matte_layer_id", "matte_mode", "matte_inverted"):
            layer.metadata.pop(key, None)
        return self._motion_advanced_changed(
            composition, "Clear Motion Track Matte", layer_id=layer.id,
        )

    def motion_key_create(
        self,
        *,
        composition_id: str,
        layer_id: str,
        kind: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.keying import KEYER_CONTRACT, KEYER_KINDS
        from app.motion_designer.schema import AnimatedProperty, MotionEffectRef

        mode = str(kind or "").strip().lower()
        if mode not in KEYER_KINDS:
            raise ValueError(f"unsupported keyer kind: {kind}")
        values = {
            "key_color": "#00ff00",
            "similarity": 0.35,
            "threshold": 0.5 if mode == "luma_key" else 0.12,
            "softness": 0.1,
            "choke": 0.0,
            "feather": 0.0,
            "despill": 0.5,
            **dict(params or {}),
        }
        effect = MotionEffectRef(
            kind=mode,
            params={
                key: AnimatedProperty.from_dict(value)
                for key, value in values.items()
            },
            metadata={"contract": KEYER_CONTRACT},
        )
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        layer.effects.append(effect)
        return self._motion_advanced_changed(
            composition,
            "Create Motion Keyer",
            layer_id=layer.id,
            effect=effect.to_dict(),
        )

    def motion_key_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        effect_id: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.keying import KEYER_KINDS
        from app.motion_designer.schema import AnimatedProperty

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        effect = next(
            (row for row in layer.effects if row.id == effect_id),
            None,
        )
        if effect is None or effect.kind not in KEYER_KINDS:
            raise ValueError(f"motion keyer not found: {effect_id}")
        for key, value in params.items():
            current = effect.params.get(str(key))
            effect.params[str(key)] = AnimatedProperty.from_dict(
                value,
                value_type=current.value_type if current is not None else "scalar",
            )
        return self._motion_advanced_changed(
            composition,
            "Update Motion Keyer",
            layer_id=layer.id,
            effect=effect.to_dict(),
        )

    def motion_key_diagnostics(
        self,
        *,
        composition_id: str,
        layer_id: str,
        effect_id: str,
        time_ms: float = 0.0,
    ) -> dict[str, Any]:
        import numpy as np
        from PySide6.QtGui import QImage

        from app.motion_designer.adapters import render_source
        from app.motion_designer.keying import KEYER_KINDS

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        effect = next(
            (row for row in layer.effects if row.id == effect_id),
            None,
        )
        if effect is None or effect.kind not in KEYER_KINDS:
            raise ValueError(f"motion keyer not found: {effect_id}")
        image = render_source(
            layer,
            float(time_ms),
            composition=composition,
            composition_time_ms=float(time_ms),
            quality="preview",
            viewport_size=(composition.width, composition.height),
        ).convertToFormat(QImage.Format_RGBA8888)
        data = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(),
            image.bytesPerLine(),
        )[:, : image.width() * 4].reshape(image.height(), image.width(), 4)
        alpha = data[..., 3]
        reference = effect.params.get("reference_uri")
        return {
            "changed": False,
            "composition_id": composition.id,
            "layer_id": layer.id,
            "effect_id": effect.id,
            "kind": effect.kind,
            "time_ms": float(time_ms),
            "transparent_ratio": float(np.mean(alpha <= 2)),
            "opaque_ratio": float(np.mean(alpha >= 253)),
            "soft_ratio": float(np.mean((alpha > 2) & (alpha < 253))),
            "reference_ready": bool(
                effect.kind != "difference_key"
                or (reference is not None and str(reference.default or ""))
            ),
        }

    def motion_matte_correction_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mask_id: str,
        time_ms: int,
        translate: list[float] | tuple[float, ...] = (0.0, 0.0),
        scale: list[float] | tuple[float, ...] = (1.0, 1.0),
        rotation: float = 0.0,
    ) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY
        from app.motion_designer.mask_tracking import (
            MotionTrackCorrection,
            MotionTrackingCache,
        )

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        mask = next((row for row in layer.masks if row.id == mask_id), None)
        if mask is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        cache = MotionTrackingCache.from_dict(
            mask.metadata.get(TRACKING_METADATA_KEY),
        )
        if not cache.samples:
            raise ValueError("matte correction requires a propagated tracking cache")
        position = list(translate)
        size = list(scale)
        if len(position) < 2 or len(size) < 2:
            raise ValueError("matte correction translate/scale require two values")
        correction = MotionTrackCorrection(
            time_ms=max(0, int(time_ms)),
            translate=(float(position[0]), float(position[1])),
            scale=(float(size[0]), float(size[1])),
            rotation=float(rotation),
        )
        cache.corrections = [
            row for row in cache.corrections
            if row.time_ms != correction.time_ms
        ]
        cache.corrections.append(correction)
        cache.corrections.sort(key=lambda row: row.time_ms)
        mask.metadata[TRACKING_METADATA_KEY] = cache.to_dict()
        return self._motion_advanced_changed(
            composition,
            "Set Matte Correction Keyframe",
            layer_id=layer.id,
            mask_id=mask.id,
            correction=correction.to_dict(),
            correction_count=len(cache.corrections),
        )

    def motion_matte_freeze(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mask_id: str,
        frozen: bool = True,
    ) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY
        from app.motion_designer.mask_tracking import MotionTrackingCache

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        mask = next((row for row in layer.masks if row.id == mask_id), None)
        if mask is None:
            raise ValueError(f"motion mask not found: {mask_id}")
        cache = MotionTrackingCache.from_dict(
            mask.metadata.get(TRACKING_METADATA_KEY),
        )
        if not cache.samples:
            raise ValueError("cannot freeze an empty matte propagation cache")
        cache.frozen = bool(frozen)
        mask.metadata[TRACKING_METADATA_KEY] = cache.to_dict()
        return self._motion_advanced_changed(
            composition,
            "Freeze Matte Propagation" if frozen else "Unfreeze Matte Propagation",
            layer_id=layer.id,
            mask_id=mask.id,
            frozen=cache.frozen,
            sample_count=len(cache.samples),
        )

    def motion_matte_diagnostics(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mask_id: str = "",
    ) -> dict[str, Any]:
        from app.motion_designer.mask_adapter import TRACKING_METADATA_KEY
        from app.motion_designer.mask_tracking import MotionTrackingCache

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        masks = [
            mask for mask in layer.masks
            if not mask_id or mask.id == mask_id
        ]
        if mask_id and not masks:
            raise ValueError(f"motion mask not found: {mask_id}")
        rows = []
        for mask in masks:
            cache = MotionTrackingCache.from_dict(
                mask.metadata.get(TRACKING_METADATA_KEY),
            )
            confidence = [
                float(sample.confidence) for sample in cache.samples
            ]
            rows.append({
                "mask_id": mask.id,
                "kind": mask.kind,
                "mode": mask.mode,
                "sample_count": len(cache.samples),
                "correction_count": len(cache.corrections),
                "frozen": cache.frozen,
                "mean_confidence": (
                    sum(confidence) / len(confidence) if confidence else 0.0
                ),
                "minimum_confidence": min(confidence) if confidence else 0.0,
                "source_revision": cache.source_revision,
            })
        return {
            "changed": False,
            "composition_id": composition.id,
            "layer_id": layer.id,
            "mask_count": len(rows),
            "masks": rows,
        }

    def motion_layer_depth_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        depth_z: float,
        camera_excluded: bool = False,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        layer.metadata["depth_z"] = max(-8.0, min(8.0, float(depth_z)))
        layer.metadata["camera_2_5d_excluded"] = bool(camera_excluded)
        return self._motion_advanced_changed(
            composition, "Set Motion Layer Depth",
            layer_id=layer.id, depth_z=layer.metadata["depth_z"],
        )

    def motion_3d_layer_enable(
        self,
        *,
        composition_id: str,
        layer_id: str,
        enabled: bool = True,
        depth_z: float = 0.0,
        rotation_x: float = 0.0,
        rotation_y: float = 0.0,
        camera_excluded: bool = False,
        cast_shadows: bool = False,
        receive_shadows: bool = False,
        shadow_strength: float = 0.45,
        shadow_softness: float = 6.0,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type in {"camera", "light", "ar_pbr"}:
            raise ValueError(
                f"motion.3d.layer.enable requires a 2D renderable layer: {layer_id}"
            )
        layer.metadata["depth_z"] = max(-8.0, min(8.0, float(depth_z)))
        layer.metadata["camera_2_5d_excluded"] = bool(camera_excluded)
        layer.metadata["three_d"] = {
            "enabled": bool(enabled),
            "rotation_x": max(-180.0, min(180.0, float(rotation_x))),
            "rotation_y": max(-180.0, min(180.0, float(rotation_y))),
            "cast_shadows": bool(cast_shadows),
            "receive_shadows": bool(receive_shadows),
            "shadow_strength": max(0.0, min(1.0, float(shadow_strength))),
            "shadow_softness": max(0.0, min(32.0, float(shadow_softness))),
            "projection_model": "affine_card_2_5d",
        }
        return self._motion_advanced_changed(
            composition,
            "Configure Motion 3D Layer",
            layer_id=layer.id,
            depth_z=layer.metadata["depth_z"],
            three_d=dict(layer.metadata["three_d"]),
        )

    def motion_blur_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        enabled: bool = True,
        samples: int = 8,
        shutter: float = 0.65,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        layer.metadata["motion_blur"] = {
            "enabled": bool(enabled),
            "samples": max(2, min(32, int(samples))),
            "shutter": max(0.0, min(2.0, float(shutter))),
        }
        return self._motion_advanced_changed(
            composition, "Set Motion Blur", layer_id=layer.id,
            motion_blur=dict(layer.metadata["motion_blur"]),
        )

    def motion_replicator_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        enabled: bool = True,
        arrangement: str = "line",
        count: int = 1,
        columns: int = 5,
        offset: list[float] | None = None,
        rotation: float = 0.0,
        scale: list[float] | None = None,
        opacity_start: float = 1.0,
        opacity_end: float = 1.0,
        jitter: list[float] | None = None,
        seed: int = 0,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        arrangement = str(arrangement or "line").lower()
        if arrangement not in {"line", "grid", "radial"}:
            raise ValueError("replicator arrangement must be line, grid, or radial")
        data = {
            "enabled": bool(enabled),
            "arrangement": arrangement,
            "count": max(1, min(256, int(count))),
            "columns": max(1, min(256, int(columns))),
            "offset": list(offset or [0.0, 0.0])[:2],
            "rotation": float(rotation),
            "scale": list(scale or [1.0, 1.0])[:2],
            "opacity_start": max(0.0, min(1.0, float(opacity_start))),
            "opacity_end": max(0.0, min(1.0, float(opacity_end))),
            "jitter": list(jitter or [0.0, 0.0])[:2],
            "seed": int(seed),
        }
        layer.metadata["replicator"] = data
        return self._motion_advanced_changed(
            composition, "Set Motion Replicator", layer_id=layer.id, replicator=data,
        )

    def motion_generator_create(
        self,
        *,
        composition_id: str,
        kind: str = "gradient",
        name: str = "",
        width: int = 0,
        height: int = 0,
        duration_ms: int = 0,
    ) -> dict[str, Any]:
        from app.motion_designer.generators import create_generator_layer

        composition = self._motion_advanced_composition(composition_id)
        layer = create_generator_layer(
            kind,
            width=width or composition.width,
            height=height or composition.height,
            duration_ms=duration_ms or composition.duration_ms,
            name=name,
        )
        composition.layers.append(layer)
        return self._motion_advanced_changed(
            composition,
            "Add Motion Generator",
            layer=layer.to_dict(),
        )

    def motion_generator_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        from app.motion_designer.generators import update_generator_params

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        update_generator_params(layer, changes)
        return self._motion_advanced_changed(
            composition,
            "Update Motion Generator",
            layer=layer.to_dict(),
        )

    def motion_text_animator_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "text":
            raise ValueError("text animator requires a text layer")
        layer.source.params["text_animation"] = dict(config)
        return self._motion_advanced_changed(
            composition, "Set Motion Text Animator",
            layer_id=layer.id, text_animation=dict(config),
        )

    def motion_text_animator_stack_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        animators: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "text":
            raise ValueError("text animator stack requires a text layer")
        if len(animators) > 32:
            raise ValueError("text animator stack is limited to 32 entries")
        layer.source.params["text_animators"] = [
            dict(animator) for animator in animators
        ]
        return self._motion_advanced_changed(
            composition,
            "Set Text Animator Stack",
            layer_id=layer.id,
            text_animators=layer.source.params["text_animators"],
        )

    def motion_text_animator_add(
        self,
        *,
        composition_id: str,
        layer_id: str,
        animator: Mapping[str, Any],
    ) -> dict[str, Any]:
        from uuid import uuid4

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "text":
            raise ValueError("text animator requires a text layer")
        stack = list(layer.source.params.get("text_animators") or [])
        if len(stack) >= 32:
            raise ValueError("text animator stack is limited to 32 entries")
        value = dict(animator)
        value.setdefault("id", f"animator_{uuid4().hex[:10]}")
        value.setdefault("name", f"Animator {len(stack) + 1}")
        value.setdefault("enabled", True)
        stack.append(value)
        layer.source.params["text_animators"] = stack
        return self._motion_advanced_changed(
            composition,
            "Add Text Animator",
            layer_id=layer.id,
            animator=value,
            text_animators=stack,
        )

    def motion_text_animator_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        animator_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        stack = list(layer.source.params.get("text_animators") or [])
        for index, animator in enumerate(stack):
            if isinstance(animator, Mapping) and str(animator.get("id") or "") == animator_id:
                stack[index] = {**dict(animator), **dict(changes), "id": animator_id}
                break
        else:
            raise ValueError(f"unknown text animator: {animator_id}")
        layer.source.params["text_animators"] = stack
        return self._motion_advanced_changed(
            composition,
            "Update Text Animator",
            layer_id=layer.id,
            text_animators=stack,
        )

    def motion_text_animator_remove(
        self,
        *,
        composition_id: str,
        layer_id: str,
        animator_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        stack = list(layer.source.params.get("text_animators") or [])
        filtered = [
            animator for animator in stack
            if not (
                isinstance(animator, Mapping)
                and str(animator.get("id") or "") == animator_id
            )
        ]
        if len(filtered) == len(stack):
            raise ValueError(f"unknown text animator: {animator_id}")
        layer.source.params["text_animators"] = filtered
        return self._motion_advanced_changed(
            composition,
            "Remove Text Animator",
            layer_id=layer.id,
            text_animators=filtered,
        )

    def motion_typography_character_3d_prepare(
        self,
        *,
        composition_id: str,
        layer_id: str,
        depth: float = 12.0,
        bevel: float = 1.5,
        z_spacing: float = 0.0,
        overrides: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.typography_3d_prep import (
            prepare_character_3d_data,
        )

        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        payload = prepare_character_3d_data(
            layer,
            depth=depth,
            bevel=bevel,
            z_spacing=z_spacing,
            overrides=overrides,
        )
        return self._motion_advanced_changed(
            composition,
            "Prepare Per-Character 3D Data",
            layer_id=layer.id,
            character_3d_prep=payload,
        )

    def motion_camera_2_5d_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        enabled: bool = True,
        parallax_strength: float = 1.0,
        pixels_per_unit: float = 120.0,
    ) -> dict[str, Any]:
        composition = self._motion_advanced_composition(composition_id)
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "camera":
            raise ValueError("2.5D camera settings require a camera layer")
        layer.source.params.update({
            "apply_to_2d": bool(enabled),
            "parallax_strength": max(0.0, min(4.0, float(parallax_strength))),
            "pixels_per_unit": max(1.0, min(1000.0, float(pixels_per_unit))),
        })
        return self._motion_advanced_changed(
            composition, "Set Motion 2.5D Camera",
            layer_id=layer.id, settings={
                "enabled": bool(enabled),
                "parallax_strength": layer.source.params["parallax_strength"],
                "pixels_per_unit": layer.source.params["pixels_per_unit"],
            },
        )

    def motion_paper_paste_create(
        self,
        *,
        composition_id: str,
        layer_id: str,
        start_ms: int,
        tape_color: str = "#BFD8C9A8",
        fold_strength: float = 0.32,
    ) -> dict[str, Any]:
        from app.motion_designer.paper_composite import build_paper_paste_rig

        composition = self._motion_advanced_composition(composition_id)
        source = find_layer(composition, layer_id)
        rig = build_paper_paste_rig(
            composition, source, start_ms=int(start_ms),
            tape_color=str(tape_color), fold_strength=float(fold_strength),
        )
        insert_at = composition.layers.index(source)
        composition.layers[insert_at:insert_at] = [rig.shadow]
        source_index = composition.layers.index(source)
        composition.layers[source_index + 1:source_index + 1] = rig.layers[1:]
        return self._motion_advanced_changed(
            composition, "Create Paper Paste Rig", source_layer_id=source.id, **rig.to_dict(),
        )

    def motion_advanced_preset_apply(
        self,
        *,
        composition_id: str,
        preset_id: str,
        layer_ids: list[str] | None = None,
        start_ms: int = 0,
        beat_interval_ms: int = 420,
    ) -> dict[str, Any]:
        from app.motion_designer.advanced_presets import apply_advanced_preset

        composition = self._motion_advanced_composition(composition_id)
        result = apply_advanced_preset(
            composition, preset_id, layer_ids=layer_ids or (),
            start_ms=int(start_ms), beat_interval_ms=int(beat_interval_ms),
        )
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Apply Advanced Motion Preset",
            "composition_id": composition.id,
            **result,
        }


__all__ = ["MotionAdvancedAdapterMixin"]
