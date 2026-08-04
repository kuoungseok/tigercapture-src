"""Launch Painter Painting mode with the card-style Presets board visible."""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication(sys.argv)
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1280, 900, "#F5F2EC"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1500, 960)
    dialog.show()

    def reveal_presets() -> None:
        dialog._paint_color_tabs.setCurrentIndex(0)
        scroll = getattr(dialog, "_paint_inspector_controls_scroll", None)
        panel = getattr(dialog, "_paint_color_panel", None)
        if scroll is not None and panel is not None:
            scroll.ensureWidgetVisible(panel, 0, 0)
        dialog.raise_()
        dialog.activateWindow()

    QTimer.singleShot(100, reveal_presets)
    QTimer.singleShot(450, reveal_presets)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
