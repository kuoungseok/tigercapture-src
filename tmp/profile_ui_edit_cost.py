"""Measure the per-edit cost of a large Painter UI document.

Loads the Auto Layout Playground import into an offscreen PaintDialog and times
the calls a single edit performs, then profiles the slowest one.
"""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DOC = ROOT / "tmp" / "auto_layout_playground.json"
IMAGES = (
    ROOT
    / "external/assets/figma/compat_corpus/nightly/grida.auto-layout.archive/extracted/images"
)


def timed(label, fn, repeat=3):
    best = None
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000.0
        best = elapsed if best is None else min(best, elapsed)
    print(f"  {label:38s} {best:9.1f} ms")
    return best


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_figma import import_figma_json

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})

    start = time.perf_counter()
    document, _report = import_figma_json(DOC, image_dir=IMAGES if IMAGES.is_dir() else None)
    print(f"import                                   {(time.perf_counter()-start)*1000:9.1f} ms")
    print(f"objects {len(document['objects'])}, artboards {len(document['artboards'])}\n")

    dialog._painter_ui_document = document

    print("per-edit calls:")
    timed("painter_action_state()", dialog.painter_action_state)
    timed("_refresh_painter_ui_overlay()", dialog._refresh_painter_ui_overlay)
    timed("_snapshot_state()", dialog._snapshot_state)

    print("\nprofile of painter_action_state():")
    profiler = cProfile.Profile()
    profiler.enable()
    dialog.painter_action_state()
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(22)
    for line in stream.getvalue().splitlines()[4:34]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
