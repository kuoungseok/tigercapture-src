from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_recovery_dialog_has_empty_state_and_emits_selected_snapshot() -> None:
    _app()
    from app.painter_recovery_dialog import PainterRecoveryDialog

    dialog = PainterRecoveryDialog()
    assert dialog.restore_button.isEnabled() is False
    row = {
        "session_id": "session-a",
        "source_path": "C:/work/design.tspaint",
        "recovery_path": "C:/recovery/a.tspaint",
        "saved_at": 1_700_000_000,
        "bytes": 2048,
    }
    dialog.set_snapshots([row])
    emitted = []
    dialog.restore_requested.connect(emitted.append)
    dialog.restore_button.click()
    assert emitted[0]["session_id"] == "session-a"
    assert "design.tspaint" in dialog.list_widget.item(0).text()
