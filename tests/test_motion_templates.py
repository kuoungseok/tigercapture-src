from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.templates import (
    TEMPLATE_CATALOG,
    apply_template_to_composition,
    instantiate_template,
    list_templates,
    template_cost,
)
from app.motion_designer.validation import validate_composition


def _rgba(image: QImage) -> np.ndarray:
    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    return array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def test_template_catalog_has_stable_entries_controls_and_tutorial_guides() -> None:
    rows = list_templates()
    assert len(rows) >= 24
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows:
        control_ids = [item["id"] for item in row["published_controls"]]
        assert {
            "headline",
            "subtitle",
            "accent_color",
            "surface_color",
            "duration_ms",
        } <= set(control_ids)
        assert row["default_duration_ms"] >= 250
        assert row["scene_count"] >= 1
        assert row["workflow"]
    tutorials = [row for row in rows if row["is_tutorial"]]
    assert len(tutorials) == 5
    assert all(row["features"] and row["tutorial_steps"] for row in tutorials)


@pytest.mark.parametrize(
    ("template_id", "duration_ms", "scene_count"),
    (
        ("ios_app_ui_motion_kit", 24000, 5),
        ("product_launch_ad_15s", 15000, 5),
        ("campaign_story_ad_30s", 30000, 6),
        ("course_module_opener_20s", 20000, 4),
        ("step_by_step_tutorial_45s", 45000, 6),
        ("lesson_explainer_60s", 60000, 8),
    ),
)
def test_production_templates_have_real_duration_and_timed_scenes(
    template_id: str,
    duration_ms: int,
    scene_count: int,
) -> None:
    composition = instantiate_template(template_id)
    assert composition.duration_ms == duration_ms
    scenes = sorted(
        (
            layer
            for layer in composition.layers
            if layer.metadata.get("template_role") == "scene"
        ),
        key=lambda layer: layer.in_ms,
    )
    assert len(scenes) == scene_count
    assert scenes[0].in_ms == 0
    assert scenes[-1].out_ms == duration_ms
    assert all(
        current.out_ms == following.in_ms
        for current, following in zip(scenes, scenes[1:])
    )
    assert any(
        layer.metadata.get("template_role") == "media_slot"
        for layer in composition.layers
    )
    metadata = composition.metadata["last_applied_template"]
    assert metadata["scene_count"] == scene_count
    assert metadata["replace_items"]


def test_learning_templates_store_actionable_tutorial_state_and_feature_examples() -> None:
    keyframes = instantiate_template("learn_keyframes_graph")
    focus = next(layer for layer in keyframes.layers if layer.name == "Focus Card")
    assert len(focus.transform.position.keyframes) == 3
    assert focus.metadata["motion_blur"]["enabled"] is True
    assert keyframes.metadata["motion_tutorial"]["current_step"] == 1
    assert len(keyframes.metadata["motion_tutorial"]["steps"]) == 4

    button = instantiate_template("learn_interactive_unreal_button")
    group = next(layer for layer in button.layers if layer.name == "CTA Button")
    assert group.metadata["interactive_component"]["type"] == "button"
    assert any(layer.parent_id == group.id for layer in button.layers)

    procedural = instantiate_template("learn_generators_replicators")
    generator = next(layer for layer in procedural.layers if layer.layer_type == "generator")
    repeated = next(layer for layer in procedural.layers if layer.name == "Replicated Star")
    assert generator.source.params["kind"] == "gradient"
    assert repeated.metadata["replicator"]["arrangement"] == "radial"


@pytest.mark.parametrize("template_id", tuple(TEMPLATE_CATALOG))
def test_every_template_instantiates_an_animated_valid_composition(template_id: str) -> None:
    template = TEMPLATE_CATALOG[template_id]
    for variant in template.variants:
        composition = instantiate_template(template_id, variant=variant)
        assert validate_composition(composition).ok
        assert composition.layers
        assert any(layer.behaviors for layer in composition.layers)
        assert composition.metadata["last_applied_template"]["variant"] == variant


def test_template_preview_changes_over_time() -> None:
    app = QApplication.instance() or QApplication([])
    composition = instantiate_template("logo_reveal", variant="16:9")
    renderer = MotionExportRenderer(cache_capacity=4)
    first = _rgba(renderer.render_frame(composition, 0, width=480, height=270))
    later = _rgba(renderer.render_frame(composition, 500, width=480, height=270))
    assert np.any(first != later)
    assert np.any(later[..., 3] > 0)
    app.processEvents()


@pytest.mark.parametrize(
    "template_id",
    (
        "ios_app_ui_motion_kit",
        "campaign_story_ad_30s",
        "lesson_explainer_60s",
    ),
)
def test_production_template_scenes_render_distinct_nonblank_frames(
    template_id: str,
) -> None:
    app = QApplication.instance() or QApplication([])
    template = TEMPLATE_CATALOG[template_id]
    composition = instantiate_template(template_id, variant=template.variants[0])
    renderer = MotionExportRenderer(cache_capacity=2)
    frames = [
        _rgba(
            renderer.render_frame(
                composition,
                composition.duration_ms * (index + .45) / template.scene_count,
                width=320,
                height=180,
                use_cache=False,
            )
        )
        for index in range(template.scene_count)
    ]
    assert all(np.any(frame[..., :3] > 0) for frame in frames)
    assert all(
        np.count_nonzero(current != following) > current.size * .01
        for current, following in zip(frames, frames[1:])
    )
    app.processEvents()


def test_template_controls_reject_unknown_ids_and_cost_marks_stinger_cached() -> None:
    with pytest.raises(ValueError, match="unknown published template control"):
        instantiate_template("clean_lower_third", controls={"unstable_name": 1})
    cost = template_cost("stream_stinger")
    assert cost["realtime_grade"] == "cached"
    assert cost["requires_pre_render"] is True
    assert cost["particle_limit"] > 0


def test_template_action_and_core_use_the_same_layer_contract() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {"comp": MotionComposition(id="comp", width=1280, height=720)}

    controls = {"headline": "LIVE NOW", "accent_color": "#ff3366"}
    direct = apply_template_to_composition(Owner()._motion_compositions["comp"], "clean_lower_third", controls=controls)
    owner = Owner()
    registry = ActionRegistry(owner)
    applied = registry.execute("motion.template.apply", {
        "composition_id": "comp", "template_id": "clean_lower_third", "controls": controls,
    })
    assert applied.ok
    action_result = owner._motion_compositions["comp"]
    signature = lambda composition: [
        (layer.layer_type, layer.metadata.get("template_role"), layer.source.params.get("text"), layer.source.params.get("fill"))
        for layer in composition.layers
    ]
    assert signature(action_result) == signature(direct)
    assert applied.result["published_controls"]["headline"] == "LIVE NOW"


def test_repeated_template_selection_replaces_previous_instance_without_growth() -> None:
    composition = MotionComposition(
        id="repeat",
        width=1920,
        height=1080,
        duration_ms=4000,
    )
    expected_counts = {}
    for template_id in (
        "ios_app_ui_motion_kit",
        "campaign_story_ad_30s",
        "lesson_explainer_60s",
        "product_launch_ad_15s",
    ):
        composition = apply_template_to_composition(
            composition,
            template_id,
            variant="16:9",
        )
        expected_counts[template_id] = len(
            instantiate_template(template_id, variant="16:9").layers
        )
        assert len(composition.layers) == expected_counts[template_id]
        instance_ids = {
            layer.metadata.get("template_instance_id")
            for layer in composition.layers
        }
        assert instance_ids == {
            composition.metadata["last_applied_template"][
                "template_instance_id"
            ]
        }


def test_template_replacement_preserves_user_layers_and_can_be_disabled() -> None:
    composition = MotionComposition(
        id="manual",
        width=1920,
        height=1080,
        layers=[MotionLayer(id="user-layer", name="User Artwork")],
    )
    first = apply_template_to_composition(
        composition,
        "clean_lower_third",
        variant="16:9",
    )
    replaced = apply_template_to_composition(
        first,
        "logo_reveal",
        variant="16:9",
    )
    assert any(layer.id == "user-layer" for layer in replaced.layers)
    assert not any(
        layer.metadata.get("template_id") == "clean_lower_third"
        for layer in replaced.layers
    )
    stacked = apply_template_to_composition(
        replaced,
        "product_callout",
        variant="16:9",
        replace_existing=False,
    )
    assert len(stacked.layers) > len(replaced.layers)
    assert {
        layer.metadata.get("template_id")
        for layer in stacked.layers
        if layer.metadata.get("template_id")
    } == {"logo_reveal", "product_callout"}


def test_template_action_reports_replaced_layers_and_supports_stack_mode() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {
                "comp": MotionComposition(
                    id="comp",
                    width=1920,
                    height=1080,
                )
            }

    owner = Owner()
    registry = ActionRegistry(owner)
    first = registry.execute(
        "motion.template.apply",
        {
            "composition_id": "comp",
            "template_id": "clean_lower_third",
        },
    )
    assert first.ok
    second = registry.execute(
        "motion.template.apply",
        {
            "composition_id": "comp",
            "template_id": "logo_reveal",
        },
    )
    assert second.ok
    assert second.result["removed_layer_ids"]
    assert second.result["replace_existing"] is True
    before_stack = len(owner._motion_compositions["comp"].layers)
    stacked = registry.execute(
        "motion.template.apply",
        {
            "composition_id": "comp",
            "template_id": "product_callout",
            "replace_existing": False,
        },
    )
    assert stacked.ok
    assert stacked.result["removed_layer_ids"] == []
    assert len(owner._motion_compositions["comp"].layers) > before_stack
