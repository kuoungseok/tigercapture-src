from __future__ import annotations


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

    assert exported["SchemaVersion"] == TIGER_UMG_SCHEMA_VERSION
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


def test_plain_frame_remains_canvas_panel() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
    )
    rows = {
        row["Id"]: row
        for row in painter_ui_to_umg_document(document)["Layers"]
    }
    assert rows[frame["id"]]["PanelKind"] == "Canvas"


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
    layer = next(
        row for row in exported["Layers"] if row["Id"] == instance_slot["id"]
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
    assert preflight_painter_umg(document)["ok"] is True
