from __future__ import annotations

import os
import json
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
        select_ui_objects,
        set_active_ui_artboard,
        update_ui_object,
    )

    document = create_ui_document(800, 600, name="Desktop")
    desktop_id = document["active_artboard_id"]
    document, group = add_ui_object(
        document,
        kind="group",
        name="Product card",
        x=80,
        y=90,
        width=320,
        height=220,
    )
    document, image = add_ui_object(
        document,
        kind="rectangle",
        name="Product image",
        artboard_id=desktop_id,
        parent_id=group["id"],
        x=104,
        y=112,
        width=272,
        height=120,
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Buy",
        artboard_id=desktop_id,
        parent_id=group["id"],
        x=104,
        y=250,
        width=112,
        height=40,
        content={"text": "Buy now"},
    )
    document, button = update_ui_object(
        document,
        button["id"],
        {
            "accessibility": {
                "role": "button",
                "label": "Buy now",
                "focus_order": 1,
            }
        },
    )
    document, interaction = add_ui_interaction(
        document,
        name="Buy hover",
        source_object_id=button["id"],
        trigger="hover",
        action="change_state",
        target_object_id=image["id"],
        target_artboard_id=desktop_id,
        parameters={"state": "hover"},
    )
    document, mobile = add_ui_artboard(
        document,
        name="Mobile",
        width=390,
        height=844,
    )
    document, existing = add_ui_object(
        document,
        kind="button",
        name="Existing focus",
        artboard_id=mobile["id"],
        x=24,
        y=24,
        width=120,
        height=44,
    )
    document, _existing = update_ui_object(
        document,
        existing["id"],
        {
            "accessibility": {
                "role": "button",
                "label": "Existing",
                "focus_order": 1,
            }
        },
    )
    document = set_active_ui_artboard(document, desktop_id)
    document = select_ui_objects(
        document,
        [group["id"]],
        primary_object_id=group["id"],
    )
    return document, desktop_id, mobile, group, image, button, interaction


def test_duplicate_to_next_artboard_preserves_hierarchy_and_interaction() -> None:
    from app.painter_ui_cross_artboard import (
        duplicate_ui_selection_to_artboard,
        inspect_cross_artboard_duplicate,
    )
    from app.painter_ui_document import validate_ui_document

    document, _desktop_id, mobile, group, image, button, interaction = (
        _document()
    )
    inspection = inspect_cross_artboard_duplicate(document)
    assert inspection["eligible"] is True
    assert inspection["target_artboard_id"] == mobile["id"]

    updated, report = duplicate_ui_selection_to_artboard(document)
    object_map = report["object_id_map"]
    created = {
        row["id"]: row
        for row in updated["objects"]
        if row["id"] in report["created_object_ids"]
    }

    assert updated["active_artboard_id"] == mobile["id"]
    assert updated["selection"]["object_ids"] == [
        object_map[group["id"]]
    ]
    assert created[object_map[group["id"]]]["parent_id"] == ""
    assert (
        created[object_map[image["id"]]]["parent_id"]
        == object_map[group["id"]]
    )
    assert (
        created[object_map[button["id"]]]["accessibility"]["focus_order"]
        == 0
    )
    assert report["focus_order_reset_object_ids"] == [
        object_map[button["id"]]
    ]

    interaction_copy = next(
        row
        for row in updated["interactions"]
        if row["id"] == report["interaction_id_map"][interaction["id"]]
    )
    assert interaction_copy["source_object_id"] == object_map[button["id"]]
    assert interaction_copy["target_object_id"] == object_map[image["id"]]
    assert interaction_copy["target_artboard_id"] == mobile["id"]
    assert validate_ui_document(updated)["ok"] is True


def test_duplicate_to_artboard_remaps_boolean_and_vector_ids() -> None:
    from app.painter_ui_boolean import compose_ui_boolean
    from app.painter_ui_cross_artboard import (
        duplicate_ui_selection_to_artboard,
    )
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        select_ui_objects,
        set_active_ui_artboard,
    )
    from app.painter_ui_vector_network import create_vector_network

    document = create_ui_document(800, 600)
    source_id = document["active_artboard_id"]
    document, left = add_ui_object(
        document,
        kind="path",
        name="Left",
        artboard_id=source_id,
        x=40,
        y=50,
        width=100,
        height=100,
        content={"vector_network": create_vector_network()},
    )
    document, right = add_ui_object(
        document,
        kind="rectangle",
        name="Right",
        artboard_id=source_id,
        x=90,
        y=50,
        width=100,
        height=100,
    )
    document = select_ui_objects(
        document,
        [left["id"], right["id"]],
        primary_object_id=right["id"],
    )
    document, boolean = compose_ui_boolean(
        document,
        "union",
        [left["id"], right["id"]],
    )
    document, target = add_ui_artboard(
        document,
        name="Target",
        width=390,
        height=844,
    )
    document = set_active_ui_artboard(document, source_id)
    document = select_ui_objects(
        document,
        [boolean["id"]],
        primary_object_id=boolean["id"],
    )

    updated, report = duplicate_ui_selection_to_artboard(
        document,
        target_artboard_id=target["id"],
    )
    object_map = report["object_id_map"]
    copied_group = next(
        row
        for row in updated["objects"]
        if row["id"] == object_map[boolean["id"]]
    )
    assert copied_group["content"]["boolean"]["operand_ids"] == [
        object_map[left["id"]],
        object_map[right["id"]],
    ]
    source_network = next(
        row for row in document["objects"] if row["id"] == left["id"]
    )["content"]["vector_network"]
    copied_network = next(
        row
        for row in updated["objects"]
        if row["id"] == object_map[left["id"]]
    )["content"]["vector_network"]
    assert copied_network != source_network
    assert len(copied_network["nodes"]) == len(source_network["nodes"])


def test_component_definition_duplicates_as_a_linked_instance() -> None:
    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_cross_artboard import (
        duplicate_ui_selection_to_artboard,
    )
    from app.painter_ui_document import (
        select_ui_objects,
        validate_ui_document,
    )

    document, _desktop_id, mobile, group, image, button, _interaction = (
        _document()
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=group["id"],
        name="Product card",
    )
    document = select_ui_objects(
        document,
        [group["id"]],
        primary_object_id=group["id"],
    )
    updated, report = duplicate_ui_selection_to_artboard(
        document,
        target_artboard_id=mobile["id"],
    )
    object_map = report["object_id_map"]
    copied = {
        row["id"]: row
        for row in updated["objects"]
        if row["id"] in report["created_object_ids"]
    }
    for source_id in (group["id"], image["id"], button["id"]):
        row = copied[object_map[source_id]]
        assert row["component_id"] == component["id"]
        assert row["component_role"] == "instance"
        assert row["component_source_object_id"] == source_id
        assert row["component_property_bindings"] == {}
    assert validate_ui_document(updated)["ok"] is True


def test_quick_action_and_action_share_cross_artboard_mutation_and_undo(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    document, _desktop_id, mobile, group, _image, _button, _interaction = (
        _document()
    )
    search = search_painter_ui_quick_actions(
        document,
        "duplicate next artboard",
    )
    command = next(
        row
        for row in search["results"]
        if row["id"] == "selection.duplicate_next_artboard"
    )
    assert command["enabled"] is True
    assert command["operation"] == {
        "type": "duplicate_to_next_artboard"
    }

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    before = dialog._painter_ui_document
    result = registry.execute(
        "paint.ui.object.duplicate_to_artboard",
        {
            "object_ids": [group["id"]],
            "target_artboard_id": mobile["id"],
        },
    )
    assert result.ok
    assert result.result["duplicate"]["target_artboard_id"] == mobile["id"]
    assert len(dialog._painter_ui_document["objects"]) > len(before["objects"])
    created_ids = set(result.result["duplicate"]["created_object_ids"])

    document_path = tmp_path / "cross_artboard.tspaint"
    saved = registry.execute(
        "paint.document.save",
        {"path": str(document_path)},
    )
    assert saved.ok
    with zipfile.ZipFile(document_path, "r") as archive:
        stored = json.loads(archive.read("document.json"))
    stored_ids = {
        row["id"]
        for row in stored["ui_document"]["objects"]
    }
    assert created_ids <= stored_ids
    assert (
        stored["ui_document"]["active_artboard_id"]
        == mobile["id"]
    )

    dialog._undo()
    assert dialog._painter_ui_document == before

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_last_artboard_reports_an_explicit_disabled_reason() -> None:
    from app.painter_ui_cross_artboard import (
        inspect_cross_artboard_duplicate,
    )
    from app.painter_ui_document import select_ui_objects
    from app.painter_ui_document import set_active_ui_artboard

    document, _desktop_id, mobile, _group, _image, _button, _interaction = (
        _document()
    )
    mobile_object = next(
        row
        for row in document["objects"]
        if row["artboard_id"] == mobile["id"]
    )
    document = set_active_ui_artboard(document, mobile["id"])
    document = select_ui_objects(
        document,
        [mobile_object["id"]],
        primary_object_id=mobile_object["id"],
    )
    report = inspect_cross_artboard_duplicate(document)
    assert report["eligible"] is False
    assert report["reason"] == "no_next_artboard"
