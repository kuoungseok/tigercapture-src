"""Per-section wall-clock breakdown of one click (selection change).

cProfile over-weights high-call-count helpers here, so this wraps the handful
of calls _refresh_painter_ui_overlay actually makes and reports perf_counter
totals instead.
"""
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


def wrap_mod(mod, name, label=None):
    m = __import__("app." + mod, fromlist=["x"])
    if not hasattr(m, name):
        print(f"  !! missing {mod}.{name}")
        return
    setattr(m, name, _timed(getattr(m, name), label or f"{mod}.{name}"))


def wrap_obj(obj, name, label):
    if obj is None or not hasattr(obj, name):
        print(f"  !! missing {label}")
        return
    setattr(obj, name, _timed(getattr(obj, name), label))


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

wrap_mod("painter_ui_document", "select_ui_object", "select_ui_object")
wrap_mod("painter_ui_document", "active_ui_page_document", "active_ui_page_document")
wrap_mod("painter_ui_document", "normalize_ui_document", "!! normalize_ui_document")
wrap_mod("painter_ui_document", "validate_ui_document", "!! validate_ui_document")
wrap_mod("painter_ui_themes", "resolve_ui_theme_document", "resolve_ui_theme_document")
wrap_mod("painter_ui_motion_delivery", "motion_delivery_report", "motion_delivery_report")
wrap_mod("painter_ui_motion_bridge", "inspect_motion_binding_links", "inspect_motion_binding_links")
wrap_mod("painter_ui_motion_actor", "motion_actor_rows", "motion_actor_rows")
wrap_mod("painter_ui_layout_diagnostics", "diagnose_ui_layout", "!! diagnose_ui_layout")

for name in (
    "_painter_ui_refresh_inputs",
    "_painter_ui_stress_preview_document",
    "_refresh_painter_umg_widget_view",
    "_sync_painter_ui_image_context",
    "_painter_ui_edit_scope_state",
    "_sync_painter_ui_quick_properties",
    "_sync_painter_ui_vector_context",
    "_sync_painter_ui_boolean_context",
    "_normalize_painter_ui_artboard_viewports",
    "_painter_ui_active_page_title",
    "_painter_ui_linked_motion_id",
):
    wrap_obj(d, name, name)

overlay = getattr(d, "_painter_ui_overlay", None)
for name in ("set_document", "set_edit_scope", "set_motion_actor_sources", "set_prototype_preview"):
    wrap_obj(overlay, name, "overlay." + name)

insp = getattr(d, "_paint_ui_inspector", None)
for name in (
    "set_document",
    "set_hierarchy_document",
    "set_stress_preview_report",
    "set_motion_delivery_report",
    "set_motion_binding_report",
    "set_prototype_preview_state",
):
    wrap_obj(insp, name, "inspector." + name)

wrap_obj(getattr(d, "_painter_ui_navigator", None), "set_document", "navigator.set_document")
wrap_obj(getattr(d, "_painter_ui_quick_actions", None), "set_document", "quick_actions.set_document")
wrap_obj(getattr(d, "_painter_ui_selection_breadcrumb", None), "set_document", "breadcrumb.set_document")

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
    for k, v in tot.most_common(14):
        if v < 1.0:
            continue
        print(f"  {v:8.1f} ms  x{cnt[k]:<4d} {k}")
    print(f"  {wall - tot['_painter_ui_refresh_inputs'] :8s}" if False else "")
print(f"\nbest {min(walls):.0f} ms  mean {sum(walls) / len(walls):.0f} ms")
