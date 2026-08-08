from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _text_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844, name="Phone")
    return add_ui_object(
        document,
        kind="text",
        name="Headline",
        x=36,
        y=80,
        width=260,
        height=72,
        style={
            "font_size": 24,
            "font_weight": 600,
            "text_color": "#F5F7FA",
        },
        content={"text": "Original title"},
    )


def test_overlay_double_click_opens_text_editor_and_commits() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = _text_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    started: list[str] = []
    changed: list[tuple[str, str]] = []
    overlay.text_edit_started.connect(started.append)
    overlay.text_change_requested.connect(
        lambda object_id, text: changed.append((object_id, text))
    )

    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=overlay._object_rect(row).center().toPoint(),
    )
    app.processEvents()
    assert overlay.is_text_editing()
    assert started == [row["id"]]
    assert overlay._text_editor.isVisible()

    overlay._text_editor.setPlainText("Edited on canvas")
    overlay._text_editor.request_commit()
    app.processEvents()
    assert not overlay.is_text_editing()
    assert changed == [(row["id"], "Edited on canvas")]

    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_inline_text_escape_cancels_without_document_mutation() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = _text_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.show()
    changed: list[tuple[str, str]] = []
    overlay.text_change_requested.connect(
        lambda object_id, text: changed.append((object_id, text))
    )
    assert overlay.begin_text_edit(row["id"])
    overlay._text_editor.setPlainText("Discard me")
    QTest.keyClick(overlay._text_editor, Qt.Key.Key_Escape)
    app.processEvents()

    assert not overlay.is_text_editing()
    assert changed == []
    assert document["objects"][0]["content"]["text"] == "Original title"
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_dialog_inline_text_commit_uses_undoable_document_mutation() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, row = _text_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    assert dialog._painter_ui_overlay.begin_text_edit(row["id"])
    dialog._painter_ui_overlay._text_editor.setPlainText("Undoable title")
    dialog._painter_ui_overlay._text_editor.request_commit()
    app.processEvents()

    updated = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert updated["content"]["text"] == "Undoable title"
    assert dialog._undo_labels[-1] == "Edit UI text"
    dialog._undo()
    restored = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    assert restored["content"]["text"] == "Original title"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_text_content_action_matches_inline_editor_mutation() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, row = _text_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.text.content.set",
        {"object_id": row["id"], "text": "Set by Action"},
    )

    assert result.ok
    assert result.result["text_object"] == {
        "object_id": row["id"],
        "text": "Set by Action",
    }
    assert next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )["content"]["text"] == "Set by Action"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_text_tool_click_creates_auto_width_layer_and_enters_edit_mode() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._set_painter_ui_tool("text")
    overlay = dialog._painter_ui_overlay
    overlay.resize(900, 700)
    overlay.show()
    app.processEvents()
    viewport, _scale = overlay._artboard_viewport()
    point = QPoint(round(viewport.left() + 180), round(viewport.top() + 120))

    QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=point)
    app.processEvents()

    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["kind"] == "text"
    )
    assert row["name"] == "Text 1"
    assert row["content"]["text"] == ""
    assert row["content"]["text_resize"] == "auto_width"
    assert overlay.is_text_editing()
    assert overlay._text_edit_object_id == row["id"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_text_tool_drag_creates_fixed_size_layer() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._set_painter_ui_tool("text")
    overlay = dialog._painter_ui_overlay
    overlay.resize(900, 700)
    overlay.show()
    app.processEvents()
    viewport, _scale = overlay._artboard_viewport()
    start = QPoint(round(viewport.left() + 100), round(viewport.top() + 90))
    end = QPoint(start.x() + 240, start.y() + 100)

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end, delay=10)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()

    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["kind"] == "text"
    )
    assert row["content"]["text_resize"] == "fixed_size"
    assert row["width"] > 100
    assert row["height"] > 40
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_enter_on_selected_text_starts_inline_editing() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import select_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = _text_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(select_ui_object(document, row["id"]))
    overlay.show()
    app.processEvents()

    QTest.keyClick(overlay, Qt.Key.Key_Return)
    app.processEvents()
    assert overlay.is_text_editing()
    assert overlay._text_edit_object_id == row["id"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()
