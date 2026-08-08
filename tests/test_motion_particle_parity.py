from __future__ import annotations

import json

import numpy as np
from PySide6.QtGui import QImage

from app.actions.registry import ActionRegistry
from app.motion_designer.adapters.particle import render_particle
from app.motion_designer.particle_gpu import build_particle_gpu_packet
from app.motion_designer.particles import create_particle_layer
from app.motion_designer.schema import MotionComposition


def _rgba(image: QImage) -> np.ndarray:
    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    return array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def test_preview_export_source_frames_and_gpu_instances_share_simulation() -> None:
    layer = create_particle_layer(width=320, height=180, params={"seed": 7, "birth_rate": 18})
    preview = render_particle(layer, 650, quality="preview")
    export = render_particle(layer, 650, quality="export")
    assert np.array_equal(_rgba(preview), _rgba(export))
    packet, reason = build_particle_gpu_packet(layer, 650)
    assert reason == "" and packet is not None
    assert len(packet.instances) > 0
    assert any(value.color != (1.0, 1.0, 1.0, 1.0) for value in packet.instances)


def test_particle_actions_update_diagnose_and_bake_alpha(tmp_path) -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {"comp": MotionComposition(id="comp", width=160, height=90,
                                                                      duration_ms=200, fps=5)}

    owner = Owner()
    registry = ActionRegistry(owner)
    added = registry.execute("motion.particle.add", {
        "composition_id": "comp", "params": {"seed": 99, "birth_rate": 5, "max_particles": 20},
    })
    assert added.ok
    layer_id = added.result["layer"]["id"]
    updated = registry.execute("motion.particle.update", {
        "composition_id": "comp", "layer_id": layer_id,
        "changes": {"emitter": {"kind": "box", "size": [40, 20]}},
    })
    assert updated.ok
    diagnostics = registry.execute("motion.particle.diagnostics", {
        "composition_id": "comp", "layer_id": layer_id, "time_ms": 100,
    }).result
    assert diagnostics["deterministic"] and diagnostics["gpu_preview_eligible"]
    baked = registry.execute("motion.particle.bake", {
        "composition_id": "comp", "layer_id": layer_id, "output_dir": str(tmp_path), "sample_fps": 5,
    })
    assert baked.ok and baked.result["frame_count"] == 1
    manifest = json.loads((tmp_path / "particle_bake.json").read_text(encoding="utf-8"))
    assert manifest["premultiplied_alpha"] is True
    assert (tmp_path / "particle_000000.png").is_file()
