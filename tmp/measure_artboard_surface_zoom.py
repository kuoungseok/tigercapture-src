"""Measure Painter UI canvas zoom/pan frame cost before and after clipping.

Run with the project venv:
    QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe tmp/measure_artboard_surface_zoom.py
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

WIDGET_WIDTH = 1450
WIDGET_HEIGHT = 900
BOARD_COUNT = 12
OBJECT_COUNT = 8_000
ZOOM_STEPS = (100, 125, 150, 200, 250, 300, 400, 500, 650, 800)
PAN_ZOOM = 400
PAN_STEPS = 12
PAN_DX = 90.0


def build_document() -> dict:
    from app.painter_ui_document import add_ui_artboard, create_ui_document

    document = create_ui_document(1440, 900, name="Zoom QA")
    artboard_ids = [document["active_artboard_id"]]
    for index in range(BOARD_COUNT - 1):
        document, board = add_ui_artboard(
            document,
            name=f"Board {index + 2}",
            width=1440,
            height=900,
        )
        artboard_ids.append(str(board["id"]))
    per_board = max(1, OBJECT_COUNT // len(artboard_ids))
    objects = []
    for board_index, artboard_id in enumerate(artboard_ids):
        for index in range(per_board):
            objects.append(
                {
                    "id": f"obj-{board_index}-{index}",
                    "kind": "text" if index % 7 == 0 else "rectangle",
                    "name": f"Object {board_index}-{index}",
                    "artboard_id": artboard_id,
                    "parent_id": "",
                    "x": float((index % 40) * 35),
                    "y": float((index // 40) * 45),
                    "width": 30.0,
                    "height": 40.0,
                    "content": (
                        {"text": f"Label {index}"} if index % 7 == 0 else {}
                    ),
                    "style": {"fill": "#3B82F6", "radius": 4.0},
                }
            )
    document["objects"] = objects
    return document


def cached_pixels(overlay) -> tuple[int, int]:
    entries = 0
    pixels = 0
    for cache in (
        overlay._overview_artboard_cache,
        overlay._exact_artboard_cache,
    ):
        for image in cache.values():
            entries += 1
            pixels += image.width() * image.height()
    return entries, pixels


def run_case(label: str, *, full_board: bool) -> dict:
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage

    from app.painter_ui_workspace import PainterUIDesignOverlay

    if full_board:
        def surface_rect(self, viewport):
            return (
                0,
                0,
                max(1, int(math.ceil(viewport.width()))),
                max(1, int(math.ceil(viewport.height()))),
            )

        original = PainterUIDesignOverlay._artboard_surface_rect
        PainterUIDesignOverlay._artboard_surface_rect = surface_rect
    else:
        original = None

    try:
        overlay = PainterUIDesignOverlay()
        overlay.resize(WIDGET_WIDTH, WIDGET_HEIGHT)
        overlay.set_document(build_document())
        board = overlay._document["artboards"][0]
        frame = QImage(
            overlay.size(),
            QImage.Format.Format_ARGB32_Premultiplied,
        )

        def paint(zoom: int, pan_index: int = 0) -> float:
            scale = zoom / 100.0
            overlay._view_scale = scale
            overlay._view_offset = QPointF(
                -float(board["x"]) * scale + 40.0 - pan_index * PAN_DX,
                -float(board["y"]) * scale + 40.0,
            )
            started = time.perf_counter()
            overlay.render(frame)
            return (time.perf_counter() - started) * 1000.0

        zoom_samples = [paint(zoom) for zoom in ZOOM_STEPS]
        pan_samples = [paint(PAN_ZOOM, index) for index in range(1, PAN_STEPS)]
        entries, pixels = cached_pixels(overlay)
        result = {
            "label": label,
            "zoom_ms": [round(value, 1) for value in zoom_samples],
            "zoom_median_ms": round(statistics.median(zoom_samples), 1),
            "zoom_total_ms": round(sum(zoom_samples), 1),
            "pan_median_ms": round(statistics.median(pan_samples), 1),
            "pan_total_ms": round(sum(pan_samples), 1),
            "cache_entries": entries,
            "cache_mb": round(pixels * 4 / (1024 * 1024), 1),
        }
        overlay.close()
        overlay.deleteLater()
        return result
    finally:
        if original is not None:
            PainterUIDesignOverlay._artboard_surface_rect = original


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    rows = [
        run_case("full board (before)", full_board=True),
        run_case("clipped to view (after)", full_board=False),
    ]
    for row in rows:
        print(f"--- {row['label']}")
        print(f"    zoom steps ms   : {row['zoom_ms']}")
        print(
            "    zoom median/total: "
            f"{row['zoom_median_ms']} / {row['zoom_total_ms']} ms"
        )
        print(
            "    pan  median/total: "
            f"{row['pan_median_ms']} / {row['pan_total_ms']} ms"
        )
        print(
            f"    cache            : {row['cache_entries']} entries, "
            f"{row['cache_mb']} MB"
        )
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
