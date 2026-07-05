from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.i18n import initialize
from app.spine_editor.editor_window import SpineEditorWindow
from app.style import APP_QSS


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("TigerCapture")
    app.setStyleSheet(APP_QSS)
    initialize()

    window = SpineEditorWindow()
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
