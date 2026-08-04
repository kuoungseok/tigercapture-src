"""Capture star, polygon, line, and arrow on-canvas controls."""
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
    parser.add_argument("--output-dir", default=str(ROOT / "debugCapture" / "painter_ui_shape_gizmos"))
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import add_ui_object, create_ui_document, select_ui_objects
    from app.painter_ui_workspace import PainterUIDesignOverlay

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document = create_ui_document(900, 600, name="Shape controls")
    document, star = add_ui_object(
        document, kind="star", name="Star 1", x=120, y=140, width=240, height=240,
        style={"fill": "#D9D9D9FF"},
        content={
            "point_count": 9,
            "inner_radius": 0.62,
            "rotation_offset": -90,
            "corner_radius": 34,
        },
    )
    document, polygon = add_ui_object(
        document, kind="polygon", name="Polygon 1", x=430, y=140, width=240, height=240,
        style={"fill": "#C7D5EAFF"},
        content={"point_count": 6, "rotation_offset": -90, "corner_radius": 24},
    )
    document, arrow = add_ui_object(
        document, kind="line", name="Arrow 1", x=170, y=460, width=460, height=50,
        style={"fill": "#3B78D8FF", "stroke_width": 4}, content={"arrow_end": True},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(1100, 760)
    overlay.set_tool("select")
    overlay.show()
    captures = {}
    for label, row in (("star", star), ("polygon", polygon), ("arrow", arrow)):
        selected = select_ui_objects(document, [row["id"]], primary_object_id=row["id"])
        overlay.set_document(selected)
        app.processEvents()
        path = output / f"{label}_gizmos.png"
        captures[label] = bool(overlay.grab().save(str(path), "PNG"))
    report = {
        "schema": "tigerstudio.painter.ui.shape_gizmos.qa.v1",
        "ok": all(captures.values()),
        "captures": captures,
    }
    report_path = output / "shape_gizmos_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}, indent=2))
    overlay.close()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
