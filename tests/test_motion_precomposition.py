from __future__ import annotations

import os

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.precomposition import (
    PRECOMP_LAYER_TYPE,
    create_precomposition,
    embedded_composition,
    publish_precomp_property,
    set_embedded_composition,
    set_precomp_override,
    set_precomp_published_value,
)
from app.motion_designer.schema import (
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.validation import validate_composition


def _shape(layer_id: str, x: float, color: str) -> MotionLayer:
    layer = MotionLayer(
        id=layer_id,
        name=layer_id.title(),
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "primitive": "rectangle",
                "width": 80,
                "height": 60,
                "fill": color,
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [x, 90.0]
    return layer


def test_precompose_roundtrip_and_nested_render_match_flat_scene() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    flat = MotionComposition(
        id="flat",
        width=320,
        height=180,
        duration_ms=1000,
        layers=[
            _shape("left", 90.0, "#e76448"),
            _shape("right", 230.0, "#3da8d8"),
        ],
    )
    nested = MotionComposition.from_dict(flat.to_dict())
    nested.id = "nested"
    child, layer = create_precomposition(
        nested,
        ["left", "right"],
        name="Cards",
    )
    assert layer.layer_type == PRECOMP_LAYER_TYPE
    assert [row.id for row in child.layers] == ["left", "right"]
    assert validate_composition(nested).ok
    restored = MotionComposition.from_dict(nested.to_dict())
    restored_child = embedded_composition(restored.layers[0])
    assert restored_child is not None
    assert [row.id for row in restored_child.layers] == ["left", "right"]
    renderer = MotionExportRenderer()
    flat_frame = renderer.render_rgba_array(flat, 0)
    nested_frame = renderer.render_rgba_array(nested, 0)
    assert np.array_equal(flat_frame, nested_frame)


def test_precomp_instance_override_changes_only_nested_snapshot() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    parent = MotionComposition(
        id="override_parent",
        width=320,
        height=180,
        duration_ms=1000,
        layers=[_shape("card", 80.0, "#efb34c")],
    )
    _child, precomp_layer = create_precomposition(parent, ["card"])
    before_child = embedded_composition(precomp_layer)
    assert before_child is not None
    assert before_child.layers[0].transform.position.default == [80.0, 90.0]
    set_precomp_override(
        precomp_layer,
        "card",
        {"transform": {"position": [220.0, 90.0]}},
    )
    renderer = MotionExportRenderer()
    frame = renderer.render_rgba_array(parent, 0)
    alpha = frame[:, :, 3]
    _ys, xs = np.nonzero(alpha > 32)
    assert float(xs.mean()) > 190.0
    unchanged = embedded_composition(precomp_layer)
    assert unchanged is not None
    assert unchanged.layers[0].transform.position.default == [80.0, 90.0]


def test_precomp_actions_create_inspect_override_and_refresh() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {
            "name": "Parent",
            "width": 320,
            "height": 180,
            "duration_ms": 1000,
        },
    )
    composition_id = created.result["payload"]["composition"]["id"]
    for layer in (_shape("a", 80, "#ffffff"), _shape("b", 220, "#ffffff")):
        assert registry.execute(
            "motion.layer.add",
            {"composition_id": composition_id, "layer": layer.to_dict()},
        ).ok
    result = registry.execute(
        "motion.precomp.create",
        {
            "composition_id": composition_id,
            "layer_ids": ["a", "b"],
            "name": "Nested Cards",
        },
    )
    assert result.ok
    payload = result.result["payload"]
    layer_id = payload["precomp_layer"]["id"]
    child_id = payload["nested_composition"]["id"]
    inspected = registry.execute(
        "motion.precomp.inspect",
        {"composition_id": composition_id, "layer_id": layer_id},
    )
    assert inspected.ok
    assert inspected.result["nested_composition"]["id"] == child_id
    assert registry.execute(
        "motion.precomp.override.set",
        {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "child_layer_id": "a",
            "changes": {"visible": False},
        },
    ).ok
    assert registry.execute(
        "motion.precomp.refresh",
        {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "nested_composition_id": child_id,
        },
    ).ok


def test_precomp_ui_multiselect_open_in_place_and_parent_navigation() -> None:
    from app.motion_designer.ui.window import MotionDesignerWindow

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    composition = MotionComposition(
        id="ui_parent",
        name="Parent",
        width=320,
        height=180,
        duration_ms=1000,
        layers=[_shape("a", 80, "#ffffff"), _shape("b", 220, "#ffffff")],
    )
    window = MotionDesignerWindow(composition)
    for item in window.layers.findItems(
        "*",
        Qt.MatchFlag.MatchWildcard | Qt.MatchFlag.MatchRecursive,
        0,
    ):
        item.setSelected(True)
    window._precompose_selected()
    assert len(window.controller.composition.layers) == 1
    precomp_id = window.controller.composition.layers[0].id
    window._open_layer_in_place(precomp_id)
    assert window.controller.composition.name == "Pre-compose"
    assert window.toolbar.parent_action.isEnabled()
    child = MotionComposition.from_dict(window.controller.composition.to_dict())
    child.name = "Edited Child"
    window.controller.replace(child)
    window._navigate_to_parent_composition()
    assert window.controller.composition.name == "Parent"
    assert not window.toolbar.parent_action.isEnabled()
    embedded = embedded_composition(window.controller.composition.layers[0])
    assert embedded is not None and embedded.name == "Edited Child"
    window.close()
    app.processEvents()


def test_published_property_drives_one_precomp_instance_non_destructively() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    parent = MotionComposition(
        id="published_parent",
        width=320,
        height=180,
        duration_ms=1000,
        layers=[_shape("card", 80.0, "#58c49a")],
    )
    child, precomp_layer = create_precomposition(parent, ["card"])
    publication = publish_precomp_property(
        child,
        "card",
        "position",
        name="Card Position",
    )
    set_embedded_composition(precomp_layer, child)
    set_precomp_published_value(
        precomp_layer,
        publication["id"],
        [230.0, 90.0],
    )
    frame = MotionExportRenderer().render_rgba_array(parent, 0)
    _ys, xs = np.nonzero(frame[:, :, 3] > 32)
    assert float(xs.mean()) > 200.0
    stored_child = embedded_composition(precomp_layer)
    assert stored_child is not None
    assert stored_child.layers[0].transform.position.default == [80.0, 90.0]


def test_published_property_actions_refresh_then_set_instance_value() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"name": "Parent", "duration_ms": 1000},
    )
    parent_id = created.result["payload"]["composition"]["id"]
    assert registry.execute(
        "motion.layer.add",
        {
            "composition_id": parent_id,
            "layer": _shape("card", 80, "#ffffff").to_dict(),
        },
    ).ok
    precomp = registry.execute(
        "motion.precomp.create",
        {"composition_id": parent_id, "layer_ids": ["card"]},
    )
    payload = precomp.result["payload"]
    child_id = payload["nested_composition"]["id"]
    precomp_layer_id = payload["precomp_layer"]["id"]
    published = registry.execute(
        "motion.property.publish",
        {
            "composition_id": child_id,
            "layer_id": "card",
            "property_name": "position",
            "name": "Card Position",
        },
    )
    assert published.ok
    publication_id = published.result["payload"]["published_property"]["id"]
    assert registry.execute(
        "motion.precomp.refresh",
        {
            "composition_id": parent_id,
            "layer_id": precomp_layer_id,
            "nested_composition_id": child_id,
        },
    ).ok
    assert registry.execute(
        "motion.precomp.published_value.set",
        {
            "composition_id": parent_id,
            "layer_id": precomp_layer_id,
            "publication_id": publication_id,
            "value": [250.0, 100.0],
        },
    ).ok
