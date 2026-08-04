"""Open a production-shaped Painter template and its UMG projection together."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--template",
        default="saas_dashboard",
        help="Built-in Painter UI template id.",
    )
    parser.add_argument(
        "--painter-only",
        action="store_true",
        help="Do not open the matching UMG projection window.",
    )
    args = parser.parse_args()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_ui_font(app)

    document, report = instantiate_ui_template(args.template)
    template = report["template"]
    # Start with a meaningful layer selected so the inspector demonstrates the
    # real selection-driven surface instead of an empty page shell.
    selected = next(
        (
            row
            for row in document.get("objects", [])
            if row.get("name") == "Page Heading"
        ),
        document.get("objects", [None])[0],
    )
    if selected:
        object_id = str(selected["id"])
        document["selection"] = {
            "object_id": object_id,
            "object_ids": [object_id],
        }

    painter = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    painter.setWindowTitle(f"페인터 — {template['name']}")
    painter.resize(1450, 900)
    registry = ActionRegistry(owner=painter)
    workspace = registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    if not workspace.ok:
        raise RuntimeError(workspace.message)
    painter._painter_ui_document = document
    painter._set_painter_ui_empty_page_mode(False)
    painter._refresh_painter_ui_overlay()
    painter.show()
    painter.raise_()
    painter.activateWindow()

    umg = None
    if not args.painter_only:
        umg = PainterUMGWidgetView()
        umg.setWindowTitle(f"UMG 위젯 — {template['name']}")
        umg.set_document(document)
        umg.resize(1120, 760)
        umg.show()

    def close_review_session(*_args) -> None:
        if umg is not None:
            umg.close()
        app.quit()

    # Painter is the primary review window. Closing it must also close the
    # companion preview so the launcher cannot survive as a hidden process.
    painter.finished.connect(close_review_session)

    QTimer.singleShot(
        120,
        lambda: registry.execute("paint.ui.view.fit", {"mode": "all"}),
    )
    # Keep both top-level widgets alive for the full Qt event loop.
    app._painter_review_windows = (painter, umg)  # type: ignore[attr-defined]
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
