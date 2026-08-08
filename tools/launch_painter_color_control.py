"""Launch Painter Painting mode with the Color Control board visible."""
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
    from PySide6.QtGui import QColor
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
    dialog._paint_color_tabs.setCurrentIndex(1)
    dialog._apply_pen_color(QColor("#FF4B12"), remember=False)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()

    def reveal_color_control() -> None:
        scroll = getattr(dialog, "_paint_inspector_controls_scroll", None)
        panel = getattr(dialog, "_paint_color_panel", None)
        if scroll is not None and panel is not None:
            scroll.ensureWidgetVisible(panel, 0, 0)
            scroll.verticalScrollBar().setValue(max(0, int(panel.y())))
        dialog._paint_color_tabs.setCurrentIndex(1)
        dialog.raise_()
        dialog.activateWindow()

    QTimer.singleShot(100, reveal_color_control)
    QTimer.singleShot(450, reveal_color_control)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
