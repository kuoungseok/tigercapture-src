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
    ordered_labels = [button.accessibleName() for button in panel._program_launcher_buttons]

    assert {
        "Composer",
        "Voice Lab",
        "VTuber Studio",
        "Painter",
        "PPT Maker",
        "Motion Designer",
        "Character Hub",
        "Engine Link",
    } <= labels
    assert ordered_labels[:3] == ["Composer", "Voice Lab", "Motion Designer"]
    motion_button = next(
        button for button in panel._program_launcher_buttons
        if button.accessibleName() == "Motion Designer"
    )
    assert getattr(motion_button, "_program_launcher_icon_name") == "motion-designer"
    assert all(not button.icon().isNull() for button in buttons)
    tile_sizes = {(button.width(), button.height()) for button in buttons}
    assert tile_sizes == {(72, 86)}

    panel.resize(340, 430)
    app.processEvents()
    panel._update_program_launcher_metrics()
    small_tile = (buttons[0].width(), buttons[0].height())
    assert 66 <= small_tile[0] <= 72
    assert small_tile[1] > small_tile[0]

    panel.resize(860, 430)
    app.processEvents()
    panel._update_program_launcher_metrics()
    large_tile = (buttons[0].width(), buttons[0].height())
    assert 72 < large_tile[0] <= 84
    assert large_tile[1] > large_tile[0]

    panel.close()
