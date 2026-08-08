from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))


def _hash(image) -> str:
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def main() -> int:
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_large_canvas import LargeCanvasRuntime, UndoMemoryBudget

    app = QApplication.instance() or QApplication([])
    root = ROOT / "debugCapture" / "painter" / "painting_m7"; root.mkdir(parents=True, exist_ok=True)
    handles: dict[tuple[str, int, int], int] = {}; upload_calls = []
    def upload(key, image, old):
        handle = old or len(handles) + 1; handles[key] = handle
        upload_calls.append({"key": list(key), "old": old, "handle": handle, "bytes": image.width() * image.height() * 4})
        return handle
    runtime = LargeCanvasRuntime(tile_size=256, tile_budget_mb=96, undo_budget_mb=64, gpu_uploader=upload)
    image = QImage(3840, 2160, QImage.Format.Format_ARGB32_Premultiplied); image.fill(0xFF315A89)
    stroke_target = QImage(3840, 2160, QImage.Format.Format_ARGB32_Premultiplied); stroke_target.fill(0)
    long_stroke = Stroke(
        points=[(index / 1999.0, 0.5 + 0.18 * ((index % 41) / 40.0 - 0.5)) for index in range(2000)],
        width_px=18, brush_style="bristle_oil", source_tool="pen",
        brush_dynamics={"enabled": True, "flow": 72, "buildup": 38, "scatter": 12, "scatter_count": 2},
    )
    painter = QPainter(stroke_target); stroke_started = time.perf_counter()
    DrawingCanvas._paint_stroke(painter, long_stroke, 3840, 2160); painter.end()
    stroke_ms = (time.perf_counter() - stroke_started) * 1000
    stroke_painted = stroke_target.pixelColor(1920, 1080).alpha() > 0
    started = time.perf_counter(); initial = runtime.update_layer("paint", image); initial_ms = (time.perf_counter() - started) * 1000
    initial_hash = _hash(runtime.tiles.reconstruct("paint")); initial_upload_count = len(upload_calls)
    image.setPixel(1910, 1070, 0xFFFFAA22)
    dirty = runtime.update_layer("paint", image, dirty_rect=(1904, 1064, 16, 16))
    dirty_hash = _hash(runtime.tiles.reconstruct("paint")); dirty_upload_count = len(upload_calls) - initial_upload_count
    runtime.cache_brush_stamp("bristle", image.copy(0, 0, 128, 128))
    runtime.update_layer("material", image, dirty_rect=(500, 500, 24, 24), material=True, wet=True)
    runtime.update_material_map("normal", image, dirty_rect=(500, 500, 24, 24))
    material_queue_before = runtime.material_tasks.telemetry()
    drained = runtime.material_tasks.drain(lambda kind, tx, ty: f"{kind}:{tx}:{ty}", limit=8)
    undo_stack = [{"raster": image.copy()} for _ in range(4)]; undo_labels = [f"Full {i}" for i in range(4)]
    undo = UndoMemoryBudget(64 * 1024 * 1024); undo_report = undo.enforce(undo_stack, undo_labels)
    def fail(*_args): raise RuntimeError("forced context loss")
    fallback = LargeCanvasRuntime(tile_size=256, tile_budget_mb=16, undo_budget_mb=16, gpu_uploader=fail)
    fallback.update_layer("paint", image, dirty_rect=(0, 0, 128, 128))
    fallback_tile = fallback.tiles.tile("paint", 0, 0)
    fallback_parity = fallback_tile is not None and _hash(fallback_tile) == _hash(image.copy(0, 0, 256, 256))
    dialog = PaintDialog(background_pixmap=create_blank_paint_pixmap(3840, 2160, "transparent"), initial_strokes=[], time_ms=0, standalone=True)
    dialog.configure_painter_large_canvas(tile_size=256, tile_budget_mb=64, undo_budget_mb=64)
    dialog._set_paint_layer_raster(dialog._active_paint_layer_id, image)
    state = dialog.painter_action_state(); dialog_runtime = state["gpu"]["large_canvas"]
    passed = (
        initial["updated_tiles"] == 135 and dirty["updated_tiles"] == 1 and dirty_upload_count == 1
        and initial_hash != dirty_hash and runtime.telemetry()["tiles"]["bounded"]
        and runtime.telemetry()["brush_stamp_atlas"]["tile_count"] == 1
        and material_queue_before["queued"] > 0 and len(drained) == 8
        and undo_report["bounded"] and len(undo_stack) <= 2
        and fallback.telemetry()["cpu_fallback"] and fallback.telemetry()["tiles"]["gpu_failures"] == 1
        and fallback_parity and dialog_runtime["tiles"]["bounded"]
        and stroke_painted
    )
    report = {
        "schema": "tigerstudio.painter.painting_m7_qa.v2", "artifacts": {"root": str(root)},
        "canvas": [3840, 2160], "initial": {**initial, "elapsed_ms_total": round(initial_ms, 3), "upload_calls": initial_upload_count},
        "long_brush": {"points": 2000, "elapsed_ms": round(stroke_ms, 3), "rendered": stroke_painted},
        "dirty_update": {**dirty, "upload_calls": dirty_upload_count}, "hash_changed": initial_hash != dirty_hash,
        "retained_gpu": runtime.telemetry(), "material_queue_before": material_queue_before,
        "material_tasks_drained": drained, "undo": undo_report, "undo_labels_remaining": undo_labels,
        "forced_fallback": fallback.telemetry(), "fallback_tile_parity": fallback_parity,
        "dialog_runtime": dialog_runtime, "performance_threshold_claim": False, "passed": bool(passed),
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False)); dialog.close(); app.processEvents()
    return 0 if passed else 1


if __name__ == "__main__": raise SystemExit(main())
