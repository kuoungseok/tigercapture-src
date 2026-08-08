from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    return app


def test_locale_audit_covers_supported_languages_without_hard_failures() -> None:
    _app()
    from app.painter_ui_locale_audit import inspect_painter_ui_locales

    report = inspect_painter_ui_locales()
    assert report["language_count"] == 6
    assert report["entry_count"] >= 10
    assert report["status"] == "covered"
    assert report["issues"] == []


def test_locale_audit_reports_non_elidable_overflow() -> None:
    _app()
    from app.painter_ui_locale_audit import inspect_painter_ui_locales

    report = inspect_painter_ui_locales(
        [{"id": "tiny", "text": "Keyboard shortcuts", "width": 2}],
        languages=["en"],
    )
    assert report["status"] == "blocked"
    assert report["issues"][0]["reason"] == "overflow"


def test_locale_audit_action_and_quick_action_are_read_only() -> None:
    _app()
    from app.actions.registry import ActionRegistry
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_quick_actions import search_painter_ui_quick_actions

    result = ActionRegistry(owner=object()).execute(
        "paint.ui.locale_audit.inspect", {}
    ).to_dict()
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["result"]["status"] == "covered"
    quick = search_painter_ui_quick_actions(
        create_ui_document(390, 844), "locale font"
    )
    row = next(
        item
        for item in quick["results"]
        if item["id"] == "document.locale_audit"
    )
    assert row["operation"] == {"type": "locale_audit"}
