from __future__ import annotations

import copy
import json


def _text_boolean_component_document() -> tuple[dict, dict, dict, dict]:
    from app.painter_ui_components import (
        bind_ui_component_property,
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=40,
        y=50,
        width=220,
        height=120,
    )
    document, label = add_ui_object(
        document,
        kind="text",
        name="Label",
        parent_id=root["id"],
        x=60,
        y=72,
        width=140,
        height=28,
        content={"text": "Default"},
    )
    document, badge = add_ui_object(
        document,
        kind="frame",
        name="Badge",
        parent_id=root["id"],
        x=210,
        y=70,
        width=24,
        height=24,
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Card",
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Label",
        definition={"type": "text", "default": "Default"},
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=label["id"],
        property_name="Label",
        target_path="content.text",
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Show badge",
        definition={"type": "boolean", "default": True},
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=badge["id"],
        property_name="Show badge",
        target_path="visible",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=360,
        y=220,
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Label",
        property_value="Hello UMG",
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Show badge",
        property_value=False,
    )
    return document, component, instance, {"root": root, "label": label, "badge": badge}


def test_schema18_splits_definition_and_instance_with_static_properties() -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.unreal_umg_component import (
        TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION,
        validate_umg_component_contract,
    )

    document, component, instance, source = _text_boolean_component_document()
    exported = painter_ui_to_umg_document(document)

    assert exported["SchemaVersion"] == TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION == 18
    screen_ids = {row["Id"] for row in exported["Layers"]}
    assert source["root"]["id"] in screen_ids
    assert source["label"]["id"] not in screen_ids
    assert screen_ids >= {"__tiger_artboard_background", instance["root_object_id"]}
    definition = exported["Components"][0]
    assert definition["Id"] == component["id"]
    assert definition["RootLayerId"] == source["root"]["id"]
    assert {row["Id"] for row in definition["Layers"]} == {
        source["root"]["id"],
        source["label"]["id"],
        source["badge"]["id"],
    }
    root_layer = next(
        row for row in definition["Layers"] if row["Id"] == source["root"]["id"]
    )
    assert root_layer["ParentId"] == ""
    assert root_layer["Position"] == {"X": 110.0, "Y": 60.0}
    properties = {row["Name"]: row for row in definition["Properties"]}
    assert properties["Label"]["Bindings"] == [
        {"LayerId": source["label"]["id"], "TargetPath": "content.text"}
    ]
    assert properties["Show badge"]["Bindings"] == [
        {"LayerId": source["badge"]["id"], "TargetPath": "visible"}
    ]
    assert {row["Id"] for row in exported["ComponentInstances"]} == {
        source["root"]["id"],
        instance["root_object_id"],
    }
    implicit_placement = next(
        row
        for row in exported["ComponentInstances"]
        if row["Id"] == source["root"]["id"]
    )
    implicit_values = json.loads(implicit_placement["PropertyValuesJson"])
    assert implicit_values["Label"] == "Default"
    assert implicit_values["Show badge"] is True
    placement = next(
        row
        for row in exported["ComponentInstances"]
        if row["Id"] == instance["root_object_id"]
    )
    assert placement["Id"] == placement["LayerId"] == instance["root_object_id"]
    assert json.loads(placement["PropertyValuesJson"])["Label"] == "Hello UMG"
    assert json.loads(placement["PropertyValuesJson"])["Show badge"] is False
    screen_root = next(row for row in exported["Layers"] if row["Id"] == placement["Id"])
    marker = json.loads(screen_root["PayloadJson"])["component_instance"]
    assert marker["component_id"] == component["id"]
    assert marker["property_values"]["Label"] == "Hello UMG"
    assert validate_umg_component_contract(exported) == []
    missing_implicit_record = copy.deepcopy(exported)
    missing_implicit_record["ComponentInstances"] = [
        row
        for row in missing_implicit_record["ComponentInstances"]
        if row["Id"] != source["root"]["id"]
    ]
    assert (
        "umg_component_definition_layer_leaked_to_screen"
        in validate_umg_component_contract(missing_implicit_record)
    )


def test_resized_rounded_card_component_root_binds_live_instance_geometry() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, root = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        name="Responsive Card",
        width=100,
        height=50,
        style={"fill": "#123456FF", "radius": 20},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Responsive Card",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=300,
        y=200,
    )
    document, _ = update_ui_object(
        document,
        instance["root_object_id"],
        {"width": 240, "height": 100},
    )

    exported = painter_ui_to_umg_document(document)
    definition = exported["Components"][0]
    definition_root = next(
        row
        for row in definition["Layers"]
        if row["Id"] == definition["RootLayerId"]
    )

    assert exported["SchemaVersion"] == 19
    assert definition_root["CanvasSlot"] == {
        "AnchorMinimum": {"X": 0.0, "Y": 0.0},
        "AnchorMaximum": {"X": 1.0, "Y": 1.0},
        "Offsets": {"Left": 0.0, "Top": 0.0, "Right": 0.0, "Bottom": 0.0},
        "Alignment": {"X": 0.0, "Y": 0.0},
    }
    assert definition_root["Material"]["SizeBinding"] == "WidgetGeometry"
    assert preflight_painter_umg(document)["ok"] is True
    placement = next(
        row
        for row in exported["ComponentInstances"]
        if row["Id"] == instance["root_object_id"]
    )
    placement_layer = next(
        row
        for row in exported["Layers"]
        if row["Id"] == instance["root_object_id"]
    )
    assert placement_layer["Disposition"] == "Native"
    assert placement_layer["Material"] == {}
    assert placement_layer["ImageFill"] == {}
    assert placement_layer["Flipbook"] == {}
    assert placement_layer["ButtonStyle"] == {}
    assert json.loads(placement_layer["PayloadJson"])["umg_mapping"] == (
        "native_component_instance"
    )
    assert json.loads(placement["ResolvedOverridesJson"]) == {}


def test_schema19_component_mixes_legacy_gradient_and_dynamic_card() -> None:
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, root = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        width=400,
        height=240,
    )
    gradient_style = {
        "fill_gradient": {
            "type": "linear",
            "start": {"x": 0.0, "y": 0.5},
            "end": {"x": 1.0, "y": 0.5},
            "stops": [
                {"position": 0.0, "color": "#112233FF"},
                {"position": 1.0, "color": "#445566FF"},
            ],
        }
    }
    document, gradient = add_ui_object(
        document,
        kind="rectangle",
        parent_id=root["id"],
        name="Legacy Gradient",
        style=gradient_style,
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        parent_id=root["id"],
        name="Dynamic Card",
        style={"fill": "#245DA8FF", "radius": 12},
    )
    document, _ = update_ui_object(
        document,
        card["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "top"}},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Mixed Card",
    )

    exported = painter_ui_to_umg_document(document)
    definition = next(
        row for row in exported["Components"] if row["Id"] == component["id"]
    )
    layers = {row["Id"]: row for row in definition["Layers"]}

    assert exported["SchemaVersion"] == 19
    assert layers[gradient["id"]]["Material"]["Schema"].endswith(".v1")
    assert "SizeBinding" not in layers[gradient["id"]]["Material"]
    assert layers[card["id"]]["Material"]["SizeBinding"] == "WidgetGeometry"
    assert preflight_painter_umg(document)["ok"] is True
    assert preflight_painter_umg(document)["ok"] is True


def test_nested_instance_is_definition_placeholder_and_dependency() -> None:
    from app.painter_ui_components import (
        bind_ui_component_property,
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_component import validate_umg_component_contract

    document = create_ui_document(800, 600)
    document, badge_root = add_ui_object(
        document, kind="frame", name="Badge", width=28, height=28
    )
    document, badge_component = convert_ui_object_to_component(
        document, root_object_id=badge_root["id"], name="Badge"
    )
    document, card_root = add_ui_object(
        document, kind="frame", name="Card", x=100, y=120, width=240, height=120
    )
    document, nested = instantiate_ui_component(
        document, component_id=badge_component["id"], x=290, y=150
    )
    document, _ = update_ui_object(
        document, nested["root_object_id"], {"parent_id": card_root["id"]}
    )
    document, card_component = convert_ui_object_to_component(
        document, root_object_id=card_root["id"], name="Card"
    )
    document, _ = define_ui_component_property(
        document,
        component_id=card_component["id"],
        property_name="Show badge",
        definition={"type": "boolean", "default": True},
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=card_component["id"],
        source_object_id=nested["root_object_id"],
        property_name="Show badge",
        target_path="visible",
    )
    document, placement = instantiate_ui_component(
        document, component_id=card_component["id"], x=430, y=260
    )

    exported = painter_ui_to_umg_document(document)
    card = next(row for row in exported["Components"] if row["Id"] == card_component["id"])
    assert card["DependencyComponentIds"] == [badge_component["id"]]
    nested_layer = next(
        row for row in card["Layers"] if row["Id"] == nested["root_object_id"]
    )
    marker = json.loads(nested_layer["PayloadJson"])["component_instance"]
    assert marker["id"] == nested["root_object_id"]
    assert marker["component_id"] == badge_component["id"]
    show_badge = next(row for row in card["Properties"] if row["Name"] == "Show badge")
    assert show_badge["Bindings"] == [
        {"LayerId": nested["root_object_id"], "TargetPath": "visible"}
    ]
    assert {row["Id"] for row in exported["ComponentInstances"]} == {
        badge_root["id"],
        card_root["id"],
        placement["root_object_id"],
    }
    assert nested["root_object_id"] not in {
        row["Id"] for row in exported["Layers"]
    }
    assert validate_umg_component_contract(exported) == []


def test_static_variant_id_and_tuple_are_preserved_and_validated() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_component import validate_umg_component_contract

    document = create_ui_document(800, 600)
    document, root = add_ui_object(document, kind="button", name="Button")
    document, family = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Button"
    )
    document, _ = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="State",
        values=["Default", "Hover"],
        default_value="Default",
    )
    document, hover = create_ui_component_variant(
        document,
        component_id=family["id"],
        name="Button / Hover",
        variant_properties={"State": "Hover"},
    )
    document, placement = instantiate_ui_component(
        document, component_id=hover["id"], x=340, y=220
    )

    exported = painter_ui_to_umg_document(document)
    hover_record = next(row for row in exported["Components"] if row["Id"] == hover["id"])
    assert hover_record["BaseComponentId"] == family["id"]
    assert json.loads(hover_record["VariantValuesJson"]) == {"State": "Hover"}
    instance = next(row for row in exported["ComponentInstances"] if row["Id"] == placement["root_object_id"])
    assert instance["ComponentId"] == hover["id"]
    assert json.loads(instance["PropertyValuesJson"])["State"] == "Hover"
    assert validate_umg_component_contract(exported) == []

    malformed = copy.deepcopy(exported)
    malformed["ComponentInstances"][0]["PropertyValuesJson"] = json.dumps(
        {**json.loads(malformed["ComponentInstances"][0]["PropertyValuesJson"]), "State": "Default"}
    )
    assert "umg_component_instance_variant_tuple_mismatch" in validate_umg_component_contract(malformed)


def test_slot_custom_content_stays_in_screen_layers_and_is_named() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        insert_ui_object_into_component_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_component import validate_umg_component_contract

    document = create_ui_document(800, 600)
    document, root = add_ui_object(document, kind="frame", name="Card")
    document, slot = add_ui_object(
        document, kind="frame", name="Content", parent_id=root["id"]
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Card"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=component["id"],
        source_object_id=slot["id"],
        property_name="Content",
    )
    document, placement = instantiate_ui_component(
        document, component_id=component["id"], x=300, y=200
    )
    document, custom = add_ui_object(
        document,
        kind="text",
        name="Custom",
        x=520,
        y=400,
        width=100,
        height=24,
        content={"text": "Slot content"},
    )
    document, _ = insert_ui_object_into_component_slot(
        document,
        instance_root_id=placement["root_object_id"],
        property_name="Content",
        object_id=custom["id"],
    )
    exported = painter_ui_to_umg_document(document)
    definition = exported["Components"][0]
    assert definition["Slots"] == [
        {"Name": "Content", "LayerId": slot["id"], "ExposeOnInstanceOnly": True}
    ]
    instance = next(
        row
        for row in exported["ComponentInstances"]
        if row["Id"] == placement["root_object_id"]
    )
    assert instance["SlotContents"] == [
        {"SlotName": "Content", "RootLayerIds": [custom["id"]]}
    ]
    custom_layer = next(row for row in exported["Layers"] if row["Id"] == custom["id"])
    assert custom_layer["ParentId"] == placement["root_object_id"]
    assert validate_umg_component_contract(exported) == []


def test_rounded_card_named_slot_root_uses_generated_overlay_geometry() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        insert_ui_object_into_component_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document, kind="frame", name="Card", width=240, height=120
    )
    document, slot = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=root["id"],
        width=200,
        height=80,
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Card"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=component["id"],
        source_object_id=slot["id"],
        property_name="Content",
    )
    document, placement = instantiate_ui_component(
        document, component_id=component["id"], x=300, y=200
    )
    document, custom = add_ui_object(
        document,
        kind="rectangle",
        name="Rounded custom content",
        x=320,
        y=220,
        width=180,
        height=70,
        style={"fill": "#245DA8FF", "radius": 18},
    )
    document, _ = insert_ui_object_into_component_slot(
        document,
        instance_root_id=placement["root_object_id"],
        property_name="Content",
        object_id=custom["id"],
    )
    document, _ = update_ui_object(
        document,
        custom["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "stretch"}},
    )

    exported = painter_ui_to_umg_document(document)
    custom_layer = next(
        row for row in exported["Layers"] if row["Id"] == custom["id"]
    )

    assert exported["SchemaVersion"] == 19
    assert custom_layer["ParentId"] == placement["root_object_id"]
    assert custom_layer["Disposition"] == "Material"
    assert custom_layer["Material"]["SizeBinding"] == "WidgetGeometry"
    assert preflight_painter_umg(document)["ok"] is True


def test_nested_component_named_slot_rounded_root_uses_live_overlay_size() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        insert_ui_object_into_component_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document = create_ui_document(900, 700)
    document, inner_root = add_ui_object(
        document, kind="frame", name="Inner", width=220, height=100
    )
    document, slot = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=inner_root["id"],
        width=180,
        height=70,
    )
    document, inner_component = convert_ui_object_to_component(
        document, root_object_id=inner_root["id"], name="Inner"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=inner_component["id"],
        source_object_id=slot["id"],
        property_name="Content",
    )
    document, outer_root = add_ui_object(
        document,
        kind="frame",
        name="Outer",
        x=260,
        y=180,
        width=320,
        height=180,
    )
    document, nested = instantiate_ui_component(
        document,
        component_id=inner_component["id"],
        x=280,
        y=200,
    )
    document, _ = update_ui_object(
        document,
        nested["root_object_id"],
        {"parent_id": outer_root["id"]},
    )
    document, custom = add_ui_object(
        document,
        kind="rectangle",
        name="Nested rounded content",
        x=300,
        y=220,
        width=160,
        height=60,
        style={"fill": "#123456FF", "radius": 14},
    )
    document, _ = insert_ui_object_into_component_slot(
        document,
        instance_root_id=nested["root_object_id"],
        property_name="Content",
        object_id=custom["id"],
    )
    document, _ = update_ui_object(
        document,
        custom["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "stretch"}},
    )
    document, outer_component = convert_ui_object_to_component(
        document,
        root_object_id=outer_root["id"],
        name="Outer",
    )

    exported = painter_ui_to_umg_document(document)
    definition = next(
        row
        for row in exported["Components"]
        if row["Id"] == outer_component["id"]
    )
    custom_layer = next(
        row for row in definition["Layers"] if row["Id"] == custom["id"]
    )

    assert exported["SchemaVersion"] == 19
    assert custom_layer["Disposition"] == "Material"
    assert custom_layer["Material"]["SizeBinding"] == "WidgetGeometry"
    assert preflight_painter_umg(document)["ok"] is True


def test_fill_image_named_slot_root_remains_explicitly_blocked(tmp_path) -> None:
    from PIL import Image

    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        insert_ui_object_into_component_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    source = tmp_path / "slot_fill.png"
    Image.new("RGBA", (32, 32), (30, 90, 180, 255)).save(source)
    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document, kind="frame", name="Card", width=240, height=120
    )
    document, slot = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=root["id"],
        width=200,
        height=80,
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Card"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=component["id"],
        source_object_id=slot["id"],
        property_name="Content",
    )
    document, placement = instantiate_ui_component(
        document, component_id=component["id"], x=300, y=200
    )
    document, custom = add_ui_object(
        document,
        kind="image",
        name="Fill custom content",
        width=180,
        height=70,
        content={"source_path": str(source), "image_fit": "fill"},
    )
    document, _ = insert_ui_object_into_component_slot(
        document,
        instance_root_id=placement["root_object_id"],
        property_name="Content",
        object_id=custom["id"],
    )
    document, _ = update_ui_object(
        document,
        custom["id"],
        {"constraints": {"horizontal": "stretch", "vertical": "stretch"}},
    )

    exported = painter_ui_to_umg_document(document)
    custom_layer = next(
        row for row in exported["Layers"] if row["Id"] == custom["id"]
    )
    preflight = preflight_painter_umg(document)

    assert custom_layer["Disposition"] == "Blocked"
    assert custom_layer["BlockReasons"] == [
        "image_fill_runtime_resize_requires_dynamic_uv_binding"
    ]
    assert preflight["ok"] is False
    assert any(
        blocker["object_id"] == custom["id"]
        and blocker["reasons"]
        == ["image_fill_runtime_resize_requires_dynamic_uv_binding"]
        for blocker in preflight["blockers"]
    )


def test_unsupported_instance_override_remains_explicitly_blocked() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, _component, instance, source = _text_boolean_component_document()
    instance_label = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == source["label"]["id"]
    )
    document, _ = update_ui_object(
        document,
        instance_label["id"],
        {"style": {"text_color": "#FF0000FF"}},
    )
    exported = painter_ui_to_umg_document(document)
    root_layer = next(
        row
        for row in exported["Layers"]
        if row["Id"] == instance["root_object_id"]
    )
    assert root_layer["Disposition"] == "Blocked"
    assert "component_instance_override_runtime_unsupported:style.text_color" in root_layer["BlockReasons"]
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(
        "component_instance_override_runtime_unsupported:style.text_color"
        in row["reasons"]
        for row in preflight["blockers"]
    )


def test_number_and_instance_swap_properties_remain_explicitly_blocked() -> None:
    from app.painter_ui_components import define_ui_component_property
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document, component, _instance, _source = _text_boolean_component_document()
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Progress",
        definition={"type": "number", "default": 0.5},
    )
    preflight = preflight_painter_umg(document)
    assert preflight["ok"] is False
    assert any(
        "umg_component_property_runtime_unsupported:number" in row["reasons"]
        for row in preflight["blockers"]
    )


def test_documents_without_components_keep_their_existing_schema() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(800, 600)
    document, _ = add_ui_object(document, kind="text", name="Plain")
    exported = painter_ui_to_umg_document(document)
    assert exported["SchemaVersion"] < 18
    assert "Components" not in exported
    assert "ComponentInstances" not in exported


def test_component_interaction_is_kept_when_definition_uses_another_artboard() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document = create_ui_document(800, 600)
    screen_artboard_id = document["active_artboard_id"]
    document, library = add_ui_artboard(
        document, name="Component Library", width=800, height=600
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Library Button",
        artboard_id=library["id"],
        x=80,
        y=100,
        width=160,
        height=48,
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=button["id"], name="Library Button"
    )
    document, _ = add_ui_interaction(
        document,
        source_object_id=button["id"],
        trigger="click",
        action="set_opacity",
        target_object_id=button["id"],
        parameters={"opacity": 0.8},
    )
    document, _ = instantiate_ui_component(
        document,
        component_id=component["id"],
        artboard_id=screen_artboard_id,
        x=320,
        y=240,
    )

    exported = painter_ui_to_umg_document(
        document, artboard_id=screen_artboard_id
    )
    assert [row["ComponentId"] for row in exported["Interactions"]] == [
        button["id"]
    ]
    assert exported["Interactions"][0]["Actions"][0]["Type"] == "set_opacity"
    assert {row["Id"] for row in exported["ComponentInstances"]} == {
        next(
            row["id"]
            for row in document["objects"]
            if row["component_role"] == "instance"
            and row["component_id"] == component["id"]
            and row["component_source_object_id"] == button["id"]
        )
    }
    assert button["id"] not in {row["Id"] for row in exported["Layers"]}


def test_unreal_runner_preserves_component_result_map_keys(tmp_path) -> None:
    from app.unreal_umg_workflow import _runner_script

    script = _runner_script(
        tmp_path / "document.json",
        tmp_path / "report.json",
        "/Game/TigerStudio/Generated",
    )
    assert '"generated_component_count"' in script
    assert 'read_property(result, "generated_component_asset_paths")' in script
    assert 'read_property(result, "generated_component_class_paths")' in script
    assert "for key, value in dict(" in script


def test_builtin_active_artboard_component_definition_is_implicit_placement() -> None:
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.unreal_umg_component import validate_umg_component_contract

    for template_id in ("mobile_onboarding", "saas_dashboard"):
        document, _ = instantiate_ui_template(template_id)
        component = next(
            row
            for row in document["components"]
            if row["id"] == "ui-component-primary-button"
        )
        exported = painter_ui_to_umg_document(document)
        root_id = component["root_object_id"]
        screen_layer = next(
            row for row in exported["Layers"] if row["Id"] == root_id
        )
        placement = next(
            row
            for row in exported["ComponentInstances"]
            if row["Id"] == root_id
        )
        assert placement["ComponentId"] == component["id"]
        assert placement["LayerId"] == root_id
        assert json.loads(placement["PropertyValuesJson"]) == {
            name: definition["default"]
            for name, definition in component["property_definitions"].items()
        }
        marker = json.loads(screen_layer["PayloadJson"])[
            "component_instance"
        ]
        assert marker["id"] == root_id
        assert marker["component_id"] == component["id"]
        assert screen_layer["Disposition"] == "Native"
        assert screen_layer["ButtonStyle"] == {}
        definition = next(
            row
            for row in exported["Components"]
            if row["Id"] == component["id"]
        )
        definition_root = next(
            row
            for row in definition["Layers"]
            if row["Id"] == definition["RootLayerId"]
        )
        assert definition_root["ButtonStyle"]["Enabled"] is True
        assert validate_umg_component_contract(exported) == []
        preflight = preflight_painter_umg(document)
        assert not any(
            blocker["object_id"] == root_id
            and "button_style_missing" in blocker["reasons"]
            for blocker in preflight["blockers"]
        )


def test_off_canvas_definition_stays_authoring_only_on_active_artboard() -> None:
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_component import validate_umg_component_contract

    document = create_ui_document(800, 600)
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Library Card",
        x=-320,
        y=80,
        width=160,
        height=80,
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Library Card"
    )
    exported = painter_ui_to_umg_document(document)

    assert [row["Id"] for row in exported["Components"]] == [component["id"]]
    assert exported["ComponentInstances"] == []
    assert root["id"] not in {row["Id"] for row in exported["Layers"]}
    assert validate_umg_component_contract(exported) == []
