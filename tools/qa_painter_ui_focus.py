"""Capture keyboard-focus QA for desktop and compact Painter UI Design."""
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
    from PySide6.QtWidgets import QApplication, QAbstractButton

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font
    from app.painter_ui_focus_audit import inspect_painter_ui_focus
    from app.painter_ui_focus_audit_dialog import PainterUIFocusAuditDialog

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    output = ROOT / "debugCapture" / "painter_ui_designer" / "focus"
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (1360, 900)), ("compact", (900, 700))):
        dialog = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1440,
                900,
                "transparent",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        dialog.resize(*size)
        dialog.show()
        dialog._set_canvas_workspace_mode("ui_design")
        app.processEvents()
        button = next(
            control
            for control in dialog.findChildren(QAbstractButton)
            if "Quick Actions" in control.toolTip()
        )
        button.setFocus()
        app.processEvents()
        audit = inspect_painter_ui_focus(dialog)
        screenshot = output / f"focus_{label}.png"
        focus_crop = output / f"focus_{label}_control.png"
        saved = dialog.grab().save(str(screenshot), "PNG")
        crop_saved = button.grab().save(str(focus_crop), "PNG")
        focus_visible = button.hasFocus()

        audit_dialog = PainterUIFocusAuditDialog()
        audit_dialog.set_report(audit)
        audit_dialog.resize(620 if label == "desktop" else 420, 480)
        audit_dialog.show()
        app.processEvents()
        audit_path = output / f"focus_{label}_audit.png"
        audit_saved = audit_dialog.grab().save(str(audit_path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and crop_saved
                and audit_saved
                and focus_visible
                and audit["status"] == "covered"
            ),
            "size": [dialog.width(), dialog.height()],
            "screenshot": str(screenshot),
            "focus_control": str(focus_crop),
            "audit_screenshot": str(audit_path),
            "audit": audit,
        }
        audit_dialog.close()
        dialog.close()
        audit_dialog.deleteLater()
        dialog.deleteLater()
        app.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.focus.qa.v1",
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
