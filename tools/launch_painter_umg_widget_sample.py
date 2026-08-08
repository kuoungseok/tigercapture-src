"""Open the UMG Widget View with the shared production-shaped review sample."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_ui_templates import instantiate_ui_template
    from app.painter_ui_umg_widget_view import PainterUMGWidgetView

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    apply_ui_font(app)

    document, report = instantiate_ui_template("saas_dashboard")
    template = report["template"]
    button = next(
        row for row in document["objects"] if row["name"] == "Primary CTA"
    )
    document["selection"] = {"object_id": button["id"], "object_ids": [button["id"]]}

    view = PainterUMGWidgetView()
    view.setWindowTitle(f"UMG 위젯 — {template['name']}")
    view.set_document(document)
    view.resize(1240, 780)
    view.show()
    view.raise_()
    view.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
