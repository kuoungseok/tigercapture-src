from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.schema import MotionComposition
from app.motion_designer.validation import validate_composition
from app.motion_designer.vrm_source import (
    create_vrm_layer, evaluate_vrm_frame, inspect_vrm_source, update_vrm_params,
)


ROOT = Path(__file__).resolve().parents[1]
AVATAR = ROOT / "external/assets/vtuber/booth_milica/Milica1.3free/Milica_v1.3.vrm"


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_vrm_source_contract_inspects_real_avatar_and_roundtrips() -> None:
    info = inspect_vrm_source(AVATAR)
    assert info["ok"] is True
    assert info["profile"]["profile"] == "VRM0"
    assert info["profile"]["humanoid_bone_count"] > 10
    layer = create_vrm_layer(AVATAR, width=640, height=360, duration_ms=3000)
    composition = MotionComposition(width=640, height=360, duration_ms=3000, layers=[layer])
    assert validate_composition(composition).ok
    assert MotionComposition.from_dict(composition.to_dict()).to_dict() == composition.to_dict()


def test_vrm_frame_evaluates_pose_lighting_and_source_visibility_policy() -> None:
    layer = create_vrm_layer(
        AVATAR, width=640, height=360, duration_ms=3000,
        params={
            "pose": {"yaw_deg": {"default": 18.0}, "mouth_open": {"default": 0.6}},
            "placement": {"source_exposure": "upper_body", "framing_preset": "bust_up"},
            "lighting": {"ibl_exposure": {"default": 1.4}},
            "playback": {"idle_motion": False, "rate": {"default": 1.5}},
        },
    )
    frame = evaluate_vrm_frame(layer, 400)
    settings = frame.source["settings"]
    assert frame.sample_time_ms == pytest.approx(600)
    assert settings["motion_frame"]["yaw_deg"] == pytest.approx(18.0)
    assert settings["motion_frame"]["mouth_open"] == pytest.approx(0.6)
    assert settings["lighting"]["ibl_exposure"] == pytest.approx(1.4)
    assert settings["framing_preset"] == "half_body"
    assert frame.diagnostics["visibility_policy"]["upgraded_from_requested"] is True


def test_internal_vrm_fallback_accepts_explicit_motion_frame(monkeypatch) -> None:
    from app.vtuber import internal_vrm_fallback as fallback
    from app.vtuber.video_face_driver import idle_motion_frame

    captured = {}

    def attach(descriptor, frames, *, upper_body_mode):
        captured["frame"] = frames[0]
        captured["mode"] = upper_body_mode
        return descriptor

    module = SimpleNamespace(
        _attach_pose_animation=attach,
        _apply_face_morphs=lambda descriptor, _targets, _frame: descriptor,
    )
    monkeypatch.setattr(fallback, "_load_cached_runtime", lambda *_args: {
        "module": module, "frames": (idle_motion_frame(0),), "morph_targets": {},
        "base_descriptor": {}, "descriptor_source": "test", "motion_source": "idle_internal_motion",
    })
    monkeypatch.setattr(fallback, "_render_descriptor_frame", lambda *_args, **_kwargs: (
        Image.new("RGBA", (32, 32), (40, 90, 150, 255)), {"ok": True},
    ))
    image, diagnostics = fallback.render_internal_vrm_fallback_frame({"settings": {
        "avatar_vrm": str(AVATAR),
        "motion_frame": {"yaw_deg": 14, "pitch_deg": -8, "mouth_open": 0.5, "blink_l": 1.0},
        "placement": {"framing": "full_body", "target_width_ratio": 0.8, "target_height_ratio": 0.9},
    }}, width=32, height=32)
    assert image.getbbox() is not None
    assert diagnostics["ok"] is True
    assert diagnostics["pose_source"] == "explicit_motion_frame"
    assert captured["frame"].yaw_deg == pytest.approx(14.0)
    assert captured["frame"].blink_l == pytest.approx(1.0)


def test_vrm_adapter_uses_one_canonical_preview_export_frame(monkeypatch) -> None:
    from app.motion_designer.adapters import vrm as adapter
    from app.vtuber import internal_vrm_fallback as fallback

    layer = create_vrm_layer(AVATAR, width=64, height=64, duration_ms=1000)
    composition = MotionComposition(width=64, height=64, duration_ms=1000, layers=[layer])
    calls: list[int] = []

    def render(_source, *, time_ms, width, height, renderer):
        calls.append(int(time_ms))
        return Image.new("RGBA", (width, height), (32, 96, 180, 255)), {
            "ok": True, "renderer": renderer, "renderer_family": "vtuber_vrm",
        }

    monkeypatch.setattr(fallback, "render_internal_vrm_fallback_frame", render)
    adapter.clear_vrm_cache()
    preview = adapter.render_vrm(layer, 500, composition=composition, quality="preview", viewport_size=(64, 64))
    exported = adapter.render_vrm(layer, 500, composition=composition, quality="export", viewport_size=(64, 64))
    assert not preview.isNull() and preview == exported
    assert calls == [500]
    diagnostics = adapter.vrm_diagnostics(layer.id)
    assert diagnostics["renderer"] == "vrm_mtoon_gpu"
    assert diagnostics["cache_hit"] is True


def test_invalid_vrm_update_is_atomic(tmp_path: Path) -> None:
    layer = create_vrm_layer(AVATAR, width=64, height=64, duration_ms=1000)
    original = layer.source.params["asset"]["avatar_vrm"]
    with pytest.raises(ValueError):
        update_vrm_params(layer, {"asset": {"avatar_vrm": str(tmp_path / "missing.vrm")}})
    assert layer.source.params["asset"]["avatar_vrm"] == original


def test_motion_vrm_actions_add_update_pose_and_list() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "VRM Motion", "width": 640, "height": 360, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.vrm.add", {
        "composition_id": composition_id, "avatar_path": str(AVATAR),
    })
    assert added.ok
    layer_id = added.result["layer"]["id"]
    assert registry.execute("motion.vrm.update", {
        "composition_id": composition_id, "layer_id": layer_id,
        "changes": {"placement": {"framing_preset": "bust_up", "source_exposure": "chest_up"}},
    }).ok
    assert registry.execute("motion.vrm.pose.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "pose": {"yaw_deg": 12.0, "mouth_open": 0.45},
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["pose"]["yaw_deg"]["default"] == pytest.approx(12.0)
    assert layer.source.params["pose"]["mouth_open"]["default"] == pytest.approx(0.45)
    specs = {row["id"] for row in registry.list_actions()}
    assert {"motion.vrm.add", "motion.vrm.update", "motion.vrm.pose.set", "motion.vrm.diagnostics"} <= specs


def test_motion_vrm_inspector_updates_controls_and_has_dark_surface() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication([])
    layer = create_vrm_layer(AVATAR, width=640, height=360, duration_ms=1000)
    window = MotionDesignerWindow(MotionComposition(width=640, height=360, duration_ms=1000, layers=[layer]))
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.vrm)
    window.vrm.yaw.setValue(16.0)
    window.vrm.target_height.setValue(0.88)
    changed = window.controller.composition.layers[0]
    assert changed.source.params["pose"]["yaw_deg"]["default"] == pytest.approx(16.0)
    assert changed.source.params["placement"]["target_height_ratio"]["default"] == pytest.approx(0.88)
    window.resize(1000, 720)
    window.show()
    app.processEvents()
    image = window.vrm.scroll.viewport().grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 80
    window.close()
    app.processEvents()
