"""Capture real Painter UI Page CRUD and page-scoped canvas behavior."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")

    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    output_dir = (
        ROOT / "debugCapture" / "painter_ui_pages_m1"
    ).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    results = {}

    for label, size in (("desktop", (1360, 900)), ("compact", (900, 650))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                390,
                844,
                "#F5F7FA",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        registry = ActionRegistry(owner=dialog)
        registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
        registry.execute(
            "paint.ui.object.add",
            {
                "kind": "button",
                "name": "Home CTA",
                "x": 52,
                "y": 680,
                "width": 286,
                "height": 56,
                "style": {"fill": "#4D79FF", "radius": 12},
                "content": {"text": "Continue"},
            },
        )
        registry.execute(
            "paint.ui.page.update",
            {"page_id": "page-1", "changes": {"name": "Home"}},
        )
        added = registry.execute(
            "paint.ui.page.add",
            {"name": "Settings", "width": 1440, "height": 900},
        ).to_dict()
        settings_id = added["result"]["ui_design"]["active_page_id"]
        registry.execute(
            "paint.ui.object.add",
            {
                "kind": "text",
                "name": "Settings title",
                "x": 96,
                "y": 80,
                "width": 520,
                "height": 72,
                "content": {"text": "Settings"},
                "style": {"fill": "#243246"},
            },
        )
        registry.execute(
            "paint.ui.artboard.add",
            {
                "name": "Tablet",
                "width": 834,
                "height": 1194,
                "breakpoint": "tablet",
            },
        )
        dialog.resize(*size)
        dialog.show()
        app.processEvents()

        registry.execute(
            "paint.ui.navigator.presentation",
            {"mode": "auto_hide"},
        )
        auto_hide_width = dialog._painter_ui_navigator.width()
        registry.execute(
            "paint.ui.navigator.presentation",
            {"mode": "pinned"},
        )
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        app.processEvents()
        settings_canvas = dialog._painter_ui_overlay._document
        settings_path = output_dir / f"settings_page_{label}.png"
        settings_saved = dialog.grab().save(str(settings_path), "PNG")

        registry.execute(
            "paint.ui.page.activate",
            {"page_id": "page-1"},
        )
        registry.execute("paint.ui.view.fit", {"mode": "all"})
        app.processEvents()
        home_canvas = dialog._painter_ui_overlay._document
        home_path = output_dir / f"home_page_{label}.png"
        home_saved = dialog.grab().save(str(home_path), "PNG")
        navigator = dialog._painter_ui_navigator

        results[label] = {
            "ok": bool(
                settings_saved
                and home_saved
                and auto_hide_width <= 40
                and navigator.page_list.count() == 2
                and navigator.page_add_button.isVisible()
                and navigator.page_remove_button.isVisible()
                and {row["page_id"] for row in settings_canvas["artboards"]}
                == {settings_id}
                and len(settings_canvas["artboards"]) == 2
                and {row["page_id"] for row in home_canvas["artboards"]}
                == {"page-1"}
                and len(home_canvas["artboards"]) == 1
            ),
            "settings_screenshot": str(settings_path),
            "home_screenshot": str(home_path),
            "page_names": [
                navigator.page_list.item(index).text()
                for index in range(navigator.page_list.count())
            ],
            "settings_artboards": len(settings_canvas["artboards"]),
            "home_artboards": len(home_canvas["artboards"]),
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.pages.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output_dir / "pages_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
