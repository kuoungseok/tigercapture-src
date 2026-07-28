from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.i18n import current_language, initialize, set_language
from app.motion_designer.templates import instantiate_template
from app.motion_designer.ui.template_gallery import MotionTemplateGalleryDialog
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_2026_trend_ui"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    initialize()
    set_language("en")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    composition = instantiate_template(
        "liquid_glass_app_promo",
        variant="16:9",
    )
    window = MotionDesignerWindow(composition)
    window.resize(1520, 920)
    window.show()
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.project_and_viewer.setSizes([280, 920])
    window.timeline.set_time_and_emit(6000)
    app.processEvents()
    workspace_path = OUTPUT / "motion_designer_trend_workspace.png"
    workspace_ok = window.grab().save(str(workspace_path), "PNG")

    gallery = MotionTemplateGalleryDialog(window, variant="16:9")
    gallery.resize(1180, 760)
    category_index = gallery.category.findText("2026 Trends")
    gallery.category.setCurrentIndex(category_index)
    gallery.show()
    app.processEvents()
    gallery_path = OUTPUT / "trend_template_gallery.png"
    gallery_ok = gallery.grab().save(str(gallery_path), "PNG")
    trend_count = gallery.items.count()

    report = {
        "schema": "tigerstudio.motion.2026_trend_ui_qa.v1",
        "ok": bool(
            workspace_ok
            and gallery_ok
            and workspace_path.is_file()
            and workspace_path.stat().st_size > 0
            and gallery_path.is_file()
            and gallery_path.stat().st_size > 0
            and trend_count == 7
        ),
        "workspace": str(workspace_path),
        "gallery": str(gallery_path),
        "gallery_trend_template_count": trend_count,
        "source": "real_qt_motion_designer_window",
        "ui_language": current_language(),
        "toolbar_templates_label": window.toolbar.templates_button.text(),
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    gallery.close()
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
