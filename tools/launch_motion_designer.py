from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ["QT_QPA_PLATFORM"] = "windows"


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.ui.window import MotionDesignerWindow
from app.window_placement import install_global_window_placement


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    install_global_window_placement(app)
    project_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = MotionDesignerWindow(
        None,
        project_path=project_path,
        standalone_document=True,
    )
    window.show()
    window.raise_()
    window.activateWindow()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
