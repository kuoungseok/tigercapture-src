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
    panel.resize(520, 430)
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
    tile_sizes = {button.width() for button in buttons}
    assert tile_sizes == {53}

    panel.resize(340, 430)
    app.processEvents()
    panel._update_program_launcher_metrics()
    small_tile = buttons[0].width()
    assert 48 <= small_tile <= 53

    panel.resize(860, 430)
    app.processEvents()
    panel._update_program_launcher_metrics()
    large_tile = buttons[0].width()
    assert 53 < large_tile <= 56

    panel.close()
