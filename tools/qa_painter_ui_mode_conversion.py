"""Capture real Painter UI to Vector and Paint conversion evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(900, 620, name="Conversion Studio")
    rows = (
        (
            "rectangle",
            "Editorial Card",
            110,
            120,
            420,
            260,
            {"fill": "#223247", "stroke": "#6B829C", "radius": 24},
            {},
        ),
        (
            "ellipse",
            "Accent Disc",
            590,
            130,
            170,
            170,
            {"fill": "#3B7081", "stroke": "#8DB4BC"},
            {},
        ),
        (
            "text",
            "Headline",
            150,
            165,
            320,
            70,
            {
                "text_color": "#F1F5F9",
                "font_size": 34,
                "font_weight": 700,
            },
            {"text": "Design becomes paint"},
        ),
        (
            "text",
            "Body",
            150,
            255,
            300,
            70,
            {"text_color": "#B8C7D8", "font_size": 18},
            {"text": "Keep the editable source. Explore freely."},
        ),
    )
    created = []
    for kind, name, x, y, width, height, style, content in rows:
        document, row = add_ui_object(
            document,
            kind=kind,
            name=name,
            x=x,
            y=y,
            width=width,
            height=height,
            style=style,
            content=content,
        )
        created.append(row["id"])
    document["selection"] = {
        "object_id": created[0],
        "object_ids": created,
    }
    return document, created


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["TIGERSTUDIO_PAINTER_PANEL_SETTINGS"] = "0"
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "mode_conversion"
    )
    output.mkdir(parents=True, exist_ok=True)
    document, object_ids = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 620, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_conversion_asset_root = lambda: output
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.resize(1360, 860)
    dialog.show()
    dialog._refresh_painter_ui_overlay()
    app.processEvents()

    vector_report = dialog._convert_painter_ui_selection_to_vector(
        object_ids=object_ids[:2],
    )
    vector_id = vector_report["converted_object_ids"][0]
    dialog._set_painter_ui_selection([vector_id], vector_id)
    dialog._painter_ui_overlay._vector_edit_object_id = vector_id
    dialog._painter_ui_overlay._vector_active_node_id = ""
    dialog._painter_ui_overlay._vector_active_segment_id = ""
    dialog._painter_ui_overlay.update()
    app.processEvents()
    vector_screenshot = output / "converted_vector_network.png"
    vector_saved = dialog.grab().save(str(vector_screenshot), "PNG")

    dialog._undo()
    dialog._set_painter_ui_selection(object_ids, object_ids[0])
    paint_report = dialog._convert_painter_ui_selection_to_paint(
        object_ids=object_ids,
    )
    app.processEvents()
    paint_screenshot = output / "converted_paint_layer.png"
    paint_saved = dialog.grab().save(str(paint_screenshot), "PNG")
    document_path = output / "conversion_roundtrip.tspaint"
    save_report = dialog.save_document_to_path(document_path)
    from app.painter_document_io import load_painter_document

    loaded, load_report = load_painter_document(
        document_path,
        asset_root=output / "roundtrip_assets",
    )
    roundtrip_stickers = list(loaded.get("stickers") or [])
    report = {
        "schema": "tigerstudio.painter.ui.mode_conversion.qa.v1",
        "ok": bool(
            vector_saved
            and paint_saved
            and vector_report["converted_count"] == 2
            and Path(paint_report["asset_path"]).is_file()
            and len(roundtrip_stickers) == 1
            and Path(roundtrip_stickers[0]["png_path"]).is_file()
        ),
        "vector": vector_report,
        "paint": paint_report,
        "roundtrip": {
            "save": save_report,
            "load": load_report,
            "sticker_count": len(roundtrip_stickers),
        },
        "screenshots": {
            "vector": str(vector_screenshot),
            "paint": str(paint_screenshot),
        },
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    dialog.close()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
