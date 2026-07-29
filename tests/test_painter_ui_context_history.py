from __future__ import annotations

import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_context_history_is_unique_recent_and_available_only() -> None:
    from app.painter_ui_context_history import (
        recent_available_actions,
        record_context_action,
    )

    history = []
    for action_id in (
        "copy",
        "fit",
        "copy",
        "replace",
        "scale",
    ):
        history = record_context_action(history, action_id, limit=4)

    assert history == ["scale", "replace", "copy", "fit"]
    assert recent_available_actions(
        history,
        {"copy", "fit", "scale"},
        limit=2,
    ) == ["scale", "copy"]


def test_context_menu_hides_unavailable_and_replays_canonical_action() -> None:
    _app()
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 240, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    menu = QMenu(dialog)
    copy_action = menu.addAction("Copy object")
    copy_action.setEnabled(True)
    replace_action = menu.addAction("Replace")
    replace_action.setEnabled(False)
    triggered = []
    copy_action.triggered.connect(lambda: triggered.append("copy"))
    dialog._painter_ui_recent_context_actions = ["copy_object"]

    dialog._prepare_painter_ui_context_menu(
        menu,
        {
            "copy_object": copy_action,
            "replace": replace_action,
        },
    )

    visible = [
        action
        for action in menu.actions()
        if (
            action.isVisible()
            and action.isEnabled()
            and not action.isSeparator()
        )
    ]
    assert [action.text() for action in visible] == [
        "Copy object",
        "Copy object",
    ]
    assert replace_action.isVisible() is False
    assert isinstance(visible[0], QAction)
    visible[0].trigger()
    assert triggered == ["copy"]
    assert dialog._painter_ui_recent_context_actions[0] == "copy_object"
    dialog.close()
    dialog.deleteLater()


def test_ui_canvas_context_menu_omits_selection_only_commands(
) -> None:
    _app()
    from PySide6.QtCore import QPoint
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_i18n import painter_text
    from app.painter_ui_document import create_ui_document

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = create_ui_document(640, 480)
    dialog._set_canvas_workspace_mode("ui_design")
    menu = dialog._show_canvas_context_menu(QPoint(10, 10), execute=False)
    texts = [
        action.text()
        for action in menu.actions()
        if action.isVisible() and not action.isSeparator()
    ]

    assert painter_text("Place image...") in texts
    assert painter_text("Copy object") not in texts
    assert painter_text("Fit selection") not in texts
    dialog.close()
    dialog.deleteLater()
