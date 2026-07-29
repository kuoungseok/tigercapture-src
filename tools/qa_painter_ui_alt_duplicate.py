"""Capture Figma-style Alt-drag duplication at desktop and compact sizes."""
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
        default=str(
            ROOT / "debugCapture" / "painter_ui_alt_duplicate_m1"
        ),
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
    for label, size in (
        ("desktop", (1360, 900)),
        ("compact", (900, 650)),
    ):
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
            name="Product card",
            x=230,
            y=210,
            width=320,
            height=260,
            style={
                "fill": "#26374D",
                "stroke": "#6C8EB8",
                "stroke_width": 2,
                "radius": 20,
            },
        )
        document, _title = add_ui_object(
            document,
            kind="text",
            name="Card title",
            parent_id=card["id"],
            x=270,
            y=250,
            width=230,
            height=44,
            style={"fill": "#EEF4FC", "font_size": 28},
            content={"text": "Original card"},
        )
        document = select_ui_objects(
            document,
            [card["id"]],
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
        dialog._update_canvas_geometry()
        app.processEvents()

        overlay = dialog._painter_ui_overlay
        source = next(
            row for row in overlay._document["objects"] if row["id"] == card["id"]
        )
        start = overlay._object_rect(source).center().toPoint()
        end = QPoint(start.x() + 380, start.y() + 50)
        QTest.mousePress(
            overlay,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.AltModifier,
            start,
        )
        QTest.mouseMove(overlay, end)
        QTest.mouseRelease(
            overlay,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.AltModifier,
            end,
        )
        app.processEvents()
        dialog._hide_painter_ui_quick_properties()
        app.processEvents()
        path = output_dir / f"alt_drag_duplicate_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        selected_id = dialog._painter_ui_document["selection"]["object_id"]
        copied = next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == selected_id
        )
        ok = bool(
            saved
            and len(dialog._painter_ui_document["objects"]) == 4
            and selected_id != card["id"]
            and dialog._painter_ui_document["selection"]["object_ids"]
            == [selected_id]
            and float(copied["x"]) > float(card["x"]) + 200
            and dialog._paint_inspector_frame.width() <= 40
            and dialog._painter_ui_navigator.width() <= 40
        )
        results[label] = {
            "ok": ok,
            "screenshot": str(path),
            "selected_copy_id": selected_id,
            "copy_position": [copied["x"], copied["y"]],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.alt_duplicate.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "alt_duplicate_report.json"
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
