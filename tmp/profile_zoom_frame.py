"""Profile one Painter UI canvas frame at a given zoom, warm and cold.

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/profile_zoom_frame.py 400
"""
from __future__ import annotations

import cProfile
import os
import pstats
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from measure_artboard_surface_zoom import (  # noqa: E402
    WIDGET_HEIGHT,
    WIDGET_WIDTH,
    build_document,
)


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    zoom = float(sys.argv[1]) if len(sys.argv) > 1 else 400.0
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    overlay = PainterUIDesignOverlay()
    overlay.resize(WIDGET_WIDTH, WIDGET_HEIGHT)
    overlay.set_document(build_document())
    board = overlay._document["artboards"][0]
    frame = QImage(overlay.size(), QImage.Format.Format_ARGB32_Premultiplied)
    scale = zoom / 100.0

    def place(pan: float) -> None:
        overlay._view_scale = scale
        overlay._view_offset = QPointF(
            -float(board["x"]) * scale + 40.0 - pan,
            -float(board["y"]) * scale + 40.0,
        )

    def timed(pan: float) -> float:
        place(pan)
        started = time.perf_counter()
        overlay.render(frame)
        return (time.perf_counter() - started) * 1000.0

    print(f"zoom {zoom:.0f}%  cold frame {timed(0.0):.1f} ms")
    print(f"zoom {zoom:.0f}%  warm frame {timed(4.0):.1f} ms")

    for label, pan in (("cold", 512.0), ("warm", 516.0)):
        profiler = cProfile.Profile()
        place(pan)
        profiler.enable()
        overlay.render(frame)
        profiler.disable()
        print(f"\n===== {label} frame (pan {pan}) =====")
        stats = pstats.Stats(profiler)
        stats.sort_stats("cumulative").print_stats(14)

    overlay.close()
    overlay.deleteLater()
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
