from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_component_document() -> tuple[dict, dict, dict]:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_property,
        instantiate_ui_component,
        set_ui_component_instance_swap_preferred_values,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(1200, 760, name="M3 component QA")
    components: list[dict] = []
    for index, name in enumerate(("Card", "Icon / Search", "Icon / Add")):
        document, root = add_ui_object(
            document,
            kind="frame",
            name=name,
            x=80 + index * 180,
            y=80,
            width=144,
            height=56,
            style={"fill": "#FFFFFF", "radius": 12},
        )
        document, component = convert_ui_object_to_component(
            document,
            root_object_id=root["id"],
            name=name,
        )
        components.append(component)

    card, icon_search, icon_add = components
    document, _ = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Label",
        definition={"type": "text", "default": "Continue"},
    )
    document, _ = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Show icon",
        definition={"type": "boolean", "default": True},
    )
    document, _ = define_ui_component_property(
        document,
        component_id=card["id"],
        property_name="Icon",
        definition={"type": "instance_swap", "default": icon_search["id"]},
    )
    document, _ = set_ui_component_instance_swap_preferred_values(
        document,
        component_id=card["id"],
        property_name="Icon",
        preferred_component_ids=[icon_add["id"], icon_search["id"]],
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=180,
        y=220,
    )
    document["selection"] = {
        "object_id": instance["root_object_id"],
        "object_ids": [instance["root_object_id"]],
    }
    return document, card, icon_add


def _build_interactive_button_document() -> tuple[dict, dict, dict, dict, dict]:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        convert_ui_object_to_component,
        create_ui_component_variant,
        define_ui_component_variant_property,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document, update_ui_object

    document = create_ui_document(900, 600, name="Interactive button QA")
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Button / Default",
        x=100,
        y=100,
        width=160,
        height=52,
        style={"fill": "#0D99FF", "radius": 10},
    )
    document, family = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    document, _ = define_ui_component_variant_property(
        document,
        component_id=family["id"],
        property_name="State",
        values=["Default", "Hover", "Pressed"],
        default_value="Default",
    )
    document, hover = create_ui_component_variant(
        document,
        component_id=family["id"],
        name="Button / Hover",
        variant_properties={"State": "Hover"},
    )
    document, pressed = create_ui_component_variant(
        document,
        component_id=family["id"],
        name="Button / Pressed",
        variant_properties={"State": "Pressed"},
    )
    for component, x, color in (
        (hover, 320, "#0B85DD"),
        (pressed, 540, "#086DB8"),
    ):
        variant_root = next(
            row
            for row in document["objects"]
            if row["id"] == component["root_object_id"]
        )
        document, _ = update_ui_object(
            document,
            variant_root["id"],
            {"x": float(x), "style": {"fill": color, "radius": 10}},
        )
    document, _ = add_ui_component_change_to_interaction(
        document,
        source_component_id=family["id"],
        target_component_id=hover["id"],
        trigger="mouse_enter",
    )
    document, _ = add_ui_component_change_to_interaction(
        document,
        source_component_id=hover["id"],
        target_component_id=pressed["id"],
        trigger="press",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=family["id"],
        x=360,
        y=300,
    )
    document["selection"] = {"object_id": "", "object_ids": []}
    return document, family, hover, pressed, instance


def _capture_widget(widget, path: Path) -> dict:
    from PySide6.QtWidgets import QApplication

    widget.show()
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
        "non_empty": not pixmap.isNull(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--inspector-width", type=int, default=360)
    parser.add_argument("--inspector-height", type=int, default=900)
    parser.add_argument("--canvas-width", type=int, default=900)
    parser.add_argument("--canvas-height", type=int, default=650)
    args = parser.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QFont, QFontDatabase, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_component_preferred_values_dialog import (
        PainterUIInstanceSwapPreferredDialog,
    )
    from app.painter_ui_inspector import PainterUIInspector
    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    # Qt's offscreen Windows platform does not enumerate system fonts. Load the
    # same UI fallback explicitly so QA captures validate glyphs as well as
    # geometry. The normal desktop platform continues to use system discovery.
    loaded_font_ids = []
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

    document, card, _preferred = _build_component_document()
    inspector = PainterUIInspector()
    inspector.resize(args.inspector_width, args.inspector_height)
    inspector.set_document(document)
    inspector_capture = _capture_widget(
        inspector, output / "painter_ui_m3_inspector_150.png"
    )

    dialog = PainterUIInstanceSwapPreferredDialog(
        document=document,
        component_id=card["id"],
        property_name="Icon",
    )
    dialog.resize(520, 620)
    dialog_capture = _capture_widget(
        dialog, output / "painter_ui_m3_preferred_instances_150.png"
    )
    interactive_document, default_variant, hover_variant, pressed_variant, instance = (
        _build_interactive_button_document()
    )
    from app.painter_ui_prototype import (
        execute_ui_prototype_trigger,
        prototype_initial_state,
        resolve_ui_component_prototype_document,
    )

    canvas = PainterUIDesignOverlay()
    canvas.resize(args.canvas_width, args.canvas_height)
    runtime_state = prototype_initial_state(interactive_document)
    pointer_events: list[dict] = []

    def apply_runtime() -> None:
        canvas.set_document(
            resolve_ui_component_prototype_document(
                interactive_document,
                runtime_state,
            )
        )
        canvas.set_prototype_preview(True, runtime_state)

    def execute_trigger(object_id: str, trigger: str, key: str) -> None:
        nonlocal runtime_state
        pointer_events.append(
            {"object_id": object_id, "trigger": trigger, "key": key}
        )
        runtime_state = execute_ui_prototype_trigger(
            interactive_document,
            runtime_state,
            source_object_id=object_id,
            trigger=trigger,
            key=key,
        )
        apply_runtime()

    canvas.prototype_trigger_requested.connect(execute_trigger)
    apply_runtime()
    canvas.fit_all()
    default_capture = _capture_widget(
        canvas, output / "painter_ui_m3_button_default.png"
    )
    instance_row = next(
        row
        for row in canvas._document["objects"]
        if row["id"] == instance["root_object_id"]
    )
    pointer = canvas._object_rect(instance_row).center().toPoint()
    initial_hit_ids = canvas.object_ids_at(float(pointer.x()), float(pointer.y()))
    QTest.mouseMove(canvas, QPoint(5, 5))
    app.processEvents()
    QTest.mouseMove(canvas, pointer)
    app.processEvents()
    if not any(row["trigger"] == "mouse_enter" for row in pointer_events):
        global_pointer = canvas.mapToGlobal(pointer)
        QApplication.sendEvent(
            canvas,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(pointer),
                QPointF(global_pointer),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        app.processEvents()
    hover_capture = _capture_widget(
        canvas, output / "painter_ui_m3_button_hover.png"
    )
    hover_state_component_id = str(
        runtime_state.get("component_variants", {}).get(
            instance["root_object_id"], ""
        )
    )
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=pointer)
    app.processEvents()
    pressed_capture = _capture_widget(
        canvas, output / "painter_ui_m3_button_pressed.png"
    )
    pressed_state_component_id = str(
        runtime_state.get("component_variants", {}).get(
            instance["root_object_id"], ""
        )
    )
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=pointer)

    controls = inspector.component_instance_property_controls
    control_geometry = {}
    for name, control in controls.items():
        point = control.mapTo(inspector, control.rect().topLeft())
        control_geometry[name] = {
            "x": int(point.x()),
            "y": int(point.y()),
            "width": int(control.width()),
            "height": int(control.height()),
            "visible": bool(control.isVisibleTo(inspector)),
            "inside_horizontal_viewport": bool(
                point.x() >= 0
                and point.x() + control.width() <= inspector.width()
            ),
        }
    report = {
        "schema": "tigerstudio.painter.ui.m3_dpi_capture.v1",
        "requested_scale": os.environ.get("QT_SCALE_FACTOR", ""),
        "font_family": app.font().family(),
        "loaded_font_count": sum(value >= 0 for value in loaded_font_ids),
        "inspector": inspector_capture,
        "preferred_instances_dialog": dialog_capture,
        "canvas": default_capture,
        "interactive_button": {
            "default": default_capture,
            "hover": hover_capture,
            "pressed": pressed_capture,
            "default_component_id": default_variant["id"],
            "hover_component_id": hover_variant["id"],
            "pressed_component_id": pressed_variant["id"],
            "hover_state_component_id": hover_state_component_id,
            "pressed_state_component_id": pressed_state_component_id,
            "pointer": {"x": pointer.x(), "y": pointer.y()},
            "initial_hit_ids": initial_hit_ids,
            "pointer_events": pointer_events,
        },
        "visible_component_controls": sorted(controls),
        "component_control_geometry": control_geometry,
        "preferred_value_count": len(dialog.preferred_component_ids()),
    }
    expected_dpr = float(os.environ.get("QT_SCALE_FACTOR", "1") or 1)
    report["passed"] = bool(
        inspector_capture["saved"]
        and dialog_capture["saved"]
        and inspector_capture["device_pixel_ratio"] >= expected_dpr - 0.01
        and dialog_capture["device_pixel_ratio"] >= expected_dpr - 0.01
        and default_capture["saved"]
        and hover_capture["saved"]
        and pressed_capture["saved"]
        and default_capture["device_pixel_ratio"]
        == inspector_capture["device_pixel_ratio"]
        and hover_state_component_id == hover_variant["id"]
        and pressed_state_component_id == pressed_variant["id"]
        and report["loaded_font_count"] >= 1
        and set(report["visible_component_controls"])
        == {"Icon", "Label", "Show icon"}
        and all(
            row["visible"] and row["inside_horizontal_viewport"]
            for row in control_geometry.values()
        )
        and report["preferred_value_count"] == 2
    )
    report_path = output / "painter_ui_m3_dpi_capture.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dialog.close()
    canvas.close()
    inspector.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
