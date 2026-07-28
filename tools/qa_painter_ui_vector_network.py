"""Capture editable Painter UI vector paths at desktop and compact sizes."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _network() -> dict:
    return {
        "nodes": [
            {
                "id": "node-1",
                "x": 0.04,
                "y": 0.72,
                "in_handle": None,
                "out_handle": {"x": 0.18, "y": 0.08},
                "kind": "corner",
            },
            {
                "id": "node-2",
                "x": 0.38,
                "y": 0.28,
                "in_handle": {"x": 0.24, "y": 0.18},
                "out_handle": {"x": 0.50, "y": 0.42},
                "kind": "smooth",
            },
            {
                "id": "node-3",
                "x": 0.68,
                "y": 0.60,
                "in_handle": {"x": 0.56, "y": 0.76},
                "out_handle": {"x": 0.80, "y": 0.08},
                "kind": "smooth",
            },
            {
                "id": "node-4",
                "x": 0.96,
                "y": 0.34,
                "in_handle": {"x": 0.84, "y": 0.20},
                "out_handle": None,
                "kind": "corner",
            },
        ],
        "segments": [
            {
                "id": "segment-1",
                "start_node_id": "node-1",
                "end_node_id": "node-2",
                "kind": "cubic",
            },
            {
                "id": "segment-2",
                "start_node_id": "node-2",
                "end_node_id": "node-3",
                "kind": "cubic",
            },
            {
                "id": "segment-3",
                "start_node_id": "node-3",
                "end_node_id": "node-4",
                "kind": "cubic",
            },
        ],
        "closed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(
            ROOT / "debugCapture" / "painter_ui_designer_m1"
        ),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
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
    added = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "path",
            "name": "Editable Bezier Flow",
            "x": 150,
            "y": 190,
            "width": 980,
            "height": 340,
            "style": {
                "fill": "#00000000",
                "stroke": "#7FB4FF",
                "stroke_width": 7,
                "stroke_cap": "round",
                "stroke_join": "round",
            },
            "content": {"vector_network": _network()},
        },
    ).to_dict()
    object_id = str(
        added["result"]["ui_design"]["selected_object_id"]
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
    registry.execute(
        "paint.ui.view.focus",
        {"target": "selection", "object_id": object_id},
    )
    app.processEvents()

    overlay = dialog._painter_ui_overlay
    row = next(
        item
        for item in dialog._painter_ui_document["objects"]
        if item["id"] == object_id
    )
    path_rect = overlay._object_rect(row)
    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=path_rect.center().toPoint(),
    )
    app.processEvents()
    nodes, _handles = overlay._vector_control_positions(
        overlay._selected_row()
    )
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=nodes["node-2"].toPoint(),
    )
    app.processEvents()
    dialog._update_canvas_geometry()
    app.processEvents()

    desktop_path = (
        output_dir / "painter_ui_designer_m1_vector_network.png"
    )
    desktop_saved = dialog.grab().save(str(desktop_path), "PNG")
    desktop_state = dialog._painter_ui_vector_context_bar.state()
    desktop_ok = bool(
        desktop_saved
        and desktop_path.is_file()
        and desktop_path.stat().st_size > 0
        and overlay._vector_edit_object_id == object_id
        and desktop_state.get("node_id") == "node-2"
        and dialog._painter_ui_vector_context_bar.isVisible()
        and dialog._paint_inspector_frame.width() <= 40
    )

    dialog.resize(900, 650)
    app.processEvents()
    dialog._sync_ui_design_toolbar_density()
    dialog._update_canvas_geometry()
    app.processEvents()
    compact_path = (
        output_dir
        / "painter_ui_designer_m1_vector_network_compact.png"
    )
    compact_saved = dialog.grab().save(str(compact_path), "PNG")
    bar = dialog._painter_ui_vector_context_bar
    host = dialog._canvas_host
    compact_ok = bool(
        compact_saved
        and compact_path.is_file()
        and compact_path.stat().st_size > 0
        and bar.isVisible()
        and bar.geometry().left() >= 0
        and bar.geometry().right() <= host.width()
        and bar.geometry().bottom() <= host.height()
        and dialog._paint_inspector_frame.width() <= 40
    )

    report = {
        "schema": "tigerstudio.painter.ui.vector.qa.v1",
        "ok": desktop_ok and compact_ok,
        "object_id": object_id,
        "desktop_ok": desktop_ok,
        "compact_ok": compact_ok,
        "desktop_screenshot": str(desktop_path),
        "compact_screenshot": str(compact_path),
        "vector_state": desktop_state,
        "inspector_presentation": "auto_hide",
    }
    report_path = output_dir / "vector_network_report.json"
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
