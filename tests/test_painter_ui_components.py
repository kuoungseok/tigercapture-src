from __future__ import annotations

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
    document, root, _child = _component_document()
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.ui.component.create",
        "paint.ui.component.instantiate",
        "paint.ui.component.sync",
    } <= action_ids

    created = registry.execute(
        "paint.ui.component.create",
        {"root_object_id": root["id"], "name": "Profile Card"},
    ).to_dict()
    assert created["ok"] is True
    component_id = dialog._painter_ui_document["components"][0]["id"]
    instantiated = registry.execute(
        "paint.ui.component.instantiate",
        {"component_id": component_id, "x": 320, "y": 100},
    ).to_dict()
    assert instantiated["ok"] is True
    assert any(
        row["component_role"] == "instance"
        for row in dialog._painter_ui_document["objects"]
    )
    dialog._undo()
    assert not any(
        row["component_role"] == "instance"
        for row in dialog._painter_ui_document["objects"]
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


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
