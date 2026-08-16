"""Dump what gc considers garbage-collectable (cyclic) after the selection loop."""
from __future__ import annotations

import gc
import os
import sys
import time
from collections import Counter
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tmp"))
from profile_selection_cost import _large_document  # noqa: E402


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
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()

    object_ids = [row["id"] for row in document["objects"][:20]]
    registry.execute("paint.ui.selection.set", {"object_ids": [object_ids[0]]})

    gc.collect()
    counts_before = Counter(type(o).__name__ for o in gc.get_objects())

    for object_id in object_ids[1:]:
        registry.execute("paint.ui.selection.set", {"object_ids": [object_id]})

    # How many objects gen0/1/2 are holding right before a collection would fire,
    # and how many of those are actually unreachable-but-for-cycles garbage.
    gc.set_debug(gc.DEBUG_SAVEALL)
    unreachable = gc.collect()
    garbage_types = Counter(type(o).__name__ for o in gc.garbage)
    gc.set_debug(0)
    gc.garbage.clear()

    counts_after = Counter(type(o).__name__ for o in gc.get_objects())
    grew = (counts_after - counts_before)

    print(f"unreachable_cyclic_objects_collected={unreachable}")
    print("top cyclic garbage types:", garbage_types.most_common(15))
    print("top object-count growth by type since warmup:", grew.most_common(15))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
