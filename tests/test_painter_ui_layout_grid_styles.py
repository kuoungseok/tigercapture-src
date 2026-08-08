from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_named_layout_grid_style_crud_updates_linked_artboards() -> None:
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_layout_grid_styles import (
        add_ui_layout_grid_style,
        apply_ui_layout_grid_style,
        remove_ui_layout_grid_style,
        update_ui_layout_grid_style,
    )

    document = create_ui_document(1440, 900)
    document, style = add_ui_layout_grid_style(
        document,
        name="Desktop Grid",
        layout_grids=[
            {"mode": "columns", "count": 12, "gutter": 24, "margin": 80},
            {"mode": "rows", "count": 8, "size": 48, "alignment": "center"},
        ],
    )
    document, artboard = apply_ui_layout_grid_style(
        document,
        artboard_id="artboard-1",
        style_id=style["id"],
    )
    assert artboard["layout_grid_style_id"] == style["id"]
    assert [row["mode"] for row in artboard["layout_grids"]] == [
        "columns",
        "rows",
    ]

    document, updated = update_ui_layout_grid_style(
        document,
        style["id"],
        {"layout_grids": [{"mode": "columns", "count": 6}]},
    )
    assert updated["layout_grids"][0]["count"] == 6
    assert document["artboards"][0]["layout_grids"][0]["count"] == 6

    document, removed = remove_ui_layout_grid_style(
        document,
        style["id"],
        detach_references=True,
    )
    assert removed["detached_artboard_ids"] == ["artboard-1"]
    assert document["artboards"][0]["layout_grid_style_id"] == ""
    assert document["artboards"][0]["layout_grids"][0]["count"] == 6


def test_layout_grid_style_actions_share_document_mutations() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    added = registry.execute(
        "paint.ui.layout_grid.style.add",
        {
            "name": "Six Columns",
            "layout_grids": [{"mode": "columns", "count": 6}],
        },
    ).to_dict()
    assert added["ok"] is True
    style_id = added["result"]["layout_grid_style"]["id"]

    applied = registry.execute(
        "paint.ui.layout_grid.style.apply",
        {"artboard_id": "artboard-1", "style_id": style_id},
    ).to_dict()
    assert applied["ok"] is True
    artboard = applied["result"]["ui_design"]["document"]["artboards"][0]
    assert artboard["layout_grid_style_id"] == style_id

    removed = registry.execute(
        "paint.ui.layout_grid.style.remove",
        {"style_id": style_id, "detach_references": True},
        confirm_destructive=True,
    ).to_dict()
    assert removed["ok"] is True
    assert (
        removed["result"]["ui_design"]["document"]["artboards"][0][
            "layout_grid_style_id"
        ]
        == ""
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_exposes_contextual_grid_style_controls() -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_inspector import PainterUIInspector
    from app.painter_ui_layout_grid_styles import add_ui_layout_grid_style

    document, style = add_ui_layout_grid_style(
        create_ui_document(1440, 900),
        name="Desktop Grid",
        layout_grids=[{"mode": "columns", "count": 12}],
    )
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, str]] = []
    inspector.layout_grid_style_apply_requested.connect(
        lambda artboard_id, style_id: emitted.append((artboard_id, style_id))
    )
    inspector.artboard_grid_style_combo.setCurrentIndex(
        inspector.artboard_grid_style_combo.findData(style["id"])
    )
    app.processEvents()

    assert emitted == [("artboard-1", style["id"])]
    assert inspector.artboard_grid_style_update_button.isEnabled()
    inspector.close()
    inspector.deleteLater()
    app.processEvents()
