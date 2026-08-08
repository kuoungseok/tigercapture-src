"""Capture Painter UI performance budget evidence at two densities."""
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
    from app.painter_ui_performance_budget import (
        inspect_painter_ui_performance_budget,
    )
    from app.painter_ui_performance_budget_dialog import (
        PainterUIPerformanceBudgetDialog,
    )
    from app.painter_ui_release_corpus import (
        build_painter_ui_release_document,
    )

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    audit = inspect_painter_ui_performance_budget(
        build_painter_ui_release_document()
    )
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "performance_budget"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (620, 470)), ("compact", (420, 500))):
        dialog = PainterUIPerformanceBudgetDialog()
        dialog.set_report(audit)
        dialog.resize(*size)
        dialog.show()
        app.processEvents()
        path = output / f"performance_budget_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        compact = label == "compact"
        results[label] = {
            "ok": bool(
                saved
                and dialog.tree.topLevelItemCount() == 6
                and dialog.tree.isColumnHidden(2) is compact
                and dialog.tree.isColumnHidden(3) is compact
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.performance_budget.qa.v1",
        "ok": audit["status"] == "covered"
        and all(row["ok"] for row in results.values()),
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
