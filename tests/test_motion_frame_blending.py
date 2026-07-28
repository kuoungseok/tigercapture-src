from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.frame_blending import (
    frame_blending_preflight,
    set_layer_frame_blending,
)
from app.motion_designer.precomposition import create_precomposition
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.schema import (
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.validation import validate_composition


def _animated_shape() -> MotionLayer:
    layer = MotionLayer(
        id="moving",
        name="Moving",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "primitive": "rectangle",
                "width": 20,
                "height": 20,
                "fill": "#ffffff",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[60.0, 60.0], interpolation="linear"),
        Keyframe(time_ms=1000, value=[180.0, 60.0], interpolation="linear"),
    ]
    return layer


def _composition() -> tuple[MotionComposition, MotionLayer]:
    composition = MotionComposition(
        id="frame_blend",
        width=240,
        height=120,
        fps=30.0,
        duration_ms=1000,
        layers=[_animated_shape()],
    )
    _child, precomp = create_precomposition(composition, ["moving"])
    return composition, precomp


def test_frame_mix_renders_two_neighboring_nested_source_frames() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    composition, precomp = _composition()
    set_layer_frame_blending(precomp, "frame_mix", source_fps=2.0)
    renderer = MotionExportRenderer()
    frame = renderer.render_rgba_array(composition, 250)
    alpha = frame[:, :, 3]
    assert int(alpha[60, 60]) > 40
    assert int(alpha[60, 120]) > 40
    graph = build_render_graph(composition, 250)
    assert graph.diagnostics["frame_mix_node_count"] == 1
    assert validate_composition(composition).ok


def test_optical_flow_preflight_is_explicit_deterministic_fallback() -> None:
    composition, precomp = _composition()
    set_layer_frame_blending(precomp, "optical_flow")
    report = frame_blending_preflight(precomp)
    assert report["requested_mode"] == "optical_flow"
    assert report["effective_mode"] == "frame_mix"
    assert report["fallback_reason"] == "optical_flow_vector_warp_not_enabled"
    assert isinstance(report["optical_flow"]["available"], bool)


def test_frame_blending_actions_and_ui_menu() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    layer = _animated_shape()
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    changed = registry.execute(
        "motion.frame_blending.set",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "mode": "optical_flow",
            "source_fps": 24.0,
        },
    )
    assert changed.ok
    report = registry.execute(
        "motion.frame_blending.preflight",
        {"composition_id": composition_id, "layer_id": layer.id},
    )
    assert report.ok
    assert report.result["effective_mode"] == "frame_mix"

    from app.motion_designer.ui.window import MotionDesignerWindow

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    window = MotionDesignerWindow(MotionComposition(
        id="frame_blend_ui",
        duration_ms=1000,
        layers=[_animated_shape()],
    ))
    window._select_layer("moving")
    window._apply_time_remap_preset("blend:frame_mix")
    metadata = window.controller.composition.layers[0].metadata
    assert metadata["frame_blending"]["mode"] == "frame_mix"
    window.close()
    app.processEvents()
