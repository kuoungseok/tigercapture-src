"""Capture the ellipse Arc sweep and inner-radius canvas gizmos."""
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
        default=str(ROOT / "debugCapture" / "painter_ui_arc_gizmo"),
    )
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document, ellipse = add_ui_object(
        create_ui_document(800, 600, name="Arc controls"),
        kind="ellipse",
        name="Ellipse 1",
        x=250,
        y=150,
        width=300,
        height=260,
        style={"fill": "#D9D9D9FF"},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 720)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()

    rect = overlay._object_rect(ellipse)
    sweep = overlay._arc_handle_positions(ellipse, rect)["sweep"]
    initial_path = output_dir / "ellipse_arc_handle.png"
    initial_saved = overlay.grab().save(str(initial_path), "PNG")
    sweep_start = QPoint(round(sweep.x()), round(sweep.y()))
    sweep_end = QPoint(round(rect.center().x()), round(rect.bottom()))
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=sweep_start)
    QTest.mouseMove(overlay, sweep_end, delay=1)
    app.processEvents()
    sweep_path = output_dir / "arc_sweep.png"
    sweep_saved = overlay.grab().save(str(sweep_path), "PNG")
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=sweep_end)

    row = next(item for item in overlay._document["objects"] if item["id"] == ellipse["id"])
    ratio = overlay._arc_handle_positions(row, rect)["ratio"]
    ratio_start = QPoint(round(ratio.x()), round(ratio.y()))
    ratio_end = QPoint(
        round(rect.center().x() + rect.width() * 0.25),
        round(rect.center().y() + rect.height() * 0.25),
    )
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=ratio_start)
    QTest.mouseMove(overlay, ratio_end, delay=1)
    app.processEvents()
    ratio_path = output_dir / "arc_inner_radius.png"
    ratio_saved = overlay.grab().save(str(ratio_path), "PNG")
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=ratio_end)

    row = next(item for item in overlay._document["objects"] if item["id"] == ellipse["id"])
    report = {
        "schema": "tigerstudio.painter.ui.arc_gizmo.qa.v2",
        "ok": bool(
            sweep_saved
            and initial_saved
            and ratio_saved
            and row["kind"] == "arc"
            and 1.0 <= abs(float(row["content"]["sweep_angle"])) < 360.0
            and 0.0 < float(row["content"]["inner_radius"]) < 1.0
        ),
        "kind": row["kind"],
        "content": row["content"],
        "screenshots": [str(initial_path), str(sweep_path), str(ratio_path)],
    }
    report_path = output_dir / "arc_gizmo_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}, indent=2))
    overlay.close()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
