from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_quick_properties_hosts_and_releases_canonical_widget() -> None:
    app = _app()
    from PySide6.QtWidgets import QLabel, QWidget

    from app.painter_ui_quick_properties import (
        PainterUIQuickPropertiesPopover,
    )

    host = QWidget()
    host.resize(900, 700)
    popover = PainterUIQuickPropertiesPopover(host)
    content = QLabel("Properties")

    popover.attach(content)
    host.show()
    app.processEvents()

    assert popover.contains(content)
    assert content.parent() is popover.scroll_area.viewport()
    assert popover.isVisible()
    assert popover.geometry().right() <= host.rect().right()
    assert popover.width() == 320
    assert popover.geometry().bottom() <= host.rect().bottom() - 120

    released = popover.take()
    assert released is content
    assert released.parent() is None
    assert not popover.isVisible()

    content.deleteLater()
    host.deleteLater()
    app.processEvents()


def test_collapsed_inspector_opens_contextual_properties_for_new_selection() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object, create_ui_document

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            390,
            844,
            "#F5F7FA",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    document = create_ui_document(390, 844, name="Phone")
    document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = []
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    dialog.show()
    app.processEvents()

    dialog._paint_ui_inspector.set_collapsed(True)
    assert dialog._paint_ui_inspector.is_collapsed()
    assert dialog._paint_inspector_frame.maximumWidth() == 0

    document, row = add_ui_object(
        document,
        kind="text",
        name="Headline",
        x=24,
        y=48,
        width=280,
        height=72,
        content={"text": "Tiger Studio"},
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    app.processEvents()

    popover = dialog._painter_ui_quick_properties
    inspector = dialog._paint_ui_inspector
    assert popover.isVisible()
    assert popover.contains(inspector)
    assert inspector.is_temporary_expanded()
    assert inspector.parent() is popover.scroll_area.viewport()
    toolbar = dialog._ui_design_tool_host
    assert popover.geometry().bottom() < toolbar.geometry().top()

    inspector.collapse_button.click()
    app.processEvents()
    assert not popover.isVisible()
    assert inspector.parent() is dialog._paint_inspector_controls
    assert inspector.is_collapsed()
    assert not inspector.is_temporary_expanded()

    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    assert not popover.isVisible()

    document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = []
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    document["selection"]["object_id"] = row["id"]
    document["selection"]["object_ids"] = [row["id"]]
    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    assert popover.isVisible()

    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert not popover.isVisible()
    assert inspector.parent() is dialog._paint_inspector_controls

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_hidden_inspector_defers_large_document_sync_until_needed() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object, create_ui_document

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1200, 760)
    dialog.show()
    app.processEvents()
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._paint_ui_inspector.set_auto_hide(True)
    document = create_ui_document(800, 600)
    dialog._painter_ui_document = document
    inspector = dialog._paint_ui_inspector
    original = inspector.set_document
    calls: list[str] = []

    def record(value) -> None:
        calls.append(str((value or {}).get("active_artboard_id") or ""))
        original(value)

    inspector.set_document = record
    dialog._refresh_painter_ui_overlay()
    assert calls == []

    dialog._toggle_painter_ui_inspector()
    assert calls == ["artboard-1"]
    dialog._hide_painter_ui_quick_properties()
    calls.clear()

    document, row = add_ui_object(document, kind="text", name="Title")
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    assert calls == ["artboard-1"]
    assert dialog._painter_ui_quick_properties.isVisible()
    assert inspector._document["selection"]["object_id"] == row["id"]

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
