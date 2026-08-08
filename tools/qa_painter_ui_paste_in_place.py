"""Capture Painter UI Paste in Place at desktop and compact sizes."""
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

    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )
    from app.painter_ui_property_clipboard import copy_ui_object_payload

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_paste_in_place_m1"
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
        document = create_ui_document(1280, 720, name="Paste in place")
        document, card = add_ui_object(
            document,
            kind="frame",
            name="Product card",
            x=390,
            y=210,
            width=330,
            height=220,
            style={
                "fill": "#203044",
                "stroke": "#6C91BC",
                "stroke_width": 2,
                "radius": 22,
            },
        )
        document, _title = add_ui_object(
            document,
            kind="text",
            name="Card title",
            parent_id=card["id"],
            x=435,
            y=275,
            width=240,
            height=54,
            style={"text_color": "#F4F7FB", "font_size": 30},
            content={"text": "Original + Copy"},
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
        result = registry.execute(
            "paint.ui.object.paste_in_place",
            {"clipboard": copy_ui_object_payload(document, card["id"])},
        )
        report = result.result["paste_in_place"]
        copied_id = report["created_root_object_ids"][0]
        copied = next(
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == copied_id
        )
        same_position = (
            copied["x"] == card["x"] and copied["y"] == card["y"]
        )
        registry.execute(
            "paint.ui.object.update",
            {
                "object_id": copied_id,
                "changes": {
                    "x": float(copied["x"]) + 64.0,
                    "y": float(copied["y"]) + 52.0,
                },
            },
        )
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._hide_painter_ui_quick_properties()
        app.processEvents()
        path = output_dir / f"paste_in_place_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and same_position
                and len(dialog._painter_ui_document["objects"]) == 4
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            ),
            "screenshot": str(path),
            "same_position_before_evidence_offset": same_position,
            "created_object_ids": report["created_object_ids"],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.paste_in_place.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "paste_in_place_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
