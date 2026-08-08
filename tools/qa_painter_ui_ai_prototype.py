"""Capture review-first Painter UI AI Prototype Build evidence."""
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
    from app.drawing import _PAINT_DIALOG_QSS
    from app.painter_ui_ai_prototype import plan_ui_prototype_build
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_production_panel import PainterUIProductionPanel

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    document = create_ui_document(390, 844, name="AI Prototype Source")
    plan = plan_ui_prototype_build(
        document,
        prompt="Create an interactive mobile onboarding screen",
    )
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "ai_prototype"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (560, 700)), ("compact", (390, 560))):
        panel = PainterUIProductionPanel()
        panel.setStyleSheet(_PAINT_DIALOG_QSS)
        panel.set_document(document)
        panel.ai_mode_combo.setCurrentIndex(
            panel.ai_mode_combo.findData("prototype")
        )
        panel.ai_prompt_edit.setText(
            "Create an interactive mobile onboarding screen"
        )
        panel.set_ai_plan(plan)
        ai_tab = next(
            (
                index
                for index in range(panel.tabs.count())
                if panel.tabs.tabText(index) == "AI"
            ),
            -1,
        )
        panel.tabs.setCurrentIndex(ai_tab)
        panel.resize(*size)
        panel.show()
        app.processEvents()
        screenshot = output / f"ai_prototype_{label}.png"
        saved = panel.grab().save(str(screenshot), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and ai_tab >= 0
                and panel.ai_mode_combo.currentData() == "prototype"
                and panel.ai_summary.isVisible()
            ),
            "screenshot": str(screenshot),
            "size": [panel.width(), panel.height()],
        }
        panel.close()
        panel.deleteLater()
        app.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.ai_prototype.qa.v1",
        "ok": bool(plan["prototype"]["ok"])
        and all(row["ok"] for row in results.values()),
        "plan": {
            "schema": plan["schema"],
            "plan_id": plan["plan_id"],
            "operation_count": len(plan["operations"]),
            "interaction_count": len(plan["interaction_specs"]),
            "requires_explicit_apply": plan["requires_explicit_apply"],
        },
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
