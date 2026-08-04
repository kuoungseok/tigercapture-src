"""Generate M3 selection, transform, crop, and Bezier-path parity evidence."""
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

from PIL import Image
from PySide6.QtWidgets import QApplication

from app.drawing import PaintDialog, create_blank_paint_pixmap


def _digest(path: Path) -> str:
    image = Image.open(path).convert("RGBA")
    return hashlib.sha256(image.tobytes()).hexdigest()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    output = ROOT / "debugCapture" / "painter" / "painting_m3"
    output.mkdir(parents=True, exist_ok=True)
    paths = {name: output / f"{name}.png" for name in (
        "before_transform", "transform_preview", "after_cancel",
        "after_commit", "after_undo", "after_reopen", "reopened_window",
    )}
    document_path = output / "selection_transform_path.tspaint"

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 400, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    assert dialog._select_lasso_points(
        [(0.08, 0.12), (0.48, 0.08), (0.42, 0.54), (0.12, 0.66)],
        polygonal=True,
    )
    assert dialog._fill_document("solid", color1="#E85A42")
    dialog._deselect()
    assert dialog._create_path_from_points(
        [(0.56, 0.18), (0.90, 0.24), (0.76, 0.72), (0.52, 0.62)],
        closed=True,
    )
    assert dialog._edit_path_anchor(
        "path:0", 1, "smooth", out_handle=(0.96, 0.48)
    )
    assert dialog._fill_saved_path("path:0", "#55A7E8")
    dialog.export_png_to_path(paths["before_transform"], include_background=False)

    dialog.canvas.select_rectangle(0.05, 0.05, 0.50, 0.70)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._preview_selection_transform(
        translate_x=42, translate_y=28, rotation_degrees=-8,
        scale_x=0.92, scale_y=1.08, skew_x_degrees=4,
        pivot_x=0.28, pivot_y=0.35,
    )
    dialog.export_png_to_path(paths["transform_preview"], include_background=False)
    assert dialog._cancel_selection_transform()
    dialog.export_png_to_path(paths["after_cancel"], include_background=False)

    assert dialog._preview_selection_transform(
        translate_x=42, translate_y=28, rotation_degrees=-8,
        scale_x=0.92, scale_y=1.08, skew_x_degrees=4,
        pivot_x=0.28, pivot_y=0.35,
    )
    assert dialog._commit_selection_transform()
    dialog.export_png_to_path(paths["after_commit"], include_background=False)
    save_report = dialog.save_document_to_path(document_path)
    dialog._undo()
    dialog.export_png_to_path(paths["after_undo"], include_background=False)

    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    load_report = reopened.open_document_from_path(document_path)
    reopened.export_png_to_path(paths["after_reopen"], include_background=False)
    reopened.resize(1280, 760)
    reopened.show(); app.processEvents()
    assert reopened.grab().save(str(paths["reopened_window"]), "PNG")

    digests = {name: _digest(path) for name, path in paths.items() if name != "reopened_window"}
    state = reopened.painter_action_state()
    report = {
        "schema": "tigerstudio.painter.painting_m3_qa.v1",
        "document": str(document_path),
        "artifacts": {name: str(path) for name, path in paths.items()},
        "sha256_rgba": digests,
        "save": save_report,
        "load": load_report,
        "cancel_pixel_parity": digests["before_transform"] == digests["after_cancel"],
        "preview_commit_pixel_parity": digests["transform_preview"] == digests["after_commit"],
        "undo_pixel_parity": digests["before_transform"] == digests["after_undo"],
        "save_open_pixel_parity": digests["after_commit"] == digests["after_reopen"],
        "selection_mask_restored": bool(state["selection"]["pixel_mask"]),
        "bezier_path_restored": bool(state["paths"]["saved"][0]["bezier"]),
    }
    report["passed"] = all((
        report["cancel_pixel_parity"], report["preview_commit_pixel_parity"],
        report["undo_pixel_parity"], report["save_open_pixel_parity"],
        report["selection_mask_restored"], report["bezier_path_restored"],
    ))
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reopened.close(); dialog.close()
    reopened.deleteLater(); dialog.deleteLater(); app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
