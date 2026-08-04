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


def _build_document() -> tuple[dict, dict]:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        move_ui_objects_in_hierarchy,
        update_ui_object,
    )

    document = create_ui_document(900, 640, name="Nested Change to QA")
    document, toggle_root = add_ui_object(
        document, kind="frame", name="Toggle / Off", x=60, y=60,
        width=64, height=32, style={"fill": "#8A8F98", "radius": 16},
    )
    document, toggle = convert_ui_object_to_component(
        document, root_object_id=toggle_root["id"], name="Toggle"
    )
    document, _ = define_ui_component_variant_property(
        document, component_id=toggle["id"], property_name="State",
        values=["Off", "On"], default_value="Off",
    )
    document, toggle_on = create_ui_component_variant(
        document, component_id=toggle["id"], name="Toggle / On",
        variant_properties={"State": "On"},
    )
    document, _ = update_ui_object(
        document, toggle_on["root_object_id"],
        {"style": {"fill": "#47C58E", "radius": 16}},
    )
    document, _ = add_ui_component_change_to_interaction(
        document, source_component_id=toggle["id"],
        target_component_id=toggle_on["id"], trigger="click",
    )
    document, _ = add_ui_component_change_to_interaction(
        document, source_component_id=toggle_on["id"],
        target_component_id=toggle["id"], trigger="click",
    )
    document, card_root = add_ui_object(
        document, kind="frame", name="Settings Card", x=80, y=180,
        width=320, height=160, style={"fill": "#FFFFFFFF", "radius": 16},
    )
    document, nested_definition = instantiate_ui_component(
        document, component_id=toggle["id"], x=300, y=240,
    )
    document = move_ui_objects_in_hierarchy(
        document, [nested_definition["root_object_id"]],
        target_parent_id=card_root["id"], placement="inside",
    )
    document, card = convert_ui_object_to_component(
        document, root_object_id=card_root["id"], name="Settings Card"
    )
    document, card_instance = instantiate_ui_component(
        document, component_id=card["id"], x=480, y=180,
    )
    nested = next(
        row for row in document["objects"]
        if row["parent_id"] == card_instance["root_object_id"]
        and row["component_id"] == toggle["id"]
    )
    document, _ = update_ui_object(document, nested["id"], {"opacity": 0.7})
    document["selection"] = {"object_id": "", "object_ids": []}
    return document, {
        "outer_id": card_instance["root_object_id"],
        "outer_component_id": card["id"],
        "nested_id": nested["id"],
        "off_component_id": toggle["id"],
        "on_component_id": toggle_on["id"],
    }


def _capture(widget, path: Path) -> dict:
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    pixmap = widget.grab()
    return {"path": str(path), "saved": bool(pixmap.save(str(path), "PNG")),
            "width": pixmap.width(), "height": pixmap.height()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    loaded = []
    for path in (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf",
                 Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"):
        if path.is_file():
            loaded.append(QFontDatabase.addApplicationFont(str(path)))
    if "Malgun Gothic" in QFontDatabase.families():
        app.setFont(QFont("Malgun Gothic", 9))
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    document, ids = _build_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()
    dialog._refresh_painter_ui_overlay()
    overlay = dialog._painter_ui_overlay
    overlay.fit_all()
    dialog._set_painter_ui_prototype_preview(True)
    app.processEvents()
    nested = next(row for row in overlay._document["objects"] if row["id"] == ids["nested_id"])
    pointer = overlay._object_rect(nested).center().toPoint()
    captures = {"off": _capture(dialog, output / "nested_change_to_off.png")}
    QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=pointer)
    app.processEvents()
    state_on = copy.deepcopy(dialog._painter_ui_prototype_state)
    captures["on"] = _capture(dialog, output / "nested_change_to_on.png")
    effective_on = next(
        row for row in overlay._effective_document["objects"]
        if row["id"] == ids["nested_id"]
    )
    on_fill = str((effective_on.get("style") or {}).get("fill") or "")
    QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=pointer)
    app.processEvents()
    state_off_again = copy.deepcopy(dialog._painter_ui_prototype_state)
    captures["off_again"] = _capture(dialog, output / "nested_change_to_off_again.png")
    effective = overlay._effective_document
    outer = next(row for row in effective["objects"] if row["id"] == ids["outer_id"])
    effective_nested = next(row for row in effective["objects"] if row["id"] == ids["nested_id"])
    report = {
        "schema": "tigerstudio.painter.ui.m3_nested_change_to_capture.v1",
        "captures": captures, "pointer": {"x": pointer.x(), "y": pointer.y()},
        **ids,
        "expected_on_component_id": ids["on_component_id"],
        "expected_off_component_id": ids["off_component_id"],
        "on_component_id": state_on.get("component_variants", {}).get(ids["nested_id"], ""),
        "off_again_component_id": state_off_again.get("component_variants", {}).get(ids["nested_id"], ""),
        "effective_outer_component_id": outer["component_id"],
        "effective_nested_parent_id": effective_nested["parent_id"],
        "effective_nested_opacity": effective_nested["opacity"],
        "on_fill": on_fill,
        "off_again_fill": str(
            (effective_nested.get("style") or {}).get("fill") or ""
        ),
    }
    report["passed"] = bool(
        all(item["saved"] for item in captures.values())
        and report["on_component_id"] == ids["on_component_id"]
        and report["off_again_component_id"] == ids["off_component_id"]
        and report["effective_outer_component_id"] == ids["outer_component_id"]
        and report["effective_nested_parent_id"] == ids["outer_id"]
        and float(report["effective_nested_opacity"]) == 0.7
        and report["on_fill"] == "#47C58E"
        and report["off_again_fill"] == "#8A8F98"
        and (output / "nested_change_to_off.png").read_bytes()
        != (output / "nested_change_to_on.png").read_bytes()
    )
    (output / "nested_change_to_capture.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    dialog.close()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
