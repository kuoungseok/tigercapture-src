from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sha(image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def main() -> int:
    from PIL import Image
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, compose_pil_paint_overlays, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    root = ROOT / "debugCapture" / "painter" / "painting_m5"
    root.mkdir(parents=True, exist_ok=True)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(160, 96, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    base_id = dialog._active_paint_layer_id
    raster = QImage(160, 96, QImage.Format.Format_ARGB32_Premultiplied)
    raster.fill(QColor("#315F9B"))
    painter = QPainter(raster)
    painter.fillRect(QRect(80, 0, 80, 96), QColor("#D99548"))
    painter.setPen(QColor("#55C878")); painter.setBrush(QColor("#55C878"))
    painter.drawEllipse(QRect(28, 20, 54, 54))
    painter.end()
    dialog._set_paint_layer_raster(base_id, raster)

    def render():
        return compose_pil_paint_overlays(
            paint_layers=dialog._paint_layers,
            layer_rasters=dialog._paint_layer_rasters,
            frame_size=(160, 96),
        )

    original = render(); original.save(root / "original.png")
    dialog.canvas.select_rectangle(0, 0, 0.5, 1)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._preview_paint_adjustment("curves", {"points": [[0, 0], [96, 42], [180, 230], [255, 255]]})
    preview = render(); preview.save(root / "preview.png")
    assert dialog._cancel_paint_adjustment()
    cancelled = render(); cancelled.save(root / "cancelled.png")
    assert dialog._preview_paint_adjustment("curves", {"points": [[0, 0], [96, 42], [180, 230], [255, 255]]})
    assert dialog._commit_paint_adjustment()
    committed = render(); committed.save(root / "committed.png")
    dialog._undo(); undone = render(); undone.save(root / "undone.png")

    adjustment = dialog._new_adjustment_layer(
        "hue_saturation", {"hue": 38, "saturation": 32}, use_selection=False
    )
    nondestructive_source = bytes(dialog._paint_layer_raster(base_id).constBits())
    adjusted = render(); adjusted.save(root / "adjustment_layer.png")
    source_unchanged = nondestructive_source == bytes(dialog._paint_layer_raster(base_id).constBits())
    dialog._set_named_swatch_group("Production", [
        {"name": "Sky", "rgb": [49, 95, 155]},
        {"name": "Accent", "rgb": [217, 149, 72]},
    ])
    ase = root / "production.ase"; gpl = root / "production.gpl"
    dialog._export_named_palette(ase); dialog._export_named_palette(gpl)
    document = root / "adjustments.tspaint"
    save_report = dialog.save_document_to_path(document)
    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    load_report = reopened.open_document_from_path(document)
    reopened_image = compose_pil_paint_overlays(
        paint_layers=reopened._paint_layers,
        layer_rasters=reopened._paint_layer_rasters,
        frame_size=(160, 96),
    )
    reopened_image.save(root / "adjustment_reopened.png")
    hashes = {
        "original": _sha(original), "preview": _sha(preview),
        "cancelled": _sha(cancelled), "committed": _sha(committed),
        "undone": _sha(undone), "adjustment": _sha(adjusted),
        "reopened": _sha(reopened_image),
    }
    report = {
        "schema": "tigerstudio.painter.painting_m5_qa.v1",
        "artifacts": {"root": str(root), "document": str(document), "ase": str(ase), "gpl": str(gpl)},
        "sha256_rgba": hashes,
        "preview_changes_pixels": hashes["preview"] != hashes["original"],
        "cancel_pixel_parity": hashes["cancelled"] == hashes["original"],
        "preview_commit_pixel_parity": hashes["preview"] == hashes["committed"],
        "undo_pixel_parity": hashes["undone"] == hashes["original"],
        "adjustment_non_destructive": source_unchanged,
        "adjustment_save_open_parity": hashes["adjustment"] == hashes["reopened"],
        "adjustment_layer_restored": bool(
            reopened._paint_layer_by_id(adjustment.layer_id)
            and reopened._paint_layer_by_id(adjustment.layer_id).node_type == "adjustment"
        ),
        "named_palette_restored": "Production" in reopened._named_swatch_groups,
        "save": save_report, "load": load_report,
    }
    report["passed"] = all(value for key, value in report.items() if key in {
        "preview_changes_pixels", "cancel_pixel_parity", "preview_commit_pixel_parity",
        "undo_pixel_parity", "adjustment_non_destructive", "adjustment_save_open_parity",
        "adjustment_layer_restored", "named_palette_restored",
    })
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    reopened.close(); dialog.close(); app.processEvents()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
