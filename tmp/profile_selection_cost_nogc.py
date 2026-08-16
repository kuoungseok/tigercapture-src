"""Same as profile_selection_cost.py but with cyclic GC disabled, to test
whether the late-loop timing spike is a GC pause artifact."""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tmp"))
from profile_selection_cost import _large_document  # noqa: E402


def main() -> int:
    gc.disable()
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

    timings = []
    for object_id in object_ids[1:]:
        started = time.perf_counter()
        registry.execute("paint.ui.selection.set", {"object_ids": [object_id]})
        timings.append((time.perf_counter() - started) * 1000.0)
    print("gc.isenabled():", gc.isenabled())
    print("per-selection ms:", [round(v, 1) for v in timings])
    print(f"avg ms: {sum(timings) / len(timings):.2f}, max ms: {max(timings):.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
