"""Generate deterministic Motion LUT/tone-map preview/export parity evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.color_management import settings_from_composition_metadata
from app.motion_designer.color_runtime import (
    apply_motion_color_pipeline_premultiplied_rgba,
)
from app.motion_designer.export_pipeline import MotionProfileExporter
from app.motion_designer.schema import MotionComposition


def _write_look_lut(path: Path) -> None:
    lines = [
        'TITLE "Tiger Motion QA Look"',
        "LUT_3D_SIZE 2",
        "DOMAIN_MIN 0 0 0",
        "DOMAIN_MAX 1 1 1",
    ]
    for blue in (0.0, 1.0):
        for green in (0.0, 1.0):
            for red in (0.0, 1.0):
                lines.append(
                    f"{min(1.0, red * 1.04):.6f} "
                    f"{min(1.0, green * 0.94 + red * 0.04):.6f} "
                    f"{min(1.0, blue * 0.88 + red * 0.08):.6f}"
                )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _source_rgba(width: int, height: int) -> np.ndarray:
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    straight = np.empty((height, width, 3), dtype=np.float32)
    straight[..., 0] = x
    straight[..., 1] = y
    straight[..., 2] = 1.0 - x * 0.7
    radius = np.sqrt((x - 0.5) ** 2 + (y - 0.5) ** 2)
    alpha = np.clip((0.58 - radius) * 12.0, 0.0, 1.0)[..., None]
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = np.rint(straight * alpha * 255.0).clip(0, 255).astype(np.uint8)
    rgba[..., 3] = np.rint(alpha[..., 0] * 255.0).clip(0, 255).astype(np.uint8)
    return rgba


def _read_premultiplied(path: Path) -> np.ndarray:
    image = QImage(str(path)).convertToFormat(QImage.Format_RGBA8888_Premultiplied)
    rows = np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
    return rows[:, : image.width() * 4].reshape(image.height(), image.width(), 4).copy()


def main() -> int:
    output_dir = ROOT / "debugCapture" / "motion_color_pipeline"
    output_dir.mkdir(parents=True, exist_ok=True)
    lut_path = output_dir / "qa_look.cube"
    _write_look_lut(lut_path)
    source = _source_rgba(256, 144)
    composition = MotionComposition(width=256, height=144, duration_ms=1000)
    settings = settings_from_composition_metadata(composition.metadata).to_dict()
    settings["tone_map"] = "aces-fitted"
    settings["project"]["input_lut"] = {
        "path": str(lut_path), "strength": 0.35, "enabled": True,
    }
    settings["project"]["creative_lut"] = {
        "path": str(lut_path), "strength": 0.8, "enabled": True,
    }
    settings["project"]["output_lut"] = {
        "path": str(lut_path), "strength": 0.25, "enabled": True,
    }
    composition.metadata["color_management"] = settings
    color = settings_from_composition_metadata(composition.metadata)
    expected, runtime_report = apply_motion_color_pipeline_premultiplied_rgba(source, color)

    class Renderer:
        def render_rgba_array(self, *_args, **_kwargs):
            return source.copy()

    export_path = output_dir / "export.png"
    MotionProfileExporter(renderer=Renderer()).export(
        composition, "png_still", export_path, time_ms=0.0,
    )
    actual = _read_premultiplied(export_path)
    difference = np.abs(actual.astype(np.int16) - expected.astype(np.int16))
    report = {
        "ok": bool(np.max(difference) == 0),
        "schema": "tigerstudio.motion.color.parity.v1",
        "preview_export_max_abs_byte_delta": int(np.max(difference)),
        "preview_export_mean_abs_byte_delta": float(np.mean(difference)),
        "alpha_max_abs_byte_delta": int(
            np.max(np.abs(actual[..., 3].astype(np.int16) - source[..., 3].astype(np.int16)))
        ),
        "pipeline": runtime_report,
        "lut": str(lut_path),
        "export": str(export_path),
    }
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
