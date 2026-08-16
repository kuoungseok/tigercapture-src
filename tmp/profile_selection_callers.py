"""Find exact callers of validate_ui_document / _classification during one selection."""
from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
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

    profiler = cProfile.Profile()
    profiler.enable()
    registry.execute("paint.ui.selection.set", {"object_ids": [object_ids[2]]})
    profiler.disable()

    stats = pstats.Stats(profiler)
    stream = io.StringIO()
    stats.stream = stream
    for name in ("validate_ui_document", "_classification"):
        stream.write(f"\n===== callers of {name} =====\n")
        stats.print_callers(name)
    print(stream.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
