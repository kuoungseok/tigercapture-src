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

from app.motion_designer.particles import create_particle_layer, particle_diagnostics
from app.motion_designer.render_graph import build_render_graph, paint_render_graph
from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "particles"


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(converted.height(), converted.bytesPerLine())
    return data[:, : converted.width() * 4].reshape(converted.height(), converted.width(), 4).copy()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    composition = MotionComposition(id="particle_gpu_qa", name="Particle GPU QA", width=960, height=540,
                                    fps=30, duration_ms=3000)
    layer = create_particle_layer(width=composition.width, height=composition.height,
                                  duration_ms=composition.duration_ms, params={
        "seed": 20260722, "birth_rate": 48, "bursts": [{"time_ms": 0, "count": 36}],
        "emitter": {"kind": "circle", "position": [480, 300], "radius": 95, "size": [190, 190], "path": []},
        "velocity": {"speed": 185, "speed_variance": .25, "angle_deg": -90, "spread_deg": 110},
        "gravity": [0, 135], "turbulence": {"strength": 12, "frequency": 1.2},
        "particle": {"shape": "square", "size_start": 17, "size_end": 4,
                     "opacity_start": 1, "opacity_end": 0, "color_start": "#54e3c2",
                     "color_end": "#f3c76500", "rotation_speed": 70, "sprite_uri": ""},
    })
    layer.blend_mode = "screen"
    composition.layers.append(layer)
    time_ms = 900
    window = MotionDesignerWindow(composition)
    window.resize(1500, 900)
    window.show()
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.particle)
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(time_ms)
    for _ in range(50):
        app.processEvents()
        sleep(.02)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    framebuffer = window.preview.grabFramebuffer()
    gpu_path = OUTPUT / "particle_gpu_preview.png"
    ui_path = OUTPUT / "particle_gpu_ui.png"
    painter_path = OUTPUT / "particle_painter_reference.png"
    if framebuffer.isNull() or not framebuffer.save(str(gpu_path), "PNG"):
        raise RuntimeError("Could not capture particle GPU framebuffer")
    if not window.grab().save(str(ui_path), "PNG"):
        raise RuntimeError("Could not capture particle UI")
    painter = QImage(framebuffer.size(), QImage.Format_RGBA8888_Premultiplied)
    painter.fill(QColor("#0b0d11"))
    scale = min(framebuffer.width() / composition.width, framebuffer.height() / composition.height)
    target = QRectF((framebuffer.width() - composition.width * scale) * .5,
                    (framebuffer.height() - composition.height * scale) * .5,
                    composition.width * scale, composition.height * scale)
    reference_painter = QPainter(painter)
    paint_render_graph(reference_painter, build_render_graph(composition, time_ms), target)
    reference_painter.end()
    if not painter.save(str(painter_path), "PNG"):
        raise RuntimeError("Could not save particle Painter reference")
    gpu = _rgba(framebuffer).astype(np.int16)
    reference = _rgba(painter).astype(np.int16)
    difference = np.abs(gpu[..., :3] - reference[..., :3])
    diagnostics = window.preview.diagnostics()
    particle_info = particle_diagnostics(layer, time_ms)
    report = {
        "ok": bool(
            diagnostics.get("backend") == "motion_vector_gpu"
            and diagnostics.get("context_valid")
            and int(diagnostics.get("gl_error", -1)) == 0
            and particle_info["particle_count"] > 0
            and float(difference.mean()) <= 5.0
            and float(np.any(difference > 12, axis=2).mean()) <= .06
        ),
        "opengl_only": True,
        "software_renderer_used": False,
        "backend": diagnostics,
        "particle": particle_info,
        "parity": {
            "mean_rgb_abs_error": float(difference.mean()),
            "p99_rgb_abs_error": float(np.percentile(difference, 99)),
            "pixel_fraction_over_12": float(np.any(difference > 12, axis=2).mean()),
        },
        "outputs": {"gpu_preview": str(gpu_path), "ui": str(ui_path), "painter_reference": str(painter_path)},
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise RuntimeError(f"Motion particle GPU QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
