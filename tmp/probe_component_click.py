"""Wrap suspect call sites with perf_counter timers and click one instance row."""
from __future__ import annotations
import os, sys, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOC = ROOT / "tmp" / "auto_layout_playground.json"

from PySide6.QtWidgets import QApplication
QApplication.instance() or QApplication([])
from app.actions.registry import ActionRegistry
from app.drawing import PaintDialog, create_blank_paint_pixmap
from app.painter_ui_figma import import_figma_json

timings = {}

def wrap(mod, name):
    orig = getattr(mod, name)
    def f(*a, **k):
        t = time.perf_counter()
        r = orig(*a, **k)
        timings[name] = timings.get(name, 0.0) + (time.perf_counter() - t) * 1000
        return r
    setattr(mod, name, f)

import app.painter_ui_document as D
import app.painter_ui_themes as TH
import app.painter_ui_motion_delivery as MD
import app.painter_ui_motion_bridge as MB
import app.painter_ui_motion_actor as MA
import app.painter_ui_component_library as CL
import app.painter_ui_components as COMP
import app.painter_ui_inspector as INSP
import app.painter_ui_artboard_layout as AL

for mod, names in [
    (D, ["select_ui_object", "active_ui_page_document"]),
    (TH, ["resolve_ui_theme_document"]),
    (MD, ["motion_delivery_report"]),
    (MB, ["inspect_motion_binding_links"]),
    (MA, ["motion_actor_rows"]),
    (AL, ["normalize_ui_artboard_layout"]),
    (COMP, [
        "resolve_ui_component_document",
        "inspect_ui_component_set",
        "inspect_ui_component_instance_overrides",
        "_component_family_members",
        "_component_source_map",
    ]),
]:
    for n in names:
        if hasattr(mod, n):
            wrap(mod, n)

# Inspector.set_document, set_hierarchy_document — wrap the class method
if hasattr(INSP, "PainterUIInspector"):
    cls = INSP.PainterUIInspector
    for n in ["set_document", "set_hierarchy_document", "set_stress_preview_report",
              "set_motion_delivery_report", "set_motion_binding_report",
              "_sync_selected_fields", "_sync_artboard_layout_fields",
              "_sync_layer_hierarchy_lists", "_sync_dev_panel_report",
              "_sync_token_suggestions"]:
        if hasattr(cls, n):
            orig = getattr(cls, n)
            def make(n, orig):
                def f(self, *a, **k):
                    t = time.perf_counter()
                    r = orig(self, *a, **k)
                    timings[f"inspector.{n}"] = timings.get(f"inspector.{n}", 0.0) + (time.perf_counter() - t) * 1000
                    return r
                return f
            setattr(cls, n, make(n, orig))

import app.painter_ui_component_library as PCL
import app.painter_ui_style_library as PSL
import app.painter_ui_library_panel as PLP
import app.painter_ui_token_library as PTL
import app.painter_ui_prototype_panel as PPP
import app.painter_ui_production_panel as PRP
import app.painter_ui_comments as PCM

for mod, cls_name in [
    (PCL, "PainterUIComponentLibrary"),
    (PSL, "PainterUIStyleLibrary"),
    (PLP, "PainterUILibraryPanel"),
    (PTL, "PainterUITokenLibrary"),
    (PPP, "PainterUIPrototypePanel"),
    (PRP, "PainterUIProductionPanel"),
    (PCM, "PainterUICommentsPanel"),
]:
    cls = getattr(mod, cls_name, None)
    if cls is not None and hasattr(cls, "set_document"):
        orig = getattr(cls, "set_document")
        def make(n, orig):
            def f(self, *a, **k):
                t = time.perf_counter()
                r = orig(self, *a, **k)
                timings[n] = timings.get(n, 0.0) + (time.perf_counter() - t) * 1000
                return r
            return f
        setattr(cls, "set_document", make(f"{cls_name}.set_document", orig))

d = PaintDialog(background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
                initial_strokes=[], time_ms=0, standalone=True)
ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
doc, _ = import_figma_json(DOC, image_dir=None)
d._painter_ui_document = doc
insts = [r for r in doc["objects"] if r.get("component_role") == "instance"]
oid = insts[0]["id"]
print("clicking instance", oid)

timings.clear()
t0 = time.perf_counter()
d._select_painter_ui_object(oid)
total = (time.perf_counter() - t0) * 1000
print(f"TOTAL {total:.1f} ms")
for n, ms in sorted(timings.items(), key=lambda x: -x[1]):
    print(f"  {n:<40s} {ms:9.1f} ms")
