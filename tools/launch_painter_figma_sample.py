"""Open Painter UI Designer with a local Figma REST JSON snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        parser.error(f"Figma REST JSON not found: {source}")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1600, 980)
    registry = ActionRegistry(owner=dialog)
    workspace_result = registry.execute(
        "paint.ui.workspace.set",
        {"mode": "ui_design"},
    )
    if not workspace_result.ok:
        raise RuntimeError(workspace_result.message)
    import_result = registry.execute(
        "paint.ui.figma.import",
        {
            "source": str(source),
            "json_snapshot": True,
            "mode": "replace",
        },
    )
    if not import_result.ok:
        raise RuntimeError(import_result.message)

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QTimer.singleShot(
        100,
        lambda: registry.execute("paint.ui.view.fit", {"mode": "artboard"}),
    )
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
