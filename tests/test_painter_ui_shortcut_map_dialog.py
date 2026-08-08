from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_shortcut_dialog_is_searchable_and_has_friendly_empty_state() -> None:
    _app()
    from app.painter_ui_shortcut_map_dialog import (
        PainterUIShortcutMapDialog,
    )

    dialog = PainterUIShortcutMapDialog()
    assert dialog.tree.topLevelItemCount() > 10
    dialog.search_edit.setText("not-a-real-command")
    assert dialog.tree.topLevelItemCount() == 0
    from app.painter_i18n import painter_text

    assert dialog.status_label.text() == painter_text(
        "No shortcuts match this search."
    )


def test_shortcut_dialog_marks_inactive_mode_rows() -> None:
    _app()
    from app.painter_ui_shortcut_map_dialog import (
        PainterUIShortcutMapDialog,
    )

    dialog = PainterUIShortcutMapDialog()
    dialog.search_edit.setText("Deselect")
    assert dialog.tree.topLevelItemCount() == 1
    item = dialog.tree.topLevelItem(0)
    from app.painter_i18n import painter_text

    assert item.text(2) == painter_text("Paint")
    assert item.foreground(0).color().name() == "#747b89"
