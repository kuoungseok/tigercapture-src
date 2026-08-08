from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from app.drawing import _PAINT_DIALOG_QSS
    from app.painter_ui_accessibility_audit import audit_ui_accessibility
    from app.painter_ui_accessibility_panel import PainterUIAccessibilityPanel
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    application = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/malgun.ttf")
    application.setFont(QFont("Malgun Gothic", 9))
    application.setStyleSheet(_PAINT_DIALOG_QSS)
    document = create_ui_document(390, 844)
    document, button = add_ui_object(
        document,
        kind="button",
        name="Checkout",
        x=24,
        y=80,
        width=38,
        height=30,
        style={
            "fill": "#F3F5F7",
            "text_color": "#B5BBC4",
            "font_size": 14,
        },
        content={"text": ""},
    )
    document, _button = update_ui_object(
        document,
        button["id"],
        {
            "accessibility": {
                "role": "button",
                "label": "",
                "focus_order": 1,
            }
        },
    )
    report = audit_ui_accessibility(document)

    output = ROOT / "debugCapture" / "painter_ui_designer" / "accessibility"
    output.mkdir(parents=True, exist_ok=True)
    panel = PainterUIAccessibilityPanel()
    panel.set_report(report)
    panel.resize(420, 300)
    panel.show()
    application.processEvents()
    desktop = output / "accessibility_qa_desktop.png"
    panel.grab().save(str(desktop), "PNG")
    panel.resize(244, 300)
    application.processEvents()
    compact = output / "accessibility_qa_compact.png"
    panel.grab().save(str(compact), "PNG")
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "desktop": str(desktop),
                "compact": str(compact),
                "report": str(report_path),
                "issue_count": len(report["issues"]),
            },
            ensure_ascii=False,
        )
    )
    panel.close()
    panel.deleteLater()
    application.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
