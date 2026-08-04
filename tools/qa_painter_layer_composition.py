"""Generate M2 Painter group/clipping/merge parity evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.drawing import PaintDialog, create_blank_paint_pixmap


def _same_pixels(first: Path, second: Path) -> bool:
    left = Image.open(first).convert("RGBA")
    right = Image.open(second).convert("RGBA")
    return left.size == right.size and left.tobytes() == right.tobytes()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    output = ROOT / "debugCapture" / "painter" / "painting_m2"
    output.mkdir(parents=True, exist_ok=True)
    document_path = output / "layer_composition.tspaint"
    before_path = output / "before_save.png"
    reopened_path = output / "after_reopen.png"
    merged_path = output / "after_merge_visible.png"
    screenshot_path = output / "reopened_layer_stack.png"

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(960, 540, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    assert dialog._fill_document("solid", color1="#343A46")
    base = QImage(520, 300, QImage.Format.Format_ARGB32_Premultiplied)
    base.fill(0)
    painter = QPainter(base)
    try:
        painter.fillRect(QRect(40, 30, 440, 240), QColor("#CC5544"))
    finally:
        painter.end()
    base_layer = dialog._create_raster_layer_from_image(base, name="Base Shape")
    clip = QImage(960, 540, QImage.Format.Format_ARGB32_Premultiplied)
    clip.fill(QColor("#42A7E8"))
    clip_layer = dialog._create_raster_layer_from_image(clip, name="Clipped Color")
    assert base_layer is not None and clip_layer is not None
    clip_layer.clipping = True
    clip_layer.blend_mode = "screen"
    group = dialog._new_paint_layer_group(
        "Card Group", layer_ids=[base_layer.layer_id, clip_layer.layer_id]
    )
    group.opacity = 78
    dialog._sync_canvas_layer_view()
    dialog.export_png_to_path(before_path, include_background=False)
    saved = dialog.save_document_to_path(document_path)
    dialog.close()

    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    loaded = reopened.open_document_from_path(document_path)
    reopened.export_png_to_path(reopened_path, include_background=False)
    reopened.resize(1280, 760)
    reopened.show()
    app.processEvents()
    assert reopened.grab().save(str(screenshot_path), "PNG")
    premerge_count = len(reopened._paint_layers)
    merged = reopened._merge_visible()
    assert merged is not None
    reopened.export_png_to_path(merged_path, include_background=False)
    report = {
        "schema": "tigerstudio.painter.painting_m2_qa.v1",
        "document": str(document_path),
        "before": str(before_path),
        "reopened": str(reopened_path),
        "merged": str(merged_path),
        "screenshot": str(screenshot_path),
        "save": saved,
        "load": loaded,
        "premerge_layer_count": premerge_count,
        "postmerge_layer_count": len(reopened._paint_layers),
        "save_open_pixel_parity": _same_pixels(before_path, reopened_path),
        "merge_pixel_parity": _same_pixels(reopened_path, merged_path),
    }
    report["passed"] = bool(
        report["save_open_pixel_parity"]
        and report["merge_pixel_parity"]
        and premerge_count == 4
        and len(reopened._paint_layers) == 1
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reopened.close()
    reopened.deleteLater()
    dialog.deleteLater()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
