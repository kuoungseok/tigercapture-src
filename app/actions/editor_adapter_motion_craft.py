"""Action adapter for Motion Designer craft/imperfection styling."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.craft_style import (
    craft_style_presets,
    is_craft_style_effect,
    make_craft_style_effect,
)


class MotionCraftAdapterMixin:
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


__all__ = ["MotionCraftAdapterMixin"]
