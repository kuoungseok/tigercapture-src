"""Capture Painter UI Find/Replace evidence at desktop and compact sizes."""
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

    from app.drawing import _PAINT_DIALOG_QSS
    from app.font_fallback import apply_ui_font
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_find_replace_dialog import (
        PainterUIFindReplaceDialog,
    )

    application = QApplication.instance() or QApplication([])
    apply_ui_font(application)
    application.setStyleSheet(_PAINT_DIALOG_QSS)
    document = create_ui_document(1000, 650)
    document, _row = add_ui_object(
        document,
        kind="text",
        name="Product title",
        content={"text": "Product overview"},
    )
    document, _row = add_ui_object(
        document,
        kind="image",
        name="Product image",
        content={"source_path": "assets/product/hero.png"},
    )
    output = (
        ROOT / "debugCapture" / "painter_ui_designer" / "find_replace"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (540, 520)), ("compact", (420, 560))):
        dialog = PainterUIFindReplaceDialog()
        dialog.set_document(document)
        dialog.find_edit.setText("Product")
        dialog.replace_edit.setText("Library")
        dialog.resize(*size)
        dialog.show()
        application.processEvents()
        report = dialog.preview()
        application.processEvents()
        path = output / f"find_replace_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and report
                and report["match_count"] == 2
                and dialog.apply_button.isEnabled()
                and dialog.results.count() == 2
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        application.processEvents()

    report = {
        "schema": "tigerstudio.painter.ui.find_replace.qa.v1",
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
