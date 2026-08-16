"""cProfile a whole click, now that the big whole-document walks are gone."""
import cProfile
import io
import os
import pstats
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = "E:/ClaudeCodeApp/GifCam"
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication  # noqa: E402
from app.actions.registry import ActionRegistry  # noqa: E402
from app.drawing import PaintDialog, create_blank_paint_pixmap  # noqa: E402
from app.painter_ui_figma import import_figma_json  # noqa: E402

QApplication.instance() or QApplication([])
d = PaintDialog(
    background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
    initial_strokes=[], time_ms=0, standalone=True,
)
ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
doc, _ = import_figma_json(ROOT + "/tmp/auto_layout_playground.json", image_dir=None)
d._painter_ui_document = doc
page = doc["active_page_id"]
boards = {r["id"] for r in doc["artboards"] if r["page_id"] == page}
ids = [r["id"] for r in doc["objects"] if r["artboard_id"] in boards][:8]
d._select_painter_ui_object(ids[0])
d._select_painter_ui_object(ids[1])

p = cProfile.Profile()
p.enable()
for i in range(3):
    d._select_painter_ui_object(ids[2 + i])
p.disable()
s = io.StringIO()
pstats.Stats(p, stream=s).sort_stats("tottime").print_stats(22)
print("\n".join(s.getvalue().splitlines()[:34]))
