"""Capture Painter locale/font audit evidence at desktop and compact sizes."""
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
    from app.painter_ui_locale_audit import inspect_painter_ui_locales
    from app.painter_ui_locale_audit_dialog import (
        PainterUILocaleAuditDialog,
    )

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    audit = inspect_painter_ui_locales()
    output = ROOT / "debugCapture" / "painter_ui_designer" / "locale_audit"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (580, 470)), ("compact", (420, 520))):
        dialog = PainterUILocaleAuditDialog()
        dialog.set_report(audit)
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        path = output / f"locale_audit_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and audit["status"] == "covered"
                and dialog.tree.topLevelItemCount() == audit["language_count"]
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.locale_audit.qa.v1",
        "ok": all(row["ok"] for row in results.values()),
        "audit": audit,
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
