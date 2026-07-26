from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_layout_diagnostics_accepts_default_document() -> None:
    from app.painter_ui_document import create_ui_document, validate_ui_document

    report = validate_ui_document(create_ui_document())
    assert report["schema"] == "tigerstudio.painter.ui.validation.v2"
    assert report["ok"] is True
    assert report["layout_diagnostics"]["diagnostics"] == []


def test_layout_diagnostics_blocks_hug_fill_cycles_and_invalid_limits() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        validate_ui_document,
    )

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        width=300,
        height=100,
    )
    document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "width_sizing": "hug",
    }
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=parent["id"],
        width=100,
        height=40,
    )
    document["objects"][-1]["layout"] = {"width_sizing": "fill"}
    document["objects"][-1]["constraints"] = {
        "min_width": 200,
        "max_width": 100,
    }

    report = validate_ui_document(document)
    assert report["ok"] is False
    assert (
        f"layout_hug_fill_cycle:{parent['id']}:width:{child['id']}"
        in report["errors"]
    )
    assert f"constraint_min_exceeds_max:{child['id']}:width" in report["errors"]


def test_layout_diagnostics_blocks_collapsed_columns_and_safe_area() -> None:
    from app.painter_ui_document import create_ui_document, validate_ui_document

    document = create_ui_document(320, 200)
    artboard = document["artboards"][0]
    artboard["layout_grid"] = {
        "mode": "columns",
        "visible": True,
        "count": 4,
        "gutter": 80,
        "margin": 50,
    }
    artboard["safe_area"] = {
        "left": 160,
        "right": 160,
        "top": 110,
        "bottom": 100,
    }

    report = validate_ui_document(document)
    assert "artboard_columns_collapsed:artboard-1:width" in report["errors"]
    assert "artboard_safe_area_collapsed:artboard-1:width" in report["errors"]
    assert "artboard_safe_area_collapsed:artboard-1:height" in report["errors"]


def test_layout_diagnostics_warns_about_ignored_wrap_and_overflow() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        validate_ui_document,
    )

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        width=180,
        height=100,
    )
    document["objects"][0]["layout"] = {
        "mode": "horizontal",
        "width_sizing": "hug",
        "wrap": True,
        "gap": 20,
    }
    for _index in range(2):
        document, _child = add_ui_object(
            document,
            kind="rectangle",
            parent_id=parent["id"],
            width=100,
            height=40,
        )

    report = validate_ui_document(document)
    assert f"wrap_ignored_on_hug_axis:{parent['id']}:width" in report["warnings"]
    assert f"auto_layout_fixed_overflow:{parent['id']}:width" not in report[
        "warnings"
    ]
    document["objects"][0]["layout"]["wrap"] = False
    document["objects"][0]["layout"]["width_sizing"] = "fixed"
    report = validate_ui_document(document)
    assert f"auto_layout_fixed_overflow:{parent['id']}:width" in report["warnings"]


def test_layout_diagnostics_action_and_inspector_share_report() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_inspector import PainterUIInspector

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 200, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document["artboards"][0]["safe_area"] = {
        "left": 200,
        "right": 200,
        "top": 0,
        "bottom": 0,
    }
    registry = ActionRegistry(owner=dialog)
    assert "paint.ui.layout.diagnostics" in {
        row["id"] for row in registry.list_actions()
    }
    result = registry.execute("paint.ui.layout.diagnostics", {}).to_dict()
    assert result["ok"] is True
    assert result["result"]["ok"] is False
    assert result["result"]["errors"] == [
        "artboard_safe_area_collapsed:artboard-1:width"
    ]

    inspector = PainterUIInspector()
    inspector.set_document(dialog._painter_ui_document)
    assert inspector.artboard_layout_status_label.text() == "Layout: 1 error"
    assert "usable width" in inspector.artboard_layout_status_label.toolTip()
    inspector.deleteLater()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
