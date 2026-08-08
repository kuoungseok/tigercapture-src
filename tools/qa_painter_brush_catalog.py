"""Render a contact sheet for visual QA of the professional Painter brush catalog."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from app.drawing import (
    BRUSH_LIBRARY_PRESETS,
    DrawingCanvas,
    PaintDialog,
    Stroke,
    create_blank_paint_pixmap,
)


CATALOG_CATEGORIES = (
    "Basic",
    "Drawing",
    "Ink",
    "Oils",
    "Pro Oils",
    "Water Media",
    "Airbrush",
    "Concept",
    "Texture",
    "FX",
)


def render_contact_sheet(path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    app.processEvents()
    rows = [
        row
        for row in BRUSH_LIBRARY_PRESETS
        if str(row.get("category") or "") in CATALOG_CATEGORIES
    ]
    columns = 2
    item_width = 600
    item_height = 112
    width = item_width * columns
    row_count = (len(rows) + columns - 1) // columns
    image = QImage(width, 76 + item_height * row_count, QImage.Format.Format_ARGB32)
    image.fill(QColor("#202020"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        painter.fillRect(QRectF(0, 0, width, 76), QColor("#292929"))
        painter.setPen(QColor("#f0f0f0"))
        font = QFont("Segoe UI", 18)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QPointF(28, 34), "Tiger Studio Painter - Professional Brush Catalog")
        painter.setPen(QColor("#b9b9b9"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QPointF(28, 56), "Actual Qt canvas renderer output")

        colors = (
            (221, 102, 53), (210, 137, 50), (80, 134, 94), (57, 108, 146),
            (154, 91, 58), (185, 76, 99), (105, 94, 147), (93, 139, 176),
        )
        for index, row in enumerate(rows):
            column = index % columns
            row_index = index // columns
            left = column * item_width
            top = 76 + row_index * item_height
            name = str(row["name"])
            style = str(row["style"])
            brush_width = min(42, max(4, int(row["width"])))
            color = colors[index % len(colors)]
            painter.fillRect(
                QRectF(left, top, item_width, item_height),
                QColor("#252525" if row_index % 2 == 0 else "#222222"),
            )
            painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
            painter.drawLine(QPointF(left, top), QPointF(left + item_width, top))
            painter.setPen(QColor("#ededed"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(QPointF(left + 22, top + 30), name)
            painter.setPen(QColor("#8f8f8f"))
            painter.setFont(QFont("Consolas", 8))
            painter.drawText(QPointF(left + 22, top + 50), style)
            x0 = left + 174
            x1 = left + item_width - 20
            y0 = top + 76
            y1 = top + 36
            stroke = Stroke(
                points=[
                    (x0 / image.width(), y0 / image.height()),
                    ((x0 + (x1 - x0) * 0.24) / image.width(), y1 / image.height()),
                    ((x0 + (x1 - x0) * 0.50) / image.width(), (top + 70) / image.height()),
                    ((x0 + (x1 - x0) * 0.76) / image.width(), (top + 30) / image.height()),
                    (x1 / image.width(), (top + 62) / image.height()),
                ],
                color=color,
                opacity=max(1, min(255, int(float(row.get("opacity") or 100) * 2.55))),
                width_px=brush_width,
                brush_style=style,
            )
            DrawingCanvas._paint_stroke(painter, stroke, image.width(), image.height())
    finally:
        painter.end()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Failed to save Painter brush QA sheet: {path}")


def render_brush_panel(path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(960, 540, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1180, 760)
    dialog.show()
    dialog._set_brush_tab("presets")
    app.processEvents()
    app.processEvents()
    path.parent.mkdir(parents=True, exist_ok=True)
    panel = dialog._paint_brush_detail_panel
    if not panel.grab().save(str(path), "PNG"):
        dialog.close()
        raise RuntimeError(f"Failed to save Painter brush panel QA image: {path}")
    dialog.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("debugCapture/painter/professional_brush_catalog.png"),
    )
    parser.add_argument(
        "--ui-output",
        type=Path,
        default=Path("debugCapture/painter/corel_style_brush_library_panel.png"),
    )
    args = parser.parse_args()
    render_contact_sheet(args.output)
    render_brush_panel(args.ui_output)
    print(args.output.resolve())
    print(args.ui_output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
