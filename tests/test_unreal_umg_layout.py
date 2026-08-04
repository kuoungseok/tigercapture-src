from __future__ import annotations

import pytest


def _assert_vector(value, expected) -> None:
    assert value["X"] == pytest.approx(expected[0])
    assert value["Y"] == pytest.approx(expected[1])


def _assert_offsets(value, expected) -> None:
    for key, number in zip(("Left", "Top", "Right", "Bottom"), expected):
        assert value[key] == pytest.approx(number)


def test_motion_document_v9_separates_canvas_slot_and_render_pivot() -> None:
    from app.motion_designer.schema import (
        MotionComposition,
        MotionLayer,
        SourceRef,
    )
    from app.unreal_umg_document import motion_composition_to_umg_document
    from app.unreal_umg_layout import TIGER_UMG_SCHEMA_VERSION

    layer = MotionLayer(
        id="motion-card",
        layer_type="image",
        source=SourceRef(
            kind="image",
            params={"width": 200, "height": 40},
        ),
    )
    layer.transform.position.default = [120.0, 80.0]
    layer.transform.anchor.default = [0.25, 0.75]

    document = motion_composition_to_umg_document(
        MotionComposition(id="motion-layout", layers=[layer])
    )
    exported = document["Layers"][0]

    assert document["SchemaVersion"] == TIGER_UMG_SCHEMA_VERSION == 11
    _assert_vector(exported["Position"], (120.0, 80.0))
    _assert_vector(exported["Size"], (200.0, 40.0))
    _assert_vector(exported["Anchor"], (0.25, 0.75))
    _assert_vector(exported["RenderTransformPivot"], (0.25, 0.75))
    slot = exported["CanvasSlot"]
    _assert_vector(slot["AnchorMinimum"], (0.0, 0.0))
    _assert_vector(slot["AnchorMaximum"], (0.0, 0.0))
    _assert_offsets(slot["Offsets"], (120.0, 80.0, 200.0, 40.0))
    _assert_vector(slot["Alignment"], (0.25, 0.75))


@pytest.mark.parametrize(
    (
        "horizontal",
        "vertical",
        "anchor_minimum",
        "anchor_maximum",
        "offsets",
    ),
    [
        ("left", "top", (0.0, 0.0), (0.0, 0.0), (60.0, 98.0, 100.0, 60.0)),
        (
            "center",
            "center",
            (0.5, 0.5),
            (0.5, 0.5),
            (-140.0, -52.0, 100.0, 60.0),
        ),
        (
            "right",
            "bottom",
            (1.0, 1.0),
            (1.0, 1.0),
            (-340.0, -202.0, 100.0, 60.0),
        ),
        (
            "stretch",
            "stretch",
            (0.0, 0.0),
            (1.0, 1.0),
            (40.0, 50.0, 260.0, 190.0),
        ),
        (
            "scale",
            "scale",
            (0.1, 50.0 / 300.0),
            (0.35, 110.0 / 300.0),
            (0.0, 0.0, 0.0, 0.0),
        ),
    ],
)
def test_painter_adapter_maps_all_constraint_modes_to_canvas_slot(
    horizontal,
    vertical,
    anchor_minimum,
    anchor_maximum,
    offsets,
) -> None:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        PAINTER_UMG_ADAPTER_SCHEMA,
        painter_ui_to_umg_document,
    )

    document = create_ui_document(400, 300)
    document, row = add_ui_object(
        document,
        kind="button",
        x=40,
        y=50,
        width=100,
        height=60,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": horizontal,
            "vertical": vertical,
            "pivot_x": 0.2,
            "pivot_y": 0.8,
        },
    )

    umg_document = painter_ui_to_umg_document(document)
    assert PAINTER_UMG_ADAPTER_SCHEMA.endswith(".v7")
    exported = umg_document["Layers"][0]

    _assert_vector(exported["Position"], (60.0, 98.0))
    _assert_vector(exported["Size"], (100.0, 60.0))
    _assert_vector(exported["Anchor"], (0.2, 0.8))
    _assert_vector(exported["RenderTransformPivot"], (0.2, 0.8))
    slot = exported["CanvasSlot"]
    _assert_vector(slot["AnchorMinimum"], anchor_minimum)
    _assert_vector(slot["AnchorMaximum"], anchor_maximum)
    _assert_offsets(slot["Offsets"], offsets)
    _assert_vector(slot["Alignment"], (0.2, 0.8))


def test_painter_adapter_uses_current_resolved_constraint_geometry() -> None:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(400, 300)
    document, _row = add_ui_object(
        document,
        kind="button",
        x=280,
        y=230,
        width=100,
        height=50,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "right",
            "vertical": "bottom",
            "pivot_x": 0.2,
            "pivot_y": 0.8,
        },
    )
    document["artboards"][0]["width"] = 600.0
    document["artboards"][0]["height"] = 500.0

    exported = painter_ui_to_umg_document(document)["Layers"][0]

    _assert_vector(exported["Position"], (500.0, 470.0))
    slot = exported["CanvasSlot"]
    _assert_vector(slot["AnchorMinimum"], (1.0, 1.0))
    _assert_vector(slot["AnchorMaximum"], (1.0, 1.0))
    _assert_offsets(slot["Offsets"], (-100.0, -30.0, 100.0, 50.0))


def test_painter_adapter_converts_nested_native_group_child_to_parent_local() -> None:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        x=100,
        y=80,
        width=400,
        height=300,
    )
    document, child = add_ui_object(
        document,
        kind="text",
        parent_id=parent["id"],
        x=160,
        y=130,
        width=100,
        height=50,
        content={"text": "Nested"},
    )
    authored = next(
        row for row in document["objects"] if row["id"] == child["id"]
    )
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 100.0, "y": 80.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "left",
            "vertical": "top",
            "pivot_x": 0.25,
            "pivot_y": 0.75,
        },
    )

    layers = {
        row["Id"]: row for row in painter_ui_to_umg_document(document)["Layers"]
    }
    exported = layers[child["id"]]

    assert exported["ParentId"] == parent["id"]
    _assert_vector(exported["Position"], (85.0, 87.5))
    _assert_offsets(
        exported["CanvasSlot"]["Offsets"],
        (85.0, 87.5, 100.0, 50.0),
    )


def test_painter_adapter_emits_fractional_custom_point_anchor() -> None:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _row = add_ui_object(
        create_ui_document(400, 300),
        kind="button",
        x=100,
        y=60,
        width=80,
        height=40,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 0.25,
            "anchor_max_x": 0.25,
            "anchor_min_y": 0.5,
            "anchor_max_y": 0.5,
            "pivot_x": 0.25,
            "pivot_y": 0.75,
        },
    )

    exported = painter_ui_to_umg_document(document)["Layers"][0]

    _assert_vector(exported["Position"], (120.0, 90.0))
    _assert_vector(exported["RenderTransformPivot"], (0.25, 0.75))
    slot = exported["CanvasSlot"]
    _assert_vector(slot["AnchorMinimum"], (0.25, 0.5))
    _assert_vector(slot["AnchorMaximum"], (0.25, 0.5))
    _assert_offsets(slot["Offsets"], (20.0, -60.0, 80.0, 40.0))
    _assert_vector(slot["Alignment"], (0.25, 0.75))


def test_painter_adapter_emits_fractional_custom_stretched_anchor() -> None:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _row = add_ui_object(
        create_ui_document(400, 300),
        kind="frame",
        x=100,
        y=60,
        width=200,
        height=100,
    )
    authored = document["objects"][0]
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 400.0, "height": 300.0},
        {
            "horizontal": "custom",
            "vertical": "custom",
            "anchor_min_x": 0.2,
            "anchor_max_x": 0.8,
            "anchor_min_y": 0.1,
            "anchor_max_y": 0.9,
        },
    )

    exported = painter_ui_to_umg_document(document)["Layers"][0]

    slot = exported["CanvasSlot"]
    _assert_vector(slot["AnchorMinimum"], (0.2, 0.1))
    _assert_vector(slot["AnchorMaximum"], (0.8, 0.9))
    _assert_offsets(slot["Offsets"], (20.0, 30.0, 20.0, 110.0))
