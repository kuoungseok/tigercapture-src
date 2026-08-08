"""Capture Painter UI shortcut-map evidence at desktop and compact sizes."""
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

    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_ui_shortcut_map_dialog import (
        PainterUIShortcutMapDialog,
    )

    application = QApplication.instance() or QApplication([])
    apply_ui_font(application)
    output = (
        ROOT / "debugCapture" / "painter_ui_designer" / "shortcuts"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (620, 560)), ("compact", (420, 580))):
        dialog = PainterUIShortcutMapDialog()
        dialog.resize(*size)
        dialog.show()
        application.processEvents()
        report = dialog.refresh()
        application.processEvents()
        path = output / f"shortcut_map_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and report["visible_count"] > 10
                and report["active_count"] > 0
                and dialog.tree.topLevelItemCount()
                == report["visible_count"]
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        application.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.shortcut_map.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "results": results,
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
