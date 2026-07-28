from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.templates import (
    apply_template_to_composition,
    get_template,
    instantiate_template,
)
from app.motion_designer.trend_templates import (
    TREND_TEMPLATE_SPECS,
    preflight_trend_templates,
    trend_template_capabilities,
)
from app.motion_designer.validation import validate_composition
from app.unreal_umg_document import motion_composition_to_umg_document


TREND_IDS = tuple(str(item["id"]) for item in TREND_TEMPLATE_SPECS)


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(),
        converted.bytesPerLine(),
    )
    return array[:, : converted.width() * 4].reshape(
        converted.height(),
        converted.width(),
        4,
    ).copy()


def test_trend_catalog_has_seven_supported_products_and_explicit_3d_block():
    assert len(TREND_IDS) == 7
    assert len(set(TREND_IDS)) == 7
    for template_id in TREND_IDS:
        template = get_template(template_id)
        assert template.category == "2026 Trends"
        assert template.scene_count >= 3
        assert len(template.tutorial_steps) >= 4
        assert template.replace_items
        assert template.features
    capabilities = trend_template_capabilities()
    assert capabilities["available_template_ids"] == list(TREND_IDS)
    assert capabilities["blocked"] == [{
        "id": "painterly_3d_character_spot",
        "reason": "M24 painterly 2D/3D material pipeline is not implemented",
        "fallback": "Use a 2D character layer with Luxury Craft or Editorial Collage",
    }]
    preflight = preflight_trend_templates()
    assert preflight["ok"] is True
    assert preflight["summary"]["template_count"] == 7
    assert preflight["summary"]["variant_count"] == 17


def test_trend_templates_are_valid_editable_and_have_complete_scene_ranges():
    for template_id in TREND_IDS:
        template = get_template(template_id)
        for variant in template.variants:
            composition = instantiate_template(template_id, variant=variant)
            assert validate_composition(composition).ok
            state = composition.metadata["trend_template_state"]
            assert state["editable"] is True
            assert state["template_id"] == template_id
            scenes = sorted(
                (
                    layer for layer in composition.layers
                    if layer.metadata.get("template_role") == "scene"
                ),
                key=lambda layer: layer.in_ms,
            )
            assert len(scenes) == template.scene_count
            assert scenes[0].in_ms == 0
            assert scenes[-1].out_ms == composition.duration_ms
            assert all(
                current.out_ms == following.in_ms
                for current, following in zip(scenes, scenes[1:])
            )
            assert sum(
                layer.metadata.get("template_role") == "media_slot"
                for layer in composition.layers
            ) == template.scene_count


def test_trend_styles_use_real_feature_contracts_and_umg_never_silently_omits():
    craft = instantiate_template("luxury_craft_product_reveal")
    assert any(effect.kind == "craft_style" for layer in craft.layers for effect in layer.effects)

    glass = instantiate_template("liquid_glass_app_promo")
    assert sum(effect.kind == "tiger_glass" for layer in glass.layers for effect in layer.effects) == 3
    assert all(
        effect.metadata.get("driver", {}).get("source") == "pointer"
        for layer in glass.layers
        for effect in layer.effects
        if effect.kind == "tiger_glass"
    )

    stop = instantiate_template("clay_stop_motion_mascot")
    assert any("stop_motion" in layer.metadata for layer in stop.layers)

    story = instantiate_template("emotional_brand_story")
    assert len(story.metadata["story_direction"]["beats"]) == 5

    kinetic = instantiate_template("kinetic_type_vertical_short", variant="9:16")
    assert any(
        layer.transform.scale.keyframes
        for layer in kinetic.layers
        if layer.metadata.get("template_role") == "headline"
    )

    for composition in (craft, glass, stop):
        document = motion_composition_to_umg_document(composition)
        visual_layers = [
            row for row in document["Layers"]
            if row["Kind"] not in {"Group", "Unsupported"}
        ]
        assert visual_layers
        assert all(row["Disposition"] in {"Native", "Blocked"} for row in visual_layers)
        assert all(
            row["Disposition"] != "Blocked"
            or "umg_block_reasons" in row["PayloadJson"]
            for row in visual_layers
        )


def test_replacing_stop_motion_trend_template_clears_only_managed_state():
    stop = instantiate_template("clay_stop_motion_mascot")
    stop.metadata["manual_note"] = {"keep": True}

    replaced = apply_template_to_composition(
        stop,
        "kinetic_type_vertical_short",
        variant="9:16",
    )

    assert replaced.metadata["manual_note"] == {"keep": True}
    assert replaced.metadata["trend_template_state"]["style"] == "kinetic_type"
    assert "stop_motion" not in replaced.metadata


def test_trend_scene_frames_are_real_nonblank_and_visually_distinct():
    app = QApplication.instance() or QApplication([])
    renderer = MotionExportRenderer(cache_capacity=2)
    for template_id in TREND_IDS:
        template = get_template(template_id)
        composition = instantiate_template(template_id, variant=template.variants[0])
        frames = [
            _rgba(
                renderer.render_frame(
                    composition,
                    composition.duration_ms * (index + 0.45) / template.scene_count,
                    width=240,
                    height=135,
                    use_cache=False,
                )
            )
            for index in range(template.scene_count)
        ]
        assert all(np.any(frame[..., 3] > 0) for frame in frames)
        assert all(
            np.count_nonzero(current != following) > current.size * 0.005
            for current, following in zip(frames, frames[1:])
        )
    app.processEvents()
