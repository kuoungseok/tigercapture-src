"""Capture resolved equal-gap Smart Guides at desktop and compact sizes."""
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
        default=str(ROOT / "debugCapture" / "painter_ui_smart_guides_m1"),
    )
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QTimer
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
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1280, 720, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    document = create_ui_document(1280, 720, name="Desktop")
    cards = []
    for name, x, color in (
        ("Left", 200, "#1C2A3B"),
        ("Moving", 500, "#2A405A"),
        ("Right", 800, "#385270"),
    ):
        document, card = add_ui_object(
            document,
            kind="rectangle",
            name=name,
            x=x,
            y=220,
            width=220,
            height=240,
            style={"fill": color, "radius": 18},
        )
        cards.append(card)
    moving = cards[1]
    document = select_ui_objects(
        document,
        [moving["id"]],
        primary_object_id=moving["id"],
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    registry.execute("paint.ui.inspector.presentation", {"mode": "auto_hide"})
    registry.execute("paint.ui.navigator.presentation", {"mode": "auto_hide"})

    results = {}
    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._update_canvas_geometry()
        app.processEvents()
        overlay = dialog._painter_ui_overlay
        overlay.set_snap(True, 8.0)
        overlay._move_original_positions = {
            moving["id"]: (moving["x"], moving["y"])
        }
        snapped = overlay._smart_snap_position(moving, 498.0, 220.0)
        overlay.update()
        app.processEvents()
        path = output_dir / f"equal_gap_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        guide_kinds = {
            row["kind"]
            for row in overlay._smart_guide_plan.get("guides", [])
        }
        results[label] = {
            "ok": bool(
                saved
                and snapped[0] == 500.0
                and "equal_gap" in guide_kinds
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "snapped": list(snapped),
            "guide_kinds": sorted(guide_kinds),
        }

    report = {
        "schema": "tigerstudio.painter.ui.smart_guides.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "smart_guide_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}, indent=2))
    QTimer.singleShot(0, dialog.close)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
