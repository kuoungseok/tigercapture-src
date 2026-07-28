"""Generate real Motion Designer craft-style comparison evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.craft_style import CRAFT_STYLE_PRESETS, make_craft_style_effect
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _composition(preset: str | None) -> MotionComposition:
    layer = MotionLayer(
        name="Craft QA Card",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 300,
            "height": 160,
            "fill": "#d6a15f",
            "stroke": "#183244",
            "stroke_width": 5,
            "radius": 18,
        }),
        out_ms=4001,
    )
    layer.transform.position.default = [160, 90]
    if preset is not None:
        layer.effects.append(make_craft_style_effect(
            {"seed": 20260729, "loop_period": 4.0},
            preset=preset,
        ))
    return MotionComposition(
        name=f"Craft QA {preset or 'clean'}",
        width=320,
        height=180,
        duration_ms=4001,
        fps=30,
        layers=[layer],
    )


def _digest(image: QImage) -> str:
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def run(output_dir: Path) -> dict:
    QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=2)
    names = ["clean", *CRAFT_STYLE_PRESETS]
    frames: list[QImage] = []
    rows: list[dict] = []
    for name in names:
        composition = _composition(None if name == "clean" else name)
        frame = renderer.render_frame(composition, 1750, use_cache=False)
        path = output_dir / f"{name}.png"
        if not frame.save(str(path), "PNG"):
            raise RuntimeError(f"Failed to save {path}")
        frames.append(frame)
        rows.append({"name": name, "path": str(path), "sha256": _digest(frame)})

    columns = 2
    cell_width, cell_height = 320, 208
    sheet = QImage(
        columns * cell_width,
        ((len(frames) + columns - 1) // columns) * cell_height,
        QImage.Format_RGBA8888,
    )
    sheet.fill(QColor("#101319"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 11))
    painter.setPen(QColor("#f2f4f8"))
    for index, (name, frame) in enumerate(zip(names, frames)):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        painter.drawImage(QRect(x, y, 320, 180), frame)
        painter.drawText(
            QRect(x + 8, y + 182, 304, 22),
            name.replace("_", " ").title(),
        )
    painter.end()
    sheet_path = output_dir / "craft_style_contact_sheet.png"
    sheet.save(str(sheet_path), "PNG")
    report = {
        "ok": True,
        "contract": "tigerstudio.motion.craft_style.v1",
        "comparison_count": len(rows),
        "contact_sheet": str(sheet_path),
        "rows": rows,
    }
    (output_dir / "craft_style_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "debugCapture" / "motion_craft_style_qa",
    )
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
