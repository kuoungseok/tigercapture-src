"""Capture equal-width/height Smart Guides during canvas resize."""
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

    from PySide6.QtCore import QPoint, Qt
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
        ROOT / "debugCapture" / "painter_ui_equal_size_guides_m1"
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
        document = create_ui_document(1280, 720, name="Equal size")
        document, target = add_ui_object(
            document,
            kind="rectangle",
            name="Reference 180 x 120",
            x=650,
            y=250,
            width=180,
            height=120,
            style={
                "fill": "#26384D",
                "stroke": "#6F91B8",
                "stroke_width": 2,
                "radius": 14,
            },
        )
        document, moving = add_ui_object(
            document,
            kind="rectangle",
            name="Resize me",
            x=300,
            y=250,
            width=130,
            height=80,
            style={
                "fill": "#3D5874",
                "stroke": "#8EB6DF",
                "stroke_width": 2,
                "radius": 14,
            },
        )
        document = select_ui_objects(
            document, [moving["id"]], primary_object_id=moving["id"]
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
        overlay = dialog._painter_ui_overlay
        overlay.set_snap(True, 1.0)
        app.processEvents()
        moving_rect = overlay._object_rect(moving)
        _viewport, scale = overlay._artboard_viewport()
        handle = overlay._handle_rects(moving_rect)["se"].center().toPoint()
        drag_target = QPoint(
            round(moving_rect.left() + 177.0 * scale),
            round(moving_rect.top() + 118.0 * scale),
        )
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
        QTest.mouseMove(overlay, drag_target)
        app.processEvents()
        kinds = {
            row["kind"]
            for row in overlay._smart_guide_plan.get("guides", [])
        }
        path = output_dir / f"equal_size_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        QTest.mouseRelease(
            overlay, Qt.MouseButton.LeftButton, pos=drag_target
        )
        app.processEvents()
        resized = next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == moving["id"]
        )
        results[label] = {
            "ok": bool(
                saved
                and kinds == {"equal_width", "equal_height"}
                and resized["width"] == target["width"]
                and resized["height"] == target["height"]
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "guide_kinds": sorted(kinds),
            "resized": [resized["width"], resized["height"]],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.equal_size_guides.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "equal_size_guides_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
