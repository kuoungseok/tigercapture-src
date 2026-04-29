"""macOS entry point for TigerCapture.

Prepends the `mac/` directory to sys.path so that `import app` resolves
to `mac/app/` — which then falls through to the shared `app/` at the
repo root via an extended `__path__` (see `mac/app/__init__.py`).

Keep this file tiny: all real UI wiring lives in the shared modules.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_paths() -> None:
    here = Path(__file__).resolve().parent
    mac_dir = str(here)
    if mac_dir not in sys.path:
        sys.path.insert(0, mac_dir)


def main() -> int:
    _bootstrap_paths()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("TigerCapture")
    app.setOrganizationName("TigerCapture")

    # Shared dark QSS.
    from app.style import APP_QSS

    app.setStyleSheet(APP_QSS)

    from app.i18n import initialize as init_i18n

    init_i18n()

    from app.controller import AppController
    from app.main_window import MainWindow

    window = MainWindow()
    controller = AppController(window)
    _ = controller
    window.show()

    return app.exec()


if __name__ == "__main__":
    # When launched from a PyInstaller .app bundle, stdout/stderr go to
    # /dev/null by default. Redirect to Console.app via os.fdopen(2).
    if os.environ.get("TIGERCAPTURE_LOG_TO_STDERR"):
        sys.stderr = os.fdopen(2, "w", buffering=1)
    sys.exit(main())
