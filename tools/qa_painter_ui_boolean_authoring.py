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
    desktop_inspector_ok = bool(
        not dialog._paint_inspector_frame.isVisible()
        or dialog._paint_inspector_frame.width() <= 40
    )
    desktop_navigator_ok = bool(
        not dialog._painter_ui_navigator.isVisible()
        or dialog._painter_ui_navigator.width() <= 80
    )
    desktop_ok = bool(
        selection_saved
        and bar.isVisible()
        and selection_state.get("mode") == "selection"
        and desktop_inspector_ok
        and desktop_navigator_ok
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
    group_row = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == group_id
    )
    subtract_style_ok = str(group_row["style"].get("fill") or "").upper().startswith(
        "#3C75B8"
    )

    dialog.resize(900, 650)
    app.processEvents()
    dialog._sync_ui_design_toolbar_density()
    dialog._update_canvas_geometry()
    app.processEvents()
    compact_path = output_dir / "boolean_subtract_group_compact.png"
    compact_saved = dialog.grab().save(str(compact_path), "PNG")
    compact_inspector_ok = bool(
        not dialog._paint_inspector_frame.isVisible()
        or dialog._paint_inspector_frame.width() <= 40
    )
    compact_navigator_ok = bool(
        not dialog._painter_ui_navigator.isVisible()
        or dialog._painter_ui_navigator.width() <= 80
    )
    compact_ok = bool(
        compact_saved
        and bar.isVisible()
        and bar.geometry().left() >= 0
        and bar.geometry().right() <= dialog._canvas_host.width()
        and compact_inspector_ok
        and compact_navigator_ok
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
    registry.execute("paint.ui.object.remove", {"object_id": second})
    text = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "text",
            "name": "Boolean Text",
            "x": 690,
            "y": 125,
            "width": 250,
            "height": 150,
            "style": {
                "text_color": "#F2F6FFFF",
                "font_family": "Arial",
                "font_size": 120,
                "font_weight": 700,
            },
            "content": {"text": "UI"},
        },
    ).to_dict()["result"]["ui_design"]["selected_object_id"]
    registry.execute(
        "paint.ui.selection.set",
        {"object_ids": [first, text], "primary_object_id": text},
    )
    app.processEvents()
    text_selection_ok = bool(
        bar.isVisible()
        and bar.state().get("mode") == "selection"
        and bar.state().get("eligible")
    )
    bar.operation_buttons["union"].click()
    dialog.resize(1360, 900)
    registry.execute("paint.ui.view.fit", {"mode": "artboard"})
    dialog._update_canvas_geometry()
    app.processEvents()
    text_group_id = str(bar.state().get("group_id") or "")
    text_group = next(
        (
            row
            for row in dialog._painter_ui_document["objects"]
            if row["id"] == text_group_id
        ),
        None,
    )
    text_path = output_dir / "boolean_text_union_desktop.png"
    text_saved = dialog.grab().save(str(text_path), "PNG")
    text_union_ok = bool(
        text_saved
        and text_group is not None
        and str(text_group["style"].get("fill") or "").upper().startswith(
            "#F2F6FF"
        )
    )
    report = {
        "schema": "tigerstudio.painter.ui.boolean.qa.v2",
        "ok": (
            desktop_ok
            and group_ok
            and subtract_style_ok
            and compact_ok
            and release_ok
            and text_selection_ok
            and text_union_ok
        ),
        "desktop_ok": desktop_ok,
        "desktop_inspector_ok": desktop_inspector_ok,
        "desktop_navigator_ok": desktop_navigator_ok,
        "group_ok": group_ok,
        "subtract_style_ok": subtract_style_ok,
        "compact_ok": compact_ok,
        "compact_inspector_ok": compact_inspector_ok,
        "compact_navigator_ok": compact_navigator_ok,
        "release_ok": release_ok,
        "text_selection_ok": text_selection_ok,
        "text_union_ok": text_union_ok,
        "text_group_style": dict((text_group or {}).get("style") or {}),
        "selection_screenshot": str(selection_path),
        "group_screenshot": str(group_path),
        "compact_screenshot": str(compact_path),
        "text_union_screenshot": str(text_path),
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
        "final_panel_metrics": {
            "inspector_visible": dialog._paint_inspector_frame.isVisible(),
            "inspector_width": dialog._paint_inspector_frame.width(),
            "navigator_visible": dialog._painter_ui_navigator.isVisible(),
            "navigator_width": dialog._painter_ui_navigator.width(),
        },
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
