"""Measure the per-move cost of a large Painter UI document.

Companion to profile_ui_edit_cost.py, which times the read-only calls a single
edit performs. This one times the edit itself.

Measurement rules that this script exists to enforce (see the perf handoff
memory -- getting these wrong once produced a 46x-optimistic number):

  * Every timed iteration must MUTATE the document. Repeating an edit with the
    same payload re-enters the resolved-document cache and reads tens of times
    faster than the real thing. Each move here uses a fresh coordinate.
  * The moved object must be one this script created. Every object already in
    the playground import is a component source, so moving one fails
    validation with invalid_component_instance_source.

Usage:
    .venv/Scripts/python.exe tmp/profile_ui_move_cost.py [--profile] [--moves N]
"""

from __future__ import annotations

import argparse
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


def _build_dialog(use_images: bool = True):
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_figma import import_figma_json

    QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})

    start = time.perf_counter()
    image_dir = IMAGES if (use_images and IMAGES.is_dir()) else None
    print(f"images{'':34s}{'on' if image_dir else 'off':>9s}")
    document, _report = import_figma_json(DOC, image_dir=image_dir)
    print(f"import{'':34s}{(time.perf_counter() - start) * 1000:9.1f} ms")
    print(
        f"objects {len(document['objects'])}, "
        f"artboards {len(document['artboards'])}"
    )
    dialog._painter_ui_document = document
    return dialog


def _add_probe_object(dialog) -> str:
    """Add a plain rectangle to move. Import rows are all component sources."""
    from app.painter_ui_document import add_ui_object

    document, row = add_ui_object(
        dialog._painter_ui_document,
        kind="rectangle",
        name="perf probe",
        x=40.0,
        y=40.0,
        width=120.0,
        height=48.0,
    )
    dialog._painter_ui_document = document
    object_id = str(row["id"])
    print(f"probe object {object_id}\n")
    return object_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--moves", type=int, default=5)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip the image sidecar. Required when A/B-ing against a "
        "worktree that does not carry the extracted assets.",
    )
    args = parser.parse_args()

    dialog = _build_dialog(use_images=not args.no_images)
    object_id = _add_probe_object(dialog)

    print(f"move timings ({args.moves} distinct coordinates):")
    timings = []
    for i in range(args.moves):
        start = time.perf_counter()
        dialog._move_painter_ui_object(object_id, 60.0 + i * 7.0, 80.0 + i * 5.0)
        elapsed = (time.perf_counter() - start) * 1000.0
        timings.append(elapsed)
        print(f"  move {i + 1:<3d}{'':26s}{elapsed:9.1f} ms")

    best = min(timings)
    worst = max(timings)
    mean = sum(timings) / len(timings)
    print(f"\n  best {best:.1f} ms | mean {mean:.1f} ms | worst {worst:.1f} ms")
    if worst > best * 1.4:
        print("  NOTE: spread is wide -- check for a growth trend, not just noise.")

    if args.profile:
        print("\nprofile of one move:")
        profiler = cProfile.Profile()
        profiler.enable()
        dialog._move_painter_ui_object(object_id, 500.0, 500.0)
        profiler.disable()
        stream = io.StringIO()
        pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(26)
        for line in stream.getvalue().splitlines()[4:38]:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
