"""Regenerate desktop and compact Painter UI template-search evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.drawing import _PAINT_DIALOG_QSS
from app.painter_ui_template_gallery import PainterUITemplateGalleryDialog
from app.painter_ui_template_insert import insert_ui_template
from app.painter_ui_template_store import search_ui_templates
from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_document import create_ui_document


def main() -> int:
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(_PAINT_DIALOG_QSS)
    root = (
        Path("debugCapture")
        / "painter_ui_designer"
        / "template_search"
    ).resolve()
    root.mkdir(parents=True, exist_ok=True)
    dialog = PainterUITemplateGalleryDialog()
    dialog.search_edit.setText("dashboard")
    dialog.platform_combo.setCurrentText("Desktop")
    dialog.insert_mode_combo.setCurrentIndex(
        dialog.insert_mode_combo.findData("page")
    )
    dialog.show()
    app.processEvents()

    dialog.resize(1120, 720)
    app.processEvents()
    dialog.grab().save(str(root / "template_search_desktop.png"))

    dialog.resize(760, 620)
    app.processEvents()
    dialog.grab().save(str(root / "template_search_compact.png"))

    source, _source_report = instantiate_ui_template("saas_dashboard")
    _document, insert_report = insert_ui_template(
        create_ui_document(390, 844),
        source,
        template_id="saas_dashboard",
        mode="page",
    )
    report = {
        "search": search_ui_templates(
            query="dashboard",
            platform="desktop",
        ),
        "insert": insert_report,
    }
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dialog.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
