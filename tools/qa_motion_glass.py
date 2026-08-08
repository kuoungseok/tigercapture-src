"""Render Tiger Glass presets at 1080p and record timing evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.glass_material import GLASS_PRESETS, make_glass_effect
from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.templates import instantiate_template


def _shape(
    name: str,
    color: str,
    width: int,
    height: int,
    x: float,
    y: float,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": width,
            "height": height,
            "fill": color,
            "stroke_width": 0,
        }),
        out_ms=3001,
    )
    layer.transform.position.default = [x, y]
    return layer


def _composition(preset: str) -> MotionComposition:
    layers = [
        _shape("Backdrop", "#153450", 1920, 1080, 960, 540),
        _shape("Warm Panel", "#ef8d4f", 760, 1080, 380, 540),
        _shape("Cool Panel", "#3a78d5", 760, 1080, 1540, 540),
        _shape("Center Accent", "#f3d36a", 520, 1080, 960, 540),
    ]
    glass = _shape("Tiger Glass", "#ffffff", 980, 360, 960, 540)
    glass.effects.append(make_glass_effect(
        {"quality": "preview", "driver_x": 1.2, "driver_y": -0.6},
        preset=preset,
    ))
    layers.append(glass)
    return MotionComposition(
        name=f"Tiger Glass QA {preset}",
        width=1920,
        height=1080,
        duration_ms=3001,
        fps=30,
        layers=layers,
    )


def run(output_dir: Path) -> dict:
    QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=2)
    rows: list[dict] = []
    previews: list[tuple[str, QImage]] = []
    for preset in GLASS_PRESETS:
        composition = _composition(preset)
        timings: list[float] = []
        frame = QImage()
        for time_ms in (250.0, 750.0, 1250.0):
            started = perf_counter()
            frame = renderer.render_frame(composition, time_ms, use_cache=False)
            timings.append((perf_counter() - started) * 1000.0)
        path = output_dir / f"{preset}_1080p.png"
        frame.save(str(path), "PNG")
        previews.append((preset, frame.scaled(480, 270)))
        rows.append({
            "preset": preset,
            "path": str(path),
            "frame_ms": timings,
            "mean_ms": sum(timings) / len(timings),
        })

    sheet = QImage(960, 3 * 306, QImage.Format_RGBA8888)
    sheet.fill(QColor("#101319"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 12))
    painter.setPen(QColor("#f2f4f8"))
    for index, (preset, frame) in enumerate(previews):
        x = (index % 2) * 480
        y = (index // 2) * 306
        painter.drawImage(QRect(x, y, 480, 270), frame)
        painter.drawText(
            QRect(x + 8, y + 274, 464, 24),
            preset.replace("_", " ").title(),
        )
    painter.end()
    sheet_path = output_dir / "tiger_glass_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")

    interactive = _composition("liquid_cta")
    interactive_effect = interactive.layers[-1].effects[0]
    interactive_effect.metadata["driver"] = {
        "source": "pointer",
        "strength": 1.5,
    }
    center = render_graph_image(build_render_graph(
        interactive,
        750.0,
        render_quality="preview",
        runtime_inputs={"pointer": (0.0, 0.0)},
    ))
    lower_right = render_graph_image(build_render_graph(
        interactive,
        750.0,
        render_quality="preview",
        runtime_inputs={"pointer": (1.0, 1.0)},
    ))
    driver_sheet = QImage(960, 270, QImage.Format_RGBA8888)
    driver_sheet.fill(QColor("#101319"))
    driver_painter = QPainter(driver_sheet)
    driver_painter.drawImage(QRect(0, 0, 480, 270), center.scaled(480, 270))
    driver_painter.drawImage(
        QRect(480, 0, 480, 270),
        lower_right.scaled(480, 270),
    )
    driver_painter.end()
    driver_path = output_dir / "tiger_glass_pointer_driver.png"
    driver_sheet.save(str(driver_path), "PNG")

    viewport_graph = build_render_graph(
        interactive,
        750.0,
        render_quality="preview",
    )
    started = perf_counter()
    full_view = render_graph_image(viewport_graph)
    full_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    viewport_view = render_graph_image(
        viewport_graph,
        output_size=(960, 540),
    )
    viewport_ms = (perf_counter() - started) * 1000.0
    reference_view = full_view.scaled(
        960,
        540,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).convertToFormat(QImage.Format_RGBA8888)
    viewport_rgba = viewport_view.convertToFormat(QImage.Format_RGBA8888)

    def rgba(image: QImage) -> np.ndarray:
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(),
            image.bytesPerLine(),
        )
        return rows[:, : image.width() * 4].reshape(
            image.height(),
            image.width(),
            4,
        )

    viewport_difference = np.abs(
        rgba(reference_view).astype(np.int16)
        - rgba(viewport_rgba).astype(np.int16)
    )
    viewport_sheet = QImage(960, 270, QImage.Format_RGBA8888)
    viewport_sheet.fill(QColor("#101319"))
    viewport_painter = QPainter(viewport_sheet)
    viewport_painter.drawImage(
        QRect(0, 0, 480, 270),
        reference_view.scaled(480, 270),
    )
    viewport_painter.drawImage(
        QRect(480, 0, 480, 270),
        viewport_view.scaled(480, 270),
    )
    viewport_painter.end()
    viewport_path = output_dir / "tiger_glass_viewport_parity.png"
    viewport_sheet.save(str(viewport_path), "PNG")
    template = instantiate_template("liquid_glass_app_promo", variant="16:9")
    template_timings: list[dict[str, float]] = []
    for time_ms in range(0, template.duration_ms, 1000):
        started = perf_counter()
        template_graph = build_render_graph(
            template,
            float(time_ms),
            include_vector_gpu=True,
            render_quality="preview",
            output_size=(template.width, template.height),
        )
        render_graph_image(template_graph, output_size=(716, 403))
        template_timings.append({
            "time_ms": float(time_ms),
            "frame_ms": (perf_counter() - started) * 1000.0,
        })
    report = {
        "ok": True,
        "contract": "tigerstudio.motion.glass.v1",
        "resolution": [1920, 1080],
        "quality": "preview",
        "contact_sheet": str(sheet_path),
        "interactive_driver": {
            "source": "pointer",
            "strength": 1.5,
            "center_and_lower_right_differ": center != lower_right,
            "comparison": str(driver_path),
        },
        "viewport_raster": {
            "full_size": [1920, 1080],
            "viewport_size": [960, 540],
            "full_ms": full_ms,
            "viewport_ms": viewport_ms,
            "speedup": full_ms / max(0.001, viewport_ms),
            "mean_rgb_abs_difference": float(
                viewport_difference[..., :3].mean()
            ),
            "mean_alpha_abs_difference": float(
                viewport_difference[..., 3].mean()
            ),
            "comparison": str(viewport_path),
            "template_sample_mean_ms": sum(
                row["frame_ms"] for row in template_timings
            ) / len(template_timings),
            "template_sample_max_ms": max(
                row["frame_ms"] for row in template_timings
            ),
            "template_samples": template_timings,
        },
        "rows": rows,
    }
    (output_dir / "tiger_glass_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "debugCapture" / "motion_glass_qa",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
