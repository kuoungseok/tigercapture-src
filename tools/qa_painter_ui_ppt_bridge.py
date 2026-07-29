"""Capture Painter UI transferred into the shared PPT Maker."""
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
    from app.painter_ui_ppt_bridge import painter_ui_to_ppt_deck
    from app.painter_ui_templates import instantiate_ui_template
    from app.pptgen.ui.window import PptGeneratorWindow
    from app.pptgen.writer_ooxml import write_pptx

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "ppt_delivery"
    )
    output.mkdir(parents=True, exist_ok=True)
    document, _template = instantiate_ui_template("saas_dashboard")
    deck, bridge = painter_ui_to_ppt_deck(
        document,
        scope="all_artboards",
        asset_dir=output / "assets",
        title="Painter UI Presentation",
    )
    pptx = write_pptx(deck, output / "painter_ui_presentation.pptx")
    window = PptGeneratorWindow(deck=deck)
    window.resize(1280, 800)
    window.show()
    app.processEvents()
    screenshot = output / "painter_ui_in_ppt_maker.png"
    saved = window.grab().save(str(screenshot), "PNG")
    report = {
        "schema": "tigerstudio.painter.ui.ppt_bridge.qa.v1",
        "ok": bool(
            saved
            and pptx.is_file()
            and pptx.stat().st_size > 1000
            and window.slide_list.count() == len(deck.slides)
            and window.canvas.slide is not None
        ),
        "bridge": bridge,
        "screenshot": str(screenshot),
        "pptx": str(pptx),
        "window_size": [window.width(), window.height()],
    }
    report_path = output / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": report["ok"], "report": str(report_path)}))
    window.close()
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
