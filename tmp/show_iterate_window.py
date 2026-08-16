"""Open a real (non-offscreen) Painter UI window focused on the fixed 'iterate' shape."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TARGET_ID = "figma-node-2411-13174"  # 'iterate' under Auto Layout UI3 > Auto Layout


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    fig_path = Path.home() / "Downloads" / "Figma auto layout playground (Community).fig"

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    import_result = registry.execute(
        "paint.ui.figma.import",
        {
            "source": str(fig_path),
            "json_snapshot": False,
            "fig_archive": True,
            "image_dir": "",
            "mode": "replace",
        },
    )
    if not import_result.ok:
        raise RuntimeError(import_result.message)

    document = dialog._painter_ui_document
    target_row = next(
        (row for row in document["objects"] if str(row.get("id")) == TARGET_ID),
        None,
    )
    artboard_id = str((target_row or {}).get("artboard_id") or "")
    artboard = next(
        (a for a in document["artboards"] if str(a.get("id")) == artboard_id),
        None,
    )
    page_id = str((artboard or {}).get("page_id") or "")

    def activate_page_select_and_focus() -> None:
        if page_id:
            registry.execute("paint.ui.page.activate", {"page_id": page_id})
        registry.execute(
            "paint.ui.selection.set",
            {"object_ids": [TARGET_ID], "primary_object_id": TARGET_ID},
        )
        registry.execute("paint.ui.view.focus", {"object_id": TARGET_ID})

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    QTimer.singleShot(150, activate_page_select_and_focus)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
