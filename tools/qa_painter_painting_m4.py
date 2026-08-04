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
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, Stroke, compose_pil_paint_overlays, create_blank_paint_pixmap
    from app.painter_palette import export_brush_bundle, import_brush_bundle

    app = QApplication.instance() or QApplication([])
    root = Path.cwd() / "debugCapture" / "painter" / "painting_m4"
    root.mkdir(parents=True, exist_ok=True)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 192, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dynamics = {
        "enabled": True, "flow": 58, "buildup": 68, "stabilization": 55,
        "scatter": 28, "scatter_count": 2, "texture_strength": 42,
        "transfer_flow": 74, "hue_jitter": 18, "tilt_size": 40,
        "rotation_angle": 65, "barrel_flow": 35, "mode": "mixer", "mix": 38,
    }
    stroke = Stroke(
        points=[(0.08, 0.66), (0.25, 0.25), (0.48, 0.58), (0.72, 0.3), (0.92, 0.62)],
        color=(224, 68, 42), opacity=230, width_px=30, brush_spacing=22,
        brush_roundness=58, brush_seed=991, brush_dynamics=dynamics,
        point_pressure=[0.15, 0.4, 0.75, 0.95, 0.55],
        point_tilt_x=[0, 0.3, 0.5, -0.2, -0.4],
        point_tilt_y=[0, -0.35, 0.2, 0.45, 0.1],
        point_rotation=[0.1, 0.3, 0.5, 0.7, 0.9],
        point_tangential_pressure=[0, 0.2, 0.5, 0.8, 1.0],
        layer_id=dialog._active_paint_layer_id,
    )
    dialog.canvas.add_stroke_direct(stroke)
    before = compose_pil_paint_overlays(
        strokes=dialog.canvas.embedded_strokes(), frame_size=(320, 192),
        paint_layers=dialog._paint_layers, layer_rasters=dialog._paint_layer_rasters,
    )
    before_path = root / "dynamic_brush.png"; before.save(before_path)
    document = root / "dynamic_brush.tspaint"
    save_report = dialog.save_document_to_path(document)
    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    load_report = reopened.open_document_from_path(document)
    after = compose_pil_paint_overlays(
        strokes=reopened.canvas.embedded_strokes(), frame_size=(320, 192),
        paint_layers=reopened._paint_layers, layer_rasters=reopened._paint_layer_rasters,
    )
    after_path = root / "dynamic_brush_reopened.png"; after.save(after_path)
    preset = dialog._current_brush_preset_payload("M4 QA Brush", ["qa"])
    preset["dynamics"] = dynamics
    bundle = root / "dynamic_brush.tsbrushes"
    export_brush_bundle([preset], bundle)
    restored_presets = import_brush_bundle(bundle)
    baseline_stroke = Stroke(**{**stroke.__dict__, "brush_dynamics": {}})
    baseline = compose_pil_paint_overlays(
        strokes=[baseline_stroke], frame_size=(320, 192),
        paint_layers=dialog._paint_layers,
    )
    baseline_path = root / "baseline_brush.png"; baseline.save(baseline_path)
    report = {
        "schema": "tigerstudio.painter.painting_m4_qa.v1",
        "artifacts": {
            "dynamic": str(before_path), "reopened": str(after_path),
            "baseline": str(baseline_path), "document": str(document),
            "bundle": str(bundle),
        },
        "sha256_rgba": {
            "dynamic": _sha(before), "reopened": _sha(after), "baseline": _sha(baseline),
        },
        "save": save_report,
        "load": load_report,
        "save_open_pixel_parity": _sha(before) == _sha(after),
        "dynamics_change_pixels": _sha(before) != _sha(baseline),
        "preset_roundtrip": bool(restored_presets and restored_presets[0]["dynamics"]["mode"] == "mixer"),
    }
    report["passed"] = all((
        report["save_open_pixel_parity"], report["dynamics_change_pixels"],
        report["preset_roundtrip"],
    ))
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    reopened.close(); dialog.close(); app.processEvents()
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
