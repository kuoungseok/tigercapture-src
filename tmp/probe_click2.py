"""Drill into the three sections probe_click.py flagged: inspector.set_document,
overlay.set_document and resolve_ui_theme_document."""
import collections
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = "E:/ClaudeCodeApp/GifCam"
sys.path.insert(0, ROOT)

tot = collections.Counter()
cnt = collections.Counter()


def _timed(orig, label):
    def f(*a, **k):
        t = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            tot[label] += (time.perf_counter() - t) * 1000
            cnt[label] += 1

    return f


def wrap_obj(obj, name, label):
    if obj is None or not hasattr(obj, name):
        print(f"  !! missing {label}")
        return
    setattr(obj, name, _timed(getattr(obj, name), label))


def wrap_mod(mod, name, label=None):
    m = __import__("app." + mod, fromlist=["x"])
    if not hasattr(m, name):
        print(f"  !! missing {mod}.{name}")
        return
    setattr(m, name, _timed(getattr(m, name), label or f"{mod}.{name}"))


from PySide6.QtWidgets import QApplication  # noqa: E402
from app.actions.registry import ActionRegistry  # noqa: E402
from app.drawing import PaintDialog, create_blank_paint_pixmap  # noqa: E402
from app.painter_ui_figma import import_figma_json  # noqa: E402

QApplication.instance() or QApplication([])
d = PaintDialog(
    background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
    initial_strokes=[],
    time_ms=0,
    standalone=True,
)
ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
doc, _ = import_figma_json(ROOT + "/tmp/auto_layout_playground.json", image_dir=None)
d._painter_ui_document = doc
page = doc["active_page_id"]
boards = {r["id"] for r in doc["artboards"] if r["page_id"] == page}
ids = [r["id"] for r in doc["objects"] if r["artboard_id"] in boards][:8]
d._select_painter_ui_object(ids[0])

insp = d._paint_ui_inspector
for name in (
    "_sync_token_suggestions",
    "_sync_dev_panel_report",
    "_sync_artboard_layout_fields",
    "_sync_layer_hierarchy_lists",
    "_sync_selected_fields",
):
    wrap_obj(insp, name, "insp." + name)
for panel in (
    "comments_panel",
    "component_library",
    "style_library",
    "library_panel",
    "token_library",
    "prototype_panel",
    "production_panel",
):
    wrap_obj(getattr(insp, panel, None), "set_document", f"insp.{panel}.set_document")

wrap_mod("painter_ui_token_suggestion", "suggest_ui_tokens")
wrap_mod("painter_ui_components", "resolve_ui_component_document")
wrap_mod("painter_ui_themes", "_resolved_cache_key", "themes._resolved_cache_key")
wrap_mod("painter_ui_themes", "resolve_ui_theme_document", "THEME resolve_ui_theme_document")
wrap_mod("painter_ui_document", "normalize_ui_document", "!! normalize_ui_document")

overlay = d._painter_ui_overlay
for name in ("set_document",):
    wrap_obj(overlay, name, "overlay." + name)
wrap_obj(insp, "set_document", "INSPECTOR set_document")

reps = int(sys.argv[1]) if len(sys.argv) > 1 else 4
walls = []
for i in range(reps):
    tot.clear()
    cnt.clear()
    t = time.perf_counter()
    d._select_painter_ui_object(ids[1 + i % (len(ids) - 1)])
    wall = (time.perf_counter() - t) * 1000
    walls.append(wall)
    print(f"\n=== click {i + 1}: {wall:.0f} ms ===")
    for k, v in tot.most_common(20):
        if v < 1.0:
            continue
        print(f"  {v:8.1f} ms  x{cnt[k]:<4d} {k}")
print(f"\nbest {min(walls):.0f} ms  mean {sum(walls) / len(walls):.0f} ms")
