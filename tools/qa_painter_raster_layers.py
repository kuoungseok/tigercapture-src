"""Generate M1 Painter raster-layer persistence and export evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.drawing import PaintDialog, create_blank_paint_pixmap


def main() -> int:
    app = QApplication.instance() or QApplication([])
    output = ROOT / "debugCapture" / "painter" / "painting_m1"
    output.mkdir(parents=True, exist_ok=True)
    document_path = output / "raster_layers_roundtrip.tspaint"
    export_path = output / "raster_layers_export.png"
    screenshot_path = output / "raster_layers_reopened.png"

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(960, 540, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1280, 760)
    dialog.show()
    app.processEvents()
    assert dialog._fill_document("solid", color1="#D64B45")
    source = QImage(520, 300, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(0)
    painter = QPainter(source)
    try:
        painter.fillRect(QRect(0, 0, 260, 300), QColor("#3288E8"))
        painter.fillRect(QRect(260, 0, 260, 300), QColor("#F1C44B"))
    finally:
        painter.end()
    imported = dialog._create_raster_layer_from_image(source, name="Imported Color Card")
    assert imported is not None
    imported.opacity = 82
    imported.mask = [(0.28, 0.18), (0.82, 0.18), (0.82, 0.82), (0.28, 0.82)]
    imported.mask_enabled = True
    dialog._sync_canvas_layer_view()
    saved = dialog.save_document_to_path(document_path)
    dialog.close()

    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    loaded = reopened.open_document_from_path(document_path)
    exported = reopened.export_png_to_path(export_path, include_background=False)
    reopened.resize(1280, 760)
    reopened.show()
    app.processEvents()
    assert reopened.grab().save(str(screenshot_path), "PNG")
    restored = reopened._paint_layer_raster(imported.layer_id)
    assert restored is not None and not restored.isNull()
    report = {
        "schema": "tigerstudio.painter.painting_m1_qa.v1",
        "document": str(document_path),
        "export": str(export_path),
        "screenshot": str(screenshot_path),
        "save": saved,
        "load": loaded,
        "png": exported,
        "layer_order": [layer.layer_id for layer in reopened._paint_layers],
        "restored_center": restored.pixelColor(480, 270).name(),
        "passed": len(reopened._paint_layers) == 2 and loaded["layer_count"] == 2,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    reopened.close()
    reopened.deleteLater()
    dialog.deleteLater()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
