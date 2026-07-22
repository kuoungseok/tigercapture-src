from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_workbench_programs_tab_exposes_icon_launchers() -> None:
    app = _app()
    from PySide6.QtWidgets import QToolButton

    from app.i18n import set_language
    from app.workbench_panel import WorkbenchPanel

    set_language("ko")
    panel = WorkbenchPanel()
    panel.show()
    app.processEvents()

    assert panel._inspector_tab_buttons["programs"].text() == "프로그램"

    panel._set_inspector_tab("programs")
    app.processEvents()

    buttons = panel.findChildren(QToolButton, "ProgramLauncherButton")
    labels = {button.accessibleName() for button in buttons}

    assert {
        "Composer",
        "Voice Lab",
        "VTuber Studio",
        "PPT Maker",
        "Motion Designer",
        "Character Hub",
        "Engine Link",
    } <= labels
    assert all(not button.icon().isNull() for button in buttons)

    panel.close()
