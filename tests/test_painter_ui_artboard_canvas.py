from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.i18n import set_language

    app = QApplication.instance() or QApplication([])
    set_language("en")
    return app


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


def test_ui_design_workspace_is_opaque_and_uses_editor_canvas_gray() -> None:
    app = _app()
    from PySide6.QtGui import QColor

    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(640, 420)
    overlay.show()
    app.processEvents()

    pixel = overlay.grab().toImage().pixelColor(2, 2)
    assert pixel.alpha() == 255
    assert pixel == QColor("#3F4145")
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_ui_design_mode_expands_inspector_and_has_one_fit_tool_set() -> None:
    app = _app()
    from PySide6.QtWidgets import QAbstractSpinBox, QFrame

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.i18n import current_language
    from app.painter_i18n import painter_text

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1500, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()

    assert len(dialog._ui_design_view_buttons) == 3
    assert dialog._paint_inspector_controls_scroll.maximumHeight() == 16777215
    assert dialog._paint_ui_inspector.isVisible()
    assert dialog._painter_ui_template_strip.isVisible()
    assert dialog._painter_ui_template_strip.y() >= dialog._painter_menu_bar.height()
    assert dialog.property("canvasWorkspaceMode") == "ui_design"
    assert not dialog._paint_top_bar.isVisible()
    assert not dialog._tool_rail.isVisible()
    assert not dialog._paint_ui_inspector.artboard_layout_frame.isVisible()
    dialog._paint_ui_inspector.artboard_settings_toggle.click()
    app.processEvents()
    assert dialog._paint_ui_inspector.artboard_layout_frame.isVisible()
    assert (
        dialog._paint_ui_inspector.artboard_grid_count_spin.buttonSymbols()
        == QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    assert not dialog._paint_layer_dock_panel.isVisible()
    assert dialog._painter_ui_overlay.geometry() == dialog._canvas_host.rect()
    assert dialog._paint_inspector_controls_scroll.parentWidget().width() >= 320
    assert dialog._painter_file_menu.menuAction().isVisible()
    assert dialog._painter_ui_menu.menuAction().isVisible()
    assert not dialog._painter_edit_menu.menuAction().isVisible()
    assert not dialog._painter_image_menu.menuAction().isVisible()
    assert not dialog._painter_layer_menu.menuAction().isVisible()
    assert not dialog._painter_select_menu.menuAction().isVisible()
    assert not dialog._painter_view_menu.menuAction().isVisible()
    assert not dialog._painter_window_menu.menuAction().isVisible()
    tabs = dialog._paint_ui_inspector._tabs
    assert tabs.objectName() == "PainterUIInspectorTabs"
    assert tabs.count() == 6
    assert tabs.tabBar().usesScrollButtons() is False
    assert all(tabs.tabText(index) == "" for index in range(tabs.count()))
    assert {
        tabs.tabToolTip(index)
        for index in range(tabs.count())
    } == {
        painter_text(label, current_language())
        for label in (
            "Sections",
            "Components",
            "Tokens",
            "Motion",
            "Publish",
            "Inspect",
        )
    }
    assert dialog._painter_ui_navigator.isVisible()
    assert dialog._painter_ui_navigator.page_list.count() == 1
    assert (
        dialog._painter_ui_navigator._layer_list
        is dialog._paint_ui_inspector.layer_list
    )
    assert (
        dialog._ui_design_tool_host.parentWidget().objectName()
        == "PaintCanvasFrame"
    )
    dialog._canvas_host.resize(400, 500)
    dialog._sync_ui_design_toolbar_density()
    assert dialog._ui_design_tool_buttons["ellipse"].isHidden()
    assert dialog._ui_design_view_buttons["selection"].isHidden()
    dialog._canvas_host.resize(900, 500)
    dialog._sync_ui_design_toolbar_density()
    assert not dialog._ui_design_tool_buttons["ellipse"].isHidden()
    assert not dialog._ui_design_view_buttons["selection"].isHidden()

    compact_grids = dialog._paint_ui_inspector.findChildren(
        QFrame,
        "PainterUICompactGrid",
    )
    assert [grid.layout().count() for grid in compact_grids] == [4, 5, 3]

    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert dialog._paint_top_bar.isVisible()
    assert dialog._tool_rail.isVisible()
    assert not dialog._painter_ui_template_strip.isVisible()

    dialog.close()
    dialog.deleteLater()
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
    assert inspector.artboard_preset_combo.isHidden()
    assert inspector.add_artboard_button.menu() is not None
    assert len(inspector.add_artboard_button.menu().actions()) == len(presets)
    inspector._emit_add_artboard_preset(0)
    assert emitted[-1] == ("iPhone", 390, 844, "mobile")
    assert not inspector.delete_artboard_button.isEnabled()
    inspector.deleteLater()
    app.processEvents()


def test_ui_artboard_delete_button_is_safe_and_emits_active_artboard() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_artboard, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document = create_ui_document(390, 844, name="Phone")
    inspector = PainterUIInspector()
    inspector.set_document(document)
    assert not inspector.delete_artboard_button.isEnabled()

    document, desktop = add_ui_artboard(
        document,
        name="Desktop",
        width=1440,
        height=900,
    )
    inspector.set_document(document)
    deleted: list[str] = []
    inspector.artboard_delete_requested.connect(deleted.append)
    assert inspector.delete_artboard_button.isEnabled()
    inspector.delete_artboard_button.click()
    assert deleted == [desktop["id"]]
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
    added_id = dialog._painter_ui_document["active_artboard_id"]
    dialog._delete_painter_ui_artboard(added_id)
    assert len(dialog._painter_ui_document["artboards"]) == 1
    dialog._undo()
    assert len(dialog._painter_ui_document["artboards"]) == 2
    dialog._undo()
    assert len(dialog._painter_ui_document["artboards"]) == 1
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
