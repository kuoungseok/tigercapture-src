"""Measure Painter UI canvas frames the way a wheel zoom or a drag produces them.

Drives the real view API so the gesture path is exercised, renders every frame
synchronously and reports the per-frame wall clock.

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/measure_gesture_frames.py
"""
from __future__ import annotations

import os
import statistics
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

ZOOM_NOTCHES = 14
ZOOM_STEP = 1.15
PAN_FRAMES = 24
PAN_STEP = -26.0


def report(label: str, samples: list[float], approximated: int) -> None:
    over = [value for value in samples if value > 10.0]
    print(
        f"{label:<34} median {statistics.median(samples):6.1f} ms   "
        f"max {max(samples):6.1f} ms   "
        f">10ms {len(over)}/{len(samples)}   "
        f"stand-in frames {approximated}"
    )


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from app.painter_ui_workspace import PainterUIDesignOverlay

    app = QApplication.instance() or QApplication([])
    overlay = PainterUIDesignOverlay()
    overlay.resize(WIDGET_WIDTH, WIDGET_HEIGHT)
    overlay.set_document(build_document())
    frame = QImage(overlay.size(), QImage.Format.Format_ARGB32_Premultiplied)
    anchor = QPointF(WIDGET_WIDTH * 0.5, WIDGET_HEIGHT * 0.5)

    def draw() -> tuple[float, bool]:
        started = time.perf_counter()
        overlay.render(frame)
        elapsed = (time.perf_counter() - started) * 1000.0
        used = bool(
            overlay._last_paint_metrics.get("approximate_artboard_count")
        )
        return elapsed, used

    def sweep(label: str, steps, *, settle: bool = True) -> None:
        overlay._end_view_gesture()
        draw()  # settled starting frame, not counted
        samples: list[float] = []
        approximated = 0
        for step in steps:
            step()
            elapsed, used = draw()
            samples.append(elapsed)
            approximated += int(used)
        report(label, samples, approximated)
        if settle:
            overlay._end_view_gesture()
            settled, _used = draw()
            print(f"{'  settle frame after gesture':<34} {settled:6.1f} ms")

    overlay.set_view_state(
        {"zoom_percent": 100.0, "center_x": 700.0, "center_y": 450.0},
        emit=False,
    )
    sweep(
        "wheel zoom in (x1.15 a notch)",
        [
            lambda: overlay.set_zoom_percent(
                overlay.view_state()["zoom_percent"] * ZOOM_STEP,
                anchor=anchor,
            )
            for _index in range(ZOOM_NOTCHES)
        ],
    )
    sweep(
        "wheel zoom out (/1.15 a notch)",
        [
            lambda: overlay.set_zoom_percent(
                overlay.view_state()["zoom_percent"] / ZOOM_STEP,
                anchor=anchor,
            )
            for _index in range(ZOOM_NOTCHES)
        ],
    )
    overlay.set_zoom_percent(400.0, anchor=anchor)
    sweep(
        "drag pan at 400% (26px a frame)",
        [lambda: overlay.pan_view(dx=PAN_STEP) for _index in range(PAN_FRAMES)],
    )
    overlay.set_zoom_percent(100.0, anchor=anchor)
    sweep(
        "drag pan at 100% (26px a frame)",
        [lambda: overlay.pan_view(dx=PAN_STEP) for _index in range(PAN_FRAMES)],
    )
    # Panning across a board that has never been rasterised is the one case a
    # stand-in cannot cover, so measure it deliberately.
    overlay.set_zoom_percent(30.0, anchor=anchor)
    sweep(
        "drag pan at 30% (new boards enter)",
        [
            lambda: overlay.pan_view(dx=PAN_STEP * 6.0)
            for _index in range(PAN_FRAMES)
        ],
    )
    overlay.set_zoom_percent(8.0, anchor=anchor)
    sweep(
        "drag pan at 8% (overview LOD)",
        [
            lambda: overlay.pan_view(dx=PAN_STEP * 4.0)
            for _index in range(PAN_FRAMES)
        ],
    )

    overlay.close()
    overlay.deleteLater()
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
