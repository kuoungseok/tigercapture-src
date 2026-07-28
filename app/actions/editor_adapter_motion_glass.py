"""Action adapter for Motion Designer Tiger Glass materials."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.glass_material import (
    glass_effect,
    glass_presets,
    make_glass_effect,
)


class MotionGlassAdapterMixin:
    def motion_glass_presets(self) -> dict[str, Any]:
        presets = glass_presets()
        return {"count": len(presets), "presets": presets}

    def motion_glass_get(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = glass_effect(layer.effects)
        return {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "enabled": effect is not None,
            "effect": effect.to_dict() if effect is not None else None,
        }

    def motion_glass_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        preset: str = "clear",
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        previous = glass_effect(layer.effects)
        effect = make_glass_effect(settings, preset=preset)
        if previous is None:
            layer.effects.append(effect)
        else:
            effect.id = previous.id
            if "driver" in previous.metadata:
                effect.metadata["driver"] = dict(previous.metadata["driver"])
            layer.effects[layer.effects.index(previous)] = effect
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Tiger Glass",
            "effect": effect.to_dict(),
            "revision": composition.revision,
        }

    def motion_glass_remove(self, *, composition_id: str, layer_id: str) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        previous = glass_effect(layer.effects)
        if previous is None:
            return {"changed": False, "revision": composition.revision}
        layer.effects.remove(previous)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Remove Tiger Glass",
            "revision": composition.revision,
        }

    def motion_glass_driver_bind(
        self,
        *,
        composition_id: str,
        layer_id: str,
        source: str,
        strength: float = 1.0,
        x: float = 0.0,
        y: float = 0.0,
    ) -> dict[str, Any]:
        from app.motion_designer.schema import AnimatedProperty

        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = glass_effect(layer.effects)
        if effect is None:
            raise ValueError(f"Tiger Glass not found on layer: {layer_id}")
        source_id = str(source or "").lower()
        if source_id not in {"pointer", "velocity", "scroll", "manual"}:
            raise ValueError(f"Unsupported Tiger Glass driver: {source}")
        scale = max(0.0, min(10.0, float(strength)))
        effect.metadata["driver"] = {"source": source_id, "strength": scale}
        effect.params["driver_x"] = AnimatedProperty(default=float(x) * scale)
        effect.params["driver_y"] = AnimatedProperty(default=float(y) * scale)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Bind Tiger Glass Driver",
            "driver": dict(effect.metadata["driver"]),
            "driver_value": [float(x) * scale, float(y) * scale],
            "revision": composition.revision,
        }

    def motion_glass_preflight(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        effect = glass_effect(find_layer(composition, layer_id).effects)
        if effect is None:
            return {"ok": False, "issues": ["glass_material_missing"]}
        advanced = any(
            float(effect.params.get(key).default if effect.params.get(key) is not None else 0.0) > threshold
            for key, threshold in {
                "refraction": 0.0,
                "dispersion": 0.0,
                "specular": 0.0,
                "bloom": 0.0,
            }.items()
        )
        return {
            "ok": True,
            "issues": [],
            "preview_backend": "shared_backdrop_raster",
            "umg_disposition": "deterministic_bake" if advanced else "ui_material_candidate",
            "umg_reason": "effect_requires_bake:tiger_glass" if advanced else "",
        }

    def motion_glass_tiled_export_set(
        self,
        *,
        composition_id: str,
        enabled: bool,
        tile_size: int = 512,
    ) -> dict[str, Any]:
        from app.motion_designer.tiled_renderer import TILED_EXPORT_CONTRACT

        composition = self._motion_store()[composition_id]
        size = max(64, min(4096, int(tile_size)))
        composition.metadata["tiled_export"] = {
            "contract": TILED_EXPORT_CONTRACT,
            "enabled": bool(enabled),
            "tile_size": size,
        }
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Tiled Glass Export",
            "tiled_export": dict(composition.metadata["tiled_export"]),
            "revision": composition.revision,
        }

    def motion_glass_tiled_export_preflight(
        self,
        *,
        composition_id: str,
        time_ms: float = 0.0,
    ) -> dict[str, Any]:
        from app.motion_designer.render_graph import build_render_graph
        from app.motion_designer.tiled_renderer import (
            glass_tile_padding,
            tiled_render_preflight,
        )

        composition = self._motion_store()[composition_id]
        graph = build_render_graph(
            composition,
            float(time_ms),
            render_quality="export",
            output_size=(composition.width, composition.height),
        )
        report = tiled_render_preflight(graph)
        report.update({
            "composition_id": composition_id,
            "time_ms": float(time_ms),
            "padding": glass_tile_padding(graph) if report["glass_effect_count"] else 0,
        })
        return report


__all__ = ["MotionGlassAdapterMixin"]
