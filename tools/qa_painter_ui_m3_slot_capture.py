from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_slot_document() -> tuple[dict, dict, dict]:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        inspect_ui_component_instance_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )

    document = create_ui_document(900, 640, name="M3 Slot pointer QA")
    document, card_root = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=80,
        y=70,
        width=420,
        height=180,
        style={"fill": "#FFFFFFFF", "radius": 16},
    )
    document, slot_source = add_ui_object(
        document,
        kind="frame",
        name="Actions",
        parent_id=card_root["id"],
        x=110,
        y=120,
        width=340,
        height=80,
        style={"fill": "#EAF4FFFF", "radius": 10},
    )
    document, card = convert_ui_object_to_component(
        document,
        root_object_id=card_root["id"],
        name="Card",
    )
    document, _definition = define_ui_component_slot(
        document,
        component_id=card["id"],
        source_object_id=slot_source["id"],
        property_name="Actions",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=380,
        y=310,
    )
    slot = inspect_ui_component_instance_slot(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Actions",
    )
    document, outsider = add_ui_object(
        document,
        kind="ellipse",
        name="Dropped action",
        x=120,
        y=410,
        width=52,
        height=52,
        style={"fill": "#0D99FFFF"},
    )
    return select_ui_object(document, outsider["id"]), outsider, slot


def _capture(widget, path: Path) -> dict:
    from PySide6.QtWidgets import QApplication

    QApplication.processEvents()
    pixmap = widget.grab()
    saved = bool(pixmap.save(str(path), "PNG"))
    return {
        "path": str(path),
        "saved": saved,
        "logical_width": int(widget.width()),
        "logical_height": int(widget.height()),
        "pixel_width": int(pixmap.width()),
        "pixel_height": int(pixmap.height()),
        "device_pixel_ratio": float(pixmap.devicePixelRatio()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=820)
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_components import inspect_ui_component_instance_slot

    app = QApplication.instance() or QApplication([])
    loaded_font_ids: list[int] = []
    for font_path in (
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf",
    ):
        if font_path.is_file():
            loaded_font_ids.append(
                int(QFontDatabase.addApplicationFont(str(font_path)))
            )
    if "Malgun Gothic" in QFontDatabase.families():
        app.setFont(QFont("Malgun Gothic", 9))

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    document, outsider, slot = _build_slot_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(args.width, args.height)
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()
    dialog._refresh_painter_ui_overlay()
    overlay = dialog._painter_ui_overlay
    overlay.fit_all()
    app.processEvents()

    current_outsider = next(
        row for row in overlay._document["objects"]
        if row["id"] == outsider["id"]
    )
    current_slot = next(
        row for row in overlay._document["objects"]
        if row["id"] == slot["slot_object_id"]
    )
    outsider_rect = overlay._object_rect(current_outsider)
    start = QPointF(
        outsider_rect.left() + outsider_rect.width() * 0.35,
        outsider_rect.top() + outsider_rect.height() * 0.65,
    ).toPoint()
    target = overlay._object_rect(current_slot).center().toPoint()
    arc_hit = overlay._arc_handle_at(
        current_outsider,
        outsider_rect,
        QPointF(start),
    )
    before_parent_id = str(current_outsider.get("parent_id") or "")
    undo_before = len(dialog._undo_labels)
    captures = {
        "before": _capture(dialog, output / "painter_ui_m3_slot_before.png")
    }

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, target)
    app.processEvents()
    if not overlay._hierarchy_drop_preview_id:
        app.sendEvent(
            overlay,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(target),
                QPointF(overlay.mapToGlobal(target)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        app.processEvents()
    preview_id = str(overlay._hierarchy_drop_preview_id or "")
    interaction = str(overlay._interaction or "")
    captures["drag_preview"] = _capture(
        dialog, output / "painter_ui_m3_slot_drag_preview.png"
    )

    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()
    captures["after"] = _capture(
        dialog, output / "painter_ui_m3_slot_after.png"
    )
    dropped = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
    )
    updated_slot = inspect_ui_component_instance_slot(
        dialog._painter_ui_document,
        instance_root_id=slot["instance_root_id"],
        property_name="Actions",
    )
    dropped_overlay_row = next(
        row for row in overlay._document["objects"]
        if row["id"] == outsider["id"]
    )
    dropped_slot_row = next(
        row for row in overlay._document["objects"]
        if row["id"] == current_slot["id"]
    )
    visually_inside_slot = overlay._object_rect(dropped_slot_row).contains(
        overlay._object_rect(dropped_overlay_row).center()
    )
    undo_after_drop = len(dialog._undo_labels)
    dialog._undo()
    app.processEvents()
    captures["undo"] = _capture(
        dialog, output / "painter_ui_m3_slot_undo.png"
    )
    restored = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
    )

    report = {
        "schema": "tigerstudio.painter.ui.m3_slot_pointer_capture.v1",
        "font_family": app.font().family(),
        "loaded_font_count": sum(value >= 0 for value in loaded_font_ids),
        "captures": captures,
        "pointer": {
            "start": {"x": start.x(), "y": start.y()},
            "target": {"x": target.x(), "y": target.y()},
            "arc_handle_hit": arc_hit,
            "interaction": interaction,
        },
        "object_id": outsider["id"],
        "slot_object_id": current_slot["id"],
        "drop_preview_id": preview_id,
        "before_parent_id": before_parent_id,
        "dropped_parent_id": str(dropped.get("parent_id") or ""),
        "slot_child_ids": list(updated_slot["child_ids"]),
        "visually_inside_slot": bool(visually_inside_slot),
        "undo_before": undo_before,
        "undo_after_drop": undo_after_drop,
        "restored_parent_id": str(restored.get("parent_id") or ""),
    }
    report["passed"] = bool(
        all(row["saved"] for row in captures.values())
        and report["loaded_font_count"] >= 1
        and not arc_hit
        and interaction == "move"
        and preview_id == current_slot["id"]
        and report["dropped_parent_id"] == current_slot["id"]
        and outsider["id"] in report["slot_child_ids"]
        and report["visually_inside_slot"]
        and undo_after_drop == undo_before + 1
        and report["restored_parent_id"] == before_parent_id
    )
    report_path = output / "painter_ui_m3_slot_pointer_capture.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dialog.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
