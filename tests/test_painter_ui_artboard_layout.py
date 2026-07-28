from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_artboard_layout_normalizes_grid_guides_and_safe_area() -> None:
    from app.painter_ui_artboard_layout import normalize_ui_artboard_layout

    layout = normalize_ui_artboard_layout(
        {
            "layout_grid": {
                "mode": "columns",
                "count": 12,
                "gutter": 16,
                "margin": 24,
            },
            "safe_area": {"left": 20, "top": 30, "right": 20, "bottom": 30},
            "safe_area_visible": True,
            "guides": {
                "vertical": [200, 100, 200, 9999],
                "horizontal": [40, -10],
            },
        },
        width=390,
        height=844,
    )

    assert layout["layout_grid"]["mode"] == "columns"
    assert layout["layout_grid"]["count"] == 12
    assert layout["safe_area_visible"] is True
    assert layout["safe_area"] == {
        "left": 20,
        "top": 30,
        "right": 20,
        "bottom": 30,
    }
    assert layout["guides"]["vertical"] == [100.0, 200.0, 390.0]
    assert layout["guides"]["horizontal"] == [0.0, 40.0]


def test_artboard_layout_inspector_emits_provider_neutral_changes() -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    inspector.set_document(create_ui_document(390, 844))
    emitted: list[tuple[str, dict]] = []
    inspector.artboard_layout_changed.connect(
        lambda artboard_id, changes: emitted.append((artboard_id, changes))
    )
    inspector._syncing = True
    inspector.artboard_grid_mode_combo.setCurrentIndex(
        inspector.artboard_grid_mode_combo.findData("columns")
    )
    inspector.artboard_grid_count_spin.setValue(4)
    inspector.artboard_grid_gutter_spin.setValue(12)
    inspector.artboard_grid_margin_spin.setValue(20)
    inspector.artboard_safe_visible_check.setChecked(True)
    inspector.artboard_safe_controls["top"].setValue(47)
    inspector.artboard_vertical_guides_edit.setText("100, 200")
    inspector.artboard_horizontal_guides_edit.setText("80")
    inspector._syncing = False
    inspector._emit_artboard_layout()

    assert emitted[-1][0] == "artboard-1"
    changes = emitted[-1][1]
    assert changes["layout_grid"]["mode"] == "columns"
    assert changes["layout_grid"]["count"] == 4
    assert changes["safe_area_visible"] is True
    assert changes["safe_area"]["top"] == 47
    assert changes["guides"]["vertical"] == [100.0, 200.0]
    inspector.deleteLater()
    app.processEvents()


def test_artboard_layout_action_updates_and_undoes_document() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    original = dict(dialog._painter_ui_document["artboards"][0])
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.artboard.layout.set",
        {
            "artboard_id": "artboard-1",
            "layout_grid": {
                "mode": "grid",
                "visible": True,
                "size": 10,
            },
            "safe_area": {"left": 24, "top": 24, "right": 24, "bottom": 24},
            "safe_area_visible": True,
            "guides": {"visible": True, "vertical": [100], "horizontal": [80]},
        },
    ).to_dict()

    assert result["ok"] is True
    artboard = result["result"]["ui_design"]["document"]["artboards"][0]
    assert artboard["layout_grid"]["mode"] == "grid"
    assert artboard["safe_area_visible"] is True
    assert artboard["guides"]["vertical"] == [100.0]
    dialog._undo()
    assert dialog._painter_ui_document["artboards"][0] == original
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_artboard_layout_renderer_draws_columns_and_safe_area() -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_workspace import PainterUIDesignOverlay

    image = QImage(120, 100, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#FFFFFF"))
    painter = QPainter(image)
    PainterUIDesignOverlay._paint_artboard_layout(
        painter,
        {
            "width": 120,
            "height": 100,
            "layout_grid": {
                "mode": "columns",
                "visible": True,
                "count": 2,
                "gutter": 10,
                "margin": 10,
            },
            "safe_area": {"left": 8, "top": 8, "right": 8, "bottom": 8},
            "safe_area_visible": True,
            "guides": {"visible": True, "vertical": [60], "horizontal": []},
        },
        QRectF(0, 0, 120, 100),
        1.0,
    )
    painter.end()

    assert image.pixelColor(15, 50) != QColor("#FFFFFF")
    assert image.pixelColor(60, 50) != QColor("#FFFFFF")
    assert image.pixelColor(8, 8) != QColor("#FFFFFF")


def test_ui_canvas_rulers_draw_and_drag_guides() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 480)
    overlay.set_document(create_ui_document(390, 844))
    overlay.show()
    app.processEvents()
    viewport, _scale = overlay._artboard_viewport()
    emitted: list[tuple[str, float]] = []
    overlay.guide_create_requested.connect(
        lambda orientation, position: emitted.append(
            (orientation, position)
        )
    )

    image = overlay.grab().toImage()
    assert image.pixelColor(15, 15).name().upper() == "#171B21"

    target_y = int(viewport.top() + viewport.height() * 0.25)
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(max(30, int(viewport.center().x())), 5),
    )
    QTest.mouseMove(
        overlay,
        QPoint(max(30, int(viewport.center().x())), target_y),
    )
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(max(30, int(viewport.center().x())), target_y),
    )
    app.processEvents()

    assert emitted
    assert emitted[-1][0] == "horizontal"
    assert abs(emitted[-1][1] - 844 * 0.25) < 4.0
    overlay.deleteLater()


def test_ui_canvas_guide_creation_uses_document_undo_path() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    original = dict(dialog._painter_ui_document["artboards"][0])
    dialog._create_painter_ui_guide("vertical", 123.0)

    guides = dialog._painter_ui_document["artboards"][0]["guides"]
    assert guides["visible"] is True
    assert guides["vertical"] == [123.0]
    dialog._undo()
    assert dialog._painter_ui_document["artboards"][0] == original
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_guide_actions_share_mutation_and_ruler_surface() -> None:
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
    created = registry.execute(
        "paint.ui.guide.create",
        {
            "orientation": "vertical",
            "position": 96,
        },
    ).to_dict()
    assert created["ok"] is True
    assert created["result"]["ui_design"]["document"]["artboards"][0][
        "guides"
    ]["vertical"] == [96.0]

    removed = registry.execute(
        "paint.ui.guide.remove",
        {
            "orientation": "vertical",
            "position": 96.2,
            "tolerance": 0.5,
        },
    ).to_dict()
    assert removed["ok"] is True
    assert removed["result"]["ui_design"]["document"]["artboards"][0][
        "guides"
    ]["vertical"] == []

    registry.execute(
        "paint.ui.ruler.visibility.set",
        {"visible": False},
    )
    assert dialog._painter_ui_overlay.rulers_visible() is False
    registry.execute(
        "paint.ui.ruler.visibility.set",
        {"visible": True},
    )
    assert dialog._painter_ui_overlay.rulers_visible() is True
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
