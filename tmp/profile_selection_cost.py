"""Profile app.actions 'paint.ui.selection.set' cost on a large document."""
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARTBOARD_COUNT = 100
OBJECTS_PER_ARTBOARD = 150


def _large_document() -> dict:
    from app.painter_ui_document import create_ui_document, normalize_ui_document

    document = create_ui_document(1440, 900, name="Desktop 1")
    document["pages"] = []
    document["artboards"] = []
    document["objects"] = []
    pages = 5
    artboards_per_page = ARTBOARD_COUNT // pages
    for page_index in range(pages):
        page_id = f"page-{page_index + 1}"
        first_artboard_id = f"artboard-{page_index * artboards_per_page + 1}"
        document["pages"].append(
            {
                "id": page_id,
                "name": f"Flow {page_index + 1}",
                "active_artboard_id": first_artboard_id,
            }
        )
        for artboard_offset in range(artboards_per_page):
            artboard_index = page_index * artboards_per_page + artboard_offset
            artboard_id = f"artboard-{artboard_index + 1}"
            document["artboards"].append(
                {
                    "id": artboard_id,
                    "page_id": page_id,
                    "name": f"Screen {artboard_index + 1}",
                    "width": 1440,
                    "height": 900,
                    "x": float(artboard_offset * 1560),
                    "y": float(page_index * 1200),
                    "background": "#F7F9FC",
                    "breakpoint": "desktop",
                }
            )
            for object_offset in range(OBJECTS_PER_ARTBOARD):
                object_index = artboard_index * OBJECTS_PER_ARTBOARD + object_offset
                column = object_offset % 10
                row = object_offset // 10
                document["objects"].append(
                    {
                        "id": f"ui-object-{object_index + 1}",
                        "artboard_id": artboard_id,
                        "name": f"Card {object_index + 1}",
                        "kind": "rectangle",
                        "x": 24.0 + column * 130.0,
                        "y": 24.0 + row * 60.0,
                        "width": 110.0,
                        "height": 44.0,
                        "style": {
                            "fill": "#DDE8F5" if row % 2 == 0 else "#E9EDF4",
                            "stroke": "#A7B5C8",
                            "stroke_width": 1.0,
                            "radius": 6.0,
                        },
                    }
                )
    document["active_page_id"] = "page-1"
    document["active_artboard_id"] = "artboard-1"
    return normalize_ui_document(document)


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.font_fallback import apply_ui_font

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})

    document = _large_document()
    print(f"object_count={len(document['objects'])} artboard_count={len(document['artboards'])}")
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()

    object_ids = [row["id"] for row in document["objects"][:20]]

    # Warm-up call (first selection after load always cold - not what we care about).
    registry.execute("paint.ui.selection.set", {"object_ids": [object_ids[0]]})

    # Timed selections: alternate between two different objects on the SAME
    # active artboard/page, simulating repeated clicks in the layers panel.
    timings = []
    for object_id in object_ids[1:]:
        started = time.perf_counter()
        registry.execute("paint.ui.selection.set", {"object_ids": [object_id]})
        timings.append((time.perf_counter() - started) * 1000.0)
    print("per-selection ms:", [round(value, 1) for value in timings])
    print(f"avg ms: {sum(timings) / len(timings):.2f}, max ms: {max(timings):.2f}")

    # cProfile a single selection call to see where time actually goes.
    profiler = cProfile.Profile()
    profiler.enable()
    registry.execute("paint.ui.selection.set", {"object_ids": [object_ids[2]]})
    profiler.disable()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(20)
    print(stream.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
