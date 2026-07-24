from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.advanced_presets import apply_advanced_preset
from app.motion_designer.ar_pbr_source import create_camera_layer
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.validation import validate_composition


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _box(*, x: float = 80.0, color: str = "#ff3030") -> MotionLayer:
    layer = MotionLayer(
        name="Box",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 24, "height": 24, "fill": color, "stroke_width": 0,
        }),
        out_ms=2000,
    )
    layer.transform.position.default = [x, 60.0]
    return layer


def test_2_5d_camera_projects_opted_in_layers_without_changing_default_camera() -> None:
    layer = _box()
    camera = create_camera_layer(duration_ms=2000)
    composition = MotionComposition(width=200, height=120, duration_ms=2000, layers=[layer, camera])
    baseline = evaluate_composition(composition, 500)[0].matrix
    camera.source.params.update({
        "apply_to_2d": True,
        "parallax_strength": 1.0,
        "pixels_per_unit": 100.0,
        "position": AnimatedProperty(value_type="vector3", default=[0.5, 0.0, 3.25]).to_dict(),
    })
    layer.metadata["depth_z"] = 1.0
    projected = evaluate_composition(composition, 500)[0].matrix
    assert projected != baseline
    assert projected[4] < baseline[4]


def test_generic_replicator_draws_any_renderable_layer_and_motion_blur_spreads_fast_motion() -> None:
    app = _app()
    layer = _box(x=30)
    layer.metadata["replicator"] = {
        "enabled": True, "count": 3, "offset": [35.0, 0.0],
        "rotation": 0.0, "scale": [1.0, 1.0],
        "opacity_start": 1.0, "opacity_end": 1.0,
    }
    composition = MotionComposition(width=140, height=120, duration_ms=2000, fps=30, layers=[layer])
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    assert all(rgba[60, x, 3] > 200 for x in (30, 65, 100))

    layer.metadata.pop("replicator")
    layer.metadata["motion_blur"] = {"enabled": True, "samples": 12, "shutter": 1.0}
    layer.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[20.0, 60.0],
        keyframes=[
            Keyframe(time_ms=900, value=[20.0, 60.0], interpolation="linear"),
            Keyframe(time_ms=1000, value=[120.0, 60.0], interpolation="linear"),
        ],
    )
    composition.revision += 1
    blurred = MotionExportRenderer().render_rgba_array(composition, 999)
    visible_x = np.flatnonzero(blurred[60, :, 3] > 12)
    assert visible_x.size > 24
    app.processEvents()


def test_distortion_and_paper_effects_share_the_layer_effect_path() -> None:
    app = _app()
    layer = _box(x=60, color="#e8dfce")
    layer.effects.extend([
        MotionEffectRef(kind="mesh_warp", params={
            "amplitude_x": AnimatedProperty(default=8.0),
            "amplitude_y": AnimatedProperty(default=4.0),
            "frequency_x": AnimatedProperty(default=1.0),
            "frequency_y": AnimatedProperty(default=1.0),
        }),
        MotionEffectRef(kind="paper_fold", params={
            "strength": AnimatedProperty(default=0.55),
            "angle": AnimatedProperty(default=-18.0),
            "width": AnimatedProperty(default=12.0),
        }),
    ])
    composition = MotionComposition(width=120, height=120, duration_ms=2000, layers=[layer])
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    assert rgba[..., 3].max() > 200
    visible = rgba[..., :3][rgba[..., 3] > 100]
    assert visible.max() > visible.min()
    app.processEvents()


def test_direction_presets_build_editable_camera_paper_and_impact_layers() -> None:
    image = _box()
    image.layer_type = "image"
    image.source.kind = "image"
    image.source.params.update({"width": 320, "height": 180})
    title = _box()
    title.layer_type = "text"
    title.source = SourceRef(kind="typography", params={"text": "POWER", "font_size": 64})
    composition = MotionComposition(width=640, height=360, duration_ms=5000, layers=[image, title])
    camera_result = apply_advanced_preset(
        composition, "editorial_camera_push", layer_ids=[image.id, title.id], start_ms=200,
    )
    assert camera_result["added_layer_ids"]
    assert any(layer.layer_type == "camera" and layer.source.params["apply_to_2d"] for layer in composition.layers)
    result = apply_advanced_preset(
        composition, "cutout_collage", layer_ids=[image.id], start_ms=400,
    )
    assert len(result["added_layer_ids"]) == 5
    assert image.metadata["paper_paste_rig"] is True
    assert any(behavior.kind == "impact" for behavior in image.behaviors)
    assert validate_composition(composition).ok


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_advanced_motion_actions_are_registered_and_mutate_shared_composition() -> None:
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Advanced", "width": 320, "height": 180, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    first = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "name": "Content", "layer_type": "shape", "out_ms": 2000,
            "source": {"kind": "shape", "params": {"width": 40, "height": 40, "fill": "#ffffff"}},
        },
    })
    content_id = first.result["payload"]["composition"]["layers"][0]["id"]
    second = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "name": "Matte", "layer_type": "shape", "out_ms": 2000,
            "source": {"kind": "shape", "params": {"width": 20, "height": 40, "fill": "#ffffff"}},
        },
    })
    matte_id = second.result["payload"]["composition"]["layers"][1]["id"]
    assert registry.execute("motion.matte.set", {
        "composition_id": composition_id, "layer_id": content_id,
        "matte_layer_id": matte_id, "mode": "luma", "inverted": False,
    }).ok
    assert registry.execute("motion.layer.depth.set", {
        "composition_id": composition_id, "layer_id": content_id, "depth_z": 1.25,
    }).ok
    assert registry.execute("motion.blur.set", {
        "composition_id": composition_id, "layer_id": content_id,
        "enabled": True, "samples": 8, "shutter": 0.7,
    }).ok
    assert registry.execute("motion.replicator.set", {
        "composition_id": composition_id, "layer_id": content_id,
        "enabled": True, "count": 4, "offset": [25, 0],
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.metadata["matte_layer_id"] == matte_id
    assert layer.metadata["replicator"]["count"] == 4
    specs = {item["id"] for item in registry.list_actions()}
    assert {
        "motion.matte.set", "motion.layer.depth.set", "motion.blur.set",
        "motion.replicator.set", "motion.text.animator.set",
        "motion.camera.2_5d.set", "motion.paper_paste.create",
        "motion.advanced_preset.apply",
    } <= specs
