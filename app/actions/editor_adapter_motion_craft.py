"""Action adapter for Motion Designer craft/imperfection styling."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import secrets
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.craft_style import (
    craft_style_presets,
    is_craft_style_effect,
    make_craft_style_effect,
)


class MotionCraftAdapterMixin:
    def _motion_craft_effect(self, composition_id: str, layer_id: str):
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = next((row for row in layer.effects if is_craft_style_effect(row)), None)
        if effect is None:
            raise ValueError(f"craft style not found on layer: {layer_id}")
        return composition, layer, effect

    def motion_craft_presets(self) -> dict[str, Any]:
        presets = craft_style_presets()
        return {"count": len(presets), "presets": presets}

    def motion_craft_get(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = next((row for row in layer.effects if is_craft_style_effect(row)), None)
        return {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "enabled": effect is not None and effect.enabled,
            "effect": effect.to_dict() if effect is not None else None,
        }

    def motion_craft_apply(
        self,
        *,
        composition_id: str,
        layer_id: str,
        preset: str = "subtle_film",
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        previous = next((row for row in layer.effects if is_craft_style_effect(row)), None)
        effect = make_craft_style_effect(settings, preset=preset)
        if previous is None:
            layer.effects.append(effect)
        else:
            effect.id = previous.id
            if "texture" in previous.metadata:
                effect.metadata["texture"] = dict(previous.metadata["texture"])
            layer.effects[layer.effects.index(previous)] = effect
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Apply Craft Style",
            "effect": effect.to_dict(),
            "revision": composition.revision,
        }

    def motion_craft_clear(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        before = len(layer.effects)
        layer.effects = [row for row in layer.effects if not is_craft_style_effect(row)]
        changed = len(layer.effects) != before
        if changed:
            composition.revision += 1
            self._motion_sync_owner()
        return {
            "changed": changed,
            "undo_label": "Clear Craft Style" if changed else "",
            "revision": composition.revision,
        }

    def motion_craft_texture_attach(
        self,
        *,
        composition_id: str,
        layer_id: str,
        uri: str,
        blend_mode: str = "multiply",
        opacity: float = 0.25,
    ) -> dict[str, Any]:
        path = Path(str(uri or "")).expanduser().resolve()
        if "debugcapture" in {part.lower() for part in path.parts}:
            raise ValueError("Craft texture must use durable assets, not debugCapture")
        if not path.is_file():
            raise ValueError(f"Craft texture does not exist: {path}")
        from PySide6.QtGui import QImage

        if QImage(str(path)).isNull():
            raise ValueError(f"Craft texture is not a readable image: {path}")
        composition, _layer, effect = self._motion_craft_effect(composition_id, layer_id)
        mode = str(blend_mode or "multiply").lower()
        if mode not in {"multiply", "screen", "overlay"}:
            raise ValueError(f"Unsupported craft texture blend mode: {blend_mode}")
        effect.metadata["texture"] = {
            "uri": str(path),
            "blend_mode": mode,
            "opacity": max(0.0, min(1.0, float(opacity))),
            "revision": str(path.stat().st_mtime_ns),
        }
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Attach Craft Texture",
            "texture": dict(effect.metadata["texture"]),
            "revision": composition.revision,
        }

    def motion_craft_seed_randomize(
        self,
        *,
        composition_id: str,
        layer_id: str,
        seed: int | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.schema import AnimatedProperty

        composition, _layer, effect = self._motion_craft_effect(composition_id, layer_id)
        value = max(0, min(2_147_483_647, int(
            seed if seed is not None else secrets.randbelow(2_147_483_647)
        )))
        effect.params["seed"] = AnimatedProperty(default=value)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Randomize Craft Seed",
            "seed": value,
            "revision": composition.revision,
        }

    def motion_craft_seed_lock(
        self,
        *,
        composition_id: str,
        layer_id: str,
        locked: bool,
    ) -> dict[str, Any]:
        composition, _layer, effect = self._motion_craft_effect(composition_id, layer_id)
        effect.metadata["seed_locked"] = bool(locked)
        composition.revision += 1
        return {
            "changed": True,
            "undo_label": "Set Craft Seed Lock",
            "seed_locked": bool(locked),
            "revision": composition.revision,
        }

    def motion_craft_preflight(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition, _layer, effect = self._motion_craft_effect(composition_id, layer_id)
        issues: list[str] = []
        texture = effect.metadata.get("texture")
        if isinstance(texture, Mapping):
            uri = str(texture.get("uri") or "")
            if uri and not Path(uri).is_file():
                issues.append("craft_texture_missing")
            if "debugcapture" in {part.lower() for part in Path(uri).parts}:
                issues.append("craft_texture_not_durable")
        if not bool(effect.metadata.get("seed_locked", True)):
            issues.append("craft_seed_unlocked")
        from app.motion_designer.glass_gpu_renderer import (
            MotionGlassGpuRenderer,
        )
        from app.motion_designer.render_graph import build_render_graph

        gpu_eligible, gpu_reason = MotionGlassGpuRenderer.can_draw(
            build_render_graph(
                composition,
                0.0,
                include_vector_gpu=True,
                render_quality="preview",
            )
        )
        return {
            "ok": not issues,
            "issues": issues,
            "preview_backend": (
                "motion_style_gpu"
                if gpu_eligible
                else "qt_painter_fallback"
            ),
            "preview_gpu_reason": gpu_reason,
            "umg_disposition": "deterministic_bake",
            "umg_reason": "effect_requires_bake:craft_style",
        }


__all__ = ["MotionCraftAdapterMixin"]
