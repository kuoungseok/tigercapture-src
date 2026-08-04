from __future__ import annotations


def test_eight_variant_button_task_and_consecutive_change_to_runtime() -> None:
    """Official M3 task: State x Size variants with interactive transitions."""

    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        component_variant_properties,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        inspect_ui_component_set,
        instantiate_ui_component,
        switch_ui_component_instance_variant_values,
    )
    from app.painter_ui_document import (
        add_ui_object,
        add_ui_interaction,
        create_ui_document,
        update_ui_object,
        validate_ui_document,
    )
    from app.painter_ui_prototype import (
        execute_ui_prototype_trigger,
        prototype_initial_state,
        resolve_ui_component_prototype_document,
    )

    document = create_ui_document(1200, 760, name="M3 Button task")
    document, button_root = add_ui_object(
        document,
        kind="frame",
        name="Button",
        x=80,
        y=100,
        width=120,
        height=40,
        style={"fill": "#0D99FF", "radius": 8},
    )
    document, _label = add_ui_object(
        document,
        kind="text",
        name="Label",
        parent_id=button_root["id"],
        x=112,
        y=110,
        width=56,
        height=20,
        content={"text": "Button"},
        style={"fill": "#FFFFFF"},
    )
    document, family = convert_ui_object_to_component(
        document,
        root_object_id=button_root["id"],
        name="Button",
    )
    document, _state = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="State",
        values=["Default", "Hover", "Pressed", "Disabled"],
        default_value="Default",
    )
    document, _size = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="Size",
        values=["Small", "Large"],
        default_value="Small",
    )

    combinations = [
        (state, size)
        for size in ("Small", "Large")
        for state in ("Default", "Hover", "Pressed", "Disabled")
    ]
    members = {("Default", "Small"): family}
    for index, (state, size) in enumerate(combinations[1:], start=1):
        document, variant = create_ui_component_variant(
            document,
            component_id=family["id"],
            name=f"Button / {state} / {size}",
            variant_properties={"State": state, "Size": size},
        )
        members[(state, size)] = variant

    fills = {
        "Default": "#0D99FF",
        "Hover": "#0B85DD",
        "Pressed": "#086DB8",
        "Disabled": "#B8C0CC",
    }
    for index, (state, size) in enumerate(combinations):
        member = members[(state, size)]
        root = next(
            row for row in document["objects"] if row["id"] == member["root_object_id"]
        )
        desired_x = 80.0 + (index % 4) * 210.0
        desired_y = 100.0 + (index // 4) * 140.0
        delta_x = desired_x - float(root["x"])
        delta_y = desired_y - float(root["y"])
        member_rows = [
            row for row in document["objects"] if row["component_id"] == member["id"]
        ]
        for row in member_rows:
            changes = {
                "x": float(row["x"]) + delta_x,
                "y": float(row["y"]) + delta_y,
            }
            if row["id"] == root["id"]:
                changes.update(
                    {
                        "width": 120 if size == "Small" else 168,
                        "height": 40 if size == "Small" else 48,
                        "style": {"fill": fills[state], "radius": 8},
                        "opacity": 0.55 if state == "Disabled" else 1.0,
                    }
                )
            document, _updated = update_ui_object(document, row["id"], changes)

    inspection = inspect_ui_component_set(document, component_id=family["id"])
    assert inspection["ok"] is True
    assert inspection["property_names"] == ["State", "Size"]
    assert len(inspection["members"]) == 8
    current_components = {row["id"]: row for row in document["components"]}
    assert {
        tuple(
            component_variant_properties(current_components[member["id"]])[name]
            for name in ("State", "Size")
        )
        for member in members.values()
    } == set(combinations)

    for size in ("Small", "Large"):
        default = members[("Default", size)]
        hover = members[("Hover", size)]
        pressed = members[("Pressed", size)]
        document, _ = add_ui_component_change_to_interaction(
            document,
            source_component_id=default["id"],
            target_component_id=hover["id"],
            trigger="mouse_enter",
            transition={"kind": "smart_animate", "duration_ms": 120},
        )
        document, _ = add_ui_component_change_to_interaction(
            document,
            source_component_id=hover["id"],
            target_component_id=pressed["id"],
            trigger="press",
            transition={"kind": "smart_animate", "duration_ms": 80},
        )
        document, _ = add_ui_component_change_to_interaction(
            document,
            source_component_id=hover["id"],
            target_component_id=default["id"],
            trigger="mouse_leave",
            transition={"kind": "smart_animate", "duration_ms": 120},
        )

    document, instance = instantiate_ui_component(
        document,
        component_id=family["id"],
        x=420,
        y=500,
    )
    root_id = instance["root_object_id"]
    runtime = execute_ui_prototype_trigger(
        document,
        prototype_initial_state(document),
        source_object_id=root_id,
        trigger="mouse_enter",
    )
    assert runtime["component_variants"][root_id] == members[("Hover", "Small")]["id"]
    runtime = execute_ui_prototype_trigger(
        document,
        runtime,
        source_object_id=root_id,
        trigger="press",
    )
    assert runtime["component_variants"][root_id] == members[("Pressed", "Small")]["id"]
    preview = resolve_ui_component_prototype_document(document, runtime)
    preview_root = next(row for row in preview["objects"] if row["id"] == root_id)
    assert preview_root["component_id"] == members[("Pressed", "Small")]["id"]

    document, _reset_navigation = add_ui_interaction(
        document,
        source_object_id=root_id,
        trigger="click",
        action="navigate",
        target_artboard_id=document["active_artboard_id"],
        parameters={"reset_component_state": True},
    )
    reset_runtime = execute_ui_prototype_trigger(
        document,
        runtime,
        source_object_id=root_id,
        trigger="click",
    )
    assert reset_runtime["component_variants"] == {}
    assert reset_runtime["component_family_variants"] == {}

    document, switched = switch_ui_component_instance_variant_values(
        document,
        instance_root_id=root_id,
        properties={"State": "Default", "Size": "Large"},
    )
    assert switched["component_id"] == members[("Default", "Large")]["id"]
    assert validate_ui_document(document)["ok"] is True


def test_nested_interactive_component_change_to_preserves_outer_instance() -> None:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document, update_ui_object
    from app.painter_ui_prototype import (
        execute_ui_prototype_trigger,
        prototype_initial_state,
        resolve_ui_component_prototype_document,
    )

    document = create_ui_document(900, 640, name="Nested Change to")
    document, toggle_root = add_ui_object(
        document,
        kind="frame",
        name="Toggle",
        x=60,
        y=60,
        width=64,
        height=32,
        style={"fill": "#8A8F98", "radius": 16},
    )
    document, toggle = convert_ui_object_to_component(
        document,
        root_object_id=toggle_root["id"],
        name="Toggle",
    )
    document, _inspection = define_ui_component_variant_property(
        document,
        component_id=toggle["id"],
        property_name="State",
        values=["Off", "On"],
        default_value="Off",
    )
    document, toggle_on = create_ui_component_variant(
        document,
        component_id=toggle["id"],
        name="Toggle / On",
        variant_properties={"State": "On"},
    )
    document, _ = update_ui_object(
        document,
        toggle_on["root_object_id"],
        {"style": {"fill": "#47C58E", "radius": 16}},
    )
    document, _ = add_ui_component_change_to_interaction(
        document,
        source_component_id=toggle["id"],
        target_component_id=toggle_on["id"],
        trigger="click",
    )
    document, _ = add_ui_component_change_to_interaction(
        document,
        source_component_id=toggle_on["id"],
        target_component_id=toggle["id"],
        trigger="click",
    )

    document, card_root = add_ui_object(
        document,
        kind="frame",
        name="Settings Card",
        x=80,
        y=180,
        width=320,
        height=160,
    )
    document, nested_definition = instantiate_ui_component(
        document,
        component_id=toggle["id"],
        x=300,
        y=240,
    )
    document, _nested_root = update_ui_object(
        document,
        nested_definition["root_object_id"],
        {"parent_id": card_root["id"]},
    )
    document, card = convert_ui_object_to_component(
        document,
        root_object_id=card_root["id"],
        name="Settings Card",
    )
    document, card_instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=480,
        y=180,
    )
    nested = next(
        row
        for row in document["objects"]
        if row["parent_id"] == card_instance["root_object_id"]
        and row["component_id"] == toggle["id"]
    )
    nested_id = nested["id"]
    outer_id = card_instance["root_object_id"]
    document, _ = update_ui_object(document, nested_id, {"opacity": 0.7})

    runtime = execute_ui_prototype_trigger(
        document,
        prototype_initial_state(document),
        source_object_id=nested_id,
        trigger="click",
    )
    assert runtime["component_variants"][nested_id] == toggle_on["id"]
    preview = resolve_ui_component_prototype_document(document, runtime)
    preview_outer = next(row for row in preview["objects"] if row["id"] == outer_id)
    preview_nested = next(row for row in preview["objects"] if row["id"] == nested_id)
    assert preview_outer["component_id"] == card["id"]
    assert preview_nested["parent_id"] == outer_id
    assert preview_nested["component_id"] == toggle_on["id"]
    assert preview_nested["opacity"] == 0.7

    runtime = execute_ui_prototype_trigger(
        document,
        runtime,
        source_object_id=nested_id,
        trigger="click",
    )
    assert runtime["component_variants"][nested_id] == toggle["id"]
