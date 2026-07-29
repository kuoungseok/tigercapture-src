"""Capture canvas reparent preview at desktop and compact sizes."""
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

    from PySide6.QtCore import Qt
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

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_reparent_preview_m1"
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
        document = create_ui_document(1280, 720, name="Reparent")
        document, frame = add_ui_object(
            document,
            kind="frame",
            name="Dashboard frame",
            x=530,
            y=150,
            width=480,
            height=410,
            style={
                "fill": "#1D2A3B",
                "stroke": "#53708F",
                "stroke_width": 2,
                "radius": 24,
            },
        )
        document, card = add_ui_object(
            document,
            kind="rectangle",
            name="Metric card",
            x=120,
            y=260,
            width=220,
            height=130,
            style={
                "fill": "#39536F",
                "stroke": "#83A9D2",
                "stroke_width": 2,
                "radius": 16,
            },
        )
        document = select_ui_objects(
            document, [card["id"]], primary_object_id=card["id"]
        )
        dialog._painter_ui_document = document
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
        overlay = dialog._painter_ui_overlay
        start = overlay._object_rect(card).center().toPoint()
        target = overlay._object_rect(frame).center().toPoint()
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(overlay, target)
        app.processEvents()
        preview_id = overlay._hierarchy_drop_preview_id
        path = output_dir / f"reparent_preview_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
        app.processEvents()
        moved = next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == card["id"]
        )
        ordered = [
            row["id"]
            for row in sorted(
                dialog._painter_ui_document["objects"],
                key=lambda row: row["z_index"],
            )
        ]
        results[label] = {
            "ok": bool(
                saved
                and preview_id == frame["id"]
                and moved["parent_id"] == frame["id"]
                and ordered.index(card["id"]) == ordered.index(frame["id"]) + 1
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "preview_target_id": preview_id,
            "parent_id_after_drop": moved["parent_id"],
            "ordered_object_ids": ordered,
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.reparent_preview.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "reparent_preview_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
