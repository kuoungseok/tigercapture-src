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
        count: int = 1,
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
        data = {
            "enabled": bool(enabled),
            "count": max(1, min(256, int(count))),
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
