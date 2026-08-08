from __future__ import annotations

import json
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _component_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    document, root = add_ui_object(
        document,
        kind="group",
        name="Profile Card",
        x=24,
        y=40,
        width=280,
        height=120,
    )
    document, child = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=root["id"],
        x=44,
        y=64,
        width=180,
        height=32,
        style={"text_color": "#20242C", "font_size": 20},
        content={"text": "Profile"},
    )
    return document, root, child


def test_convert_and_instantiate_component_subtree_with_stable_sources() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import validate_ui_document

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Profile Card",
    )
    definitions = {
        row["id"]: row
        for row in document["objects"]
        if row["component_role"] == "definition"
    }
    assert set(definitions) == {root["id"], child["id"]}
    assert component["root_object_id"] == root["id"]

    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=340,
        y=80,
    )
    instance_rows = [
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
    ]
    assert len(instance_rows) == 2
    assert {row["component_source_object_id"] for row in instance_rows} == {
        root["id"],
        child["id"],
    }
    instance_root = next(
        row for row in instance_rows if row["id"] == result["root_object_id"]
    )
    instance_child = next(
        row for row in instance_rows if row["component_source_object_id"] == child["id"]
    )
    assert instance_root["x"] == 340.0
    assert instance_child["parent_id"] == instance_root["id"]
    assert instance_child["x"] == 360.0
    assert validate_ui_document(document)["ok"] is True


def test_definition_update_syncs_instances_and_preserves_local_override() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import update_ui_object

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, _result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )

    document, _ = update_ui_object(
        document,
        child["id"],
        {"content": {"text": "Updated"}, "style": {"text_color": "#3355AA"}},
    )
    synced = next(row for row in document["objects"] if row["id"] == instance_child["id"])
    assert synced["content"]["text"] == "Updated"
    assert synced["style"]["text_color"] == "#3355AA"

    document, local = update_ui_object(
        document,
        instance_child["id"],
        {"content": {"text": "Local title"}},
    )
    assert local["instance_overrides"]["content.text"] == "Local title"
    document, _ = update_ui_object(
        document,
        child["id"],
        {"content": {"text": "Source changed again"}},
    )
    preserved = next(
        row for row in document["objects"] if row["id"] == instance_child["id"]
    )
    assert preserved["content"]["text"] == "Local title"
    assert preserved["instance_overrides"]["content.text"] == "Local title"


def test_instance_override_inspect_reset_and_reset_all_preserve_link() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        inspect_ui_component_instance_overrides,
        instantiate_ui_component,
        reset_all_ui_component_instance_overrides,
        reset_ui_component_instance_override,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import update_ui_object, validate_ui_document

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {
            "content": {"text": "Local title"},
            "style": {"text_color": "#CC8844"},
        },
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=result["root_object_id"],
        property_name="state",
        property_value="pressed",
    )

    report = inspect_ui_component_instance_overrides(
        document,
        instance_root_id=result["root_object_id"],
    )
    assert report["count"] == 3
    assert {
        (row["kind"], row["property_path"])
        for row in report["overrides"]
    } == {
        ("component_property", "component_properties.state"),
        ("object_property", "content.text"),
        ("object_property", "style.text_color"),
    }

    document, report = reset_ui_component_instance_override(
        document,
        instance_root_id=result["root_object_id"],
        object_id=instance_child["id"],
        property_path="content.text",
    )
    reset_child = next(
        row for row in document["objects"] if row["id"] == instance_child["id"]
    )
    assert reset_child["content"]["text"] == "Profile"
    assert reset_child["style"]["text_color"] == "#CC8844"
    assert report["count"] == 2

    document, report = reset_all_ui_component_instance_overrides(
        document,
        instance_root_id=result["root_object_id"],
    )
    reset_root = next(
        row
        for row in document["objects"]
        if row["id"] == result["root_object_id"]
    )
    reset_child = next(
        row for row in document["objects"] if row["id"] == instance_child["id"]
    )
    assert reset_root["component_role"] == "instance"
    assert reset_root["component_properties"]["state"] == "normal"
    assert reset_child["style"]["text_color"] == "#20242C"
    assert report["count"] == 0
    assert validate_ui_document(document)["ok"] is True


def test_inspector_lists_instance_overrides_and_emits_reset_commands() -> None:
    app = _app()
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_inspector import PainterUIInspector

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"content": {"text": "Local title"}},
    )
    document["selection"] = {
        "object_id": instance_child["id"],
        "object_ids": [instance_child["id"]],
    }
    inspector = PainterUIInspector()
    inspector.set_document(document)
    resets: list[tuple[str, str, str]] = []
    reset_all: list[str] = []
    inspector.component_override_reset_requested.connect(
        lambda *args: resets.append(args)
    )
    inspector.component_override_reset_all_requested.connect(reset_all.append)

    assert inspector.component_override_combo.count() == 1
    assert "Title" in inspector.component_override_combo.currentText()
    inspector.component_override_reset_button.click()
    assert resets == [
        (
            result["root_object_id"],
            instance_child["id"],
            "content.text",
        )
    ]
    inspector.component_override_reset_all_button.click()
    assert reset_all == [result["root_object_id"]]
    inspector.deleteLater()
    app.processEvents()


def test_definition_child_add_remove_synchronizes_instance_topology() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, remove_ui_object

    document, root, _child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, _ = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    document, badge = add_ui_object(
        document,
        kind="ellipse",
        name="Badge",
        parent_id=root["id"],
        x=260,
        y=52,
        width=24,
        height=24,
    )
    badge_instance = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == badge["id"]
    )
    assert badge_instance["component_id"] == component["id"]

    document, _ = remove_ui_object(document, badge["id"])
    assert not any(
        row["component_source_object_id"] == badge["id"]
        for row in document["objects"]
    )


def test_component_actions_and_undo_share_document_mutation() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, root, child = _component_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.ui.component.create",
        "paint.ui.component.instantiate",
        "paint.ui.component.sync",
        "paint.ui.component.property.define",
        "paint.ui.component.property.bind",
        "paint.ui.component.instance_swap.preferred.set",
        "paint.ui.component.state.override.set",
        "paint.ui.component.instance.property.set",
        "paint.ui.component.variant.create",
        "paint.ui.component.variant.property.define",
        "paint.ui.component.variant.values.set",
        "paint.ui.component.set.inspect",
        "paint.ui.component.instance.variant.set",
        "paint.ui.component.instance.variant_values.set",
        "paint.ui.component.change_to.add",
        "paint.ui.component.instance.detach",
        "paint.ui.component.override.reset",
        "paint.ui.component.override.reset_all",
    } <= action_ids

    created = registry.execute(
        "paint.ui.component.create",
        {"root_object_id": root["id"], "name": "Profile Card"},
    ).to_dict()
    assert created["ok"] is True
    component_id = dialog._painter_ui_document["components"][0]["id"]
    defined = registry.execute(
        "paint.ui.component.property.define",
        {
            "component_id": component_id,
            "property_name": "density",
            "definition": {
                "type": "enum",
                "default": "comfortable",
                "values": ["compact", "comfortable"],
            },
        },
    ).to_dict()
    assert defined["ok"] is True
    label_defined = registry.execute(
        "paint.ui.component.property.define",
        {
            "component_id": component_id,
            "property_name": "Label",
            "definition": {"type": "text", "default": "Profile"},
        },
    ).to_dict()
    assert label_defined["ok"] is True
    bound = registry.execute(
        "paint.ui.component.property.bind",
        {
            "component_id": component_id,
            "source_object_id": child["id"],
            "property_name": "Label",
            "target_path": "content.text",
        },
    ).to_dict()
    assert bound["ok"] is True
    state_override = registry.execute(
        "paint.ui.component.state.override.set",
        {
            "component_id": component_id,
            "state": "pressed",
            "source_object_id": root["id"],
            "changes": {"opacity": 0.75},
        },
    ).to_dict()
    assert state_override["ok"] is True
    instantiated = registry.execute(
        "paint.ui.component.instantiate",
        {"component_id": component_id, "x": 320, "y": 100},
    ).to_dict()
    assert instantiated["ok"] is True
    instance_root = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == root["id"]
    )
    state_set = registry.execute(
        "paint.ui.component.instance.property.set",
        {
            "instance_root_id": instance_root["id"],
            "property_name": "state",
            "value": "pressed",
        },
    ).to_dict()
    assert state_set["ok"] is True
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_properties"]["state"] == "pressed"
    dialog._undo()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_properties"]["state"] == "normal"
    from app.painter_ui_document import update_ui_object

    instance_child = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    dialog._painter_ui_document, _ = update_ui_object(
        dialog._painter_ui_document,
        instance_child["id"],
        {"content": {"text": "Local action title"}},
    )
    reset = registry.execute(
        "paint.ui.component.override.reset",
        {
            "instance_root_id": instance_root["id"],
            "object_id": instance_child["id"],
            "property_path": "content.text",
        },
    ).to_dict()
    assert reset["ok"] is True
    assert reset["result"]["override_report"]["count"] == 0
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_child["id"]
    )["content"]["text"] == "Profile"
    dialog._undo()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_child["id"]
    )["content"]["text"] == "Local action title"
    reset_all = registry.execute(
        "paint.ui.component.override.reset_all",
        {"instance_root_id": instance_root["id"]},
    ).to_dict()
    assert reset_all["ok"] is True
    assert reset_all["result"]["override_report"]["count"] == 0
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_child["id"]
    )["content"]["text"] == "Profile"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_component_set_actions_share_mutation_and_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, root, _child = _component_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    created = registry.execute(
        "paint.ui.component.create",
        {"root_object_id": root["id"], "name": "Button"},
    ).to_dict()
    assert created["ok"] is True
    family_id = dialog._painter_ui_document["components"][0]["id"]
    defined = registry.execute(
        "paint.ui.component.variant.property.define",
        {
            "component_id": family_id,
            "property_name": "State",
            "values": ["Default", "Hover"],
            "default_value": "Default",
        },
    ).to_dict()
    assert defined["ok"] is True
    variant_created = registry.execute(
        "paint.ui.component.variant.create",
        {
            "component_id": family_id,
            "name": "Button / Hover",
            "variant_properties": {"State": "Hover"},
        },
    ).to_dict()
    assert variant_created["ok"] is True
    variant = next(
        row
        for row in dialog._painter_ui_document["components"]
        if row["base_component_id"] == family_id
    )
    change_to = registry.execute(
        "paint.ui.component.change_to.add",
        {
            "source_component_id": family_id,
            "target_component_id": variant["id"],
            "trigger": "click",
            "transition": {"kind": "smart_animate", "duration_ms": 200},
        },
    ).to_dict()
    assert change_to["ok"] is True
    assert dialog._painter_ui_document["interactions"][0]["action"] == "change_variant"
    inspected = registry.execute(
        "paint.ui.component.set.inspect",
        {"component_id": family_id},
    ).to_dict()
    assert inspected["ok"] is True
    assert inspected["result"]["ok"] is True
    assert inspected["result"]["property_names"] == ["State"]
    instantiated = registry.execute(
        "paint.ui.component.instantiate",
        {"component_id": family_id, "x": 320, "y": 100},
    ).to_dict()
    assert instantiated["ok"] is True
    instance_root = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == root["id"]
    )
    switched = registry.execute(
        "paint.ui.component.instance.variant_values.set",
        {
            "instance_root_id": instance_root["id"],
            "properties": {"State": "Hover"},
        },
    ).to_dict()
    assert switched["ok"] is True
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_id"] == variant["id"]
    dialog._undo()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_id"] == family_id
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_interactive_component_change_to_previews_variant_and_preserves_override() -> None:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_prototype import (
        execute_ui_prototype_trigger,
        prototype_initial_state,
        resolve_ui_component_prototype_document,
    )

    document, root, _child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, _inspection = define_ui_component_variant_property(
        document,
        component_id=component["id"],
        property_name="State",
        values=["Default", "Hover"],
        default_value="Default",
    )
    document, hover = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Button / Hover",
        variant_properties={"State": "Hover"},
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=320,
        y=100,
    )
    document, shared_result = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=320,
        y=260,
    )
    instance_root = next(
        row for row in document["objects"] if row["id"] == result["root_object_id"]
    )
    document, instance_root = update_ui_object(
        document,
        instance_root["id"],
        {"opacity": 0.55},
    )
    document, authored = add_ui_component_change_to_interaction(
        document,
        source_component_id=component["id"],
        target_component_id=hover["id"],
        trigger="click",
        transition={"kind": "smart_animate", "duration_ms": 200},
    )
    interaction = authored["interaction"]
    assert interaction["component_id"] == hover["id"]
    assert interaction["parameters"]["preserve_overrides"] is True

    runtime = execute_ui_prototype_trigger(
        document,
        prototype_initial_state(document),
        source_object_id=instance_root["id"],
        trigger="click",
    )
    assert runtime["component_variants"] == {instance_root["id"]: hover["id"]}
    assert runtime["component_family_variants"] == {
        component["id"]: hover["id"]
    }
    preview = resolve_ui_component_prototype_document(document, runtime)
    preview_root = next(
        row for row in preview["objects"] if row["id"] == instance_root["id"]
    )
    assert preview_root["component_id"] == hover["id"]
    assert preview_root["instance_overrides"]["opacity"] == 0.55
    shared_preview_root = next(
        row
        for row in preview["objects"]
        if row["id"] == shared_result["root_object_id"]
    )
    assert shared_preview_root["component_id"] == hover["id"]

    from app.painter_ui_document import add_ui_interaction

    overridden, _regular = add_ui_interaction(
        document,
        source_object_id=instance_root["id"],
        trigger="click",
        action="set_opacity",
        target_object_id=instance_root["id"],
        parameters={"opacity": 0.2},
    )
    overridden_runtime = execute_ui_prototype_trigger(
        overridden,
        prototype_initial_state(overridden),
        source_object_id=instance_root["id"],
        trigger="click",
    )
    assert overridden_runtime["component_variants"] == {}
    assert overridden_runtime["object_opacity"][instance_root["id"]] == 0.2


def test_instance_swap_preferred_values_curate_without_restricting() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        set_ui_component_instance_swap_preferred_values,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    roots = []
    for name in ("Card", "Icon A", "Icon B"):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=name,
            width=80,
            height=40,
        )
        document, component = convert_ui_object_to_component(
            document,
            root_object_id=root["id"],
            name=name,
        )
        roots.append(component)
    card, icon_a, icon_b = roots
    document, _definition = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Icon",
        definition={"type": "instance_swap", "default": icon_a["id"]},
    )
    document, definition = set_ui_component_instance_swap_preferred_values(
        document,
        component_id=card["id"],
        property_name="Icon",
        preferred_component_ids=[icon_b["id"]],
    )
    assert definition["preferred_values"] == [icon_b["id"]]
    document, instance = instantiate_ui_component(
        document,
        component_id=card["id"],
    )
    document, properties = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Icon",
        property_value=icon_a["id"],
    )
    assert properties["Icon"] == icon_a["id"]


def test_slot_preserves_instance_content_and_reports_limits_without_blocking() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        inspect_ui_component_instance_slot,
        insert_ui_object_into_component_slot,
        instantiate_ui_component,
        reset_ui_component_instance_slot,
        sync_ui_component_instances,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        normalize_ui_document,
        update_ui_object,
        validate_ui_document,
    )

    document = create_ui_document(1000, 700)
    document, card_root = add_ui_object(
        document, kind="frame", name="Card", width=320, height=240
    )
    document, slot_source = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=card_root["id"],
        x=20,
        y=20,
        width=280,
        height=180,
        content={},
    )
    document, _default_text = add_ui_object(
        document,
        kind="text",
        name="Default",
        parent_id=slot_source["id"],
        content={"text": "Default"},
    )
    document, card = convert_ui_object_to_component(
        document, root_object_id=card_root["id"], name="Card"
    )
    document, icon_root = add_ui_object(
        document, kind="frame", name="Icon", x=500, width=32, height=32
    )
    document, icon = convert_ui_object_to_component(
        document, root_object_id=icon_root["id"], name="Icon"
    )
    document, definition = define_ui_component_slot(
        document,
        component_id=card["id"],
        source_object_id=slot_source["id"],
        property_name="Content",
        description="Card body",
        preferred_component_ids=[icon["id"]],
        slot_settings={
            "display_empty_by_default": True,
            "min_children": 2,
            "max_children": 2,
            "allow_preferred_values_only": True,
        },
    )
    assert definition["type"] == "slot"
    assert definition["default"] == slot_source["id"]

    document, card_instance = instantiate_ui_component(
        document, component_id=card["id"], x=400, y=200
    )
    initial = inspect_ui_component_instance_slot(
        document,
        instance_root_id=card_instance["root_object_id"],
        property_name="Content",
    )
    assert initial["child_count"] == 1
    assert initial["limit_violations"] == ["below_min", "has_non_preferred"]

    document, icon_instance = instantiate_ui_component(
        document, component_id=icon["id"], x=760, y=200
    )
    document, inserted = insert_ui_object_into_component_slot(
        document,
        instance_root_id=card_instance["root_object_id"],
        property_name="Content",
        object_id=icon_instance["root_object_id"],
    )
    assert inserted["child_count"] == 2
    # The default text is deliberately non-preferred; limits are diagnostics,
    # never mutation blockers, matching Figma Slot limitViolations.
    assert inserted["limit_violations"] == ["has_non_preferred"]

    document, custom = add_ui_object(
        document, kind="rectangle", name="Custom", x=780, y=280
    )
    document, over_limit = insert_ui_object_into_component_slot(
        document,
        instance_root_id=card_instance["root_object_id"],
        property_name="Content",
        object_id=custom["id"],
        index=0,
    )
    assert over_limit["child_count"] == 3
    assert over_limit["limit_violations"] == ["above_max", "has_non_preferred"]

    document, _ = update_ui_object(
        document, slot_source["id"], {"width": 300}
    )
    document = sync_ui_component_instances(document, card["id"])
    persisted = normalize_ui_document(json.loads(json.dumps(document)))
    preserved = inspect_ui_component_instance_slot(
        persisted,
        instance_root_id=card_instance["root_object_id"],
        property_name="Content",
    )
    assert custom["id"] in preserved["child_ids"]
    assert icon_instance["root_object_id"] in preserved["child_ids"]

    document, reset = reset_ui_component_instance_slot(
        persisted,
        instance_root_id=card_instance["root_object_id"],
        property_name="Content",
    )
    assert custom["id"] in reset["removed_object_ids"]
    assert icon_instance["root_object_id"] in reset["removed_object_ids"]
    assert reset["child_count"] == 1
    assert validate_ui_document(document)["ok"] is True


def test_inspector_component_commands_follow_selection_role() -> None:
    app = _app()
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_inspector import PainterUIInspector

    document, root, _child = _component_document()
    document["selection"] = {"object_id": root["id"], "object_ids": [root["id"]]}
    inspector = PainterUIInspector()
    inspector.set_document(document)
    created: list[tuple[str, str]] = []
    inspector.component_create_requested.connect(
        lambda object_id, name: created.append((object_id, name))
    )
    inspector.component_create_button.click()
    assert created == [(root["id"], "Profile Card")]

    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    inspector.set_document(document)
    instances: list[tuple[str, str, float, float]] = []
    inspector.component_instantiate_requested.connect(
        lambda *args: instances.append(args)
    )
    inspector.component_instance_button.click()
    assert instances[-1][0] == component["id"]
    assert inspector.component_status_label.text() == "Definition"
    inspector.deleteLater()
    app.processEvents()


def test_component_state_resolves_before_local_responsive_and_theme_overrides() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
        set_ui_component_state_override,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import add_ui_token, update_ui_object
    from app.painter_ui_responsive import set_ui_responsive_override
    from app.painter_ui_themes import resolve_ui_theme_document

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    assert component["property_definitions"]["state"]["values"] == [
        "normal",
        "hover",
        "pressed",
        "focused",
        "disabled",
        "selected",
    ]
    document, _ = set_ui_component_state_override(
        document,
        component_id=component["id"],
        state="hover",
        source_object_id=child["id"],
        changes={
            "content": {"text": "Hover title"},
            "style": {"text_color": "#AA0000"},
        },
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_root_id = result["root_object_id"]
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance_root_id,
        property_name="state",
        property_value="hover",
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"content": {"text": "Local title"}},
    )
    document, token = add_ui_token(
        document,
        name="Theme text",
        kind="color",
        token_value="#0099CC",
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"token_bindings": {"style.text_color": token["id"]}},
    )
    responsive_overrides = set_ui_responsive_override(
        instance_child,
        breakpoint="custom",
        orientation="portrait",
        changes={"content": {"text": "Portrait title"}},
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"responsive_overrides": responsive_overrides},
    )

    resolved = resolve_ui_theme_document(document)
    row = next(
        item for item in resolved["objects"] if item["id"] == instance_child["id"]
    )
    assert row["resolved_component_state"] == "hover"
    assert row["content"]["text"] == "Portrait title"
    assert row["style"]["text_color"] == "#0099CC"


def test_component_property_and_state_validation_rejects_invalid_values() -> None:
    import pytest

    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        set_ui_component_state_override,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import PainterUIDocumentError

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, definition = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="density",
        definition={
            "type": "enum",
            "default": "comfortable",
            "values": ["compact", "comfortable"],
        },
    )
    assert definition["default"] == "comfortable"
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    with pytest.raises(PainterUIDocumentError):
        set_ui_instance_component_property(
            document,
            instance_root_id=result["root_object_id"],
            property_name="density",
            property_value="wide",
        )
    with pytest.raises(PainterUIDocumentError):
        set_ui_component_state_override(
            document,
            component_id=component["id"],
            state="unknown",
            source_object_id=child["id"],
            changes={"opacity": 0.5},
        )


def test_component_property_binding_resolves_text_and_visibility() -> None:
    import pytest

    from app.painter_ui_components import (
        bind_ui_component_property,
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        resolve_ui_component_document,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import PainterUIDocumentError

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Label",
        definition={"type": "text", "default": "Profile"},
    )
    document, _ = define_ui_component_property(
        document,
        component_id=component["id"],
        property_name="Show label",
        definition={"type": "boolean", "default": True},
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=child["id"],
        property_name="Label",
        target_path="content.text",
    )
    document, bindings = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=child["id"],
        property_name="Show label",
        target_path="visible",
    )
    assert bindings == {
        "content.text": "Label",
        "visible": "Show label",
    }
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Label",
        property_value="Local profile",
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Show label",
        property_value=False,
    )

    resolved = resolve_ui_component_document(document)
    resolved_child = next(
        row
        for row in resolved["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    assert resolved_child["content"]["text"] == "Local profile"
    assert resolved_child["visible"] is False

    with pytest.raises(PainterUIDocumentError, match="type_mismatch"):
        bind_ui_component_property(
            document,
            component_id=component["id"],
            source_object_id=child["id"],
            property_name="Show label",
            target_path="content.text",
        )


def test_nested_instance_swap_preserves_parent_id_and_local_override() -> None:
    from app.painter_ui_components import (
        bind_ui_component_property,
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        set_ui_component_instance_swap_preferred_values,
        set_ui_instance_component_property,
        sync_ui_component_instances,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
        validate_ui_document,
    )

    document = create_ui_document(800, 600, name="Nested components")
    document, icon_a_root = add_ui_object(
        document,
        kind="rectangle",
        name="Square Icon",
        x=40,
        y=40,
        width=24,
        height=24,
    )
    document, icon_a = convert_ui_object_to_component(
        document,
        root_object_id=icon_a_root["id"],
        name="Square Icon",
    )
    document, icon_b_root = add_ui_object(
        document,
        kind="ellipse",
        name="Round Icon",
        x=80,
        y=40,
        width=24,
        height=24,
    )
    document, icon_b = convert_ui_object_to_component(
        document,
        root_object_id=icon_b_root["id"],
        name="Round Icon",
    )
    document, card_root = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=40,
        y=120,
        width=240,
        height=96,
    )
    document, nested_definition = instantiate_ui_component(
        document,
        component_id=icon_a["id"],
        x=64,
        y=144,
    )
    document, nested_source = update_ui_object(
        document,
        nested_definition["root_object_id"],
        {"parent_id": card_root["id"]},
    )
    document, card = convert_ui_object_to_component(
        document,
        root_object_id=card_root["id"],
        name="Card",
    )
    document, _ = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Icon",
        definition={
            "type": "instance_swap",
            "default": icon_a["id"],
        },
    )
    document, _ = bind_ui_component_property(
        document,
        component_id=card["id"],
        source_object_id=nested_source["id"],
        property_name="Icon",
        target_path="component_id",
    )
    document, preferred_definition = (
        set_ui_component_instance_swap_preferred_values(
            document,
            component_id=card["id"],
            property_name="Icon",
            preferred_component_ids=[icon_b["id"]],
        )
    )
    assert preferred_definition["preferred_values"] == [icon_b["id"]]
    document, card_instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=360,
        y=120,
    )
    nested_instance = next(
        row
        for row in document["objects"]
        if row["component_scope_id"] == card["id"]
        and row["component_scope_source_object_id"] == nested_source["id"]
        and row["parent_id"] == card_instance["root_object_id"]
    )
    nested_id = nested_instance["id"]
    nested_parent_id = nested_instance["parent_id"]
    document, _ = update_ui_object(
        document,
        nested_id,
        {"opacity": 0.4},
    )

    document, properties = set_ui_instance_component_property(
        document,
        instance_root_id=card_instance["root_object_id"],
        property_name="Icon",
        property_value=icon_b["id"],
    )

    swapped = next(row for row in document["objects"] if row["id"] == nested_id)
    assert properties["Icon"] == icon_b["id"]
    assert swapped["component_id"] == icon_b["id"]
    assert swapped["component_source_object_id"] == icon_b["root_object_id"]
    assert swapped["component_scope_id"] == card["id"]
    assert swapped["component_scope_source_object_id"] == nested_source["id"]
    assert swapped["parent_id"] == nested_parent_id
    assert swapped["opacity"] == 0.4
    document = sync_ui_component_instances(document, card["id"])
    resynced = next(row for row in document["objects"] if row["id"] == nested_id)
    assert resynced["component_id"] == icon_b["id"]
    assert resynced["opacity"] == 0.4
    assert validate_ui_document(document)["ok"] is True
    from app.painter_ui_document import normalize_ui_document

    reloaded = normalize_ui_document(document)
    restored = next(row for row in reloaded["objects"] if row["id"] == nested_id)
    restored_card = next(row for row in reloaded["components"] if row["id"] == card["id"])
    assert restored["component_id"] == icon_b["id"]
    assert restored["opacity"] == 0.4
    assert restored_card["property_definitions"]["Icon"]["preferred_values"] == [
        icon_b["id"]
    ]


def test_inspector_instance_state_updates_instance_root() -> None:
    app = _app()
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_inspector import PainterUIInspector

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document["selection"] = {
        "object_id": instance_child["id"],
        "object_ids": [instance_child["id"]],
    }
    inspector = PainterUIInspector()
    inspector.set_document(document)
    changes: list[tuple[str, dict[str, object]]] = []
    inspector.properties_changed.connect(
        lambda object_id, values: changes.append((object_id, dict(values)))
    )
    inspector.component_state_combo.setCurrentIndex(
        inspector.component_state_combo.findData("pressed")
    )
    assert changes[-1] == (
        result["root_object_id"],
        {"component_properties": {"state": "pressed"}},
    )
    inspector.deleteLater()
    app.processEvents()


def test_component_variant_switch_preserves_instance_ids_and_overrides() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        instantiate_ui_component,
        switch_ui_component_instance_variant,
    )
    from app.painter_ui_document import (
        normalize_ui_document,
        update_ui_object,
        validate_ui_document,
    )

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, variant = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Profile Card / Compact",
        variant_key="compact",
    )
    variant_child = next(
        row
        for row in document["objects"]
        if row["component_id"] == variant["id"]
        and row["component_role"] == "definition"
        and row["kind"] == "text"
    )
    document, _ = update_ui_object(
        document,
        variant_child["id"],
        {"style": {"font_size": 14}},
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=320,
        y=100,
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"content": {"text": "Local profile"}},
    )
    old_ids = set(result["object_ids"])

    document, switched = switch_ui_component_instance_variant(
        document,
        instance_root_id=result["root_object_id"],
        target_component_id=variant["id"],
    )
    assert switched["root_object_id"] == result["root_object_id"]
    assert set(switched["object_ids"]) == old_ids
    switched_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["id"] == instance_child["id"]
    )
    assert switched_child["component_id"] == variant["id"]
    assert switched_child["content"]["text"] == "Local profile"
    assert switched_child["style"]["font_size"] == 14
    assert validate_ui_document(document)["ok"] is True
    round_trip = normalize_ui_document(json.loads(json.dumps(document)))
    stored_variant = next(
        row for row in round_trip["components"] if row["id"] == variant["id"]
    )
    assert stored_variant["base_component_id"] == component["id"]
    assert stored_variant["metadata"]["variant_key"] == "compact"


def test_detach_instance_materializes_state_and_can_create_local_component() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        detach_ui_component_instance,
        instantiate_ui_component,
        set_ui_component_state_override,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import validate_ui_document

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, _ = set_ui_component_state_override(
        document,
        component_id=component["id"],
        state="disabled",
        source_object_id=child["id"],
        changes={"opacity": 0.45},
    )
    document, result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=result["root_object_id"],
        property_name="state",
        property_value="disabled",
    )
    document, detached = detach_ui_component_instance(
        document,
        instance_root_id=result["root_object_id"],
        create_local_component=True,
        name="Local Profile",
    )
    assert detached["root_object_id"] == result["root_object_id"]
    assert detached["local_component_id"]
    rows = [
        row
        for row in document["objects"]
        if row["id"] in detached["object_ids"]
    ]
    assert all(row["component_role"] == "definition" for row in rows)
    detached_child = next(row for row in rows if row["kind"] == "text")
    assert detached_child["opacity"] == 0.45
    assert validate_ui_document(document)["ok"] is True


def test_component_variant_and_detach_actions_share_undo() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, root, _child = _component_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    created = registry.execute(
        "paint.ui.component.create",
        {"root_object_id": root["id"], "name": "Profile Card"},
    ).to_dict()
    assert created["ok"] is True
    component_id = dialog._painter_ui_document["components"][0]["id"]
    variant_created = registry.execute(
        "paint.ui.component.variant.create",
        {
            "component_id": component_id,
            "name": "Profile Card / Compact",
            "variant_key": "compact",
        },
    ).to_dict()
    assert variant_created["ok"] is True
    variant_id = next(
        row["id"]
        for row in dialog._painter_ui_document["components"]
        if row["base_component_id"] == component_id
    )
    instantiated = registry.execute(
        "paint.ui.component.instantiate",
        {"component_id": component_id, "x": 320, "y": 100},
    ).to_dict()
    assert instantiated["ok"] is True
    instance_root = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == root["id"]
    )
    switched = registry.execute(
        "paint.ui.component.instance.variant.set",
        {
            "instance_root_id": instance_root["id"],
            "component_id": variant_id,
        },
    ).to_dict()
    assert switched["ok"] is True
    detached = registry.execute(
        "paint.ui.component.instance.detach",
        {
            "instance_root_id": instance_root["id"],
            "create_local_component": False,
        },
    ).to_dict()
    assert detached["ok"] is True
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_role"] == "none"
    dialog._undo()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == instance_root["id"]
    )["component_role"] == "instance"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_exposes_variant_switch_and_detach_commands() -> None:
    app = _app()
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        instantiate_ui_component,
    )
    from app.painter_ui_inspector import PainterUIInspector

    document, root, child = _component_document()
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, variant = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Profile Card / Compact",
    )
    document, _result = instantiate_ui_component(
        document,
        component_id=component["id"],
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document["selection"] = {
        "object_id": instance_child["id"],
        "object_ids": [instance_child["id"]],
    }
    inspector = PainterUIInspector()
    inspector.set_document(document)
    switches: list[tuple[str, str]] = []
    detaches: list[tuple[str, bool, str]] = []
    inspector.component_variant_switch_requested.connect(
        lambda *args: switches.append(args)
    )
    inspector.component_detach_requested.connect(
        lambda *args: detaches.append(args)
    )
    assert inspector.component_variant_combo.count() == 2
    inspector.component_variant_combo.setCurrentIndex(
        inspector.component_variant_combo.findData(variant["id"])
    )
    assert switches[-1][1] == variant["id"]
    inspector.component_detach_button.click()
    assert detaches[-1][1] is False
    inspector.component_localize_button.click()
    assert detaches[-1][1] is True
    inspector.deleteLater()
    app.processEvents()


def test_component_set_tracks_multidimensional_variant_properties() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        inspect_ui_component_set,
        set_ui_component_variant_properties,
    )

    document, root, _child = _component_document()
    document, family = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, state_report = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="State",
        values=["Default", "Hover", "Pressed", "Disabled"],
        default_value="Default",
    )
    assert state_report["property_names"] == ["State"]
    assert state_report["members"][0]["properties"] == {"State": "Default"}

    document, hover = create_ui_component_variant(
        document,
        component_id=family["id"],
        name="Button / Hover / Large",
        variant_properties={"State": "Hover"},
    )
    document, _size_report = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="Size",
        values=["Small", "Large"],
        default_value="Small",
    )
    document, updated = set_ui_component_variant_properties(
        document,
        component_id=hover["id"],
        properties={"Size": "Large"},
    )
    assert updated["component"]["metadata"]["variant_key"] == (
        "State=Hover, Size=Large"
    )
    report = inspect_ui_component_set(document, component_id=family["id"])
    assert report["ok"] is True
    assert report["property_names"] == ["State", "Size"]
    assert [row["combination"] for row in report["members"]] == [
        "State=Default, Size=Small",
        "State=Hover, Size=Large",
    ]


def test_component_set_reports_duplicate_combinations_without_data_loss() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        inspect_ui_component_set,
    )

    document, root, _child = _component_document()
    document, family = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Toggle",
    )
    document, _ = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="Checked",
        values=["False", "True"],
        default_value="False",
    )
    document, duplicate = create_ui_component_variant(
        document,
        component_id=family["id"],
        variant_properties={"Checked": "False"},
    )
    report = inspect_ui_component_set(document, component_id=family["id"])
    assert report["ok"] is False
    assert report["conflicts"] == [
        {
            "type": "duplicate_variant_combination",
            "properties": {"Checked": "False"},
            "component_ids": [family["id"], duplicate["id"]],
        }
    ]
    assert {row["id"] for row in document["components"]} >= {
        family["id"],
        duplicate["id"],
    }


def test_instance_switches_variant_by_property_combination_and_keeps_override() -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
        set_ui_component_variant_properties,
        switch_ui_component_instance_variant_values,
    )
    from app.painter_ui_document import update_ui_object

    document, root, child = _component_document()
    document, family = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, _ = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="State",
        values=["Default", "Hover"],
        default_value="Default",
    )
    document, _ = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="Size",
        values=["Small", "Large"],
        default_value="Small",
    )
    document, hover_large = create_ui_component_variant(
        document,
        component_id=family["id"],
        variant_properties={"State": "Hover", "Size": "Large"},
    )
    document, _ = set_ui_component_variant_properties(
        document,
        component_id=hover_large["id"],
        properties={"State": "Hover", "Size": "Large"},
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=family["id"],
        x=320,
        y=80,
    )
    instance_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["component_source_object_id"] == child["id"]
    )
    document, _ = update_ui_object(
        document,
        instance_child["id"],
        {"content": {"text": "Local label"}},
    )
    document, switched = switch_ui_component_instance_variant_values(
        document,
        instance_root_id=instance["root_object_id"],
        properties={"State": "Hover", "Size": "Large"},
    )
    assert switched["component_id"] == hover_large["id"]
    switched_root = next(
        row
        for row in document["objects"]
        if row["id"] == instance["root_object_id"]
    )
    assert switched_root["component_properties"]["State"] == "Hover"
    assert switched_root["component_properties"]["Size"] == "Large"
    switched_child = next(
        row
        for row in document["objects"]
        if row["component_role"] == "instance"
        and row["id"] != switched_root["id"]
    )
    assert switched_child["content"]["text"] == "Local label"


def test_combine_as_variants_keeps_canvas_layout_and_builds_virtual_container() -> None:
    from app.painter_ui_components import (
        combine_ui_components_as_variants,
        component_set_canvas_bounds,
        convert_ui_object_to_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(1200, 800)
    component_ids = []
    root_ids = []
    for name, x, y in (
        ("Button/Small/Default", 100, 100),
        ("Button/Large/Default", 320, 100),
        ("Button/Small/Hover", 100, 260),
    ):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=name,
            x=x,
            y=y,
            width=160 if "Small" in name else 200,
            height=64,
        )
        document, component = convert_ui_object_to_component(
            document, root_object_id=root["id"], name=name
        )
        component_ids.append(component["id"])
        root_ids.append(root["id"])
    document, report = combine_ui_components_as_variants(
        document,
        component_ids=component_ids,
    )
    family = next(row for row in document["components"] if not row["base_component_id"])
    assert family["name"] == "Button"
    assert report["property_names"] == ["Variant", "Property 2"]
    assert [row["properties"] for row in report["members"]] == [
        {"Variant": "Small", "Property 2": "Default"},
        {"Variant": "Large", "Property 2": "Default"},
        {"Variant": "Small", "Property 2": "Hover"},
    ]
    assert document["selection"]["object_ids"] == root_ids
    bounds = component_set_canvas_bounds(
        document, component_id=family["id"], padding=24
    )
    assert bounds == {
        "id": f"component-set:{family['id']}",
        "component_id": family["id"],
        "name": "Button",
        "artboard_id": document["active_artboard_id"],
        "x": 76.0,
        "y": 76.0,
        "width": 468.0,
        "height": 272.0,
        "stroke": "#9747FF",
        "fill": None,
        "dash": [6.0, 4.0],
        "member_root_ids": root_ids,
    }


def test_inspector_combine_button_emits_selected_independent_components() -> None:
    app = _app()
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(800, 600)
    component_ids = []
    root_ids = []
    for index in range(2):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=f"Button/State {index}",
            x=80 + index * 220,
        )
        document, component = convert_ui_object_to_component(
            document, root_object_id=root["id"]
        )
        root_ids.append(root["id"])
        component_ids.append(component["id"])
    document["selection"] = {
        "object_id": root_ids[-1],
        "object_ids": root_ids,
    }
    inspector = PainterUIInspector()
    inspector.set_document(document)
    assert inspector.component_combine_button.isEnabled()
    emitted: list[list[str]] = []
    inspector.component_variants_combine_requested.connect(
        lambda values: emitted.append(list(values))
    )
    inspector.component_combine_button.click()
    assert emitted == [component_ids]
    inspector.deleteLater()
    app.processEvents()
