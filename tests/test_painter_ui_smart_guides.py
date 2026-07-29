from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_smart_guides_snap_text_baselines() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_smart_guides import plan_ui_move_guides

    document = create_ui_document(800, 600)
    document, moving = add_ui_object(
        document,
        kind="text",
        x=100,
        y=101,
        width=120,
        height=32,
        style={"font_size": 20},
    )
    document, _target = add_ui_object(
        document,
        kind="text",
        x=300,
        y=100,
        width=120,
        height=32,
        style={"font_size": 20},
    )
    report = plan_ui_move_guides(
        document,
        object_id=moving["id"],
        x=100,
        y=102,
        tolerance=4,
    )
    vertical = next(
        row for row in report["guides"] if row["axis"] == "vertical"
    )
    assert vertical["kind"] == "baseline"
    assert report["y"] == 100.0


def test_smart_guides_snap_parent_padding() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_smart_guides import plan_ui_move_guides

    document = create_ui_document(800, 600)
    document, frame = add_ui_object(
        document,
        kind="frame",
        x=100,
        y=80,
        width=400,
        height=300,
    )
    document, _frame = update_ui_object(
        document,
        frame["id"],
        {
            "layout": {
                "mode": "none",
                "padding": {
                    "left": 24,
                    "top": 16,
                    "right": 24,
                    "bottom": 16,
                },
            }
        },
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=126,
        y=98,
        width=100,
        height=80,
    )
    report = plan_ui_move_guides(
        document,
        object_id=child["id"],
        x=126,
        y=98,
        excluded_object_ids=[child["id"]],
        tolerance=4,
    )
    kinds = {row["kind"] for row in report["guides"]}
    assert "padding" in kinds
    assert report["x"] == 124.0
    assert report["y"] == 96.0


def test_smart_guides_snap_equal_horizontal_gap() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_smart_guides import plan_ui_move_guides

    document = create_ui_document(800, 600)
    document, _left = add_ui_object(
        document, kind="rectangle", x=0, y=100, width=100, height=100
    )
    document, moving = add_ui_object(
        document, kind="rectangle", x=148, y=100, width=100, height=100
    )
    document, _right = add_ui_object(
        document, kind="rectangle", x=300, y=100, width=100, height=100
    )
    report = plan_ui_move_guides(
        document,
        object_id=moving["id"],
        x=148,
        y=100,
        excluded_object_ids=[moving["id"]],
        tolerance=4,
    )
    horizontal = next(
        row for row in report["guides"] if row["axis"] == "horizontal"
    )
    assert horizontal["kind"] == "equal_gap"
    assert horizontal["value"] == 50.0
    assert report["x"] == 150.0


def test_smart_guide_action_is_read_only() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, moving = add_ui_object(
        document, kind="rectangle", x=100, y=100, width=100, height=100
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    before = copy.deepcopy(dialog._painter_ui_document)
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.smart_guide.inspect",
        {"object_id": moving["id"], "x": 102, "y": 102},
    ).to_dict()
    assert result["ok"] is True
    assert dialog._painter_ui_document == before
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
