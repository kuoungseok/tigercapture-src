"""Capture Select Same menu evidence at desktop and compact sizes."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )

    application = QApplication.instance() or QApplication([])
    apply_ui_font(application)
    output = (
        ROOT / "debugCapture" / "painter_ui_designer" / "select_similar"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (1200, 760)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1000, 650, "#F5F7FA"
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        document = create_ui_document(1000, 650)
        for index, fill in enumerate(("#34506F", "#34506F", "#783B45")):
            document, row = add_ui_object(
                document,
                kind="button",
                name=f"Action {index + 1}",
                x=100 + index * 220,
                y=180,
                width=180,
                height=56,
                style={
                    "fill": fill,
                    "stroke": "#8294AA",
                    "stroke_width": 1,
                },
                content={"text": f"Action {index + 1}"},
            )
            if index == 0:
                selected_id = row["id"]
        document = select_ui_object(document, selected_id)
        dialog._painter_ui_document = document
        dialog._refresh_painter_ui_overlay()
        dialog.resize(*size)
        dialog.show()
        application.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._refresh_painter_ui_select_similar_menu()
        menu = dialog._painter_ui_select_similar_menu
        menu.ensurePolished()
        menu.adjustSize()
        menu_image = menu.grab().toImage()
        image = dialog.grab().toImage()
        x = max(12, image.width() - menu_image.width() - 28)
        y = max(80, (image.height() - menu_image.height()) // 2)
        painter = QPainter(image)
        painter.drawImage(x, y, menu_image)
        painter.end()
        path = output / f"select_similar_{label}.png"
        saved = image.save(str(path), "PNG")
        fill_action = dialog._painter_ui_select_similar_actions["fill"]
        results[label] = {
            "ok": bool(
                saved
                and fill_action.isEnabled()
                and "(2)" in fill_action.text()
            ),
            "screenshot": str(path),
            "fill_label": fill_action.text(),
        }
        dialog.close()
        dialog.deleteLater()
        application.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.select_similar.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
