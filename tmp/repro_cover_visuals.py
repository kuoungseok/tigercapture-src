from __future__ import annotations

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from PySide6.QtWidgets import QApplication

from app.painter_ui_figma import import_fig_file
from app.painter_ui_workspace import PainterUIDesignOverlay

FIG_PATH = Path.home() / "Downloads" / "Figma auto layout playground (Community).fig"
ARTBOARD_ID = "figma-artboard-2411-13170"  # the page-title 'Auto Layout' cover artboard


def main() -> None:
    app = QApplication.instance() or QApplication([])
    document, _report = import_fig_file(FIG_PATH)

    artboards = {str(a["id"]): a for a in document["artboards"]}
    artboard = artboards[ARTBOARD_ID]
    page_id = str(artboard.get("page_id") or "")
    for page in document["pages"]:
        if str(page["id"]) == page_id:
            page["active_artboard_id"] = ARTBOARD_ID
    document["active_page_id"] = page_id
    document["active_artboard_id"] = ARTBOARD_ID

    overlay = PainterUIDesignOverlay()
    overlay.resize(1400, 900)
    overlay.set_document(document)
    overlay.fit_artboard(ARTBOARD_ID)
    app.processEvents()
    overlay.show()
    app.processEvents()
    app.processEvents()

    out_name = sys.argv[1] if len(sys.argv) > 1 else "cover_visuals.png"
    image = overlay.grab()
    out_path = Path(__file__).with_name(out_name)
    image.save(str(out_path))
    print("saved:", out_path)


if __name__ == "__main__":
    main()
