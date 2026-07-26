from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_ui_artboard_title_drag_emits_document_position() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import (
        add_ui_artboard,
        create_ui_document,
        set_active_ui_artboard,
    )
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(390, 844, name="Phone")
    document, desktop = add_ui_artboard(
        document,
        name="Desktop",
        width=1440,
        height=900,
    )
    document = set_active_ui_artboard(document, "artboard-1")
    overlay = PainterUIDesignOverlay()
    overlay.resize(1200, 720)
    overlay.set_document(document)
    overlay.fit_all()
    overlay.show()
    app.processEvents()

    moved: list[tuple[str, float, float]] = []
    overlay.artboard_geometry_requested.connect(
        lambda artboard_id, x, y: moved.append((artboard_id, x, y))
    )
    title = overlay._artboard_title_rect(desktop)
    start = title.center().toPoint()
    end = start + QPoint(80, 48)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)

    assert moved
    assert moved[-1][0] == desktop["id"]
    assert moved[-1][1] > float(desktop["x"])
    assert moved[-1][2] > float(desktop["y"])
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_ui_artboard_presets_cover_product_targets() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    emitted: list[tuple[str, int, int, str]] = []
    inspector.artboard_add_requested.connect(
        lambda name, width, height, breakpoint: emitted.append(
            (name, width, height, breakpoint)
        )
    )
    presets = [
        inspector.artboard_preset_combo.itemData(index)
        for index in range(inspector.artboard_preset_combo.count())
    ]
    assert {row[3] for row in presets} == {
        "mobile",
        "desktop",
        "console",
        "broadcast",
    }
    inspector.artboard_preset_combo.setCurrentIndex(2)
    inspector._emit_add_artboard()
    assert emitted == [("Desktop", 1440, 900, "desktop")]
    inspector.deleteLater()
    app.processEvents()


def test_ui_artboard_move_and_preset_add_are_undoable() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    original = dict(dialog._painter_ui_document["artboards"][0])
    dialog._update_painter_ui_artboard_position(original["id"], 120.0, 80.0)
    moved = dialog._painter_ui_document["artboards"][0]
    assert (moved["x"], moved["y"]) == (120.0, 80.0)
    dialog._undo()
    restored = dialog._painter_ui_document["artboards"][0]
    assert (restored["x"], restored["y"]) == (original["x"], original["y"])

    dialog._add_painter_ui_artboard_preset(
        "Broadcast",
        1920,
        1080,
        "broadcast",
    )
    assert len(dialog._painter_ui_document["artboards"]) == 2
    assert dialog._painter_ui_document["artboards"][1]["breakpoint"] == "broadcast"
    dialog._undo()
    assert len(dialog._painter_ui_document["artboards"]) == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
