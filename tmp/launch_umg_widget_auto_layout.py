"""Open the UMG Widget View with the real "Auto Layout" Figma frame."""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FRAME = "Components"


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_ui_figma import import_fig_file
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_ui_font(app)

    source = (
        Path(os.environ["USERPROFILE"])
        / "Downloads"
        / "Figma auto layout playground (Community).fig"
    )
    document, _ = import_fig_file(source)
    board = next(
        row for row in document["artboards"] if str(row.get("name")) == FRAME
    )
    document["active_artboard_id"] = str(board["id"])
    document["active_page_id"] = str(board.get("page_id") or "")

    view = PainterUMGWidgetView()
    view.setWindowTitle("UMG 위젯 — Figma Auto Layout playground")
    view.set_document(document)
    view.resize(1400, 820)
    view.show()
    view.raise_()
    view.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
