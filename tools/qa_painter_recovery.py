"""Capture Painter recovery chooser evidence at desktop and compact sizes."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.painter_recovery_dialog import PainterRecoveryDialog

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    now = time.time()
    rows = [
        {
            "session_id": "qa-current",
            "source_path": "C:/Projects/TigerStudio/product_dashboard.tspaint",
            "recovery_path": "C:/TigerStudio/recovery/current.tspaint",
            "saved_at": now,
            "bytes": 284_312,
        },
        {
            "session_id": "qa-untitled",
            "source_path": "",
            "recovery_path": "C:/TigerStudio/recovery/untitled.tspaint",
            "saved_at": now - 145,
            "bytes": 41_992,
        },
    ]
    output = ROOT / "debugCapture" / "painter_ui_designer" / "recovery"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (560, 460)), ("compact", (360, 480))):
        dialog = PainterRecoveryDialog()
        dialog.set_snapshots(rows)
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        path = output / f"recovery_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        footer_visible = (
            dialog.restore_button.isVisible()
            and dialog.discard_button.isVisible()
            and dialog.restore_button.geometry().right() <= dialog.width()
        )
        results[label] = {
            "ok": bool(
                saved
                and dialog.list_widget.count() == 2
                and footer_visible
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    report = {
        "schema": "tigerstudio.painter.recovery.qa.v1",
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
