"""Capture transient Painter UI distance measurements at two window sizes."""
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
            ROOT / "debugCapture" / "painter_ui_measurements_m1"
        ),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
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
    document, _left = add_ui_object(
        document,
        kind="rectangle",
        name="Navigation",
        x=80,
        y=170,
        width=210,
        height=360,
        style={"fill": "#1B2737", "radius": 16},
    )
    document, card = add_ui_object(
        document,
        kind="frame",
        name="Selected card",
        x=350,
        y=210,
        width=420,
        height=280,
        style={
            "fill": "#26374D",
            "stroke": "#6C8EB8",
            "stroke_width": 2,
            "radius": 20,
        },
    )
    document, _right = add_ui_object(
        document,
        kind="rectangle",
        name="Inspector preview",
        x=850,
        y=170,
        width=300,
        height=360,
        style={"fill": "#31455D", "radius": 16},
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
    dialog._hide_painter_ui_quick_properties()
    overlay = dialog._painter_ui_overlay
    overlay.set_measurements_visible(True)

    screenshots: dict[str, str] = {}
    checks: list[bool] = []
    for label, size in (
        ("desktop", (1360, 900)),
        ("compact", (900, 650)),
    ):
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        dialog._update_canvas_geometry()
        overlay.set_measurements_visible(True)
        app.processEvents()
        path = output_dir / f"distance_measurements_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        screenshots[label] = str(path)
        report = overlay.measurement_report()
        checks.append(
            bool(
                saved
                and report["eligible"]
                and len(report["distances"]) == 4
                and dialog._paint_inspector_frame.width() <= 40
                and dialog._painter_ui_navigator.width() <= 40
            )
        )

    action = registry.execute(
        "paint.ui.dev.measurement.inspect",
        {"object_ids": [card["id"]]},
    ).to_dict()
    report = {
        "schema": "tigerstudio.painter.ui.measurements.qa.v1",
        "ok": all(checks) and action["ok"],
        "screenshots": screenshots,
        "desktop_ok": checks[0],
        "compact_ok": checks[1],
        "action_ok": action["ok"],
        "measurement": action.get("result", {}),
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "measurement_report.json"
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
        dialog.raise_()
        dialog.activateWindow()
        return app.exec()
    QTimer.singleShot(0, dialog.close)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
