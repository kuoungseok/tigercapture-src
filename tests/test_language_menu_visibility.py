from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_language_button_stays_visible_in_compact_command_bar() -> None:
    app = _app()
    from app.i18n import SUPPORTED_LANGUAGES
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    editor.resize(1200, 760)
    editor.show()
    for _ in range(4):
        app.processEvents()

    assert editor.language_btn.isVisible() is True
    assert editor.language_btn.toolTip()

    editor._build_language_menu()
    menu = editor.language_btn.menu()
    assert menu is not None
    labels = [action.text() for action in menu.actions() if not action.isSeparator()]
    for label in SUPPORTED_LANGUAGES.values():
        assert str(label) in labels
    editor.close()


def test_language_button_survives_tiny_responsive_refresh() -> None:
    app = _app()
    from app.video_editor_window import VideoEditorWindow

    editor = VideoEditorWindow()
    editor.resize(900, 700)
    editor.show()
    for _ in range(4):
        app.processEvents()

    editor._command_bar_scroll.setFixedWidth(700)
    editor._refresh_command_bar_responsive()
    app.processEvents()

    assert editor.language_btn.isVisible() is True
    assert editor.language_btn.width() > 0
    editor.close()
