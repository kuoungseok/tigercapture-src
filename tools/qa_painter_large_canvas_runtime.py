"""Measure real 4K/8K Painter tile, GL, process-memory, dirty, and save paths."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _resources() -> dict:
    from app.painter_runtime_metrics import windows_process_resources
    return windows_process_resources()


def _visual_parity(left, right) -> dict:
    import numpy as np
    from PySide6.QtGui import QImage
    a = left.convertToFormat(QImage.Format.Format_RGBA8888)
    b = right.convertToFormat(QImage.Format.Format_RGBA8888)
    av = np.frombuffer(bytes(a.constBits()), dtype=np.uint8).reshape((a.height(), a.width(), 4)).astype(np.int32)
    bv = np.frombuffer(bytes(b.constBits()), dtype=np.uint8).reshape((b.height(), b.width(), 4)).astype(np.int32)
    av[..., :3] = (av[..., :3] * av[..., 3:4] + 127) // 255
    bv[..., :3] = (bv[..., :3] * bv[..., 3:4] + 127) // 255
    delta = int(abs(av - bv).max()) if av.size else 0
    return {"premultiplied_max_delta": delta, "within_tolerance": delta <= 1}


def _pil_rgba(image):
    from PIL import Image
    from PySide6.QtGui import QImage
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes("RGBA", (converted.width(), converted.height()), bytes(converted.constBits()))


def _patterned_layer(width: int, height: int, index: int):
    """Create spatially identifiable content; a solid fill cannot prove display consumption."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor(20 + index * 28, 48, 112, 255 - index * 42))
    gradient.setColorAt(0.5, QColor(180, 58 + index * 31, 72, 245 - index * 34))
    gradient.setColorAt(1.0, QColor(30, 168, 116 + index * 25, 255 - index * 42))
    painter.fillRect(0, 0, width, height, gradient)
    step = 256
    for ty, y in enumerate(range(0, height, step)):
        for tx, x in enumerate(range(0, width, step)):
            if (tx + ty + index) % 2:
                painter.fillRect(
                    x, y, min(step, width - x), min(step, height - y),
                    QColor(255, 214, 72, 38 + index * 12),
                )
    pen = QPen(QColor(245, 247, 255, 185), max(4, width // 960))
    painter.setPen(pen)
    painter.drawLine(QPointF(0, height * 0.18), QPointF(width, height * 0.82))
    painter.drawLine(QPointF(width * 0.08, height), QPointF(width * 0.92, 0))
    painter.drawEllipse(QRectF(width * 0.36, height * 0.31, width * 0.28, height * 0.38))
    painter.end()
    return image


def _visual_content_metrics(image) -> dict:
    """Report content distribution without an authored quality threshold."""
    import numpy as np
    from PySide6.QtGui import QImage

    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    values = np.frombuffer(bytes(converted.constBits()), dtype=np.uint8).reshape(
        (converted.height(), converted.width(), 4)
    )
    rgb = values[..., :3].astype(np.float32)
    std = rgb.reshape(-1, 3).std(axis=0)
    h, w = rgb.shape[:2]
    quadrants = [
        rgb[: h // 2, : w // 2], rgb[: h // 2, w // 2 :],
        rgb[h // 2 :, : w // 2], rgb[h // 2 :, w // 2 :],
    ]
    means = [row.reshape(-1, 3).mean(axis=0) for row in quadrants if row.size]
    spread = max(
        (float(np.abs(left - right).max()) for i, left in enumerate(means) for right in means[i + 1 :]),
        default=0.0,
    )
    sample = values[:: max(1, h // 64), :: max(1, w // 64), :3].reshape(-1, 3)
    unique_sample_colors = int(np.unique(sample, axis=0).shape[0])
    return {
        "rgb_std": [round(float(row), 3) for row in std],
        "quadrant_max_channel_spread": round(spread, 3),
        "unique_sample_colors": unique_sample_colors,
        "spatially_varied": unique_sample_colors > 1,
        "variation_contract": "sampled_nonuniformity_fact_not_quality_threshold",
    }


def run_case(case: str, output: Path) -> dict:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas
    from app.painter_file_exchange import export_flat_image
    from app.painter_large_canvas import LargeCanvasRuntime

    app = QApplication.instance() or QApplication([])
    sizes = {"4k": (3840, 2160, 3, 256), "8k": (7680, 4320, 2, 256)}
    width, height, layer_count, budget_mb = sizes[case]
    output.mkdir(parents=True, exist_ok=True)
    samples = [{"stage": "before", **_resources()}]
    gpu_error = ""; uploader = None
    try:
        from app.painter_opengl import PainterRetainedGLTileUploader
        uploader = PainterRetainedGLTileUploader()
    except Exception as exc:
        gpu_error = f"{type(exc).__name__}: {exc}"
    runtime = LargeCanvasRuntime(
        tile_size=256, tile_budget_mb=budget_mb, undo_budget_mb=256,
        gpu_uploader=uploader, gpu_deleter=uploader.delete if uploader is not None else None,
    )
    runtime.gpu_creation_error = gpu_error
    sources = {}
    timings = []
    for index in range(layer_count):
        image = _patterned_layer(width, height, index)
        layer_id = f"layer-{index + 1}"
        started = time.perf_counter(); update = runtime.update_layer(layer_id, image); elapsed = (time.perf_counter() - started) * 1000.0
        timings.append({"operation": "full_layer_update", "layer_id": layer_id, "elapsed_ms": elapsed, **update})
        sources[layer_id] = image
        samples.append({"stage": f"layer_{index + 1}_uploaded", **_resources()})
    render_rows = []
    rendered_sources = {}
    for layer_id, image in sources.items():
        started = time.perf_counter(); rendered = runtime.render_layer_image(layer_id, image); elapsed = (time.perf_counter() - started) * 1000.0
        render_rows.append({"layer_id": layer_id, "elapsed_ms": elapsed, "parity": _visual_parity(image, rendered), "display": dict(runtime.last_display)})
        rendered_sources[layer_id] = rendered
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    canvas.resize(1024, 576); canvas.set_document_size(width, height)
    canvas.set_view_pose(rotation_degrees=0.0, content_size=QSize(1024, 576))
    canvas.set_layer_view(
        visibility={key: True for key in sources}, opacity={key: 100 for key in sources},
        order=list(rendered_sources), raster_images=rendered_sources,
    )
    reference_canvas = DrawingCanvas(lambda: 0, lambda: [])
    reference_canvas.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    reference_canvas.resize(1024, 576); reference_canvas.set_document_size(width, height)
    reference_canvas.set_view_pose(rotation_degrees=0.0, content_size=QSize(1024, 576))
    reference_canvas.set_layer_view(
        visibility={key: True for key in sources}, opacity={key: 100 for key in sources},
        order=list(sources), raster_images=sources,
    )
    reference_canvas.show(); app.processEvents()
    canvas.show(); app.processEvents()
    zoom_rows = []
    for zoom in (25, 100, 400):
        started = time.perf_counter(); canvas.set_view_zoom_percent(zoom); reference_canvas.set_view_zoom_percent(zoom); app.processEvents(); pixmap = canvas.grab(); reference_pixmap = reference_canvas.grab(); elapsed = (time.perf_counter() - started) * 1000.0
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        reference_image = reference_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        metrics = _visual_content_metrics(image)
        zoom_rows.append({
            "zoom_percent": zoom,
            "elapsed_ms": elapsed,
            "pixel_bytes": len(bytes(image.constBits())),
            "source_reference_parity": _visual_parity(reference_image, image),
            **metrics,
        })
        if zoom == 100: pixmap.save(str(output / f"{case}_zoom100.png"), "PNG")
    canvas.close(); canvas.deleteLater(); reference_canvas.close(); reference_canvas.deleteLater(); app.processEvents()
    target_id = f"layer-{layer_count}"
    changed = QImage(sources[target_id]); changed.setPixelColor(width // 3, height // 3, QColor(255, 170, 20, 255))
    started = time.perf_counter(); dirty = runtime.update_layer(target_id, changed, dirty_rect=(width // 3, height // 3, 1, 1)); dirty_ms = (time.perf_counter() - started) * 1000.0
    sources[target_id] = changed
    material = changed.copy(0, 0, min(1024, width), min(1024, height))
    material_update = runtime.update_material_map("normal", material, dirty_rect=(200, 200, 64, 64))
    executor_drained = runtime.material_executor.wait(10.0)
    export_path = output / f"{case}_save.png"
    started = time.perf_counter(); export = export_flat_image(export_path, _pil_rgba(changed), bit_depth=8); save_ms = (time.perf_counter() - started) * 1000.0
    samples.append({"stage": "after_save", **_resources()})
    status = runtime.telemetry()
    complete_count = sum(1 for layer_id in sources if runtime.tiles.layer_complete(layer_id))
    resource_deltas = {}
    for key in ("working_set_bytes", "private_usage_bytes", "process_handle_count", "gdi_objects", "user_objects"):
        first, last = samples[0].get(key), samples[-1].get(key)
        resource_deltas[key] = None if first is None or last is None else int(last) - int(first)
    claims = {
        "process_resources_measured": bool(samples[0].get("available") and samples[-1].get("available")),
        "gpu_resources_measured": bool(status["gpu"].get("active") and int(status["gpu"].get("textures", 0)) > 0),
        "all_render_outputs_match": all(row["parity"]["within_tolerance"] for row in render_rows),
        "dirty_update_is_one_tile": int(dirty["updated_tiles"]) == 1,
        "save_reopened_with_integrity": bool(export["inspection"]["integrity"]["valid"]),
        "material_executor_drained": bool(executor_drained and status["material_executor"]["failed"] == 0),
        "zoom_capture_nonuniform": all(row["spatially_varied"] for row in zoom_rows),
        "zoom_path_matches_source_reference": all(row["source_reference_parity"]["within_tolerance"] for row in zoom_rows),
        "budgets_bounded": all(status[name]["bounded"] for name in ("tiles", "brush_stamp_atlas", "material_map_tiles", "wet_canvas_tiles")),
    }
    report = {
        "schema": "tigerstudio.painter.large-canvas-runtime-qa.v3",
        "evidence_class": "native_runtime" if QGuiApplication.platformName().casefold() == "windows" else "simulated_environment",
        "case": case, "canvas": [width, height], "layer_count": layer_count,
        "configured_tile_budget_mb": budget_mb,
        "full_rgba_bytes_per_layer": width * height * 4,
        "full_rgba_bytes_all_layers": width * height * 4 * layer_count,
        "complete_cached_layers": complete_count,
        "samples": samples, "resource_deltas": resource_deltas,
        "timings": timings, "renders": render_rows,
        "zoom": zoom_rows,
        "dirty_update": {**dirty, "elapsed_ms_total": dirty_ms},
        "material_update": material_update, "save_elapsed_ms": save_ms,
        "export": export, "runtime": status, "claims": claims,
        "performance_threshold_claim": False,
        "passed": all(claims.values()),
    }
    destination = output / f"{case}_report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    runtime.close(); app.processEvents()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("4k", "8k"))
    parser.add_argument("--output", type=Path, default=Path("debugCapture/painter/large_canvas_runtime"))
    args = parser.parse_args()
    report = run_case(args.case, args.output)
    print(json.dumps({"report": str((args.output / f'{args.case}_report.json').resolve()), "claims": report["claims"], "timings_ms": {"save": report["save_elapsed_ms"], "dirty": report["dirty_update"]["elapsed_ms_total"]}, "resource_deltas": report["resource_deltas"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
