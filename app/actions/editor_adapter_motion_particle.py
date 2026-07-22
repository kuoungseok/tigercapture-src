"""Motion Designer particle action adapter."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from app.motion_designer.adapters.particle import render_particle
from app.motion_designer.composition_service import CompositionService
from app.motion_designer.evaluator import remap_layer_time
from app.motion_designer.particles import (
    PARTICLE_SOURCE_KIND,
    create_particle_layer,
    particle_diagnostics,
    update_particle_params,
)
from app.motion_designer.schema import MotionComposition


class MotionParticleAdapterMixin:
    def motion_particle_add(self, *, composition_id: str, name: str = "Particle Emitter",
                            start_ms: int = 0, end_ms: int = 0,
                            params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        service = CompositionService(self._motion_store().values())
        composition = service.get(composition_id)
        layer = create_particle_layer(
            width=composition.width, height=composition.height,
            duration_ms=max(1, int(end_ms or composition.duration_ms)), name=name, params=params,
        )
        layer.in_ms = max(0, int(start_ms))
        layer.out_ms = max(layer.in_ms + 1, int(end_ms or composition.duration_ms))
        result = service.add_layer(composition_id, layer)
        self._motion_commit(service)
        return {"changed": result.changed, "undo_label": "Add Motion Particle Emitter",
                "layer": layer.to_dict(), "validation": result.validation.to_dict()}

    def motion_particle_update(self, *, composition_id: str, layer_id: str,
                               changes: Mapping[str, Any]) -> dict[str, Any]:
        service = CompositionService(self._motion_store().values())
        current = service.get(composition_id)
        candidate = MotionComposition.from_dict(current.to_dict())
        layer = next((item for item in candidate.layers if item.id == layer_id), None)
        if layer is None:
            raise ValueError(f"motion layer not found: {layer_id}")
        update_particle_params(layer, deepcopy(dict(changes)))
        result = service.update_layer(composition_id, layer_id, {"source": layer.source.to_dict()})
        if result.validation.ok:
            self._motion_commit(service)
        return {"changed": result.changed, "undo_label": "Update Motion Particle Emitter",
                "validation": result.validation.to_dict()}

    def motion_particle_diagnostics(self, *, composition_id: str, layer_id: str,
                                    time_ms: float = 0.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = next((item for item in composition.layers if item.id == layer_id), None)
        if layer is None or layer.layer_type != PARTICLE_SOURCE_KIND:
            raise ValueError(f"motion particle layer not found: {layer_id}")
        return particle_diagnostics(layer, remap_layer_time(layer, float(time_ms)))

    def motion_particle_bake(self, *, composition_id: str, layer_id: str, output_dir: str,
                             sample_fps: float = 0.0) -> dict[str, Any]:
        composition = self._motion_store().get(composition_id)
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = next((item for item in composition.layers if item.id == layer_id), None)
        if layer is None or layer.layer_type != PARTICLE_SOURCE_KIND:
            raise ValueError(f"motion particle layer not found: {layer_id}")
        directory = Path(output_dir).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        fps = max(1.0, min(120.0, float(sample_fps or composition.fps)))
        duration = max(1, layer.out_ms - layer.in_ms)
        frame_count = max(1, int(round(duration / 1000.0 * fps)))
        frames = []
        for index in range(frame_count):
            local_time = index * 1000.0 / fps
            path = directory / f"particle_{index:06d}.png"
            if not render_particle(layer, local_time).save(str(path), "PNG"):
                raise RuntimeError(f"failed to write particle bake frame: {path}")
            frames.append({"index": index, "time_ms": local_time, "path": str(path)})
        manifest = {
            "schema": "tigercapture.motion.particle_bake.v1",
            "composition_id": composition.id,
            "layer_id": layer.id,
            "fps": fps,
            "premultiplied_alpha": True,
            "seed": particle_diagnostics(layer, 0.0)["seed"],
            "frames": frames,
        }
        manifest_path = directory / "particle_bake.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        layer.metadata["particle_bake"] = {"manifest_path": str(manifest_path), "frame_count": frame_count, "fps": fps}
        composition.revision += 1
        return {"changed": True, "undo_label": "Bake Motion Particle Alpha Media",
                "manifest_path": str(manifest_path), "frame_count": frame_count,
                "premultiplied_alpha": True, "revision": composition.revision}


__all__ = ["MotionParticleAdapterMixin"]
