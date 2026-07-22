from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.content_bridge import layer_from_ppt_element, layer_from_typography, ppt_element_from_layer
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.schema import MotionBehaviorRef, MotionComposition, MotionEffectRef, MotionLayer, SourceRef
from app.pptgen.animations import animation_payload
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


def test_ppt_bridge_round_trips_native_animation_and_only_warns_for_effects() -> None:
    element = SlideElement(
        id="title", kind="text", text="Motion", x=.1, y=.2, w=.4, h=.15,
        style=ElementStyle(font_size=48, bold=True, align="center"),
        animation=AnimationSpec(in_animation="move", start_ms=180, duration_ms=600, motion_x=-.2,
                                motion_y=.1, trigger="on_click", click_index=2, easing="ease_in"),
    )
    layer = layer_from_ppt_element(element, width=1920, height=1080, duration_ms=5000)
    assert layer.layer_type == "text" and layer.behaviors[0].kind == "slide"
    assert layer.behaviors[0].params["ppt_trigger"] == "on_click"
    assert layer.behaviors[0].params["ppt_click_index"] == 2
    layer.effects.append(MotionEffectRef(kind="glow"))
    payload, warnings = ppt_element_from_layer(layer, width=1920, height=1080)
    assert payload["kind"] == "text"
    assert animation_payload(AnimationSpec.from_dict(payload["animation"])) == animation_payload(element.animation)
    assert any("effects require bake" in warning for warning in warnings)
    assert not any("motion requires video bake" in warning for warning in warnings)


@pytest.mark.parametrize(
    ("animation", "behavior_kind", "slot"),
    [
        (AnimationSpec(in_animation="appear", start_ms=200, duration_ms=1), "fade", "in"),
        (AnimationSpec(in_animation="fade_in", start_ms=200, duration_ms=400), "fade", "in"),
        (AnimationSpec(in_animation="fade_out", start_ms=200, duration_ms=400), "fade", "in"),
        (AnimationSpec(in_animation="move", start_ms=200, duration_ms=400, motion_x=.2, motion_y=-.1), "slide", "in"),
        (AnimationSpec(in_animation="scale", start_ms=200, duration_ms=400, scale=.45), "scale", "in"),
        (AnimationSpec(out_animation="fade_out", start_ms=200, duration_ms=400), "fade", "out"),
    ],
)
def test_ppt_native_animation_effects_round_trip(animation, behavior_kind: str, slot: str) -> None:
    element = SlideElement(id="animated", kind="shape", animation=animation)
    layer = layer_from_ppt_element(element, width=1280, height=720, duration_ms=2000)

    assert len(layer.behaviors) == 1
    assert layer.behaviors[0].kind == behavior_kind
    assert layer.behaviors[0].metadata["ppt_effect_slot"] == slot
    payload, warnings = ppt_element_from_layer(layer, width=1280, height=720)

    assert warnings == []
    assert animation_payload(AnimationSpec.from_dict(payload["animation"])) == animation_payload(animation)


def test_ppt_motion_preview_holds_hidden_and_terminal_states() -> None:
    move = SlideElement(
        id="move", kind="shape", x=.2, y=.2, w=.2, h=.2,
        animation=AnimationSpec(in_animation="move", start_ms=200, duration_ms=400,
                                easing="linear", motion_x=.25, motion_y=-.1),
    )
    layer = layer_from_ppt_element(move, width=1000, height=500, duration_ms=2000)
    composition = MotionComposition(width=1000, height=500, duration_ms=2000, layers=[layer])
    before = evaluate_composition(composition, 100)[0]
    start = evaluate_composition(composition, 200)[0]
    middle = evaluate_composition(composition, 400)[0]
    after = evaluate_composition(composition, 900)[0]

    base = layer.transform.position.default
    assert before.opacity == 0.0
    assert start.opacity == 1.0 and start.position == [base[0] + 250.0, base[1] - 50.0]
    assert middle.position == [base[0] + 125.0, base[1] - 25.0]
    assert after.position == base

    appear = SlideElement(
        id="appear", kind="shape",
        animation=AnimationSpec(in_animation="appear", start_ms=300, duration_ms=1),
    )
    appear_layer = layer_from_ppt_element(appear, width=1000, height=500, duration_ms=2000)
    composition.layers = [appear_layer]
    assert evaluate_composition(composition, 299)[0].opacity == 0.0
    assert evaluate_composition(composition, 300)[0].opacity == 1.0


def test_new_native_motion_behavior_exports_without_bake_and_complex_motion_warns() -> None:
    layer = MotionLayer(
        name="Native fade", layer_type="shape", source=SourceRef(kind="shape", params={"width": 320, "height": 180}),
        behaviors=[MotionBehaviorRef(kind="fade", start_ms=100, end_ms=700,
                                     params={"direction": "out", "easing": "ease_in_out",
                                             "ppt_trigger": "after_previous"})],
    )
    payload, warnings = ppt_element_from_layer(layer, width=1280, height=720)
    exported = animation_payload(AnimationSpec.from_dict(payload["animation"]))
    assert warnings == []
    assert exported["in_animation"] == "fade_out"
    assert exported["trigger"] == "after_previous"
    assert exported["start_ms"] == 100 and exported["duration_ms"] == 600

    layer.behaviors.append(MotionBehaviorRef(kind="wiggle"))
    _, warnings = ppt_element_from_layer(layer, width=1280, height=720)
    assert any("multiple motion behaviors" in warning for warning in warnings)


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


def test_bridge_actions_round_trip_ppt_animation_without_opening_ui() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    imported = registry.execute("motion.import.ppt_element", {
        "composition_id": owner.composition_id,
        "element": {
            "id": "ppt-card", "kind": "shape", "name": "Card",
            "x": .2, "y": .2, "w": .3, "h": .25,
            "animation": {
                "in_animation": "scale", "start_ms": 400, "duration_ms": 700,
                "trigger": "on_click", "click_index": 3, "easing": "ease_in_out", "scale": .55,
            },
        },
    })
    assert imported.ok
    layer_id = imported.result["layer"]["id"]

    exported = registry.execute("motion.export.ppt_element", {
        "composition_id": owner.composition_id, "layer_id": layer_id,
    })

    assert exported.ok
    assert exported.result["native_safe"] is True
    animation = animation_payload(AnimationSpec.from_dict(exported.result["element"]["animation"]))
    assert animation["in_animation"] == "scale"
    assert animation["start_ms"] == 400 and animation["duration_ms"] == 700
    assert animation["trigger"] == "on_click" and animation["click_index"] == 3
    assert animation["easing"] == "ease_in_out" and animation["scale"] == .55
