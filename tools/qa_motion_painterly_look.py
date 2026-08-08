from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.painterly_look import (
    PAINTERLY_LOOK_PRESETS,
    make_painterly_look_effect,
)


OUTPUT = ROOT / "debugCapture" / "motion_painterly_look_qa"


def _rgba(image: QImage) -> np.ndarray:
    straight = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(),
        straight.bytesPerLine(),
    )
    return rows[:, : straight.width() * 4].reshape(
        straight.height(),
        straight.width(),
        4,
    ).copy()


def _source() -> QImage:
    image = QImage(480, 270, QImage.Format_RGBA8888_Premultiplied)
    image.fill(QColor("#18222f"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.fillRect(QRectF(0, 0, 480, 270), QColor("#d9c6a3"))
    painter.setBrush(QColor("#356a7f"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(QRectF(40, 30, 205, 205))
    painter.setBrush(QColor("#d46b4b"))
    painter.drawRoundedRect(QRectF(226, 48, 205, 174), 22, 22)
    painter.setBrush(QColor("#f4e8cf"))
    painter.drawEllipse(QRectF(166, 66, 150, 150))
    painter.setPen(QPen(QColor("#18222f"), 12, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(196, 142, 286, 142)
    painter.setPen(QPen(QColor("#f7f3e9"), 8, Qt.SolidLine, Qt.RoundCap))
    for index, width in enumerate((132, 108, 144, 84)):
        y = 91 + index * 29
        painter.drawLine(256, y, 256 + width, y)
    painter.end()
    return image


def main() -> int:
    app = QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = _source()
    source.save(str(OUTPUT / "source.png"), "PNG")
    presets = list(PAINTERLY_LOOK_PRESETS)
    rows: list[dict] = []
    frames: list[QImage] = []
    source_array = _rgba(source)
    for preset in presets:
        effect = make_painterly_look_effect({"seed": 2048}, preset=preset)
        frame = apply_effects(source, [effect], 0)
        repeated = apply_effects(source, [effect], 918)
        array = _rgba(frame)
        stable = np.array_equal(array, _rgba(repeated))
        alpha_ok = np.array_equal(array[..., 3], source_array[..., 3])
        difference = float(np.mean(np.abs(
            array[..., :3].astype(np.float32)
            - source_array[..., :3].astype(np.float32)
        )))
        output_path = OUTPUT / f"{preset}.png"
        frame.save(str(output_path), "PNG")
        frames.append(frame)
        rows.append({
            "preset": preset,
            "temporal_stable": stable,
            "alpha_preserved": alpha_ok,
            "mean_rgb_difference": difference,
            "output": str(output_path),
        })

    benchmark_source = source.scaled(960, 540)
    benchmark_effect = make_painterly_look_effect(
        {"seed": 2048},
        preset="painted",
    )
    apply_effects(benchmark_source, [benchmark_effect], 0)
    benchmark_started = time.perf_counter()
    apply_effects(benchmark_source, [benchmark_effect], 33)
    benchmark_ms = (time.perf_counter() - benchmark_started) * 1000.0

    label_height = 32
    sheet_path = OUTPUT / "painterly_look_contact_sheet.png"
    from PIL import Image, ImageDraw, ImageFont

    sheet = Image.new(
        "RGB",
        (source.width() * len(frames), source.height() + label_height),
        "#0b0e13",
    )
    font_path = Path("C:/Windows/Fonts/arialbd.ttf")
    font = (
        ImageFont.truetype(str(font_path), 16)
        if font_path.is_file()
        else ImageFont.load_default()
    )
    draw = ImageDraw.Draw(sheet)
    for index, (preset, row) in enumerate(zip(presets, rows)):
        x = index * source.width()
        draw.text((x + 10, 7), preset.upper(), fill="#f2f5f8", font=font)
        sheet.paste(Image.open(row["output"]).convert("RGB"), (x, label_height))
    sheet.save(sheet_path, "PNG")
    report = {
        "schema": "tigerstudio.motion.painterly_look_qa.v1",
        "ok": (
            len(rows) == 5
            and all(row["temporal_stable"] for row in rows)
            and all(row["alpha_preserved"] for row in rows)
            and all(row["mean_rgb_difference"] > 0.1 for row in rows[1:])
        ),
        "renderer": "motion.effect_adapter.apply_effects",
        "input_types": ["image", "video_frame", "existing_ar_pbr_frame"],
        "contact_sheet": str(sheet_path),
        "presets": rows,
        "benchmark": {
            "width": 960,
            "height": 540,
            "preset": "painted",
            "warm_frame_ms": benchmark_ms,
            "working_limit": 480,
            "measurement": "diagnostic_not_a_gpu_realtime_claim",
        },
        "material_id_overrides": "explicit_preflight_until_id_pass_exists",
    }
    report_path = OUTPUT / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app.processEvents()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
