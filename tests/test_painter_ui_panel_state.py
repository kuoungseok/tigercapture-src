from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_panel_state_round_trips_and_clamps(tmp_path) -> None:
    _app()
    from PySide6.QtCore import QSettings

    from app.painter_ui_panel_state import (
        load_painter_ui_panel_state,
        save_painter_ui_panel_state,
    )

    settings = QSettings(
        str(tmp_path / "painter-ui-panels.ini"),
        QSettings.Format.IniFormat,
    )
    saved = save_painter_ui_panel_state(
        {
            "navigator_width": 999,
            "navigator_collapsed": True,
            "navigator_user_override": True,
            "inspector_width": 120,
            "inspector_collapsed": True,
            "inspector_auto_hide": False,
        },
        settings,
    )
    assert saved == {
        "navigator_width": 320,
        "navigator_collapsed": True,
        "navigator_user_override": True,
        "inspector_width": 240,
        "inspector_collapsed": True,
        "inspector_auto_hide": False,
    }
    assert load_painter_ui_panel_state(settings) == saved


def test_panel_state_uses_compact_defaults(tmp_path) -> None:
    _app()
    from PySide6.QtCore import QSettings

    from app.painter_ui_panel_state import (
        DEFAULT_PANEL_STATE,
        load_painter_ui_panel_state,
    )

    settings = QSettings(
        str(tmp_path / "empty.ini"),
        QSettings.Format.IniFormat,
    )
    assert load_painter_ui_panel_state(settings) == DEFAULT_PANEL_STATE
