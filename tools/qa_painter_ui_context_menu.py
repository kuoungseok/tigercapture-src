"""Capture the contextual Painter UI menu at desktop and compact sizes."""
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

    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPainter
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_i18n import painter_text
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )
    from app.painter_ui_property_clipboard import copy_ui_object_payload

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_context_menu_m1"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    results = {}

    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1280, 720, "#F5F7FA"
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        document = create_ui_document(1280, 720, name="Context menu")
        document, card = add_ui_object(
            document,
            kind="frame",
            name="Context card",
            x=430,
            y=220,
            width=360,
            height=230,
            style={
                "fill": "#203044",
                "stroke": "#7198C5",
                "stroke_width": 2,
                "radius": 22,
            },
        )
        document = select_ui_objects(
            document, [card["id"]], primary_object_id=card["id"]
        )
        dialog._painter_ui_document = document
        dialog._painter_ui_property_clipboard = copy_ui_object_payload(
            document, card["id"]
        )
        dialog._painter_ui_recent_context_actions = [
            "paste_in_place",
            "copy_object",
            "fit_selection",
        ]
        dialog._refresh_painter_ui_overlay()
        registry.execute(
            "paint.ui.inspector.presentation", {"mode": "auto_hide"}
        )
        registry.execute(
            "paint.ui.navigator.presentation", {"mode": "auto_hide"}
        )
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        app.processEvents()
        menu = dialog._show_canvas_context_menu(
            QPoint(size[0] // 2, size[1] // 2),
            execute=False,
        )
        menu.ensurePolished()
        menu.adjustSize()
        menu_image = menu.grab().toImage()
        image = dialog.grab().toImage()
        x = max(16, image.width() - menu_image.width() - 36)
        y = max(96, (image.height() - menu_image.height()) // 2)
        painter = QPainter(image)
        painter.drawImage(x, y, menu_image)
        painter.end()
        path = output_dir / f"context_menu_{label}.png"
        saved = image.save(str(path), "PNG")
        visible = [
            action.text()
            for action in menu.actions()
            if action.isVisible() and not action.isSeparator()
        ]
        results[label] = {
            "ok": bool(
                saved
                and visible.count(painter_text("Paste in place")) == 2
                and visible.count(painter_text("Copy object")) == 2
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "visible_commands": visible,
        }
        menu.deleteLater()
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.context_menu.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "context_menu_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
