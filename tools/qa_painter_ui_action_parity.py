"""Capture Painter UI/Action parity evidence at desktop and compact sizes."""
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

    from app.actions.registry import ActionRegistry
    from app.font_fallback import apply_ui_font
    from app.painter_ui_action_parity import inspect_painter_ui_action_parity
    from app.painter_ui_action_parity_dialog import (
        PainterUIActionParityDialog,
    )

    application = QApplication.instance() or QApplication([])
    apply_ui_font(application)
    parity = inspect_painter_ui_action_parity(
        ActionRegistry(owner=None).list_actions()
    )
    output = ROOT / "debugCapture" / "painter_ui_designer" / "action_parity"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (660, 560)), ("compact", (420, 580))):
        dialog = PainterUIActionParityDialog()
        dialog.set_report(parity)
        dialog.resize(*size)
        dialog.show()
        application.processEvents()
        path = output / f"action_parity_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and parity["status"] == "covered"
                and dialog.tree.topLevelItemCount()
                == parity["family_count"]
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        application.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.action_parity.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "parity": parity,
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
