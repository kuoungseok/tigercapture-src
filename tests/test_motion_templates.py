from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition
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


def test_template_catalog_has_ten_stable_entries_and_controls() -> None:
    rows = list_templates()
    assert len(rows) == 10
    assert len({row["id"] for row in rows}) == 10
    for row in rows:
        control_ids = [item["id"] for item in row["published_controls"]]
        assert control_ids == ["headline", "subtitle", "accent_color", "surface_color", "duration_ms"]


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
