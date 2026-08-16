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
template = report["template"]
button = next(row for row in document["objects"] if row["name"] == "Primary CTA")
document["selection"] = {"object_id": button["id"], "object_ids": [button["id"]]}

view = PainterUMGWidgetView()
view.set_document(document)
view.resize(1240, 780)
view.show()
app.processEvents()

target_preview = view.target_pane.preview
before = target_preview.grab()
before.save(str(ROOT / "debugCapture" / "umg_pan_before.png"))

target_preview.pan_view(dx=-2000.0, dy=-2000.0)
app.processEvents()
after = target_preview.grab()
after.save(str(ROOT / "debugCapture" / "umg_pan_after.png"))

target_preview.pan_view(dx=2000.0, dy=2000.0)
app.processEvents()
restored = target_preview.grab()
restored.save(str(ROOT / "debugCapture" / "umg_pan_restored.png"))

print("view_state after big pan:", target_preview.view_state())
print("effective object count:", len(target_preview._effective_document.get("objects", [])))
