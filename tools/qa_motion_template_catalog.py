from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.templates import TEMPLATE_CATALOG, instantiate_template
from app.motion_designer.validation import validate_composition


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "templates"
PREVIEW_BOX = (480, 270)


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(converted.height(), converted.bytesPerLine())
    return data[:, : converted.width() * 4].reshape(converted.height(), converted.width(), 4).copy()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=12)
    rows = []
    previews: list[tuple[str, QImage]] = []
    for template_id, template in TEMPLATE_CATALOG.items():
        variant = template.variants[0]
        composition = instantiate_template(template_id, variant=variant)
        first = renderer.render_frame(composition, 0)
        sample_time = composition.duration_ms * .35
        sample = renderer.render_frame(composition, sample_time)
        changed = int(np.count_nonzero(_rgba(first) != _rgba(sample)))
        path = OUTPUT / f"{template_id}_{variant.replace(':', 'x')}.png"
        sample.save(str(path), "PNG")
        validation = validate_composition(composition)
        rows.append({
            "template_id": template_id, "name": template.name, "variant": variant,
            "valid": validation.ok, "animated_changed_values": changed,
            "published_control_ids": [item.id for item in template.controls],
            "realtime_grade": template.realtime_grade, "preview": str(path),
        })
        previews.append((template.name, sample.scaled(
            PREVIEW_BOX[0], PREVIEW_BOX[1], Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )))

    cell_width, cell_height = 500, 310
    columns = 2
    sheet = QImage(cell_width * columns, cell_height * 5, QImage.Format_RGBA8888_Premultiplied)
    sheet.fill(QColor("#0b0d11"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setPen(QColor("#dce2e8"))
    painter.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
    for index, (name, preview) in enumerate(previews):
        column, row = index % columns, index // columns
        x, y = column * cell_width, row * cell_height
        preview_x = x + 10 + (PREVIEW_BOX[0] - preview.width()) / 2
        preview_y = y + 10 + (PREVIEW_BOX[1] - preview.height()) / 2
        painter.drawImage(QRectF(preview_x, preview_y, preview.width(), preview.height()), preview)
        painter.drawText(QRectF(x + 12, y + 282, 476, 22), name)
    painter.end()
    sheet_path = OUTPUT / "catalog.png"
    sheet.save(str(sheet_path), "PNG")
    report = {
        "ok": len(rows) == 10 and all(row["valid"] and row["animated_changed_values"] > 0 for row in rows),
        "template_count": len(rows), "all_stable_controls": all(
            row["published_control_ids"] == ["headline", "subtitle", "accent_color", "surface_color", "duration_ms"]
            for row in rows
        ),
        "catalog": str(sheet_path), "templates": rows,
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"] or not report["all_stable_controls"]:
        raise RuntimeError(f"Motion template catalog QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
