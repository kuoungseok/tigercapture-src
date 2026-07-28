from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, source = add_ui_object(
        document,
        kind="text",
        name="Source",
        x=40,
        y=50,
        width=240,
        height=60,
        style={"fill": "#223344", "text_color": "#F7FAFC", "font_size": 24},
        content={"text": "Source label"},
    )
    document, target = add_ui_object(
        document,
        kind="rectangle",
        name="Target",
        x=400,
        y=300,
        width=120,
        height=90,
        style={"fill": "#AA3300"},
    )
    return document, source, target


def test_property_paste_preserves_identity_geometry_and_content() -> None:
    from app.painter_ui_property_clipboard import (
        copy_ui_object_payload,
        paste_ui_object_properties,
    )

    document, source, target = _document()
    payload = copy_ui_object_payload(document, source["id"])
    updated, report = paste_ui_object_properties(
        document,
        [target["id"]],
        payload,
    )
    row = next(item for item in updated["objects"] if item["id"] == target["id"])

    assert report["mode"] == "properties"
    assert row["id"] == target["id"]
    assert row["kind"] == "rectangle"
    assert (row["x"], row["y"], row["width"], row["height"]) == (
        400.0,
        300.0,
        120.0,
        90.0,
    )
    assert row["content"].get("text", "") == ""
    assert row["style"]["fill"] == "#223344"
    assert row["style"]["text_color"] == "#F7FAFC"


def test_paste_replace_preserves_stable_target_references() -> None:
    from app.painter_ui_property_clipboard import (
        copy_ui_object_payload,
        paste_replace_ui_objects,
    )

    document, source, target = _document()
    payload = copy_ui_object_payload(document, source["id"])
    updated, report = paste_replace_ui_objects(
        document,
        [target["id"]],
        payload,
    )
    row = next(item for item in updated["objects"] if item["id"] == target["id"])

    assert report["mode"] == "replace"
    assert row["id"] == target["id"]
    assert row["name"] == target["name"]
    assert row["artboard_id"] == target["artboard_id"]
    assert row["parent_id"] == target["parent_id"]
    assert (row["x"], row["y"], row["z_index"]) == (
        target["x"],
        target["y"],
        target["z_index"],
    )
    assert row["kind"] == "text"
    assert (row["width"], row["height"]) == (source["width"], source["height"])
    assert row["content"]["text"] == "Source label"


def test_property_clipboard_actions_and_ui_share_one_undoable_service() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, source = add_ui_object(
        dialog._painter_ui_document,
        kind="rectangle",
        name="Source",
        style={"fill": "#246BCE"},
    )
    document, target = add_ui_object(
        document,
        kind="rectangle",
        name="Target",
        x=320,
        style={"fill": "#C05040"},
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)

    copied = registry.execute(
        "paint.ui.object.properties.copy",
        {"object_id": source["id"]},
    ).to_dict()
    assert copied["ok"] is True
    assert copied["result"]["clipboard"]["source_object_id"] == source["id"]

    pasted = registry.execute(
        "paint.ui.object.properties.paste",
        {"target_object_ids": [target["id"]]},
    ).to_dict()
    assert pasted["ok"] is True
    target_after = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == target["id"]
    )
    assert target_after["style"]["fill"] == "#246BCE"

    dialog._undo()
    target_undone = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == target["id"]
    )
    assert target_undone["style"]["fill"] == "#C05040"

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
