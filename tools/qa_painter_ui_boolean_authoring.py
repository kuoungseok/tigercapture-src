"""Capture Figma-style transient Boolean authoring at two window sizes."""
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
        default=str(ROOT / "debugCapture" / "painter_ui_boolean_m1"),
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
    first = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "rectangle",
            "name": "Base Panel",
            "x": 270,
            "y": 190,
            "width": 520,
            "height": 300,
            "style": {
                "fill": "#3C75B8",
                "stroke": "#82B7F1",
                "stroke_width": 3,
                "radius": 48,
            },
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    second = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "ellipse",
            "name": "Boolean Lens",
            "x": 620,
            "y": 255,
            "width": 330,
            "height": 210,
            "style": {
                "fill": "#B98255",
                "stroke": "#E1B98F",
                "stroke_width": 3,
            },
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [first, second], "primary_object_id": second},
    )
    registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "auto_hide"},
    )
    registry.execute(
        "paint.ui.navigator.presentation",
        {"mode": "auto_hide"},
    )
    dialog._hide_painter_ui_quick_properties()
    dialog.resize(1360, 900)
    dialog.show()
    app.processEvents()
    registry.execute("paint.ui.view.fit", {"mode": "artboard"})
    dialog._update_canvas_geometry()
    app.processEvents()

    bar = dialog._painter_ui_boolean_context_bar
    selection_path = output_dir / "boolean_selection_desktop.png"
    selection_saved = dialog.grab().save(str(selection_path), "PNG")
    selection_state = bar.state()
    desktop_ok = bool(
        selection_saved
        and bar.isVisible()
        and selection_state.get("mode") == "selection"
        and dialog._paint_inspector_frame.width() <= 40
        and dialog._painter_ui_navigator.width() <= 40
    )

    bar.operation_buttons["subtract"].click()
    app.processEvents()
    group_state = bar.state()
    group_id = str(group_state.get("group_id") or "")
    group_path = output_dir / "boolean_subtract_group_desktop.png"
    group_saved = dialog.grab().save(str(group_path), "PNG")
    group_ok = bool(
        group_saved
        and group_id
        and group_state.get("mode") == "group"
        and group_state.get("operation") == "subtract"
        and bar.release_button.isVisible()
        and {first, second}
        <= {row["id"] for row in dialog._painter_ui_document["objects"]}
    )

    dialog.resize(900, 650)
    app.processEvents()
    dialog._sync_ui_design_toolbar_density()
    dialog._update_canvas_geometry()
    app.processEvents()
    compact_path = output_dir / "boolean_subtract_group_compact.png"
    compact_saved = dialog.grab().save(str(compact_path), "PNG")
    compact_ok = bool(
        compact_saved
        and bar.isVisible()
        and bar.geometry().left() >= 0
        and bar.geometry().right() <= dialog._canvas_host.width()
        and dialog._paint_inspector_frame.width() <= 40
        and dialog._painter_ui_navigator.width() <= 40
    )

    bar.release_button.click()
    app.processEvents()
    release_ok = bool(
        group_id
        and group_id
        not in {row["id"] for row in dialog._painter_ui_document["objects"]}
        and dialog._painter_ui_document["selection"]["object_ids"]
        == [first, second]
        and bar.state().get("mode") == "selection"
    )
    report = {
        "schema": "tigerstudio.painter.ui.boolean.qa.v1",
        "ok": desktop_ok and group_ok and compact_ok and release_ok,
        "desktop_ok": desktop_ok,
        "group_ok": group_ok,
        "compact_ok": compact_ok,
        "release_ok": release_ok,
        "selection_screenshot": str(selection_path),
        "group_screenshot": str(group_path),
        "compact_screenshot": str(compact_path),
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "boolean_authoring_report.json"
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
