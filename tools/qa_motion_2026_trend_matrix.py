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
from app.motion_designer.templates import get_template, instantiate_template
from app.motion_designer.trend_templates import (
    TREND_TEMPLATE_SPECS,
    trend_template_capabilities,
)
from app.motion_designer.validation import validate_composition
from app.unreal_umg_document import motion_composition_to_umg_document


OUTPUT = ROOT / "debugCapture" / "motion_2026_trend_matrix"
FRAME_WIDTH = 320
FRAME_HEIGHT = 180


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(),
        converted.bytesPerLine(),
    )
    return array[:, : converted.width() * 4].reshape(
        converted.height(),
        converted.width(),
        4,
    ).copy()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=3)
    rows: list[dict] = []
    strips: list[tuple[str, QImage]] = []
    for spec in TREND_TEMPLATE_SPECS:
        template_id = str(spec["id"])
        template = get_template(template_id)
        composition = instantiate_template(template_id, variant=template.variants[0])
        scene_frames: list[QImage] = []
        arrays: list[np.ndarray] = []
        for index in range(template.scene_count):
            frame = renderer.render_frame(
                composition,
                composition.duration_ms * (index + 0.45) / template.scene_count,
                width=FRAME_WIDTH,
                height=FRAME_HEIGHT,
                use_cache=False,
            )
            scene_frames.append(frame)
            arrays.append(_rgba(frame))
        strip = QImage(
            FRAME_WIDTH * template.scene_count,
            FRAME_HEIGHT,
            QImage.Format_RGBA8888_Premultiplied,
        )
        strip.fill(QColor("#090c11"))
        painter = QPainter(strip)
        for index, frame in enumerate(scene_frames):
            painter.drawImage(index * FRAME_WIDTH, 0, frame)
        painter.end()
        strip_path = OUTPUT / f"{template_id}.png"
        strip.save(str(strip_path), "PNG")
        strips.append((template.name, strip))

        document = motion_composition_to_umg_document(composition)
        blocked_rows = [
            row for row in document["Layers"]
            if row["Disposition"] == "Blocked"
        ]
        validation = validate_composition(composition)
        differences = [
            int(np.count_nonzero(current != following))
            for current, following in zip(arrays, arrays[1:])
        ]
        rows.append({
            "template_id": template_id,
            "name": template.name,
            "variant": template.variants[0],
            "duration_ms": composition.duration_ms,
            "scene_count": template.scene_count,
            "valid": validation.ok,
            "real_renderer": "MotionExportRenderer",
            "nonblank": all(np.any(array[..., 3] > 0) for array in arrays),
            "scene_differences": differences,
            "editable": composition.metadata["trend_template_state"]["editable"],
            "umg_blocked_layer_count": len(blocked_rows),
            "umg_block_reasons_explicit": all(
                "umg_block_reasons" in row["PayloadJson"]
                for row in blocked_rows
            ),
            "strip": str(strip_path),
        })

    label_height = 28
    sheet_width = max(strip.width() for _name, strip in strips)
    sheet_height = sum(strip.height() + label_height for _name, strip in strips)
    sheet = QImage(
        sheet_width,
        sheet_height,
        QImage.Format_RGBA8888_Premultiplied,
    )
    sheet.fill(QColor("#090c11"))
    painter = QPainter(sheet)
    painter.setPen(QColor("#eef3f7"))
    painter.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
    y = 0
    for name, strip in strips:
        painter.drawText(
            QRectF(10, y, sheet_width - 20, label_height),
            Qt.AlignVCenter,
            name,
        )
        y += label_height
        painter.drawImage(0, y, strip)
        y += strip.height()
    painter.end()
    sheet_path = OUTPUT / "trend_template_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")

    capabilities = trend_template_capabilities()
    report = {
        "ok": (
            len(rows) == 8
            and all(
                row["valid"]
                and row["nonblank"]
                and row["editable"]
                and row["umg_block_reasons_explicit"]
                and all(value > 0 for value in row["scene_differences"])
                for row in rows
            )
            and not capabilities["blocked"]
        ),
        "schema": "tigerstudio.motion.2026_trend_qa.v1",
        "supported_template_count": len(rows),
        "contact_sheet": str(sheet_path),
        "capabilities": capabilities,
        "templates": rows,
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
