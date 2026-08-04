from __future__ import annotations

import json
import os
from pathlib import Path
import statistics
import sys
import time
import tracemalloc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from app.drawing import DrawingCanvas, Stroke
from app.painter_brush_dynamics import (
    PAINTER_DYNAMIC_DAB_BUDGET,
    dynamic_dab_workload,
    dynamic_dabs,
)


def _worst_measured_stroke() -> Stroke:
    return Stroke(
        points=[
            (0.0 if index % 2 == 0 else 1.0, index / 39.0)
            for index in range(40)
        ],
        width_px=0.5,
        brush_spacing=1,
        brush_seed=37,
        brush_dynamics={
            "enabled": True,
            "scatter_count": 8,
            "buildup": 100,
            "scatter": 100,
            "dual_brush_enabled": True,
            "dual_brush_strength": 80,
            "noise_enabled": True,
            "noise_scale": 70,
            "wet_edges_enabled": True,
            "wet_edge_pooling": 65,
        },
    )


def main() -> int:
    generation_ms: list[float] = []
    rendered_dabs = 0
    workload: dict[str, object] = {}
    for _index in range(3):
        stroke = _worst_measured_stroke()
        started = time.perf_counter()
        dabs = dynamic_dabs(stroke, 256, 256)
        generation_ms.append((time.perf_counter() - started) * 1000.0)
        rendered_dabs = len(dabs)
        workload = dynamic_dab_workload(stroke, 256, 256)
    tracemalloc.start()
    traced_started = time.perf_counter()
    dynamic_dabs(_worst_measured_stroke(), 256, 256)
    traced_generation_ms = (time.perf_counter() - traced_started) * 1000.0
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    render_ms: list[float] = []
    for _index in range(3):
        image = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        started = time.perf_counter()
        try:
            DrawingCanvas._paint_stroke(
                painter, _worst_measured_stroke(), 256, 256
            )
        finally:
            painter.end()
        render_ms.append((time.perf_counter() - started) * 1000.0)

    report = {
        "schema": "tigerstudio.painter.dynamic-dab-budget-qa.v1",
        "scope": "painting_only_ui_design_excluded",
        "budget": PAINTER_DYNAMIC_DAB_BUDGET,
        "rendered_dabs": rendered_dabs,
        "workload": workload,
        "generation_ms": {
            "samples": generation_ms,
            "median": statistics.median(generation_ms),
            "maximum": max(generation_ms),
        },
        "qimage_render_ms": {
            "samples": render_ms,
            "median": statistics.median(render_ms),
            "maximum": max(render_ms),
        },
        "tracemalloc_peak_bytes_one_generation": peak_bytes,
        "tracemalloc_generation_ms": traced_generation_ms,
        "passed": bool(
            rendered_dabs <= PAINTER_DYNAMIC_DAB_BUDGET
            and workload.get("degraded") is True
            and int(workload.get("estimated_dabs", 0))
            > PAINTER_DYNAMIC_DAB_BUDGET
        ),
        "claim_boundary": (
            "Target-machine workload measurement; not a universal latency or "
            "memory guarantee."
        ),
    }
    destination = (
        ROOT
        / "debugCapture"
        / "painter"
        / "advanced_brush_workload"
        / "report.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"path": str(destination), **report}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
