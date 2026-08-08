from __future__ import annotations

import json


def _add_auto_layout_frame(*, mode: str, cross: str = "start"):
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(800, 600)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Auto frame",
        x=100,
        y=80,
        width=420,
        height=240,
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                "mode": mode,
                "padding": {
                    "left": 10,
                    "top": 20,
                    "right": 30,
                    "bottom": 40,
                },
                "gap": 8,
                "main_alignment": "start",
                "cross_alignment": cross,
            }
        },
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="First",
        parent_id=frame["id"],
        width=80,
        height=50,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        name="Second",
        parent_id=frame["id"],
        width=100,
        height=60,
    )
    return document, frame, first, second


def test_horizontal_auto_layout_exports_native_horizontal_box_and_slots() -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_layout import TIGER_UMG_SCHEMA_VERSION

    document, frame, first, second = _add_auto_layout_frame(
        mode="horizontal",
        cross="center",
    )
    exported = painter_ui_to_umg_document(document)
    rows = {row["Id"]: row for row in exported["Layers"]}

    assert TIGER_UMG_SCHEMA_VERSION == 13
    assert exported["SchemaVersion"] == 16
    assert rows[frame["id"]]["Disposition"] == "Native"
    assert rows[frame["id"]]["PanelKind"] == "Horizontal"
    assert rows[first["id"]]["FlowSlot"] == {
        "Padding": {"Left": 10.0, "Top": 20.0, "Right": 0.0, "Bottom": 40.0},
        "HorizontalAlignment": "Fill",
        "VerticalAlignment": "Center",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
    }
    assert rows[second["id"]]["FlowSlot"]["Padding"] == {
        "Left": 8.0,
        "Top": 20.0,
        "Right": 30.0,
        "Bottom": 40.0,
    }


def test_negative_auto_layout_gap_exports_as_native_slot_overlap() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame, _first, second = _add_auto_layout_frame(
        mode="horizontal",
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {**frame["layout"], "gap": -12}},
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }

    assert rows[frame["id"]]["Disposition"] == "Native"
    assert rows[second["id"]]["FlowSlot"]["Padding"]["Left"] == -12.0


def test_reverse_z_auto_layout_is_blocked_until_overlay_stack_support() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame, _first, _second = _add_auto_layout_frame(
        mode="horizontal",
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {**frame["layout"], "reverse_z_index": True}},
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == frame["id"])

    assert layer["Disposition"] == "Blocked"
    assert (
        "auto_layout_reverse_z_index_requires_overlay_stack_support"
        in layer["BlockReasons"]
    )
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(
        row["object_id"] == frame["id"]
        and "auto_layout_reverse_z_index_requires_overlay_stack_support"
        in row["reasons"]
        for row in preflight["blockers"]
    )


def test_vertical_auto_layout_exports_fill_rule_and_cross_stretch() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame, first, _second = _add_auto_layout_frame(
        mode="vertical",
        cross="stretch",
    )
    document, first = update_ui_object(
        document,
        first["id"],
        {"layout": {"height_sizing": "fill"}},
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }

    assert rows[frame["id"]]["PanelKind"] == "Vertical"
    assert rows[first["id"]]["FlowSlot"]["HorizontalAlignment"] == "Fill"
    assert rows[first["id"]]["FlowSlot"]["VerticalAlignment"] == "Fill"
    assert rows[first["id"]]["FlowSlot"]["SizeRule"] == "Fill"


def test_layout_panel_kind_takes_priority_over_umg_panel_override() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    document, frame, _first, _second = _add_auto_layout_frame(
        mode="horizontal"
    )
    document, _frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                **frame["layout"],
                "umg_panel_mode": "canvas",
            }
        },
    )

    contract = painter_umg_auto_layout_contract(document)
    assert contract["panel_kind_by_id"][frame["id"]] == "Horizontal"
    assert contract["classification_by_id"][frame["id"]] == {
        "policy": "layout",
        "requested": "canvas",
        "effective": "Horizontal",
        "reasons": ["layout_mode_requires_horizontal_panel"],
    }


def test_plain_frame_defaults_to_auto_overlay_panel() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }
    assert rows[frame["id"]]["PanelKind"] == "Overlay"
    classification = painter_umg_auto_layout_contract(document)[
        "classification_by_id"
    ][frame["id"]]
    assert classification == {
        "policy": "auto",
        "requested": "auto",
        "effective": "Overlay",
        "reasons": ["all_children_support_overlay_slots"],
    }


def test_auto_panel_uses_overlay_for_compatible_children_and_exposes_payload() -> None:
    import json

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=100,
        y=80,
        width=420,
        height=240,
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=120,
        y=110,
        width=80,
        height=50,
    )

    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }
    assert rows[frame["id"]]["PanelKind"] == "Overlay"
    assert rows[child["id"]]["FlowSlot"]["Padding"] == {
        "Left": 20.0,
        "Top": 30.0,
        "Right": 0.0,
        "Bottom": 0.0,
    }
    payload = json.loads(rows[frame["id"]]["PayloadJson"])
    assert payload["auto_layout"]["panel_classification"] == {
        "policy": "auto",
        "requested": "auto",
        "effective": "Overlay",
        "reasons": ["all_children_support_overlay_slots"],
    }


def test_auto_panel_falls_back_to_canvas_for_scale_constraint() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    document, frame = add_ui_object(
        create_ui_document(800, 600), kind="frame"
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
    )
    document, _child = update_ui_object(
        document,
        child["id"],
        {"constraints": {"horizontal": "scale", "vertical": "top"}},
    )

    exported = painter_ui_to_umg_document(document)
    rows = {row["Id"]: row for row in exported["Layers"]}
    assert rows[frame["id"]]["PanelKind"] == "Canvas"
    assert rows[child["id"]]["FlowSlot"] == {}
    assert preflight_painter_umg(document)["ok"] is True
    classification = painter_umg_auto_layout_contract(document)[
        "classification_by_id"
    ][frame["id"]]
    assert classification == {
        "policy": "auto",
        "requested": "auto",
        "effective": "Canvas",
        "reasons": [
            f"overlay_child_horizontal_constraint_requires_canvas:{child['id']}:scale"
        ],
    }


def test_explicit_canvas_overrides_auto_overlay_classification() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    document, frame = add_ui_object(
        create_ui_document(800, 600), kind="frame"
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {**frame["layout"], "umg_panel_mode": "canvas"}},
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
    )

    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }
    assert rows[frame["id"]]["PanelKind"] == "Canvas"
    assert rows[child["id"]]["FlowSlot"] == {}
    assert painter_umg_auto_layout_contract(document)[
        "classification_by_id"
    ][frame["id"]] == {
        "policy": "explicit",
        "requested": "canvas",
        "effective": "Canvas",
        "reasons": ["explicit_canvas_panel"],
    }


def test_explicit_overlay_preserves_choice_and_blocks_lossy_anchor() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame = add_ui_object(
        create_ui_document(800, 600), kind="frame"
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {**frame["layout"], "umg_panel_mode": "overlay"}},
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
    )
    document, _child = update_ui_object(
        document,
        child["id"],
        {"constraints": {"horizontal": "left", "vertical": "custom"}},
    )

    exported = painter_ui_to_umg_document(document)
    rows = {row["Id"]: row for row in exported["Layers"]}
    reason = (
        f"overlay_child_vertical_constraint_requires_canvas:{child['id']}:custom"
    )
    assert rows[frame["id"]]["PanelKind"] == "Overlay"
    assert rows[frame["id"]]["Disposition"] == "Blocked"
    assert reason in rows[frame["id"]]["BlockReasons"]
    assert preflight_painter_umg(document)["ok"] is False


def test_explicit_overlay_exports_schema17_native_slots_and_fixed_insets() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=100,
        y=80,
        width=420,
        height=240,
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {"layout": {"mode": "overlay"}},
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=120,
        y=110,
        width=80,
        height=50,
    )

    exported = painter_ui_to_umg_document(document)
    rows = {row["Id"]: row for row in exported["Layers"]}

    assert exported["SchemaVersion"] == 17
    assert rows[frame["id"]]["PanelKind"] == "Overlay"
    assert rows[frame["id"]]["SpacingStrategy"] == "Padding"
    assert rows[child["id"]]["FlowSlot"] == {
        "Padding": {
            "Left": 20.0,
            "Top": 30.0,
            "Right": 0.0,
            "Bottom": 0.0,
        },
        "HorizontalAlignment": "Left",
        "VerticalAlignment": "Top",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
    }
    assert preflight_painter_umg(document)["ok"] is True


def test_schema17_every_layer_has_spacing_fields_and_background_defaults() -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _frame, _first, _second = _add_auto_layout_frame(
        mode="overlay"
    )

    exported = painter_ui_to_umg_document(document)

    assert exported["SchemaVersion"] == 17
    assert exported["Layers"]
    for layer in exported["Layers"]:
        assert "SpacingStrategy" in layer, layer["Id"]
        assert "SpacerSizeRule" in layer, layer["Id"]
        assert "SpacerFillCoefficient" in layer, layer["Id"]

    background = next(
        layer
        for layer in exported["Layers"]
        if layer["Id"] == "__tiger_artboard_background"
    )
    assert background["SpacingStrategy"] == "Padding"
    assert background["SpacerSizeRule"] == "Auto"
    assert background["SpacerFillCoefficient"] == 1.0


def test_schema17_materialized_bake_preserves_spacing_outer_fields(
    tmp_path,
) -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import package_painter_umg

    document, overlay = add_ui_object(
        create_ui_document(320, 240),
        kind="frame",
        x=10,
        y=10,
        width=100,
        height=80,
    )
    document, _overlay = update_ui_object(
        document,
        overlay["id"],
        {"layout": {"mode": "overlay"}},
    )
    document, vector = add_ui_object(
        document,
        kind="path",
        x=140,
        y=60,
        width=40,
        height=30,
        content={
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {
                    "path": "M 0 30 L 20 0 L 40 30 Z",
                    "winding_rule": "nonzero",
                }
            ],
            "vector_paths": [{"path": "M 0 30 L 20 0 L 40 30 Z"}],
        },
        style={
            "fill": "#336699FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#336699FF",
                    "opacity": 1.0,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
        },
    )

    packaged = package_painter_umg(document, tmp_path / "schema17-bake")

    assert packaged["ok"] is True
    assert packaged["document"]["SchemaVersion"] == 17
    baked = next(
        layer
        for layer in packaged["document"]["Layers"]
        if layer["Id"] == vector["id"]
    )
    assert baked["Disposition"] == "Baked"
    assert baked["SpacingStrategy"] == "Padding"
    assert baked["SpacerSizeRule"] == "Auto"
    assert baked["SpacerFillCoefficient"] == 1.0


def test_linear_spacer_strategy_serializes_auto_or_fill_contract() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame, _first, _second = _add_auto_layout_frame(
        mode="horizontal"
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                **frame["layout"],
                "umg_spacing_strategy": "spacer",
                "umg_spacer_size_rule": "fill",
                "umg_spacer_fill_coefficient": 2.5,
            }
        },
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == frame["id"])

    assert exported["SchemaVersion"] == 17
    assert layer["PanelKind"] == "Horizontal"
    assert layer["SpacingStrategy"] == "Spacer"
    assert layer["SpacerSizeRule"] == "Fill"
    assert layer["SpacerFillCoefficient"] == 2.5


def test_grid_auto_layout_exports_native_grid_panel_and_spans() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame, first, second = _add_auto_layout_frame(mode="grid")
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                **frame["layout"],
                "mode": "grid",
                "grid_columns": 3,
                "cross_gap": 12,
            }
        },
    )
    document, first = update_ui_object(
        document,
        first["id"],
        {
            "layout": {
                "grid_column_span": 2,
                "grid_row_span": 2,
                "cell_horizontal_alignment": "center",
                "cell_vertical_alignment": "end",
            }
        },
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }

    assert rows[frame["id"]]["PanelKind"] == "Grid"
    assert rows[first["id"]]["FlowSlot"] == {
        "Padding": {"Left": 10.0, "Top": 20.0, "Right": 0.0, "Bottom": 40.0},
        "HorizontalAlignment": "Center",
        "VerticalAlignment": "Bottom",
        "SizeRule": "Auto",
        "FillCoefficient": 1.0,
        "Row": 0,
        "Column": 0,
        "RowSpan": 2,
        "ColumnSpan": 2,
    }
    assert rows[second["id"]]["FlowSlot"]["Column"] == 2
    assert rows[second["id"]]["FlowSlot"]["Row"] == 0


def test_nested_auto_layout_exports_nested_native_panels() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document, update_ui_object
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, outer = add_ui_object(
        create_ui_document(800, 600), kind="frame", name="Outer"
    )
    document, outer = update_ui_object(
        document, outer["id"], {"layout": {"mode": "horizontal"}}
    )
    document, inner = add_ui_object(
        document,
        kind="frame",
        name="Inner",
        parent_id=outer["id"],
    )
    document, inner = update_ui_object(
        document,
        inner["id"],
        {
            "layout": {
                "mode": "vertical",
                "width_sizing": "fill",
            }
        },
    )
    document, leaf = add_ui_object(
        document,
        kind="rectangle",
        name="Leaf",
        parent_id=inner["id"],
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }

    assert rows[outer["id"]]["PanelKind"] == "Horizontal"
    assert rows[inner["id"]]["PanelKind"] == "Vertical"
    assert rows[inner["id"]]["FlowSlot"]["SizeRule"] == "Fill"
    assert rows[leaf["id"]]["FlowSlot"]["VerticalAlignment"] == "Fill"


def test_unsupported_auto_layout_semantics_are_explicitly_blocked() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame, first, _second = _add_auto_layout_frame(
        mode="horizontal"
    )
    document, frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                **frame["layout"],
                "wrap": True,
                "main_alignment": "space_between",
            }
        },
    )
    document, _first = update_ui_object(
        document,
        first["id"],
        {"layout": {"positioning": "absolute"}},
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == frame["id"])
    reasons = set(layer["BlockReasons"])

    assert layer["Disposition"] == "Blocked"
    assert "auto_layout_wrap_requires_umg_wrap_panel" in reasons
    assert "auto_layout_main_alignment_unsupported:space_between" in reasons
    assert f"auto_layout_absolute_child_unsupported:{first['id']}" in reasons
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(row["object_id"] == frame["id"] for row in preflight["blockers"])


def test_figma_baseline_alignment_is_explicitly_blocked_for_native_umg() -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, frame, _first, _second = _add_auto_layout_frame(
        mode="horizontal",
        cross="baseline",
    )
    exported = painter_ui_to_umg_document(document)
    layer = next(row for row in exported["Layers"] if row["Id"] == frame["id"])

    assert layer["Disposition"] == "Blocked"
    assert (
        "auto_layout_cross_alignment_unsupported:baseline"
        in layer["BlockReasons"]
    )
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(
        row["object_id"] == frame["id"]
        and "auto_layout_cross_alignment_unsupported:baseline"
        in row["reasons"]
        for row in preflight["blockers"]
    )


def test_interactive_component_change_to_is_explicitly_blocked_for_umg() -> None:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document,
        kind="button",
        name="Button",
        width=140,
        height=44,
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, _inspection = define_ui_component_variant_property(
        document,
        component_id=component["id"],
        property_name="State",
        values=["Default", "Pressed"],
    )
    document, pressed = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Button / Pressed",
        variant_properties={"State": "Pressed"},
    )
    document, _result = add_ui_component_change_to_interaction(
        document,
        source_component_id=component["id"],
        target_component_id=pressed["id"],
    )

    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(
        "interactive_component_change_to_runtime_unsupported"
        in row["reasons"]
        for row in preflight["blockers"]
    )


def test_component_slot_maps_to_native_static_umg_panel_contract() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document = create_ui_document(800, 600)
    document, root = add_ui_object(document, kind="frame", name="Card")
    document, slot = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=root["id"],
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Card"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=component["id"],
        source_object_id=slot["id"],
        property_name="Content",
        slot_settings={"max_children": 5},
    )
    document, instance = instantiate_ui_component(
        document, component_id=component["id"], x=300, y=200
    )
    instance_slot = next(
        row
        for row in document["objects"]
        if row["parent_id"] == instance["root_object_id"]
        and row["component_slot_property"] == "Content"
    )
    exported = painter_ui_to_umg_document(document)
    assert exported["SchemaVersion"] == 18
    definition = next(
        row
        for row in exported["Components"]
        if row["Id"] == component["id"]
    )
    layer = next(
        row for row in definition["Layers"] if row["Id"] == slot["id"]
    )
    assert layer["Disposition"] == "Native"
    assert layer["ComponentSlot"] == {
        "property_name": "Content",
        "mapping": "native_panel_static_content",
        "runtime_mutable": False,
        "description": "",
        "preferred_values": [],
        "settings": {
            "stretch_child_on_insert": False,
            "display_empty_by_default": False,
            "min_children": None,
            "max_children": 5,
            "allow_preferred_values_only": False,
        },
    }
    assert definition["Slots"] == [
        {
            "Name": "Content",
            "LayerId": slot["id"],
            "ExposeOnInstanceOnly": True,
        }
    ]
    assert instance_slot["id"] not in {
        row["Id"] for row in exported["Layers"]
    }
    assert {row["Id"] for row in exported["ComponentInstances"]} == {
        root["id"],
        instance["root_object_id"],
    }
    explicit_instance = next(
        row
        for row in exported["ComponentInstances"]
        if row["Id"] == instance["root_object_id"]
    )
    assert explicit_instance == {
        "Id": instance["root_object_id"],
        "ComponentId": component["id"],
        "LayerId": instance["root_object_id"],
        "ParentId": "",
        "PropertyValuesJson": json.dumps(
            {
                "state": "normal",
                "Content": slot["id"],
            },
            separators=(",", ":"),
        ),
        "ResolvedOverridesJson": "{}",
        "SlotContents": [
            {"SlotName": "Content", "RootLayerIds": []}
        ],
    }
    assert preflight_painter_umg(document)["ok"] is True
