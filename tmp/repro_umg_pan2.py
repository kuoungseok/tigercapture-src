import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.font_fallback import apply_ui_font
from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_umg_widget_view import PainterUMGWidgetView

app = QApplication.instance() or QApplication([])
apply_ui_font(app)

document, report = instantiate_ui_template("saas_dashboard")
button = next(row for row in document["objects"] if row["name"] == "Primary CTA")
document["selection"] = {"object_id": button["id"], "object_ids": [button["id"]]}

view = PainterUMGWidgetView()
view.set_document(document)
view.resize(1240, 780)
view.show()
app.processEvents()

target_preview = view.target_pane.preview
start_state = target_preview.view_state()
print("start:", start_state)

for _ in range(200):
    target_preview.pan_view(dx=-10.0, dy=-10.0)
mid_state = target_preview.view_state()
print("after 200x(-10,-10):", mid_state)

for _ in range(200):
    target_preview.pan_view(dx=10.0, dy=10.0)
end_state = target_preview.view_state()
print("after 200x(+10,+10):", end_state)

print("matches start:", abs(end_state["offset_x"] - start_state["offset_x"]) < 0.01
      and abs(end_state["offset_y"] - start_state["offset_y"]) < 0.01)
target_preview.grab().save(str(ROOT / "debugCapture" / "umg_pan_incremental_end.png"))
