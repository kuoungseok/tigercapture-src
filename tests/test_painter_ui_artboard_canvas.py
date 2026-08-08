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
    assert pixel == QColor("#171B21")
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_component_set_renders_dashed_purple_no_fill_container() -> None:
    app = _app()
    from PySide6.QtGui import QColor

    from app.painter_ui_components import (
        combine_ui_components_as_variants,
        convert_ui_object_to_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document = create_ui_document(800, 600)
    component_ids = []
    for index, name in enumerate(("Button/Default", "Button/Hover")):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=name,
            x=140 + index * 220,
            y=180,
            width=160,
            height=64,
        )
        document, component = convert_ui_object_to_component(
            document, root_object_id=root["id"], name=name
        )
        component_ids.append(component["id"])
    document, _ = combine_ui_components_as_variants(
        document, component_ids=component_ids
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 720)
    overlay.set_document(document)
    overlay.fit_all()
    overlay.show()
    app.processEvents()
    image = overlay.grab().toImage()
    purple = QColor("#9747FF")
    purple_pixels = sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).red() == purple.red()
        and image.pixelColor(x, y).blue() == purple.blue()
    )
    assert purple_pixels > 20
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_ui_design_mode_shows_inspector_and_has_one_fit_tool_set() -> None:
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
    assert dialog._painter_ui_template_strip is None
    assert dialog._painter_ui_templates_action.isVisible()
    assert dialog._painter_ui_templates_action.text() == painter_text(
        "Painter UI Template Gallery",
        current_language(),
    )
    assert dialog.property("canvasWorkspaceMode") == "ui_design"
    assert not dialog._paint_top_bar.isVisible()
    assert not dialog._tool_rail.isVisible()
    assert not dialog._paint_ui_inspector.artboard_layout_frame.isVisible()
    assert not dialog._paint_ui_inspector.artboard_settings_toggle.isVisible()
    assert dialog._paint_ui_inspector.page_properties_panel.isVisible()
    assert dialog._paint_ui_inspector.page_properties_panel.height() <= 160
    assert (
        dialog._paint_ui_inspector.page_background_value.parentWidget().height()
        == 36
    )
    assert not dialog._paint_ui_inspector.object_properties_host.isVisible()
    assert not dialog._paint_ui_inspector.fill_edit.isVisible()
    assert dialog._paint_ui_inspector.zoom_button.text() == "100%"
    assert dialog._paint_ui_inspector.visible_context_tabs() == (
        "design",
        "prototype",
    )
    assert (
        dialog._paint_ui_inspector.artboard_grid_count_spin.buttonSymbols()
        == QAbstractSpinBox.ButtonSymbols.NoButtons
    )
    assert not dialog._paint_layer_dock_panel.isVisible()
    assert dialog._painter_ui_overlay.geometry() == dialog._canvas_host.rect()
    inspector_width = dialog._paint_inspector_controls_scroll.parentWidget().width()
    assert inspector_width >= 180
    assert not dialog._paint_ui_inspector.is_auto_hide()
    assert not dialog._paint_ui_inspector.is_collapsed()
    assert not dialog._paint_ui_inspector.dock_button.isVisible()
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
    assert tabs.count() == 3
    assert tabs.tabBar().usesScrollButtons() is False
    assert [
        tabs.tabText(index)
        for index in range(tabs.count())
    ] == [
        painter_text(label, current_language())
        for label in ("Design", "Prototype", "Inspect")
    ]
    assert dialog._painter_ui_navigator.isVisible()
    assert dialog._painter_ui_navigator.active_section() == "file"
    assert dialog._painter_ui_navigator.navigation_buttons["file"].isChecked()
    assert dialog._painter_ui_navigator.page_list.count() == 1
    assert (
        dialog._painter_ui_navigator._layer_list
        is dialog._paint_ui_inspector.layer_list
    )
    dialog._painter_ui_navigator.logo_button.click()
    app.processEvents()
    main_menu = dialog._painter_navigation_main_menu
    assert main_menu.actions()[0].shortcut().toString() == "Ctrl+K"
    assert main_menu._painter_file_menu.actions()[1].menu() is (
        main_menu._painter_new_menu
    )
    main_menu.hide()
    assert dialog._ui_design_tool_host.parentWidget() is dialog._canvas_host
    assert (
        dialog._ui_design_tool_host.y()
        + dialog._ui_design_tool_host.height()
        <= dialog._canvas_host.height()
    )
    dialog._canvas_host.resize(400, 500)
    dialog._sync_ui_design_toolbar_density()
    assert not dialog._ui_design_tool_buttons["ellipse"].isHidden()
    assert not dialog._ui_design_tool_host.zoom_button.isHidden()
    assert (
        dialog._ui_design_view_buttons["selection"].parentWidget()
        is dialog._ui_design_tool_host.zoom_popover
    )
    dialog._canvas_host.resize(900, 500)
    dialog._sync_ui_design_toolbar_density()
    assert not dialog._ui_design_tool_buttons["ellipse"].isHidden()
    assert not dialog._ui_design_tool_host.zoom_button.isHidden()

    compact_grids = dialog._paint_ui_inspector.findChildren(
        QFrame,
        "PainterUICompactGrid",
    )
    assert [grid.layout().count() for grid in compact_grids] == [4, 5, 3]

    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert dialog._paint_top_bar.isVisible()
    assert dialog._tool_rail.isVisible()
    assert dialog._painter_ui_template_strip is None

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_focus_mode_keeps_page_title_and_toolbar_only() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_i18n import painter_text

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._set_painter_ui_empty_page_mode(True)
    dialog.show()
    app.processEvents()

    assert dialog._paint_ui_inspector.isVisible()
    assert dialog._painter_ui_navigator.isVisible()
    dialog._ui_design_tool_host.focus_mode_button.click()
    app.processEvents()

    assert dialog._painter_ui_focus_mode is True
    assert dialog._painter_ui_page_title_label.isVisible()
    assert dialog._painter_ui_page_title_label.text() == "Page 1"
    assert dialog._ui_design_tool_host.isVisible()
    assert dialog._painter_ui_focus_island.isVisible()
    assert not hasattr(dialog._painter_ui_focus_island, "plan_label")
    assert dialog._painter_ui_focus_controls_island.isVisible()
    assert not hasattr(
        dialog._painter_ui_focus_controls_island,
        "brand_button",
    )
    assert dialog._painter_ui_focus_controls_island.zoom_button.text() == "100%"
    assert (
        dialog._painter_ui_focus_island.title_label.text()
        == painter_text("Untitled")
    )
    assert not dialog._paint_inspector_frame.isVisible()
    assert not dialog._painter_ui_navigator.isVisible()
    assert not dialog._canvas_mode_ui_btn.isVisible()
    island_center = dialog._painter_ui_focus_island.geometry().center()
    top_widget = dialog._canvas_host.childAt(island_center)
    assert top_widget is dialog._painter_ui_focus_island or (
        top_widget is not None
        and dialog._painter_ui_focus_island.isAncestorOf(top_widget)
    )
    controls_center = (
        dialog._painter_ui_focus_controls_island.geometry().center()
    )
    controls_top = dialog._canvas_host.childAt(controls_center)
    assert controls_top is dialog._painter_ui_focus_controls_island or (
        controls_top is not None
        and dialog._painter_ui_focus_controls_island.isAncestorOf(
            controls_top
        )
    )
    dialog._painter_ui_focus_controls_island.zoom_button.click()
    app.processEvents()
    assert dialog._painter_ui_focus_controls_island.zoom_popover.isVisible()
    assert not bool(
        dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    )

    dialog._painter_ui_focus_island.exit_button.click()
    app.processEvents()
    assert not dialog._painter_ui_focus_island.isVisible()
    assert not dialog._painter_ui_focus_controls_island.isVisible()
    assert dialog._paint_ui_inspector.isVisible()
    assert dialog._painter_ui_navigator.isVisible()
    assert dialog._canvas_mode_ui_btn.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_focus_mode_does_not_resurrect_empty_redocked_inspector_window() -> None:
    app = _app()

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()

    dialog._detach_painter_ui_inspector()
    app.processEvents()
    floating = dialog._painter_ui_inspector_dock_window
    assert floating.isVisible()
    assert dialog._painter_ui_inspector_detached

    dialog._dock_painter_ui_inspector()
    app.processEvents()
    assert not dialog._painter_ui_inspector_detached
    assert not floating.isVisible()
    assert dialog._paint_ui_inspector.parentWidget() is not None

    dialog._set_painter_ui_focus_mode(True)
    dialog._set_painter_ui_focus_mode(False)
    app.processEvents()

    assert not floating.isVisible()
    assert dialog._paint_ui_inspector.isVisible()
    assert not dialog._painter_ui_inspector_detached

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_empty_page_mode_hides_internal_root_artboard() -> None:
    app = _app()
    from PySide6.QtGui import QColor

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(create_ui_document(390, 844))
    overlay.set_empty_page_mode(True)
    overlay.show()
    app.processEvents()

    image = overlay.grab().toImage()
    assert image.pixelColor(400, 300) == QColor("#F5F5F5")

    overlay.set_empty_page_mode(False)
    app.processEvents()
    visible_image = overlay.grab().toImage()
    assert visible_image.pixelColor(400, 300) != QColor("#F5F5F5")
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
