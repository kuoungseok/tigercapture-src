from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_action_parity_dialog_has_empty_and_populated_states() -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.painter_ui_action_parity import inspect_painter_ui_action_parity
    from app.painter_ui_action_parity_dialog import (
        PainterUIActionParityDialog,
    )

    dialog = PainterUIActionParityDialog()
    assert dialog.tree.topLevelItemCount() == 0
    report = inspect_painter_ui_action_parity(
        ActionRegistry(owner=None).list_actions()
    )
    dialog.set_report(report)
    assert dialog.tree.topLevelItemCount() == report["family_count"]
    assert str(report["action_count"]) in dialog.status_label.text()
