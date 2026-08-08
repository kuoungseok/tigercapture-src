"""Capture transient cross-artboard duplication UX at desktop and compact sizes."""
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
            ROOT
            / "debugCapture"
            / "painter_ui_cross_artboard_m1"
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
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        select_ui_objects,
        set_active_ui_artboard,
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
    desktop_id = document["active_artboard_id"]
    document, panel = add_ui_object(
        document,
        kind="frame",
        name="Feature panel",
        x=120,
        y=130,
        width=520,
        height=300,
        style={
            "fill": "#243246",
            "stroke": "#6D8DB5",
            "stroke_width": 2,
            "radius": 24,
        },
    )
    document, _title = add_ui_object(
        document,
        kind="text",
        name="Feature title",
        artboard_id=desktop_id,
        parent_id=panel["id"],
        x=164,
        y=176,
        width=360,
        height=56,
        style={"fill": "#EEF4FC", "font_size": 34},
        content={"text": "Responsive product card"},
    )
    document, _button = add_ui_object(
        document,
        kind="button",
        name="Primary action",
        artboard_id=desktop_id,
        parent_id=panel["id"],
        x=164,
        y=340,
        width=180,
        height=52,
        style={"fill": "#4A78C9", "radius": 12},
        content={"text": "Continue"},
    )
    document, tablet = add_ui_artboard(
        document,
        name="Tablet",
        width=800,
        height=900,
    )
    document, _mobile = add_ui_artboard(
        document,
        name="Mobile",
        width=390,
        height=844,
    )
    document = set_active_ui_artboard(document, desktop_id)
    document = select_ui_objects(
        document,
        [panel["id"]],
        primary_object_id=panel["id"],
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
    dialog.resize(1360, 900)
    dialog.show()
    app.processEvents()
    registry.execute("paint.ui.view.fit", {"mode": "all"})
    dialog._update_canvas_geometry()
    app.processEvents()

    popover = dialog._painter_ui_quick_actions
    popover.open_for_document(
        dialog._painter_ui_document,
        query="duplicate next artboard",
    )
    app.processEvents()
    desktop_path = output_dir / "duplicate_command_desktop.png"
    desktop_saved = dialog.grab().save(str(desktop_path), "PNG")
    command_item = popover.result_list.item(0)
    command = dict(command_item.data(0x0100) or {})
    desktop_ok = bool(
        desktop_saved
        and popover.isVisible()
        and command.get("id") == "selection.duplicate_next_artboard"
        and command.get("enabled")
        and dialog._paint_inspector_frame.width() <= 40
        and dialog._painter_ui_navigator.width() <= 40
    )

    popover._request_item(command_item)
    app.processEvents()
    duplicated_ids = list(
        dialog._painter_ui_document["selection"]["object_ids"]
    )
    result_path = output_dir / "duplicated_to_tablet_desktop.png"
    result_saved = dialog.grab().save(str(result_path), "PNG")
    result_ok = bool(
        result_saved
        and dialog._painter_ui_document["active_artboard_id"] == tablet["id"]
        and duplicated_ids
        and all(
            row["artboard_id"] == tablet["id"]
            for row in dialog._painter_ui_document["objects"]
            if row["id"] in duplicated_ids
        )
    )

    dialog.resize(900, 650)
    app.processEvents()
    dialog._sync_ui_design_toolbar_density()
    dialog._update_canvas_geometry()
    popover.open_for_document(
        dialog._painter_ui_document,
        query="duplicate next artboard",
    )
    app.processEvents()
    compact_path = output_dir / "duplicate_command_compact.png"
    compact_saved = dialog.grab().save(str(compact_path), "PNG")
    compact_item = popover.result_list.item(0)
    compact_command = dict(compact_item.data(0x0100) or {})
    compact_ok = bool(
        compact_saved
        and popover.isVisible()
        and compact_command.get("enabled")
        and popover.geometry().left() >= 0
        and popover.geometry().right() <= dialog._canvas_host.width()
        and dialog._paint_inspector_frame.width() <= 40
        and dialog._painter_ui_navigator.width() <= 40
    )

    report = {
        "schema": "tigerstudio.painter.ui.cross_artboard.qa.v1",
        "ok": desktop_ok and result_ok and compact_ok,
        "desktop_ok": desktop_ok,
        "result_ok": result_ok,
        "compact_ok": compact_ok,
        "desktop_command_screenshot": str(desktop_path),
        "desktop_result_screenshot": str(result_path),
        "compact_command_screenshot": str(compact_path),
        "source_artboard_id": desktop_id,
        "target_artboard_id": tablet["id"],
        "created_root_object_ids": duplicated_ids,
        "inspector_presentation": "auto_hide",
        "navigator_presentation": "auto_hide",
    }
    report_path = output_dir / "cross_artboard_report.json"
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
