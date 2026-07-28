from __future__ import annotations

import pytest


def _auto_layout_document():
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(640, 360)
    document, group = add_ui_object(
        document,
        kind="group",
        name="Toolbar",
        x=20,
        y=30,
        width=400,
        height=100,
    )
    document, _group = update_ui_object(
        document,
        group["id"],
        {
            "layout": {
                "direction": "horizontal",
                "padding": 10,
                "gap": 8,
                "align": "center",
            }
        },
    )
    document, first = add_ui_object(
        document,
        kind="button",
        name="Back",
        parent_id=group["id"],
        width=80,
        height=40,
    )
    document, second = add_ui_object(
        document,
        kind="button",
        name="Continue",
        parent_id=group["id"],
        width=120,
        height=40,
    )
    return document, group, first, second


def test_painter_ui_motion_mapping_uses_stable_object_ids() -> None:
    from app.painter_ui_motion_bridge import (
        attach_motion_composition,
        create_or_sync_ui_motion_composition,
        linked_motion_composition_id,
        resolved_ui_geometry,
    )

    document, group, first, second = _auto_layout_document()
    geometry = resolved_ui_geometry(document)
    assert geometry[first["id"]]["x"] == pytest.approx(30.0)
    assert geometry[first["id"]]["y"] == pytest.approx(60.0)
    assert geometry[second["id"]]["x"] == pytest.approx(118.0)

    composition = create_or_sync_ui_motion_composition(
        document,
        group["id"],
        duration_ms=900,
    )
    assert {layer.id for layer in composition.layers} == {
        group["id"],
        first["id"],
        second["id"],
    }
    assert composition.duration_ms == 900
    linked = attach_motion_composition(
        document,
        group["id"],
        composition.id,
    )
    assert (
        linked_motion_composition_id(linked, group["id"])
        == composition.id
    )


def test_auto_layout_change_rebases_motion_without_losing_offset() -> None:
    from app.motion_designer.schema import Keyframe
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_motion_bridge import create_or_sync_ui_motion_composition

    document, group, first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    first_layer = next(layer for layer in composition.layers if layer.id == first["id"])
    base = list(first_layer.transform.position.default)
    first_layer.transform.position.default = [base[0] + 12.0, base[1] - 4.0]
    first_layer.transform.position.keyframes = [
        Keyframe(time_ms=300, value=[base[0] + 30.0, base[1] + 5.0])
    ]

    changed, _row = update_ui_object(
        document,
        group["id"],
        {
            "layout": {
                "direction": "horizontal",
                "padding": {"left": 30, "top": 10, "right": 10, "bottom": 10},
                "gap": 8,
                "align": "center",
            }
        },
    )
    synced = create_or_sync_ui_motion_composition(
        changed,
        group["id"],
        composition,
    )
    first_layer = next(layer for layer in synced.layers if layer.id == first["id"])
    assert first_layer.transform.position.default == pytest.approx(
        [base[0] + 32.0, base[1] - 4.0]
    )
    assert first_layer.transform.position.keyframes[0].value == pytest.approx(
        [base[0] + 50.0, base[1] + 5.0]
    )


def test_motion_preview_states_evaluate_painter_layers() -> None:
    from app.motion_designer.schema import Keyframe
    from app.painter_ui_motion_bridge import (
        create_or_sync_ui_motion_composition,
        motion_preview_states,
    )

    document, group, first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(
        document,
        group["id"],
        duration_ms=1000,
    )
    layer = next(layer for layer in composition.layers if layer.id == first["id"])
    start = list(layer.transform.position.default)
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=start),
        Keyframe(time_ms=1000, value=[start[0] + 100.0, start[1]]),
    ]
    states = motion_preview_states(composition, 500)
    assert states[first["id"]]["position"][0] == pytest.approx(start[0] + 50.0)
    assert states[first["id"]]["position"][1] == pytest.approx(start[1])
