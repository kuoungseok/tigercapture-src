from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.painter_ui_document import (
    add_ui_artboard,
    add_ui_interaction,
    add_ui_object,
    create_ui_document,
    select_ui_object,
    set_active_ui_artboard,
    update_ui_artboard,
)
from app.painter_ui_workspace import PainterUIDesignOverlay


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def _prototype_document():
    document = create_ui_document(390, 844)
    first_artboard = document["active_artboard_id"]
    document, second = add_ui_artboard(
        document,
        name="Details",
        width=390,
        height=844,
    )
    document, _row = update_ui_artboard(
        document,
        second["id"],
        {"x": 540.0, "y": 0.0},
    )
    document, source = add_ui_object(
        document,
        kind="button",
        name="Open details",
        artboard_id=first_artboard,
        x=80,
        y=120,
        width=180,
        height=56,
    )
    document = set_active_ui_artboard(document, first_artboard)
    return select_ui_object(document, source["id"]), source, second


def test_canvas_prototype_handle_drags_to_another_artboard() -> None:
    app = _app()
    document, source, second = _prototype_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(1100, 700)
    overlay.set_document(document)
    overlay.set_prototype_authoring_visible(True)
    overlay.show()
    app.processEvents()

    emitted: list[tuple[str, str, str]] = []
    overlay.prototype_connection_requested.connect(
        lambda source_id, artboard_id, object_id: emitted.append(
            (source_id, artboard_id, object_id)
        )
    )
    handle = overlay.prototype_connection_handle_rect()
    target_viewport, _scale = overlay._artboard_viewport(second)

    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=handle.center().toPoint(),
    )
    target = target_viewport.center().toPoint()
    QTest.mouseMove(overlay, target)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=target,
    )

    assert emitted == [(source["id"], second["id"], "")]


def test_canvas_paints_existing_selected_source_connection() -> None:
    app = _app()
    document, source, second = _prototype_document()
    document, _interaction = add_ui_interaction(
        document,
        source_object_id=source["id"],
        trigger="click",
        action="navigate",
        target_artboard_id=second["id"],
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(1100, 700)
    overlay.set_document(document)
    overlay.set_prototype_authoring_visible(True)
    overlay.show()
    app.processEvents()

    image = overlay.grab().toImage()
    handle = overlay.prototype_connection_handle_rect().center().toPoint()

    assert not image.isNull()
    color = image.pixelColor(handle)
    assert color.blue() > color.red()


def test_inspector_emits_context_mode_for_prototype_tab() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    inspector.set_document(_prototype_document()[0])
    emitted: list[str] = []
    inspector.context_mode_changed.connect(emitted.append)

    inspector._tabs.setCurrentWidget(inspector._context_pages["prototype"])
    app.processEvents()

    assert emitted[-1] == "prototype"
