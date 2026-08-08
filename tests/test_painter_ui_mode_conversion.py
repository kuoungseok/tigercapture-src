from __future__ import annotations


def _app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(400, 300, name="Conversion")
    document, rectangle = add_ui_object(
        document,
        kind="rectangle",
        name="Card",
        x=40,
        y=50,
        width=160,
        height=100,
        style={"fill": "#315273", "radius": 8},
    )
    document, text = add_ui_object(
        document,
        kind="text",
        name="Title",
        x=60,
        y=70,
        width=120,
        height=32,
        style={"text_color": "#FFFFFF", "font_size": 18},
        content={"text": "Editable"},
    )
    document["selection"] = {
        "object_id": rectangle["id"],
        "object_ids": [rectangle["id"], text["id"]],
    }
    return document, rectangle["id"], text["id"]


def test_conversion_inspection_blocks_semantic_text_from_vector() -> None:
    from app.painter_ui_mode_conversion import (
        CONVERSION_INSPECT_SCHEMA,
        inspect_painter_ui_conversion,
    )

    document, rectangle_id, text_id = _document()
    report = inspect_painter_ui_conversion(document)

    assert report["schema"] == CONVERSION_INSPECT_SCHEMA
    assert report["paint"]["available"] is True
    assert report["vector"]["counts"] == {
        "Convertible": 1,
        "Already Vector": 0,
        "Blocked": 1,
    }
    assert {row["object_id"] for row in report["vector"]["features"]} == {
        rectangle_id,
        text_id,
    }


def test_convert_to_vector_preserves_stable_id_and_one_revision() -> None:
    from app.painter_ui_document import validate_ui_document
    from app.painter_ui_mode_conversion import convert_painter_ui_to_vector

    document, rectangle_id, _text_id = _document()
    before_revision = document["revision"]
    updated, report = convert_painter_ui_to_vector(
        document,
        object_ids=[rectangle_id],
    )
    converted = next(
        row for row in updated["objects"] if row["id"] == rectangle_id
    )

    assert report["converted_object_ids"] == [rectangle_id]
    assert report["stable_ids_preserved"] is True
    assert updated["revision"] == before_revision + 1
    assert converted["kind"] == "path"
    assert converted["content"]["converted_from_kind"] == "rectangle"
    assert len(converted["content"]["vector_network"]["nodes"]) >= 4
    assert validate_ui_document(updated)["ok"] is True


def test_render_selection_to_paint_is_transparent_and_cropped() -> None:
    _app()
    from app.painter_ui_mode_conversion import (
        PAINT_CONVERSION_SCHEMA,
        render_painter_ui_selection_to_paint,
    )

    document, rectangle_id, text_id = _document()
    image, report = render_painter_ui_selection_to_paint(
        document,
        object_ids=[rectangle_id, text_id],
    )

    assert report["schema"] == PAINT_CONVERSION_SCHEMA
    assert report["ok"] is True
    assert report["source_preserved"] is True
    assert report["pixel_size"] == {"width": 160, "height": 100}
    assert set(report["source_object_ids"]) == {rectangle_id, text_id}
    assert image.width() == 160
    assert image.height() == 100
    assert image.pixelColor(80, 50).alpha() > 0


def test_paint_conversion_bounds_include_rotation() -> None:
    _app()
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_mode_conversion import (
        render_painter_ui_selection_to_paint,
    )

    document, rectangle_id, _text_id = _document()
    document, _row = update_ui_object(
        document,
        rectangle_id,
        {"rotation": 45.0},
    )
    image, report = render_painter_ui_selection_to_paint(
        document,
        object_ids=[rectangle_id],
    )

    assert image.width() > 160
    assert image.height() > 100
    assert report["source_bounds"]["width"] > 160


def test_paint_dialog_vector_conversion_is_one_undo_step() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, rectangle_id, _text_id = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(400, 300, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    before_undo = len(dialog._undo_stack)

    report = dialog._convert_painter_ui_selection_to_vector(
        object_ids=[rectangle_id],
    )

    assert report["converted_count"] == 1
    assert len(dialog._undo_stack) == before_undo + 1
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == rectangle_id
    )["kind"] == "path"
    dialog._undo()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == rectangle_id
    )["kind"] == "rectangle"
    dialog._painter_ui_convert_vector_action.trigger()
    assert next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == rectangle_id
    )["kind"] == "path"
    dialog.close()


def test_conversion_actions_and_quick_actions_are_discoverable() -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    action_ids = {row["id"] for row in ActionRegistry(owner=None).list_actions()}
    assert {
        "paint.ui.convert.inspect",
        "paint.ui.convert.to_paint",
        "paint.ui.convert.to_vector",
    }.issubset(action_ids)

    document, _rectangle_id, _text_id = _document()
    results = search_painter_ui_quick_actions(document, "convert")
    result_ids = {row["id"] for row in results["results"]}
    assert {
        "selection.convert_to_paint",
        "selection.convert_to_vector",
    }.issubset(result_ids)


def test_paint_dialog_conversion_creates_persistent_image_layer(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, rectangle_id, text_id = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(400, 300, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    monkeypatch.setattr(
        dialog,
        "_painter_ui_conversion_asset_root",
        lambda: tmp_path,
    )
    before_undo = len(dialog._undo_stack)

    report = dialog._convert_painter_ui_selection_to_paint(
        object_ids=[rectangle_id, text_id],
    )

    assert report["result"] == "paint_image_layer"
    assert report["source_preserved"] is True
    assert report["paint_layer_id"] == "sticker:0"
    assert len(dialog._stickers) == 1
    assert len(dialog._undo_stack) == before_undo + 1
    assert dialog._canvas_workspace_mode == "paint"
    from pathlib import Path

    assert Path(report["asset_path"]).is_file()
    dialog._undo()
    assert dialog._stickers == []
    assert dialog._canvas_workspace_mode == "ui_design"
    dialog.close()


def test_conversion_actions_execute_the_same_dialog_mutations(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, rectangle_id, text_id = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(400, 300, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    monkeypatch.setattr(
        dialog,
        "_painter_ui_conversion_asset_root",
        lambda: tmp_path,
    )
    registry = ActionRegistry(owner=dialog)

    vector = registry.execute(
        "paint.ui.convert.to_vector",
        {"object_ids": [rectangle_id]},
    ).to_dict()
    assert vector["ok"] is True and vector["changed"] is True
    assert vector["result"]["converted_object_ids"] == [rectangle_id]
    dialog._undo()

    paint = registry.execute(
        "paint.ui.convert.to_paint",
        {"object_ids": [rectangle_id, text_id]},
    ).to_dict()
    assert paint["ok"] is True and paint["changed"] is True
    assert paint["result"]["paint_layer_id"] == "sticker:0"
    dialog.close()
