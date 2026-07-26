"""Create a reproducible Painter UI Designer M1 workspace proof."""
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
        default=str(ROOT / "debugCapture" / "painter_ui_designer_m1"),
    )
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not args.show:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1360, 900)
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    last_add = None
    for payload in (
        {
            "kind": "frame",
            "name": "Product Card",
            "x": 28,
            "y": 110,
            "width": 334,
            "height": 590,
            "style": {"fill": "#202B38", "stroke": "#53657C"},
        },
        {
            "kind": "image",
            "name": "Product Image",
            "x": 50,
            "y": 138,
            "width": 290,
            "height": 210,
            "style": {"fill": "#17202B", "stroke": "#63748A"},
        },
        {
            "kind": "ellipse",
            "name": "New Badge",
            "x": 292,
            "y": 126,
            "width": 54,
            "height": 54,
            "style": {"fill": "#C98E4F", "text_color": "#15191F"},
            "content": {"text": "NEW"},
        },
        {
            "kind": "text",
            "name": "Product Title",
            "x": 52,
            "y": 378,
            "width": 286,
            "height": 54,
            "style": {"text_color": "#F2F5F9", "font_size": 17},
            "content": {"text": "Studio Headphones"},
        },
        {
            "kind": "line",
            "name": "Title Divider",
            "x": 52,
            "y": 445,
            "width": 286,
            "height": 10,
            "style": {"fill": "#63748A", "stroke_width": 2},
        },
        {
            "kind": "rectangle",
            "name": "Availability",
            "x": 52,
            "y": 474,
            "width": 132,
            "height": 42,
            "style": {"fill": "#304458", "stroke": "#526B82", "radius": 4},
            "content": {"text": "Ready to ship"},
        },
        {
            "kind": "progress",
            "name": "Stock Level",
            "x": 52,
            "y": 542,
            "width": 286,
            "height": 20,
            "style": {"fill": "#263344", "accent": "#75A7DD"},
            "content": {"value": 0.72},
        },
        {
            "kind": "button",
            "name": "Add to Cart",
            "x": 52,
            "y": 596,
            "width": 286,
            "height": 58,
            "style": {"fill": "#4C74DB", "stroke": "#7091E7", "radius": 6},
            "content": {"text": "Add to Cart"},
        },
    ):
        last_add = registry.execute("paint.ui.object.add", payload).to_dict()
    registry.execute(
        "paint.ui.artboard.add",
        {"name": "Desktop", "width": 1440, "height": 900, "breakpoint": "desktop"},
    )
    registry.execute("paint.ui.artboard.activate", {"artboard_id": "artboard-1"})
    button_id = str(
        (((last_add or {}).get("result") or {}).get("ui_design") or {}).get(
            "selected_object_id"
        )
        or ""
    )
    if button_id:
        registry.execute(
            "paint.ui.object.update",
            {"object_id": button_id, "changes": {"rotation": -4.0}},
        )
    dialog.show()
    app.processEvents()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "painter_ui_designer_m1.png"
    dialog.grab().save(str(screenshot_path), "PNG")
    dialog._paint_ui_inspector._tabs.setCurrentIndex(1)
    app.processEvents()
    inspect_screenshot_path = output_dir / "painter_ui_designer_m1_inspect.png"
    dialog.grab().save(str(inspect_screenshot_path), "PNG")
    state = dialog.painter_action_state()
    report = {
        "schema": "tigerstudio.painter.ui.qa.v1",
        "ok": (
            state["workspace"]["mode"] == "ui_design"
            and state["ui_design"]["validation"]["ok"]
            and state["ui_design"]["validation"]["object_count"] == 8
            and screenshot_path.is_file()
            and inspect_screenshot_path.is_file()
        ),
        "screenshot": str(screenshot_path),
        "inspect_screenshot": str(inspect_screenshot_path),
        "workspace": state["workspace"],
        "ui_design": state["ui_design"],
    }
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}, indent=2))
    if args.show:
        dialog.raise_()
        dialog.activateWindow()
        return app.exec()
    QTimer.singleShot(0, dialog.close)
    app.processEvents()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
