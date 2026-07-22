from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.content_bridge import layer_from_ppt_element, layer_from_typography, ppt_element_from_layer
from app.motion_designer.schema import MotionComposition, MotionEffectRef
from app.pptgen.schema import AnimationSpec, ElementStyle, SlideElement
from app.typography import AnimationConfig, TextClip, TextStyle


def _app():
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def test_typography_bridge_preserves_style_timing_and_multiline_render() -> None:
    app = _app()
    clip = TextClip(start_ms=1000, end_ms=4000, text="Tiger Studio motion typography",
                    style=TextStyle(font_family="Noto Sans KR", font_size=36, font_weight=700,
                                    color="#ffffff", alignment="left", line_height=1.4,
                                    letter_spacing=2, position_x=.25, position_y=.3),
                    animation=AnimationConfig(in_animation="fade-in", out_animation="fade-out"))
    layer = layer_from_typography(clip, width=1280, height=720)
    layer.source.params.update({"width": 260, "height": 160})
    image = render_typography(layer)
    assert layer.out_ms == 3000 and layer.source_in_ms == 1000
    assert layer.transform.position.default == [320.0, 216.0]
    assert layer.behaviors == []
    assert layer.source.params["text_animation"]["in"] == "fade-in"
    assert layer.source.params["text_animation"]["out"] == "fade-out"
    assert image.width() == 260 and image.height() == 160
    assert not image.isNull()
    app.processEvents()


def test_ppt_bridge_maps_animation_and_reports_native_export_loss() -> None:
    element = SlideElement(
        id="title", kind="text", text="Motion", x=.1, y=.2, w=.4, h=.15,
        style=ElementStyle(font_size=48, bold=True, align="center"),
        animation=AnimationSpec(in_animation="move", duration_ms=600, motion_x=-.2),
    )
    layer = layer_from_ppt_element(element, width=1920, height=1080, duration_ms=5000)
    assert layer.layer_type == "text" and layer.behaviors[0].kind == "slide"
    layer.effects.append(MotionEffectRef(kind="glow"))
    payload, warnings = ppt_element_from_layer(layer, width=1920, height=1080)
    assert payload["kind"] == "text"
    assert any("effects require bake" in warning for warning in warnings)
    assert any("motion requires video bake" in warning for warning in warnings)


class Owner:
    def __init__(self) -> None:
        composition = MotionComposition(width=1280, height=720, duration_ms=4000)
        self._motion_compositions = {composition.id: composition}
        self.composition_id = composition.id


def test_bridge_actions_import_and_export_without_opening_ui() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    imported = registry.execute("motion.import.typography", {
        "composition_id": owner.composition_id,
        "clip": {"text": "Action title", "start_ms": 0, "end_ms": 2000,
                 "style": {"font_size": 42, "position_x": .5, "position_y": .5}},
    })
    assert imported.ok
    layer_id = imported.result["layer"]["id"]
    exported = registry.execute("motion.export.ppt_element", {
        "composition_id": owner.composition_id, "layer_id": layer_id,
    })
    assert exported.ok and exported.result["element"]["text"] == "Action title"
