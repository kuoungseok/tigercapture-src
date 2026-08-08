"""Render the editable logo template family as a compact visual QA sheet."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.templates import instantiate_template, list_templates


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "logo_templates"


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=8)
    rows = []
    logo_rows = [
        row for row in list_templates()
        if row["id"] == "logo_reveal" or row["category"] == "Logo Reveals"
    ]
    cell_w, cell_h = 480, 305
    columns = 4
    sheet = QImage(cell_w * columns, cell_h * 4, QImage.Format_RGBA8888_Premultiplied)
    sheet.fill(QColor("#0b0d11"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setPen(QColor("#e7ebef"))
    painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
    for index, row in enumerate(logo_rows):
        composition = instantiate_template(str(row["id"]), variant="16:9")
        frame = renderer.render_frame(
            composition,
            composition.duration_ms * .42,
            width=448,
            height=252,
            use_cache=False,
        )
        path = OUTPUT / f"{row['id']}.png"
        frame.save(str(path), "PNG")
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        painter.drawImage(QRectF(x + 16, y + 12, 448, 252), frame)
        painter.drawText(QRectF(x + 16, y + 270, 448, 24), Qt.AlignCenter, str(row["name"]))
        rows.append({
            "id": row["id"],
            "frame": str(path.resolve()),
            "layer_count": len(composition.layers),
            "roles": sorted({
                str(layer.metadata.get("template_role") or "")
                for layer in composition.layers
            }),
        })
    painter.end()
    sheet_path = OUTPUT / "logo_template_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")
    report = {
        "ok": len(rows) == 16 and all(row["layer_count"] >= 8 for row in rows),
        "count": len(rows),
        "contact_sheet": str(sheet_path.resolve()),
        "templates": rows,
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
