"""Action adapter for provider-neutral Motion painterly look development."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.painterly_look import (
    is_painterly_look_effect,
    make_painterly_look_effect,
    painterly_look_presets,
)


class MotionLookdevAdapterMixin:
    def _motion_lookdev_effect(self, composition_id: str, layer_id: str):
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = next(
            (row for row in layer.effects if is_painterly_look_effect(row)),
            None,
        )
        if effect is None:
            raise ValueError(f"painterly look not found on layer: {layer_id}")
        return composition, layer, effect

    def motion_lookdev_presets(self) -> dict[str, Any]:
        presets = painterly_look_presets()
        return {"count": len(presets), "presets": presets}

    def motion_lookdev_get(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        effect = next(
            (row for row in layer.effects if is_painterly_look_effect(row)),
            None,
        )
        return {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "enabled": effect is not None and effect.enabled,
            "effect": effect.to_dict() if effect is not None else None,
        }

    def motion_lookdev_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        preset: str = "realistic",
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        previous = next(
            (row for row in layer.effects if is_painterly_look_effect(row)),
            None,
        )
        effect = make_painterly_look_effect(settings, preset=preset)
        if previous is None:
            layer.effects.append(effect)
        else:
            effect.id = previous.id
            for key in ("projected_texture", "material_overrides"):
                if key in previous.metadata:
                    effect.metadata[key] = previous.metadata[key]
            layer.effects[layer.effects.index(previous)] = effect
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Painterly Look",
            "effect": effect.to_dict(),
            "revision": composition.revision,
        }

    def motion_lookdev_clear(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store()[composition_id]
        layer = find_layer(composition, layer_id)
        before = len(layer.effects)
        layer.effects = [
            row for row in layer.effects
            if not is_painterly_look_effect(row)
        ]
        changed = before != len(layer.effects)
        if changed:
            composition.revision += 1
            self._motion_sync_owner()
        return {
            "changed": changed,
            "undo_label": "Clear Painterly Look" if changed else "",
            "revision": composition.revision,
        }

    def motion_lookdev_line_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        color: str = "#17202a",
        strength: float = 0.6,
        threshold: float = 0.18,
        softness: float = 0.08,
    ) -> dict[str, Any]:
        from app.motion_designer.schema import AnimatedProperty

        composition, _layer, effect = self._motion_lookdev_effect(
            composition_id,
            layer_id,
        )
        effect.metadata["line_color"] = str(color or "#17202a")
        effect.params["edge_strength"] = AnimatedProperty(
            default=max(0.0, min(2.0, float(strength))),
        )
        effect.params["edge_threshold"] = AnimatedProperty(
            default=max(0.0, min(1.0, float(threshold))),
        )
        effect.params["edge_softness"] = AnimatedProperty(
            default=max(0.001, min(1.0, float(softness))),
        )
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Painterly Lines",
            "line": {
                "color": effect.metadata["line_color"],
                "strength": effect.params["edge_strength"].default,
                "threshold": effect.params["edge_threshold"].default,
                "softness": effect.params["edge_softness"].default,
            },
            "revision": composition.revision,
        }

    def motion_lookdev_material_override(
        self,
        *,
        composition_id: str,
        layer_id: str,
        material_id: str,
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition, _layer, effect = self._motion_lookdev_effect(
            composition_id,
            layer_id,
        )
        overrides = dict(effect.metadata.get("material_overrides") or {})
        overrides[str(material_id)] = dict(settings or {})
        effect.metadata["material_overrides"] = overrides
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Painterly Material Override",
            "material_id": str(material_id),
            "settings": dict(settings or {}),
            "revision": composition.revision,
            "warning": "material_id_pass_required",
        }

    def motion_lookdev_texture_project(
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
            raise ValueError("Painterly texture must use durable assets")
        if not path.is_file():
            raise ValueError(f"Painterly texture does not exist: {path}")
        from PySide6.QtGui import QImage

        if QImage(str(path)).isNull():
            raise ValueError(f"Painterly texture is not readable: {path}")
        mode = str(blend_mode or "multiply").lower()
        if mode not in {"multiply", "screen", "overlay"}:
            raise ValueError(f"Unsupported texture blend mode: {blend_mode}")
        composition, _layer, effect = self._motion_lookdev_effect(
            composition_id,
            layer_id,
        )
        effect.metadata["projected_texture"] = {
            "uri": str(path),
            "blend_mode": mode,
            "opacity": max(0.0, min(1.0, float(opacity))),
            "revision": str(path.stat().st_mtime_ns),
            "projection": "screen",
        }
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Project Painterly Texture",
            "projected_texture": dict(effect.metadata["projected_texture"]),
            "revision": composition.revision,
        }

    def motion_lookdev_preflight(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition, _layer, effect = self._motion_lookdev_effect(
            composition_id,
            layer_id,
        )
        issues: list[str] = []
        texture = effect.metadata.get("projected_texture")
        if isinstance(texture, Mapping):
            uri = str(texture.get("uri") or "")
            if uri and not Path(uri).is_file():
                issues.append("painterly_texture_missing")
            if "debugcapture" in {part.lower() for part in Path(uri).parts}:
                issues.append("painterly_texture_not_durable")
        if effect.metadata.get("temporal_lock") is not True:
            issues.append("painterly_temporal_lock_disabled")
        overrides = effect.metadata.get("material_overrides")
        if isinstance(overrides, Mapping) and overrides:
            issues.append("material_id_pass_unavailable")
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
            "renderer": "provider_neutral_post_render",
            "preview_backend": (
                "motion_style_gpu"
                if gpu_eligible
                else "qt_painter_fallback"
            ),
            "preview_gpu_reason": gpu_reason,
            "temporal_stability": "locked",
            "umg_disposition": "deterministic_bake",
            "umg_reason": "effect_requires_bake:painterly_look",
        }


__all__ = ["MotionLookdevAdapterMixin"]
