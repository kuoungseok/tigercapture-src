from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_main_menu_has_action_search_and_cascading_file_commands() -> None:
    _app()
    from PySide6.QtWidgets import QMenu, QWidget

    from app.painter_i18n import painter_text
    from app.painter_ui_main_menu import build_painter_ui_main_menu

    owner = QWidget()
    invoked: list[str] = []
    callbacks = {
        key: (lambda _checked=False, value=key: invoked.append(value))
        for key in (
            "quick_actions",
            "new_design",
            "templates",
            "new_paint_canvas",
            "place_image",
            "open",
            "save",
            "save_as",
            "recovery",
            "version_save",
            "version_history",
            "export_png",
            "export_transparent",
            "export_pdf",
            "create_branch",
            "text_tool",
            "find_replace",
            "tools",
            "libraries",
            "shortcuts",
            "locale_audit",
            "action_parity",
            "figma_plugin_manager",
        )
    }
    source = QMenu("Source", owner)
    source.addAction("Canonical command")
    menu = build_painter_ui_main_menu(
        owner,
        callbacks=callbacks,
        source_menus={
            "edit": source,
            "view": source,
            "object": source,
            "arrange": source,
            "vector": source,
        },
    )

    actions = menu.actions()
    assert actions[0].text() == painter_text("Actions...")
    assert actions[0].shortcut().toString() == "Ctrl+K"
    assert not actions[0].icon().isNull()
    assert actions[1].isSeparator()

    file_menu = menu._painter_file_menu
    assert file_menu.title() == painter_text("File")
    assert file_menu.actions()[0].text() == painter_text("New Design...")
    assert file_menu.actions()[1].menu() is menu._painter_new_menu
    assert [
        action.text() for action in menu._painter_new_menu.actions()
    ] == [
        painter_text("Blank UI Design..."),
        painter_text("From Template..."),
        painter_text("Paint Canvas..."),
    ]
    assert any(
        action.text() == painter_text("Place Image...")
        and action.shortcut().toString() == "Ctrl+Shift+K"
        for action in file_menu.actions()
    )
    file_labels = [
        action.text()
        for action in file_menu.actions()
        if not action.isSeparator()
    ]
    assert painter_text("Save to version history...") in file_labels
    assert painter_text("View version history") in file_labels
    assert painter_text("Export frames to PDF...") in file_labels
    assert painter_text("Create branch...") in file_labels
    assert painter_text("Export Transparent PNG...") not in file_labels
    assert "border-radius: 10px" in menu.styleSheet()

    top_level_labels = {
        action.text() for action in actions if not action.isSeparator()
    }
    assert painter_text("Plugins") in top_level_labels
    assert painter_text("Widgets") not in top_level_labels
    assert menu._painter_plugins_menu.actions()[0].text() == painter_text(
        "Manage local Figma plugins..."
    )

    actions[0].trigger()
    assert invoked == ["quick_actions"]
    menu.deleteLater()
    owner.deleteLater()


def test_ui_logo_menu_commands_mutate_the_ui_document() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_main_menu_commands import (
        build_painter_ui_menu_callbacks,
        painter_ui_menu_state,
    )

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._add_default_painter_ui_object("rectangle")
    first = dialog._painter_ui_document["selection"]["object_id"]
    dialog._add_default_painter_ui_object("ellipse")
    second = dialog._painter_ui_document["selection"]["object_id"]
    dialog._set_painter_ui_selection([first, second], second)

    callbacks = build_painter_ui_menu_callbacks(dialog)
    assert painter_ui_menu_state(dialog)["multi_selection"] is True
    callbacks["group"]()
    selected = dialog._painter_ui_document["selection"]["object_id"]
    grouped = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == selected
    )
    assert grouped["kind"] == "group"

    callbacks["ungroup"]()
    assert not any(
        row["kind"] == "group"
        for row in dialog._painter_ui_document["objects"]
    )

    dialog._set_painter_ui_selection([first, second], second)
    callbacks["boolean_union"]()
    boolean_id = dialog._painter_ui_document["selection"]["object_id"]
    assert painter_ui_menu_state(dialog)["group_selection"] is True
    assert any(
        row["id"] == boolean_id
        and row["content"]["boolean"]["operation"] == "union"
        for row in dialog._painter_ui_document["objects"]
    )
    callbacks["ungroup"]()
    assert boolean_id not in {
        row["id"] for row in dialog._painter_ui_document["objects"]
    }

    dialog._add_default_painter_ui_object("text")
    text_id = dialog._painter_ui_document["selection"]["object_id"]
    callbacks["bold"]()
    text_row = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == text_id
    )
    assert text_row["style"]["font_weight"] == 700

    callbacks["toggle_pixel_grid"]()
    assert dialog._painter_ui_pixel_grid is True
    assert dialog._painter_ui_overlay._pixel_grid_visible is True
    callbacks["toggle_layer_outlines"]()
    assert dialog._painter_ui_layer_outlines is True
    assert dialog._painter_ui_overlay._layer_outlines_visible is True

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_tiger_painter_logo_is_a_dedicated_vector_icon() -> None:
    _app()
    from app.icons import app_icon

    logo = app_icon("tiger-painter-logo", size=32, color="#FFFFFF")
    assert not logo.isNull()
    image = logo.pixmap(32, 32).toImage()
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(image.height())
        for x in range(image.width())
    )


def test_file_menu_exports_each_ui_artboard_to_a_real_pdf(tmp_path) -> None:
    _app()
    from app.painter_ui_document import add_ui_artboard, create_ui_document
    from app.painter_ui_file_commands import export_artboards_pdf

    document = create_ui_document(390, 844)
    document, _row = add_ui_artboard(
        document,
        name="Desktop",
        width=1280,
        height=720,
    )
    output = tmp_path / "frames.pdf"
    report = export_artboards_pdf(document, output)

    assert report["ok"] is True
    assert report["page_count"] == 2
    assert output.read_bytes().startswith(b"%PDF")
    assert output.stat().st_size > 500


def test_version_history_dialog_lists_named_ui_versions() -> None:
    _app()
    from PySide6.QtCore import Qt

    from app.painter_ui_document import create_ui_document
    from app.painter_ui_file_commands import PainterUIVersionHistoryDialog
    from app.painter_ui_review import create_ui_review_checkpoint

    document = create_ui_document(390, 844)
    document, checkpoint = create_ui_review_checkpoint(
        document,
        name="Homepage ready",
    )
    dialog = PainterUIVersionHistoryDialog(document)

    assert dialog.list_widget.count() == 1
    assert "Homepage ready" in dialog.list_widget.item(0).text()
    assert (
        dialog.list_widget.item(0).data(Qt.ItemDataRole.UserRole)
        == checkpoint["id"]
    )
    dialog.deleteLater()


def test_save_local_copy_does_not_replace_active_document_path(
    tmp_path,
    monkeypatch,
) -> None:
    _app()
    from PySide6.QtWidgets import QFileDialog

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_file_commands import save_local_copy

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    active = tmp_path / "active.tspaint"
    copy_path = tmp_path / "portable-copy.tspaint"
    dialog._painter_document_path = str(active)
    dialog._painter_document_dirty = True
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(copy_path), "Tiger Studio Painter"),
    )

    report = save_local_copy(dialog)

    assert report is not None and report["copy_only"] is True
    assert copy_path.exists()
    assert dialog._painter_document_path == str(active)
    assert dialog._painter_document_dirty is True
    dialog.deleteLater()
