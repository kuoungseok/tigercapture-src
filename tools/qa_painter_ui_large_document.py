"""Measure Painter UI interaction with 500 objects across 20 artboards."""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _large_document() -> dict:
    from app.painter_ui_document import create_ui_document, normalize_ui_document

    document = create_ui_document(1440, 900, name="Desktop 1")
    document["pages"] = []
    document["artboards"] = []
    document["objects"] = []
    for page_index in range(4):
        page_id = f"page-{page_index + 1}"
        first_artboard_id = f"artboard-{page_index * 5 + 1}"
        document["pages"].append(
            {
                "id": page_id,
                "name": f"Flow {page_index + 1}",
                "active_artboard_id": first_artboard_id,
            }
        )
        for artboard_offset in range(5):
            artboard_index = page_index * 5 + artboard_offset
            artboard_id = f"artboard-{artboard_index + 1}"
            document["artboards"].append(
                {
                    "id": artboard_id,
                    "page_id": page_id,
                    "name": f"Screen {artboard_index + 1}",
                    "width": 1440,
                    "height": 900,
                    "x": float(artboard_offset * 1560),
                    "y": 0.0,
                    "background": "#F7F9FC",
                    "breakpoint": "desktop",
                }
            )
            for object_offset in range(25):
                object_index = artboard_index * 25 + object_offset
                column = object_offset % 5
                row = object_offset // 5
                document["objects"].append(
                    {
                        "id": f"ui-object-{object_index + 1}",
                        "artboard_id": artboard_id,
                        "name": f"Card {object_index + 1}",
                        "kind": "rectangle",
                        "x": 64.0 + column * 260.0,
                        "y": 72.0 + row * 150.0,
                        "width": 220.0,
                        "height": 112.0,
                        "style": {
                            "fill": (
                                "#DDE8F5" if row % 2 == 0 else "#E9EDF4"
                            ),
                            "stroke": "#A7B5C8",
                            "stroke_width": 1.0,
                            "radius": 10.0,
                        },
                    }
                )
    document["active_page_id"] = "page-1"
    document["active_artboard_id"] = "artboard-1"
    return normalize_ui_document(document)


def _elapsed_ms(callback) -> float:
    started = time.perf_counter()
    callback()
    return (time.perf_counter() - started) * 1000.0


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_large_document_m1"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)

    raw = _large_document()
    normalize_ms = _elapsed_ms(lambda: normalize_ui_document(raw))
    document = normalize_ui_document(raw)
    validation = validate_ui_document(document)

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "#F7F9FC"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1360, 900)
    dialog.show()
    app.processEvents()

    def show_document() -> None:
        dialog._painter_ui_document = document
        dialog._set_canvas_workspace_mode("ui_design")
        dialog._refresh_painter_ui_overlay()
        dialog._update_layer_list()
        app.processEvents()

    initial_refresh_ms = _elapsed_ms(show_document)
    page_switch_ms = []
    for page_id in (
        "page-2",
        "page-3",
        "page-4",
        "page-1",
        "page-4",
        "page-2",
        "page-1",
    ):
        page_switch_ms.append(
            _elapsed_ms(
                lambda target=page_id: (
                    dialog._set_painter_ui_page(target),
                    app.processEvents(),
                )
            )
        )
    dialog._fit_painter_ui_view("all")
    app.processEvents()
    screenshot_path = output_dir / "large_document_500_objects.png"
    paint_ms = _elapsed_ms(
        lambda: dialog.grab().save(str(screenshot_path), "PNG")
    )

    thresholds = {
        "normalize_ms": 750.0,
        "initial_refresh_ms": 2000.0,
        "page_switch_median_ms": 800.0,
        "paint_ms": 1500.0,
    }
    metrics = {
        "normalize_ms": round(normalize_ms, 3),
        "initial_refresh_ms": round(initial_refresh_ms, 3),
        "page_switch_median_ms": round(statistics.median(page_switch_ms), 3),
        "page_switch_max_ms": round(max(page_switch_ms), 3),
        "paint_ms": round(paint_ms, 3),
    }
    report = {
        "schema": "tigerstudio.painter.ui.large_document.qa.v1",
        "ok": bool(
            not validation["errors"]
            and len(document["pages"]) == 4
            and len(document["artboards"]) == 20
            and len(document["objects"]) == 500
            and all(
                metrics[name] <= limit
                for name, limit in thresholds.items()
            )
            and screenshot_path.exists()
        ),
        "document": {
            "page_count": len(document["pages"]),
            "artboard_count": len(document["artboards"]),
            "object_count": len(document["objects"]),
        },
        "metrics": metrics,
        "thresholds": thresholds,
        "validation_errors": validation["errors"],
        "screenshot": str(screenshot_path),
    }
    report_path = output_dir / "large_document_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    dialog.close()
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
