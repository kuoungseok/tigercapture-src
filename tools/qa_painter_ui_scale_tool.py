"""Capture the dedicated Painter UI Scale tool at desktop and compact sizes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "debugCapture" / "painter_ui_scale_tool_m1"),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QPoint, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    results: dict[str, dict] = {}

    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1280,
                720,
                "#F5F7FA",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        document = create_ui_document(1280, 720, name="Desktop")
        document, card = add_ui_object(
            document,
            kind="frame",
            name="Scale card",
            x=360,
            y=220,
            width=360,
            height=220,
            style={
                "fill": "#233246",
                "stroke": "#7298C5",
                "stroke_width": 3,
                "radius": 24,
                "effects": [
                    {
                        "type": "drop_shadow",
                        "x": 0,
                        "y": 14,
                        "blur": 32,
                        "spread": 0,
                        "color": "#08111F66",
                    }
                ],
            },
        )
        document, title = add_ui_object(
            document,
            kind="text",
            name="Scale title",
            x=410,
            y=285,
            width=260,
            height=58,
            style={"text_color": "#F0F5FC", "font_size": 32},
            content={"text": "Scale"},
        )
        document = select_ui_objects(
            document,
            [card["id"], title["id"]],
            primary_object_id=card["id"],
        )
        dialog._painter_ui_document = document
        dialog._refresh_painter_ui_overlay()
        registry.execute(
            "paint.ui.inspector.presentation",
            {"mode": "auto_hide"},
        )
        registry.execute(
            "paint.ui.navigator.presentation",
            {"mode": "auto_hide"},
        )
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._set_painter_ui_tool("scale")
        dialog._update_canvas_geometry()
        app.processEvents()

        overlay = dialog._painter_ui_overlay
        bounds = overlay._selection_bounds(overlay._multi_transform_rows())
        handle = overlay._handle_rects(bounds)["se"].center().toPoint()
        target = QPoint(handle.x() + 90, handle.y() + 55)
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
        QTest.mouseMove(overlay, target)
        QTest.mouseRelease(
            overlay,
            Qt.MouseButton.LeftButton,
            pos=target,
        )
        app.processEvents()
        dialog._hide_painter_ui_quick_properties()
        app.processEvents()
        path = output_dir / f"scale_tool_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        rows = {
            row["id"]: row for row in dialog._painter_ui_document["objects"]
        }
        factor = float(rows[card["id"]]["width"]) / float(card["width"])
        results[label] = {
            "ok": bool(
                saved
                and factor > 1.0
                and float(rows[title["id"]]["style"]["font_size"]) > 32.0
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "scale_factor": factor,
            "font_size": rows[title["id"]]["style"]["font_size"],
            "tool": overlay.tool(),
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.scale_tool.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "scale_tool_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": report["ok"], "report": str(report_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.show:
        return app.exec()
    QTimer.singleShot(0, app.quit)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
