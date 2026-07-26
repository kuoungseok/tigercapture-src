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
    for payload in (
        {
            "kind": "frame",
            "name": "Product Card",
            "x": 28,
            "y": 160,
            "width": 334,
            "height": 420,
            "style": {"fill": "#202B38"},
        },
        {
            "kind": "text",
            "name": "Product Title",
            "x": 52,
            "y": 412,
            "width": 286,
            "height": 54,
            "style": {"fill": "#314052"},
            "content": {"text": "Studio Headphones"},
        },
        {
            "kind": "button",
            "name": "Add to Cart",
            "x": 52,
            "y": 492,
            "width": 286,
            "height": 58,
            "style": {"fill": "#4C74DB", "radius": 6},
            "content": {"text": "Add to Cart"},
        },
    ):
        registry.execute("paint.ui.object.add", payload)
    dialog.show()
    app.processEvents()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "painter_ui_designer_m1.png"
    dialog.grab().save(str(screenshot_path), "PNG")
    state = dialog.painter_action_state()
    report = {
        "schema": "tigerstudio.painter.ui.qa.v1",
        "ok": (
            state["workspace"]["mode"] == "ui_design"
            and state["ui_design"]["validation"]["ok"]
            and state["ui_design"]["validation"]["object_count"] == 3
            and screenshot_path.is_file()
        ),
        "screenshot": str(screenshot_path),
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
