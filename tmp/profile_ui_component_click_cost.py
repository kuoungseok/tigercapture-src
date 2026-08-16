"""Measure selection-change (click) cost specifically for COMPONENT_INSTANCE rows.

Companion to profile_ui_click_cost.py, which samples plain objects. Instance
rows (component_role == 'instance') may hit a slower path (component library
highlight scan, override panel, Figma compat panel) that plain clicks don't.
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOC = ROOT / "tmp" / "auto_layout_playground.json"
IMAGES = ROOT / "external/assets/figma/compat_corpus/nightly/grida.auto-layout.archive/extracted/images"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clicks", type=int, default=6)
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_figma import import_figma_json
    QApplication.instance() or QApplication([])
    d = PaintDialog(background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
                    initial_strokes=[], time_ms=0, standalone=True)
    ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
    image_dir = None if args.no_images or not IMAGES.is_dir() else IMAGES
    doc, _ = import_figma_json(DOC, image_dir=image_dir)
    d._painter_ui_document = doc
    insts = [r for r in doc["objects"] if r.get("component_role") == "instance"]
    ids = [r["id"] for r in insts[: args.clicks]]
    print(f"objects {len(doc['objects'])}, instance rows {len(insts)}, clicking {len(ids)}")
    timings = []
    for oid in ids:
        t = time.perf_counter()
        d._select_painter_ui_object(oid) if hasattr(d, "_select_painter_ui_object") else \
            d._set_painter_ui_selection([oid])
        timings.append((time.perf_counter() - t) * 1000)
    for i, ms in enumerate(timings):
        print(f"  click {i+1:<3d}{'':26s}{ms:9.1f} ms")
    print(f"\n  best {min(timings):.1f} ms | mean {sum(timings)/len(timings):.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
