from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> tuple[dict, list[str]]:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    ids = []
    for name in ("Card", "Card"):
        document, row = add_ui_object(document, kind="group", name=name)
        ids.append(row["id"])
    return document, ids


def test_batch_rename_dialog_has_selection_empty_state() -> None:
    _app()
    from app.painter_ui_batch_rename_dialog import PainterUIBatchRenameDialog

    dialog = PainterUIBatchRenameDialog()
    dialog.set_document(_document()[0], [])
    assert dialog.preview_button.isEnabled() is False
    assert dialog.apply_button.isEnabled() is False
    assert dialog.preview() is None


def test_batch_rename_dialog_previews_and_emits_selected_rows() -> None:
    _app()
    from app.painter_ui_batch_rename_dialog import PainterUIBatchRenameDialog

    document, ids = _document()
    dialog = PainterUIBatchRenameDialog()
    dialog.set_document(document, ids)
    dialog.prefix_edit.setText("UI_")
    dialog.numbering_check.setChecked(True)
    report = dialog.preview()
    assert report is not None
    assert report["match_count"] == 2
    assert dialog.results.count() == 2
    emitted = []
    dialog.apply_requested.connect(emitted.append)
    dialog.apply_button.click()
    assert emitted[0]["object_ids"] == ids
    assert emitted[0]["prefix"] == "UI_"
    assert len(emitted[0]["selected_match_ids"]) == 2
