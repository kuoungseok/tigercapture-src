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
FRAME_ID = "figma-node-2411-12563"  # one of the two frames named exactly 'Auto layout'


def main() -> None:
    app = QApplication.instance() or QApplication([])
    document, _report = import_fig_file(FIG_PATH)

    objects = {str(o["id"]): o for o in document["objects"]}
    frame = objects[FRAME_ID]
    artboard_id = str(frame["artboard_id"])
    artboards = {str(a["id"]): a for a in document["artboards"]}
    artboard = artboards[artboard_id]
    page_id = str(artboard.get("page_id") or "")
    print("frame artboard_id:", artboard_id, "page_id:", page_id)
    document["active_page_id"] = page_id
    document["active_artboard_id"] = ""

    overlay = PainterUIDesignOverlay()
    overlay.resize(1600, 1100)
    overlay.set_document(document)
    overlay.fit_all()
    app.processEvents()
    overlay.show()
    app.processEvents()
    app.processEvents()

    image = overlay.grab()
    out_path = Path(__file__).with_name("auto_layout_repro_page_overview.png")
    image.save(str(out_path))
    print("saved:", out_path)


if __name__ == "__main__":
    main()
