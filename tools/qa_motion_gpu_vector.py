from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import sleep

if os.name == "nt":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QT_OPENGL", "desktop")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.motion_designer.render_graph import build_render_graph, paint_render_graph
from app.motion_designer.ui.window import MotionDesignerWindow
from tools.qa_motion_ui import build_boolean_composition


OUTPUT = ROOT / "debugCapture" / "motion_designer"


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine(),
    )
    return data[:, : converted.width() * 4].reshape(converted.height(), converted.width(), 4).copy()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    composition = build_boolean_composition()
    target = next(layer for layer in composition.layers if layer.name == "Boolean Plate")
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    window._select_layer(target.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.vector)
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(1200)
    for _ in range(40):
        app.processEvents()
        sleep(0.02)

    initial_diagnostics = window.preview.diagnostics()
    initial_upload_count = int(initial_diagnostics.get("vbo_upload_count", -1))
    for _ in range(12):
        window.preview.update()
        app.processEvents()
        sleep(0.01)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    framebuffer = window.preview.grabFramebuffer()
    gpu_path = OUTPUT / "motion_designer_boolean_gpu_preview.png"
    ui_path = OUTPUT / "motion_designer_boolean_gpu_ui_1600x900.png"
    painter_path = OUTPUT / "motion_designer_boolean_painter_reference.png"
    if framebuffer.isNull() or not framebuffer.save(str(gpu_path), "PNG"):
        raise RuntimeError("Could not capture Motion vector GPU framebuffer")
    if not window.grab().save(str(ui_path), "PNG"):
        raise RuntimeError("Could not capture Motion Designer GPU UI")
    painter = QImage(framebuffer.size(), QImage.Format_RGBA8888_Premultiplied)
    painter.fill(QColor("#0b0d11"))
    scale = min(framebuffer.width() / composition.width, framebuffer.height() / composition.height)
    target_rect = QRectF(
        (framebuffer.width() - composition.width * scale) * 0.5,
        (framebuffer.height() - composition.height * scale) * 0.5,
        composition.width * scale,
        composition.height * scale,
    )
    reference_painter = QPainter(painter)
    paint_render_graph(reference_painter, build_render_graph(composition, 1200), target_rect)
    reference_painter.end()
    if not painter.save(str(painter_path), "PNG"):
        raise RuntimeError("Could not save Motion vector Painter reference")

    gpu, reference = _rgba(framebuffer).astype(np.int16), _rgba(painter).astype(np.int16)
    difference = np.abs(gpu[..., :3] - reference[..., :3])
    diagnostics = window.preview.diagnostics()
    report = {
        "ok": bool(
            diagnostics.get("backend") == "motion_vector_gpu"
            and diagnostics.get("context_valid")
            and int(diagnostics.get("gl_error", -1)) == 0
            and int(diagnostics.get("vbo_upload_count", -2)) == initial_upload_count
            and float(difference.mean()) <= 2.0
            and float(np.any(difference > 8, axis=2).mean()) <= 0.02
        ),
        "backend": diagnostics,
        "parity": {
            "mean_rgb_abs_error": float(difference.mean()),
            "p99_rgb_abs_error": float(np.percentile(difference, 99)),
            "pixel_fraction_over_8": float(np.any(difference > 8, axis=2).mean()),
        },
        "cache": {
            "initial_vbo_upload_count": initial_upload_count,
            "repeated_vbo_upload_count": int(diagnostics.get("vbo_upload_count", -1)),
            "gpu_mesh_cache_hits": int(diagnostics.get("gpu_mesh_cache_hits", 0)),
        },
        "outputs": {
            "gpu_preview": str(gpu_path),
            "ui": str(ui_path),
            "painter_reference": str(painter_path),
        },
    }
    report_path = OUTPUT / "motion_designer_boolean_gpu_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    window.close()
    app.processEvents()
    print(report_path)
    if not report["ok"]:
        raise RuntimeError(f"Motion vector GPU QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
