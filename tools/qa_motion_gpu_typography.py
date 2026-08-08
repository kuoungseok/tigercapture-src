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
from PySide6.QtGui import QColor, QImage, QPainter, QRawFont
from PySide6.QtWidgets import QApplication

from app.motion_designer.render_graph import build_render_graph, paint_render_graph
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.typography_layout import build_typography_layout
from app.motion_designer.ui.window import MotionDesignerWindow


OUTPUT = ROOT / "debugCapture" / "motion_designer"


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine(),
    )
    return data[:, : converted.width() * 4].reshape(
        converted.height(), converted.width(), 4,
    ).copy()


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="GPU Typography",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "TIGER MOTION\n\u0627\u0644\u0633\u0644\u0627\u0645",
            "width": 900,
            "height": 580,
            "font_family": "Segoe UI",
            "font_size": 132,
            "font_weight": 700,
            "fill": "#f4f7fb",
            "padding": 18,
            "line_height": 1.0,
            "alignment": "center",
            "text_animation": {
                "in": "slide-up-in",
                "hold": "none",
                "out": "none",
                "in_duration_ms": 900,
                "out_duration_ms": 0,
                "unit": "character",
                "stagger_ms": 25,
            },
        }),
        out_ms=2200,
    )
    layer.transform.position.default = [640, 360]
    return MotionComposition(
        name="Typography GPU QA",
        width=1280,
        height=720,
        duration_ms=2200,
        layers=[layer],
    )


def main() -> int:
    app = QApplication.instance() or QApplication([])
    composition = _composition()
    layer = composition.layers[0]
    window = MotionDesignerWindow(composition)
    window.resize(1600, 900)
    window.show()
    window._select_layer(layer.id)
    window.left_tabs.setCurrentWidget(window.inspector_tabs)
    window.inspector_tabs.setCurrentWidget(window.typography)
    window.viewer_tabs.setCurrentWidget(window.preview)
    window.timeline.set_time_and_emit(700)
    for _index in range(40):
        app.processEvents()
        sleep(0.02)

    initial = window.preview.diagnostics()
    initial_upload_count = int(initial.get("glyph_atlas_texture_upload_count", -1))
    for _index in range(12):
        window.preview.update()
        app.processEvents()
        sleep(0.01)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    framebuffer = window.preview.grabFramebuffer()
    gpu_path = OUTPUT / "motion_designer_typography_gpu_preview.png"
    ui_path = OUTPUT / "motion_designer_typography_gpu_ui_1600x900.png"
    painter_path = OUTPUT / "motion_designer_typography_painter_reference.png"
    if framebuffer.isNull() or not framebuffer.save(str(gpu_path), "PNG"):
        raise RuntimeError("Could not capture Motion typography GPU framebuffer")
    if not window.grab().save(str(ui_path), "PNG"):
        raise RuntimeError("Could not capture Motion typography GPU UI")

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
    paint_render_graph(reference_painter, build_render_graph(composition, 700), target_rect)
    reference_painter.end()
    if not painter.save(str(painter_path), "PNG"):
        raise RuntimeError("Could not save Motion typography Painter reference")

    gpu = _rgba(framebuffer).astype(np.int16)
    reference = _rgba(painter).astype(np.int16)
    difference = np.abs(gpu[..., :3] - reference[..., :3])
    diagnostics = window.preview.diagnostics()
    shaped_layout = build_typography_layout(layer, 700)
    arabic_line = shaped_layout.lines[-1]
    shaped_indexes = [glyph.glyph_index for glyph in arabic_line.glyphs]
    raw_indexes = QRawFont.fromFont(shaped_layout.font).glyphIndexesForString(arabic_line.text)
    source_indexes = [glyph.source_index - arabic_line.source_start for glyph in arabic_line.glyphs]
    rtl_positions = [glyph.position.x() for glyph in arabic_line.glyphs]
    shaping = {
        "contextual_forms": shaped_indexes != raw_indexes,
        "source_indexes": source_indexes,
        "source_indexes_valid": bool(source_indexes) and all(
            0 <= index < len(arabic_line.text) for index in source_indexes
        ),
        "rtl_positions_descending": rtl_positions == sorted(rtl_positions, reverse=True),
        "shaped_glyph_indexes": shaped_indexes,
        "unshaped_glyph_indexes": raw_indexes,
    }
    repeated_upload_count = int(diagnostics.get("glyph_atlas_texture_upload_count", -2))
    report = {
        "ok": bool(
            diagnostics.get("backend") == "motion_typography_gpu"
            and diagnostics.get("context_valid")
            and int(diagnostics.get("gl_error", -1)) == 0
            and initial_upload_count > 0
            and repeated_upload_count == initial_upload_count
            and shaping["contextual_forms"]
            and shaping["source_indexes_valid"]
            and shaping["rtl_positions_descending"]
            and float(difference.mean()) <= 3.0
            and float(np.any(difference > 12, axis=2).mean()) <= 0.035
        ),
        "backend": diagnostics,
        "parity": {
            "mean_rgb_abs_error": float(difference.mean()),
            "p99_rgb_abs_error": float(np.percentile(difference, 99)),
            "pixel_fraction_over_12": float(np.any(difference > 12, axis=2).mean()),
        },
        "cache": {
            "initial_texture_upload_count": initial_upload_count,
            "repeated_texture_upload_count": repeated_upload_count,
        },
        "shaping": shaping,
        "outputs": {
            "gpu_preview": str(gpu_path),
            "ui": str(ui_path),
            "painter_reference": str(painter_path),
        },
    }
    report_path = OUTPUT / "motion_designer_typography_gpu_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    window.close()
    app.processEvents()
    print(report_path)
    if not report["ok"]:
        raise RuntimeError(f"Motion typography GPU QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
