from __future__ import annotations

from tests.test_painter_ui_locale_audit import _app


def test_locale_audit_dialog_has_empty_and_populated_states() -> None:
    _app()
    from app.painter_ui_locale_audit import inspect_painter_ui_locales
    from app.painter_ui_locale_audit_dialog import (
        PainterUILocaleAuditDialog,
    )

    dialog = PainterUILocaleAuditDialog()
    assert dialog.tree.topLevelItemCount() == 0
    report = inspect_painter_ui_locales()
    dialog.set_report(report)
    assert dialog.tree.topLevelItemCount() == 6
    assert report["font_family"] in dialog.status_label.text()
