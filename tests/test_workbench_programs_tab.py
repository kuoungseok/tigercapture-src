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
        "3D PBR Texture",
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
    pbr_button = next(
        button for button in panel._program_launcher_buttons
        if button.accessibleName() == "3D PBR Texture"
    )
    assert getattr(pbr_button, "_program_launcher_icon_name") == "pbr-texture"
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


def test_3d_pbr_texture_launcher_prompts_for_image_and_opens_lab(tmp_path, monkeypatch) -> None:
    app = _app()
    from PySide6.QtWidgets import QFileDialog

    import app.ar_pbr.texture_lab_entry as entry
    from app.workbench_panel import WorkbenchPanel

    image_path = tmp_path / "material-source.png"
    image_path.write_bytes(b"source")
    opened = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(image_path), "Images")),
    )
    monkeypatch.setattr(entry, "open_texture_lab_window", lambda owner, path: opened.append((owner, path)))

    panel = WorkbenchPanel()
    panel._open_pbr_texture_program()
    app.processEvents()

    assert len(opened) == 1
    assert opened[0][0] is panel.window()
    assert opened[0][1] == image_path
    panel.close()
