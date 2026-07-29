from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document() -> dict:
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844)
    document, _row = add_ui_object(
        document,
        kind="text",
        name="Product Title",
        content={"text": "Product"},
    )
    return document


def test_find_replace_dialog_has_friendly_empty_state() -> None:
    _app()
    from app.painter_ui_find_replace_dialog import PainterUIFindReplaceDialog

    dialog = PainterUIFindReplaceDialog()
    assert dialog.apply_button.isEnabled() is False
    assert dialog.preview() is None
    assert dialog.results.count() == 0


def test_find_replace_dialog_previews_and_emits_selected_request() -> None:
    _app()
    from app.painter_ui_find_replace_dialog import PainterUIFindReplaceDialog

    dialog = PainterUIFindReplaceDialog()
    dialog.set_document(_document())
    dialog.find_edit.setText("Product")
    dialog.replace_edit.setText("Library")
    for category, check in dialog.category_checks.items():
        check.setChecked(category == "text")

    report = dialog.preview()
    assert report is not None
    assert report["match_count"] == 1
    assert dialog.results.count() == 1
    assert dialog.apply_button.isEnabled() is True

    emitted = []
    dialog.apply_requested.connect(emitted.append)
    dialog.apply_button.click()
    assert emitted[0]["find"] == "Product"
    assert emitted[0]["replacement"] == "Library"
    assert emitted[0]["categories"] == ["text"]
    assert emitted[0]["selected_match_ids"] == [
        report["matches"][0]["match_id"]
    ]


def test_find_replace_dialog_disables_blocked_reference_rows() -> None:
    _app()
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_find_replace_dialog import PainterUIFindReplaceDialog

    document = create_ui_document(390, 844)
    document, root_a = add_ui_object(document, kind="button", name="A")
    document, root_b = add_ui_object(document, kind="button", name="B")
    document, component_a = convert_ui_object_to_component(
        document, root_object_id=root_a["id"], name="Primary Button"
    )
    document, _component_b = convert_ui_object_to_component(
        document, root_object_id=root_b["id"], name="Secondary Button"
    )
    document, _instance = instantiate_ui_component(
        document, component_id=component_a["id"]
    )
    dialog = PainterUIFindReplaceDialog()
    dialog.set_document(document)
    dialog.find_edit.setText("Primary Button")
    dialog.replace_edit.setText("Secondary Button")
    for category, check in dialog.category_checks.items():
        check.setChecked(category == "component")

    report = dialog.preview()
    assert report is not None
    assert report["invalid_match_count"] == 1
    blocked = next(
        dialog.results.item(index)
        for index in range(dialog.results.count())
        if not (
            dialog.results.item(index).flags()
            & dialog.results.item(index).flags().ItemIsEnabled
        )
    )
    assert "Instance Swap" in blocked.toolTip()
