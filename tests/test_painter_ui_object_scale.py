from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, first = add_ui_object(
        document,
        kind="text",
        name="First",
        x=0,
        y=20,
        width=100,
        height=40,
        style={
            "font_size": 20,
            "radius": 8,
            "stroke": "#FFFFFFFF",
            "stroke_width": 2,
            "effects": [
                {
                    "type": "drop_shadow",
                    "x": 2,
                    "y": 4,
                    "blur": 8,
                    "spread": 1,
                }
            ],
        },
        content={"text": "Scale"},
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        name="Second",
        x=200,
        y=20,
        width=100,
        height=40,
    )
    return document, first, second


def test_scale_selection_resizes_geometry_and_visuals_around_center() -> None:
    from app.painter_ui_object_scale import scale_ui_objects

    document, first, second = _document()
    updated, report = scale_ui_objects(
        document,
        [first["id"], second["id"]],
        scale_x=2.0,
        origin="center",
    )
    rows = {row["id"]: row for row in updated["objects"]}

    assert report["pivot"] == {"x": 150.0, "y": 40.0}
    assert (rows[first["id"]]["x"], rows[first["id"]]["width"]) == (
        -150.0,
        200.0,
    )
    assert (rows[second["id"]]["x"], rows[second["id"]]["width"]) == (
        250.0,
        200.0,
    )
    style = rows[first["id"]]["style"]
    assert style["font_size"] == 40.0
    assert style["corner_radii"]["top_left"] == 16.0
    assert style["strokes"][0]["width"] == 4.0
    assert style["effects"][0]["blur"] == 16.0
    assert style["effects"][0]["x"] == 4.0


def test_scale_rejects_objects_from_different_parent_spaces() -> None:
    from app.painter_ui_document import add_ui_object, update_ui_object
    from app.painter_ui_object_scale import scale_ui_objects

    document, first, second = _document()
    document, group = add_ui_object(
        document,
        kind="group",
        name="Group",
    )
    document, _second = update_ui_object(
        document,
        second["id"],
        {"parent_id": group["id"]},
    )

    with pytest.raises(ValueError, match="parent coordinate space"):
        scale_ui_objects(
            document,
            [first["id"], second["id"]],
            scale_x=1.5,
        )


def test_scale_action_uses_one_undoable_shared_mutation() -> None:
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
    document, row = add_ui_object(
        dialog._painter_ui_document,
        kind="rectangle",
        x=100,
        y=80,
        width=120,
        height=60,
        style={"radius": 6},
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)

    result = registry.execute(
        "paint.ui.object.scale",
        {
            "object_ids": [row["id"]],
            "scale_x": 1.5,
            "origin": "top_left",
        },
    ).to_dict()
    assert result["ok"] is True
    scaled = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert (scaled["x"], scaled["y"]) == (100.0, 80.0)
    assert (scaled["width"], scaled["height"]) == (180.0, 90.0)
    assert scaled["style"]["corner_radii"]["top_left"] == 9.0

    dialog._undo()
    restored = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert (restored["width"], restored["height"]) == (120.0, 60.0)

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
