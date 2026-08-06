"""Prove the incremental live dynamic preview equals the full-prefix repaint.

Draws the same stroke twice - once with the incremental path, once with it
forced off - and compares the composited canvas after every input sample.

    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/verify_live_dynamic_increment.py
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WIDTH = 640
HEIGHT = 420
SAMPLES = 90


def path_point(index: int) -> tuple[float, float]:
    angle = index / 18.0
    return (
        60.0 + index * 6.0 + math.sin(angle) * 14.0,
        200.0 + math.sin(angle * 0.7) * 90.0,
    )


def draw(dynamics: dict, *, incremental: bool, snapshots: list[int]):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QMouseEvent

    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(get_time_ms=lambda: 0)
    canvas.resize(WIDTH, HEIGHT)
    canvas.set_strokes_snapshot([])
    canvas.set_tool("pen")
    canvas.set_pen_width(26.0)
    canvas._brush_dynamics = dict(dynamics)
    if not incremental:
        canvas._paint_live_dynamic_increment = lambda w, h: False
    frame = QImage(canvas.size(), QImage.Format.Format_ARGB32_Premultiplied)

    def event(kind, x, y):
        return QMouseEvent(
            kind,
            QPointF(x, y),
            QPointF(x, y),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    x, y = path_point(0)
    canvas.mousePressEvent(event(QMouseEvent.Type.MouseButtonPress, x, y))
    shots = {}
    for index in range(1, SAMPLES + 1):
        x, y = path_point(index)
        canvas.mouseMoveEvent(event(QMouseEvent.Type.MouseMove, x, y))
        if index in snapshots:
            frame.fill(0)
            canvas.render(frame)
            shots[index] = frame.copy()
    canvas.close()
    canvas.deleteLater()
    return shots


def compare(left, right) -> tuple[int, int]:
    worst = 0
    differing = 0
    for y in range(left.height()):
        for x in range(left.width()):
            a = left.pixel(x, y)
            b = right.pixel(x, y)
            if a == b:
                continue
            differing += 1
            for shift in (0, 8, 16, 24):
                worst = max(
                    worst,
                    abs(((a >> shift) & 0xFF) - ((b >> shift) & 0xFF)),
                )
    return worst, differing


CASES = {
    "paint, plain": {"enabled": True, "mode": "paint"},
    "paint, scatter+jitter": {
        "enabled": True,
        "mode": "paint",
        "scatter": 65,
        "scatter_count": 3,
        "size_jitter": 50,
        "hue_jitter": 30,
        "value_jitter": 25,
        "texture_strength": 40,
        "buildup": 40,
    },
    "paint, stabilized": {
        "enabled": True,
        "mode": "paint",
        "stabilization": 70,
        "scatter": 30,
    },
    "paint, tilt+rotation": {
        "enabled": True,
        "mode": "paint",
        "tilt_size": 60,
        "tilt_angle": 50,
        "rotation_angle": 40,
    },
    "smudge (must fall back)": {"enabled": True, "mode": "smudge"},
    "paint + noise (must fall back)": {
        "enabled": True,
        "mode": "paint",
        "noise_enabled": True,
        "noise_scale": 60,
    },
    "paint + wet edges (must fall back)": {
        "enabled": True,
        "mode": "paint",
        "wet_edges_enabled": True,
    },
}


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    snapshots = [1, 2, 3, 9, 30, 60, SAMPLES]
    failures = 0
    for label, dynamics in CASES.items():
        fast = draw(dynamics, incremental=True, snapshots=snapshots)
        slow = draw(dynamics, incremental=False, snapshots=snapshots)
        worst_all = 0
        detail = []
        for index in snapshots:
            worst, differing = compare(slow[index], fast[index])
            worst_all = max(worst_all, worst)
            if worst:
                detail.append(f"sample {index}: {differing}px worst {worst}")
        status = "identical" if worst_all == 0 else "DIFF"
        if worst_all:
            failures += 1
        print(f"{label:<36} {status}")
        for row in detail:
            print(f"    {row}")
    del app
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
