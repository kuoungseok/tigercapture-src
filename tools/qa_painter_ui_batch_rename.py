"""Capture Painter UI Batch Rename evidence at desktop and compact sizes."""
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
    from app.painter_ui_batch_rename_dialog import (
        PainterUIBatchRenameDialog,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    application = QApplication.instance() or QApplication([])
    apply_ui_font(application)
    document = create_ui_document(1000, 650)
    object_ids = []
    for index in range(3):
        document, row = add_ui_object(
            document,
            kind="group",
            name=f"Card {index + 1}",
            x=80 + index * 220,
            y=160,
        )
        object_ids.append(row["id"])
    output = (
        ROOT / "debugCapture" / "painter_ui_designer" / "batch_rename"
    )
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, size in (("desktop", (500, 560)), ("compact", (420, 580))):
        dialog = PainterUIBatchRenameDialog()
        dialog.set_document(document, object_ids)
        dialog.find_edit.setText("Card")
        dialog.replace_edit.setText("Tile")
        dialog.prefix_edit.setText("UI_")
        dialog.numbering_check.setChecked(True)
        dialog.resize(*size)
        dialog.show()
        application.processEvents()
        report = dialog.preview()
        application.processEvents()
        path = output / f"batch_rename_{label}.png"
        saved = dialog.grab().save(str(path), "PNG")
        results[label] = {
            "ok": bool(
                saved
                and report
                and report["match_count"] == 3
                and dialog.apply_button.isEnabled()
                and dialog.results.count() == 3
            ),
            "screenshot": str(path),
            "size": [dialog.width(), dialog.height()],
        }
        dialog.close()
        dialog.deleteLater()
        application.processEvents()
    report = {
        "schema": "tigerstudio.painter.ui.batch_rename.qa.v1",
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
