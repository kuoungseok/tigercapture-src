"""Time the Painter UI operations the canvas actually performs.

The earlier harness timed _move_painter_ui_object, which has no production
caller. The canvas emits its edits from mouseReleaseEvent into the slots
connected in drawing.py, so those slots are what a user's action really costs.
Note the drag itself edits nothing -- mouseMoveEvent emits no document change
except alt-drag duplicate, which is why that one is measured separately.
"""
from __future__ import annotations
import argparse, os, sys, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DOC = ROOT / "tmp" / "auto_layout_playground.json"


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=3)
    args = ap.parse_args()
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_figma import import_figma_json
    from app.painter_ui_document import add_ui_object
    QApplication.instance() or QApplication([])
    d = PaintDialog(background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
                    initial_strokes=[], time_ms=0, standalone=True)
    ActionRegistry(owner=d).execute("paint.ui.workspace.set", {"mode": "ui_design"})
    doc, _ = import_figma_json(DOC, image_dir=None)
    d._painter_ui_document = doc
    print(f"objects {len(doc['objects'])}, artboards {len(doc['artboards'])}\n")

    probes = []
    for i in range(5):
        doc, row = add_ui_object(d._painter_ui_document, kind="rectangle",
                                 name=f"probe{i}", x=40 + i * 30, y=40,
                                 width=120, height=48)
        d._painter_ui_document = doc
        probes.append(str(row["id"]))
    pid = probes[0]

    page = d._painter_ui_document["active_page_id"]
    boards = {r["id"] for r in d._painter_ui_document["artboards"] if r["page_id"] == page}
    existing = [r["id"] for r in d._painter_ui_document["objects"]
                if r["artboard_id"] in boards][:args.reps]

    def bench(label, fn):
        times = []
        for i in range(args.reps):
            t = time.perf_counter()
            fn(i)
            times.append((time.perf_counter() - t) * 1000)
        print(f"  {label:44s} best {min(times):8.1f} ms   mean {sum(times)/len(times):8.1f} ms")

    print("실제 조작 (드래그 중이 아니라 '놓는 순간' 1회씩):")
    bench("드롭: 위치+크기 1개 (geometry)",
          lambda i: d._update_painter_ui_object_geometry(pid, 60.0 + i * 9, 80.0 + i * 7, 120.0, 48.0))
    bench("드롭: 다중선택 5개 (batch)",
          lambda i: d._update_painter_ui_objects_batch(
              {p: {"x": 50.0 + i * 11 + j * 5, "y": 90.0 + i * 6} for j, p in enumerate(probes)}))
    bench("클릭 선택",
          lambda i: d._select_painter_ui_object(existing[i % len(existing)]))
    bench("alt-드래그 복제 (mouseMove 중 발생)",
          lambda i: d._duplicate_painter_ui_selection_for_drag([pid]))
    bench("오브젝트 생성",
          lambda i: d._create_painter_ui_object_from_rect("rectangle", 200.0 + i * 15, 300.0, 80.0, 40.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
