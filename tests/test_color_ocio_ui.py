from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.color_ocio import preferred_aces_ocio_uri


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_color_page_auto_selects_builtin_aces_config() -> None:
    from app.color_page_window import ColorPageWindow

    _app()
    editor = SimpleNamespace(
        _project_settings={},
        _player=None,
        _active_track=lambda: None,
    )
    window = ColorPageWindow(editor=editor)
    try:
        index = window._cm_working_space.findData("acescg")
        window._cm_working_space.setCurrentIndex(index)
        settings = editor._project_settings["color_management"]
        assert settings["ocio_config_path"] == preferred_aces_ocio_uri()
    finally:
        window.close()


def test_motion_delivery_lists_builtin_aces_and_exposes_tone_map_luts(tmp_path) -> None:
    from app.motion_designer.schema import MotionComposition
    from app.motion_designer.ui.export_panel import MotionOutputPanel

    _app()
    panel = MotionOutputPanel()
    composition = MotionComposition()
    color = dict(composition.metadata["color_management"])
    color["tone_map"] = "reinhard"
    project = dict(color["project"])
    lut_path = tmp_path / "look.cube"
    lut_path.write_text(
        "LUT_3D_SIZE 2\n"
        "0 0 0\n1 0 0\n0 1 0\n1 1 0\n"
        "0 0 1\n1 0 1\n0 1 1\n1 1 1\n",
        encoding="ascii",
    )
    project["creative_lut"] = {
        "path": str(lut_path), "strength": 0.4, "enabled": True,
    }
    color["project"] = project
    composition.metadata["color_management"] = color
    panel.set_composition(composition)
    try:
        labels = [action.text() for action in panel.ocio_browse.menu().actions()]
        assert "Studio ACES 1.3" in labels
        assert "CG ACES 1.3" in labels
        assert "Studio ACES 2.0" not in labels
        assert panel.tone_map.currentData() == "reinhard"
        path_edit, strength, _browse = panel._lut_controls["creative_lut"]
        assert path_edit.text() == str(lut_path)
        assert strength.value() == 40.0
        emitted = []
        panel.color_settings_changed.connect(emitted.append)
        panel.tone_map.setCurrentIndex(panel.tone_map.findData("aces-fitted"))
        assert emitted[-1]["tone_map"] == "aces-fitted"
        assert emitted[-1]["project"]["creative_lut"]["strength"] == 0.4
        index = panel.working_space.findData("acescg")
        panel.working_space.setCurrentIndex(index)
        assert panel.ocio_path.text() == preferred_aces_ocio_uri()
    finally:
        panel.close()
