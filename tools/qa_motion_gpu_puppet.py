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

from app.motion_designer.puppet_mesh import (
    add_puppet_pin,
    create_alpha_adaptive_puppet_mesh,
    layer_puppet_mesh,
)
from app.motion_designer.render_graph import build_render_graph, paint_render_graph
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "gpu_puppet"


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine(),
    )
    return data[:, : converted.width() * 4].reshape(
        converted.height(), converted.width(), 4,
    ).copy()


def _composition(source_path: Path) -> MotionComposition:
    source = QImage(360, 360, QImage.Format_RGBA8888)
    source.fill(QColor(0, 0, 0, 0))
    painter = QPainter(source)
    painter.setPen(QColor("#f8fbff"))
    painter.setBrush(QColor("#27c7b8"))
    painter.drawEllipse(34, 22, 292, 316)
    painter.setBrush(QColor("#ffcc4d"))
    painter.drawEllipse(92, 82, 176, 176)
    painter.end()
    if not source.save(str(source_path), "PNG"):
        raise RuntimeError(f"Could not create puppet QA source: {source_path}")
    layer = MotionLayer(
        id="gpu_puppet_subject",
        name="GPU Puppet Subject",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(source_path),
            params={"width": 360, "height": 360},
        ),
        out_ms=2400,
    )
    layer.transform.position.default = [480, 270]
    create_alpha_adaptive_puppet_mesh(layer, columns=14, rows=14)
    pin = add_puppet_pin(
        layer,
        kind="position",
        position=[0.5, 0.43],
        radius=0.38,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    animated = next(row for row in mesh.pins if row.id == pin.id)
    animated.position.keyframes = [
        Keyframe(time_ms=0, value=[0.5, 0.43]),
        Keyframe(time_ms=1200, value=[0.61, 0.36]),
        Keyframe(time_ms=2400, value=[0.5, 0.43]),
    ]
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    return MotionComposition(
        id="gpu_puppet_qa",
        name="GPU Puppet QA",
        width=960,
        height=540,
        fps=30,
        duration_ms=2400,
        layers=[layer],
    )


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    composition = _composition(OUTPUT / "puppet_source.png")
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(1200)
    for _ in range(45):
        app.processEvents()
        sleep(0.015)

    initial = window.preview.diagnostics()
    initial_texture_uploads = int(initial.get("texture_upload_count", -1))
    for frame in range(12):
        window.preview.set_time(1200 + frame)
        app.processEvents()
        sleep(0.01)
    framebuffer = window.preview.grabFramebuffer()
    gpu_path = OUTPUT / "gpu_preview.png"
    ui_path = OUTPUT / "gpu_ui.png"
    painter_path = OUTPUT / "painter_reference.png"
    if framebuffer.isNull() or not framebuffer.save(str(gpu_path), "PNG"):
        raise RuntimeError("Could not capture puppet GPU framebuffer")
    if not window.grab().save(str(ui_path), "PNG"):
        raise RuntimeError("Could not capture puppet GPU UI")

    reference = QImage(framebuffer.size(), QImage.Format_RGBA8888_Premultiplied)
    reference.fill(QColor("#0b0d11"))
    scale = min(
        framebuffer.width() / composition.width,
        framebuffer.height() / composition.height,
    )
    target = QRectF(
        (framebuffer.width() - composition.width * scale) * 0.5,
        (framebuffer.height() - composition.height * scale) * 0.5,
        composition.width * scale,
        composition.height * scale,
    )
    painter = QPainter(reference)
    paint_render_graph(
        painter,
        build_render_graph(composition, 1211, include_vector_gpu=False),
        target,
    )
    painter.end()
    reference.save(str(painter_path), "PNG")

    gpu = _rgba(framebuffer).astype(np.int16)
    cpu = _rgba(reference).astype(np.int16)
    difference = np.abs(gpu[..., :3] - cpu[..., :3])
    diagnostics = window.preview.diagnostics()
    report = {
        "ok": bool(
            diagnostics.get("backend") == "motion_puppet_gpu"
            and diagnostics.get("context_valid")
            and int(diagnostics.get("gl_error", -1)) == 0
            and initial_texture_uploads == 1
            and int(diagnostics.get("texture_upload_count", -1)) == 1
            and float(difference.mean()) <= 5.0
            and float(np.any(difference > 16, axis=2).mean()) <= 0.05
        ),
        "backend": diagnostics,
        "parity": {
            "mean_rgb_abs_error": float(difference.mean()),
            "p99_rgb_abs_error": float(np.percentile(difference, 99)),
            "pixel_fraction_over_16": float(np.any(difference > 16, axis=2).mean()),
        },
        "cache": {
            "initial_texture_upload_count": initial_texture_uploads,
            "repeated_texture_upload_count": int(
                diagnostics.get("texture_upload_count", -1)
            ),
        },
        "outputs": {
            "gpu_preview": str(gpu_path.resolve()),
            "ui": str(ui_path.resolve()),
            "painter_reference": str(painter_path.resolve()),
        },
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    window.close()
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    if not report["ok"]:
        raise RuntimeError(f"Motion puppet GPU QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
