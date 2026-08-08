from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_studio_startup_splash_has_visible_status_text():
    from PySide6.QtWidgets import QApplication

    from app.studio_startup_splash import StudioStartupSplash

    app = QApplication.instance() or QApplication([])
    splash = StudioStartupSplash()
    try:
        splash.set_status("Loading editor modules...", "Preparing preview.")
        splash.show()
        app.processEvents()

        labels = [child.text() for child in splash.findChildren(type(splash._status))]
        assert "Tiger Studio" in labels
        assert "Loading editor modules..." in labels
        assert "Preparing preview." in labels
        assert splash.windowTitle() == "Tiger Studio"
    finally:
        splash.close()
        splash.deleteLater()
        app.processEvents()


def test_studio_startup_splash_error_state_stops_busy_progress():
    from PySide6.QtWidgets import QApplication

    from app.studio_startup_splash import StudioStartupSplash

    app = QApplication.instance() or QApplication([])
    splash = StudioStartupSplash()
    try:
        splash.set_error("ImportError: test")
        assert splash._status.text() == "Tiger Studio could not finish startup."
        assert splash._detail.text() == "ImportError: test"
        assert splash._progress.maximum() == 1
    finally:
        splash.close()
        splash.deleteLater()
        app.processEvents()
