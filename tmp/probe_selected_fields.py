"""cProfile a single _sync_selected_fields call (the inspector's hot half)."""
import cProfile
import os
import pstats
import sys
import io

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

target = sys.argv[1] if len(sys.argv) > 1 else "selected"
insp = d._paint_ui_inspector
if target == "selected":
    fn = lambda: insp._sync_selected_fields()  # noqa: E731
elif target == "production":
    fn = lambda: insp.production_panel.set_document(insp._document, normalize=False)  # noqa: E731
elif target == "artboard":
    fn = lambda: insp._sync_artboard_layout_fields()  # noqa: E731
elif target == "overlay":
    ov = d._painter_ui_overlay
    canvas_doc = ov._document
    fn = lambda: ov.set_document(canvas_doc, normalize=False)  # noqa: E731
elif target == "complib":
    fn = lambda: insp.component_library.set_document(insp._document, normalize=False)  # noqa: E731
else:
    raise SystemExit("unknown target")

fn()
p = cProfile.Profile()
p.enable()
for _ in range(3):
    fn()
p.disable()
s = io.StringIO()
pstats.Stats(p, stream=s).sort_stats("cumulative").print_stats(28)
print("\n".join(s.getvalue().splitlines()[:44]))
s2 = io.StringIO()
pstats.Stats(p, stream=s2).sort_stats("tottime").print_stats(14)
print("\n".join(s2.getvalue().splitlines()[4:26]))
