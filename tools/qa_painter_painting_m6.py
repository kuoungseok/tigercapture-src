from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _hash(image: Image.Image) -> str:
    return hashlib.sha256(image.convert("RGBA").tobytes()).hexdigest()


def main() -> int:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_file_exchange import export_height_map16

    app = QApplication.instance() or QApplication([])
    root = ROOT / "debugCapture" / "painter" / "painting_m6"; root.mkdir(parents=True, exist_ok=True)
    dialog = PaintDialog(background_pixmap=create_blank_paint_pixmap(96, 64, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    bottom = Image.new("RGBA", (96, 64), (34, 56, 92, 255))
    top = Image.new("RGBA", (96, 64), (0, 0, 0, 0))
    for y in range(12, 52):
        for x in range(18, 78):
            top.putpixel((x, y), (220, 114, 48, 48 + ((x + y) % 180)))
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, dialog._pil_rgba_to_qimage(bottom))
    dialog._paint_layers[0].name = "Background"; dialog._paint_layers[0].opacity = 100
    upper = dialog._new_paint_layer("Paint"); dialog._set_paint_layer_raster(upper.layer_id, dialog._pil_rgba_to_qimage(top))
    dialog._output_settings = {
        "mode": "print", "width_mm": 80, "height_mm": 50, "ppi": 300,
        "bleed_mm": 3, "include_bleed": True, "safe_margin_mm": 4,
        "output_kind": "color", "color_space": "srgb",
    }
    original = dialog._painter_composite_pil(include_background=False)
    flat: dict[str, dict] = {}
    for fmt, suffix, depth in (
        ("png", ".png", 8), ("jpeg", ".jpg", 8), ("webp", ".webp", 8),
        ("tiff", ".tiff", 8), ("png", "_16.png", 16), ("tiff", "_16.tiff", 16),
    ):
        key = f"{fmt}_{depth}"
        flat[key] = dialog.export_document_to_path(root / f"artwork{suffix}", format_name=fmt, bit_depth=depth, include_background=False)
    psd_report = dialog.export_document_to_path(root / "layers.psd", format_name="psd", include_background=False)
    reopened = PaintDialog(background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    imported = reopened.import_psd_document_from_path(root / "layers.psd")
    reopened_pixels = reopened._painter_composite_pil(include_background=False)
    psd_delta = np.abs(np.asarray(original, dtype=np.int16) - np.asarray(reopened_pixels, dtype=np.int16))
    adjustment = dialog._new_adjustment_layer("levels", {"gamma": 0.7})
    blocked = dialog.painter_exchange_preflight(format_name="psd", bake_unsupported=False)
    baked = dialog.export_document_to_path(root / "baked.psd", format_name="psd", include_background=False, bake_unsupported=True)
    height = np.linspace(0.0, 1.0, 4096, dtype=np.float32).reshape(64, 64)
    height_report = export_height_map16(root / "material_height_16.png", height)
    height_reopened = cv2.imread(height_report["path"], cv2.IMREAD_UNCHANGED)
    height_unique = int(len(np.unique(height_reopened))) if height_reopened is not None else 0
    passed = all(row["inspection"]["width"] == 96 and row["inspection"]["height"] == 64 for row in flat.values())
    passed = passed and all(row["icc_embedded"] for row in flat.values())
    passed = passed and flat["png_16"]["inspection"]["bit_depth"] == 16 and flat["tiff_16"]["inspection"]["bit_depth"] == 16
    passed = passed and int(psd_delta.max()) <= 1
    passed = passed and [row["name"] for row in imported["layers"]] == ["Background", "Paint"]
    passed = passed and blocked["ok"] is False and blocked["unsupported_policy"] == "blocked"
    passed = passed and baked["preflight"]["unsupported_policy"] == "bake" and baked["layers"] == ["Baked Artwork"]
    passed = passed and height_report["inspection"]["bit_depth"] == 16 and height_unique > 256
    report = {
        "schema": "tigerstudio.painter.painting_m6_qa.v1", "artifacts": {"root": str(root)},
        "flat_exports": flat, "psd": psd_report, "psd_import": {k: v for k, v in imported.items() if k != "layers"},
        "sha256_rgba": {"original": _hash(original), "psd_reopened": _hash(reopened_pixels)},
        "psd_pixel_delta": {"max_channel": int(psd_delta.max()), "mean_channel": float(psd_delta.mean()), "changed_channels": int(np.count_nonzero(psd_delta))},
        "psd_layer_names": [row["name"] for row in imported["layers"]],
        "unsupported_blocked": blocked, "unsupported_baked": baked,
        "material_height_16": {**height_report, "unique_values": height_unique}, "passed": bool(passed),
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    reopened.close(); dialog.close(); app.processEvents()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
