"""Measure what one brush sample costs on the Painter canvas.

Drives DrawingCanvas the way a mouse drag does - press, a run of moves, release
- and times the input handler and the repaint separately, for a few brush
configurations and canvas sizes.

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/measure_paint_stroke_latency.py
"""
from __future__ import annotations

import math
import os
import statistics
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_WIDTH = 1920
DOC_HEIGHT = 1080
VIEW_WIDTH = 1280
VIEW_HEIGHT = 720
SAMPLES = 120
COMMITTED_STROKES = 200


def committed_strokes(count: int):
    from app.drawing import Stroke

    strokes = []
    for index in range(count):
        base = index / max(1, count)
        # Localised scribbles rather than canvas-wide zig-zags: rasterisation
        # cost follows painted area, and a corpus of full-canvas strokes says
        # more about Qt than about the brush path under test.
        origin_x = 0.05 + 0.9 * ((index * 37) % 100) / 100.0
        origin_y = 0.05 + 0.9 * ((index * 61) % 100) / 100.0
        points = [
            (
                min(1.0, max(0.0, origin_x + 0.05 * math.cos(step * 0.9))),
                min(1.0, max(0.0, origin_y + 0.05 * math.sin(step * 1.3))),
            )
            for step in range(12)
        ]
        strokes.append(
            Stroke(
                points=points,
                color=(40 + int(200 * base), 90, 200 - int(150 * base)),
                width_px=6.0,
                point_pressure=[1.0] * len(points),
            )
        )
    return strokes


def make_canvas(strokes, *, dynamics: dict | None = None, embedded: bool = True):
    from PySide6.QtGui import QImage

    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(
        get_time_ms=lambda: 0,
        get_strokes=lambda: strokes,
    )
    if embedded:
        # What the standalone Painter dialog does; it is what turns on the
        # committed-stroke raster cache.
        canvas.set_strokes_snapshot(list(strokes))
    canvas.set_document_size(DOC_WIDTH, DOC_HEIGHT)
    canvas.resize(VIEW_WIDTH, VIEW_HEIGHT)
    canvas.set_tool("pen")
    canvas.set_pen_width(24.0)
    canvas.set_pen_color(canvas._pen_color)
    if dynamics is not None:
        canvas._brush_dynamics = dict(dynamics)
    frame = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)
    return canvas, frame


def drag(canvas, frame, *, samples: int = SAMPLES):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    def event(kind, x, y):
        return QMouseEvent(
            kind,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def position(step: int) -> tuple[float, float]:
        angle = step / samples * math.tau
        return (
            VIEW_WIDTH * 0.5 + math.cos(angle) * VIEW_WIDTH * 0.30,
            VIEW_HEIGHT * 0.5 + math.sin(angle * 1.7) * VIEW_HEIGHT * 0.30,
        )

    x, y = position(0)
    canvas.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress, x, y))
    canvas.render(frame)
    input_ms: list[float] = []
    paint_ms: list[float] = []
    for step in range(1, samples + 1):
        x, y = position(step)
        moved = event(QMouseEvent.Type.MouseMove, x, y)
        started = time.perf_counter()
        canvas.mouseMoveEvent(moved)
        input_ms.append((time.perf_counter() - started) * 1000.0)
        started = time.perf_counter()
        canvas.render(frame)
        paint_ms.append((time.perf_counter() - started) * 1000.0)
    x, y = position(samples)
    started = time.perf_counter()
    canvas.mouseReleaseEvent(
        event(QMouseEvent.Type.MouseButtonRelease, x, y)
    )
    canvas.render(frame)
    release_ms = (time.perf_counter() - started) * 1000.0
    return input_ms, paint_ms, release_ms


def show(label: str, input_ms, paint_ms, release_ms) -> None:
    total = [a + b for a, b in zip(input_ms, paint_ms)]
    print(
        f"{label:<40} sample {statistics.median(input_ms):6.2f} ms   "
        f"paint {statistics.median(paint_ms):6.2f} ms   "
        f"frame {statistics.median(total):6.2f} ms   "
        f"worst {max(total):7.2f} ms   "
        f"last/first sample {input_ms[-1] / max(0.001, input_ms[0]):5.1f}x   "
        f"pen-up {release_ms:7.1f} ms"
    )


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    empty: list = []
    busy = committed_strokes(COMMITTED_STROKES)

    cases = [
        ("plain pen, empty canvas", empty, None, True),
        (f"plain pen, {COMMITTED_STROKES} strokes", busy, None, True),
        (
            f"plain pen, {COMMITTED_STROKES} strokes, no raster cache",
            busy,
            None,
            False,
        ),
        (
            "dynamics on (paint), empty canvas",
            empty,
            {"enabled": True, "mode": "paint"},
            True,
        ),
        (
            f"dynamics on (paint), {COMMITTED_STROKES} strokes",
            busy,
            {"enabled": True, "mode": "paint"},
            True,
        ),
        (
            "dynamics on (smudge), empty canvas",
            empty,
            {"enabled": True, "mode": "smudge"},
            True,
        ),
    ]
    for label, strokes, dynamics, embedded in cases:
        canvas, frame = make_canvas(
            strokes,
            dynamics=dynamics,
            embedded=embedded,
        )
        try:
            show(label, *drag(canvas, frame))
        finally:
            canvas.close()
            canvas.deleteLater()
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
