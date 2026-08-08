from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.mmd_source import (
    create_mmd_layer, evaluate_mmd_frame, inspect_mmd_source, update_mmd_params,
)
from app.motion_designer.schema import MotionComposition
from app.motion_designer.validation import validate_composition


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "local_resources/mmd/model_pool/playable/flashy_girls/wuthering_waves/Cantarella/Cantarella.pmx"
MOTION = ROOT / "local_resources/mmd/model_pool/motions/validated/wavefile_v2_arora_14.vmd"


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_mmd_source_contract_inspects_real_model_motion_and_roundtrips() -> None:
    info = inspect_mmd_source(MODEL, MOTION)
    assert info["ok"] is True
    assert info["model"]["vertices"] > 10_000
    assert info["model"]["bones"] > 100
    assert info["motion"]["bone_tracks"] > 10
    layer = create_mmd_layer(MODEL, motion_path=MOTION, width=640, height=360, duration_ms=3000)
    composition = MotionComposition(width=640, height=360, duration_ms=3000, layers=[layer])
    assert validate_composition(composition).ok
    assert MotionComposition.from_dict(composition.to_dict()).to_dict() == composition.to_dict()


def test_mmd_frame_evaluates_vmd_camera_light_material_and_rate() -> None:
    layer = create_mmd_layer(
        MODEL, motion_path=MOTION, width=640, height=360, duration_ms=3000,
        params={
            "view": {"yaw": {"default": 20.0}},
            "render": {"bloom_strength": {"default": 0.65}, "material": {"skin_warmth": {"default": 1.2}}},
            "playback": {"rate": {"default": 1.5}, "use_vmd_camera": False},
        },
    )
    frame = evaluate_mmd_frame(layer, 400)
    assert frame.sample_time_ms == 600
    assert frame.track["view"]["yaw"] == 20
    assert frame.track["render"]["bloom_strength"] == pytest.approx(0.65)
    assert frame.track["render"]["material"]["skin_warmth"] == pytest.approx(1.2)
    assert frame.track["playback"]["use_vmd_camera"] is False


def test_mmd_adapter_uses_one_canonical_preview_export_frame(monkeypatch) -> None:
    from app.motion_designer.adapters import mmd as adapter

    layer = create_mmd_layer(MODEL, motion_path=MOTION, width=64, height=64, duration_ms=1000)
    composition = MotionComposition(width=64, height=64, duration_ms=1000, layers=[layer])
    calls: list[int] = []

    class FakeRuntime:
        def render(self, _track, time_ms, width, height):
            calls.append(int(time_ms))
            array = np.zeros((height, width, 4), dtype=np.uint8)
            array[8:-8, 8:-8] = [32, 96, 180, 255]
            return array, [{"diagnostics": {"gpu_skinning": True}}]

    monkeypatch.setattr(adapter, "_runtime", lambda _layer_id: FakeRuntime())
    adapter.clear_mmd_cache()
    preview = adapter.render_mmd(layer, 500, composition=composition, quality="preview", viewport_size=(64, 64))
    exported = adapter.render_mmd(layer, 500, composition=composition, quality="export", viewport_size=(64, 64))
    assert not preview.isNull() and not exported.isNull()
    assert preview == exported
    assert calls == [500]
    diagnostics = adapter.mmd_diagnostics(layer.id)
    assert diagnostics["renderer"] == "mmd_toon_opengl"
    assert diagnostics["cache_hit"] is True


def test_mmd_adapter_does_not_cache_a_transient_blank_gl_frame(monkeypatch) -> None:
    from app.motion_designer.adapters import mmd as adapter

    layer = create_mmd_layer(MODEL, motion_path=MOTION, width=32, height=32, duration_ms=1000)
    calls = 0

    class RecoveringRuntime:
        def render(self, _track, _time_ms, width, height):
            nonlocal calls
            calls += 1
            if calls == 1:
                return None, [{}]
            array = np.zeros((height, width, 4), dtype=np.uint8)
            array[4:-4, 4:-4] = [90, 140, 210, 255]
            return array, [{}]

    runtime = RecoveringRuntime()
    monkeypatch.setattr(adapter, "_runtime", lambda _layer_id: runtime)
    adapter.clear_mmd_cache()
    first = adapter.render_mmd(layer, 100, viewport_size=(32, 32))
    second = adapter.render_mmd(layer, 100, viewport_size=(32, 32))
    assert calls == 2
    assert first.pixelColor(16, 16).alpha() == 0
    assert second.pixelColor(16, 16).alpha() == 255


def test_invalid_mmd_motion_update_is_atomic(tmp_path: Path) -> None:
    layer = create_mmd_layer(MODEL, motion_path=MOTION, width=64, height=64, duration_ms=1000)
    original = layer.source.params["asset"]["motion_path"]
    with pytest.raises(ValueError):
        update_mmd_params(layer, {"asset": {"motion_path": str(tmp_path / "missing.vmd")}})
    assert layer.source.params["asset"]["motion_path"] == original


def test_motion_mmd_actions_add_update_and_replace_motion() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "MMD Motion", "width": 640, "height": 360, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.mmd.add", {
        "composition_id": composition_id, "model_path": str(MODEL), "motion_path": str(MOTION),
    })
    assert added.ok
    layer_id = added.result["layer"]["id"]
    assert registry.execute("motion.mmd.update", {
        "composition_id": composition_id, "layer_id": layer_id,
        "changes": {"render": {"bloom_strength": 0.7}, "playback": {"enable_physics": False}},
    }).ok
    assert registry.execute("motion.mmd.motion.set", {
        "composition_id": composition_id, "layer_id": layer_id, "motion_path": str(MOTION),
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["render"]["bloom_strength"]["default"] == pytest.approx(0.7)
    assert layer.source.params["playback"]["enable_physics"] is False
    assert layer.source.params["catalog"]["motion"]["bone_tracks"] > 10
    specs = {row["id"] for row in registry.list_actions()}
    assert {"motion.mmd.add", "motion.mmd.update", "motion.mmd.motion.set", "motion.mmd.diagnostics"} <= specs


def test_motion_mmd_inspector_updates_controls_and_has_dark_surface() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    layer = create_mmd_layer(MODEL, motion_path=MOTION, width=640, height=360, duration_ms=1000)
    window = MotionDesignerWindow(MotionComposition(width=640, height=360, duration_ms=1000, layers=[layer]))
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.mmd)
    window.mmd.bloom.setValue(0.75)
    window.mmd.spring.setValue(0.55)
    changed = window.controller.composition.layers[0]
    assert changed.source.params["render"]["bloom_strength"]["default"] == pytest.approx(0.75)
    assert changed.source.params["playback"]["physics_spring_response"] == pytest.approx(0.55)
    window.resize(1000, 720)
    window.show()
    app.processEvents()
    image = window.mmd.scroll.viewport().grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 80
    window.close()
    app.processEvents()
