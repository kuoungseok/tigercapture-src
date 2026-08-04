"""Launch Motion Designer with the interactive portrait palette visible."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.motion_designer.schema import MotionComposition
    from app.motion_designer.ui.window import MotionDesignerWindow

    app = QApplication.instance() or QApplication(sys.argv)
    apply_ui_font(app)
    window = MotionDesignerWindow(
        MotionComposition(
            name="Portrait Palette",
            width=1280,
            height=720,
            duration_ms=3000,
        )
    )
    window.resize(1500, 920)
    window._add_layer("rectangle")
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
