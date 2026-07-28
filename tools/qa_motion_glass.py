"""Render Tiger Glass presets at 1080p and record timing evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.glass_material import GLASS_PRESETS, make_glass_effect
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


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
    report = {
        "ok": True,
        "contract": "tigerstudio.motion.glass.v1",
        "resolution": [1920, 1080],
        "quality": "preview",
        "contact_sheet": str(sheet_path),
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
