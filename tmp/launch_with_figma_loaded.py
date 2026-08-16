from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.drawing import PaintDialog, create_blank_paint_pixmap

FIG_PATH = Path.home() / "Downloads" / "Figma auto layout playground (Community).fig"


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    try:
        from app.style import APP_QSS
        app.setStyleSheet(APP_QSS)
    except Exception:
        pass

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")

    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.figma.import",
        {"source": str(FIG_PATH), "fig_archive": True},
    ).to_dict()
    print("figma import warnings:", len(result.get("figma_import", {}).get("warnings", [])))

    dialog.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
