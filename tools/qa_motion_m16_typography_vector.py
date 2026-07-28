"""Render the M16 typography/vector acceptance corpus and write evidence."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.path_morph import set_layer_path_morph
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer, SourceRef


OUTPUT = ROOT / "debugCapture" / "motion_designer" / "m16_typography_vector"
SAMPLE_SIZE = (960, 540)


def _animated(default: Any, end: Any, duration_ms: int = 1600) -> dict[str, Any]:
    return {
        "value_type": "scalar",
        "default": default,
        "keyframes": [
            Keyframe(time_ms=0, value=default, interpolation="bezier").to_dict(),
            Keyframe(time_ms=duration_ms, value=end, interpolation="bezier").to_dict(),
        ],
    }


def _text_sample(index: int, animation_id: str) -> MotionComposition:
    palette = [
        ("#66e3c4", "#122a30"),
        ("#ffbd59", "#2d1e16"),
        ("#ff718f", "#311622"),
        ("#8eb8ff", "#17243b"),
        ("#d0a4ff", "#291c38"),
    ]
    accent, shadow = palette[index]
    text = MotionLayer(
        name=f"Kinetic {index + 1}",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": ["MAKE IT MOVE", "TYPE WITH FORCE", "WORDS IN MOTION", "DESIGN THE BEAT", "TIGER VECTOR"][index],
            "width": 900,
            "height": 230,
            "font_family": "Segoe UI",
            "font_size": 72,
            "font_weight": 800,
            "fill": "#f7f9fc",
            "alignment": "center",
            "text_animation": {
                "in": animation_id,
                "hold": "none",
                "out": "none",
                "in_duration_ms": 1500,
                "out_duration_ms": 0,
                "unit": "character",
                "stagger_ms": 45,
                "smoothness": 0.75,
            },
            "text_animators": [{
                    "id": "accent",
                    "in": animation_id,
                    "hold": "none",
                    "out": "none",
                    "in_duration_ms": 1500,
                    "out_duration_ms": 0,
                    "stagger_ms": 45,
                    "smoothness": 0.75,
                    "selector_start": 0.0,
                    "selector_end": 1.0,
                    "selector_shape": ["ramp_up", "triangle", "round", "ramp_down", "square"][index],
                    "selector_amount": 0.75,
                    "properties": {
                        "tracking": [2, 5, 8, 3, 6][index],
                        "fill": accent,
                    },
                }],
        }),
        out_ms=2200,
    )
    text.transform.position.default = [480, 270]
    plate = MotionLayer(
        name="Plate",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "rectangle",
            "width": 900,
            "height": 360,
            "radius": 34,
            "fill": shadow,
            "stroke": accent,
            "stroke_width": 4,
            "offset_path": {"amount": -8, "join": "round"},
        }),
        out_ms=2200,
    )
    plate.transform.position.default = [480, 270]
    return MotionComposition(
        name=text.name,
        width=SAMPLE_SIZE[0],
        height=SAMPLE_SIZE[1],
        duration_ms=2200,
        layers=[plate, text],
    )


def _logo_sample(index: int) -> MotionComposition:
    colors = ["#42d9b5", "#ffbf52", "#ff6688", "#72a7ff", "#c990ff"]
    shape_kind = ["star", "polygon", "ellipse", "rectangle", "star"][index]
    logo = MotionLayer(
        name=f"Logo Reveal {index + 1}",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": shape_kind,
            "width": 230,
            "height": 230,
            "sides": 5 + index,
            "inner_ratio": 0.42,
            "radius": 42,
            "fill": colors[index],
            "stroke": "#f8fbff",
            "stroke_width": 8,
            "stroke_gradient": {
                "type": "linear",
                "start": [0, 0],
                "end": [1, 1],
                "stops": [
                    {"position": 0, "color": "#ffffff"},
                    {"position": 1, "color": colors[index]},
                ],
            },
            "dash": [10 + index * 2, 5],
            "dash_offset": _animated(30.0, 0.0),
            "offset_path": {"amount": 4 + index, "join": "round"},
        }),
        out_ms=2200,
    )
    logo.transform.position.default = [480, 250]
    logo.transform.scale.keyframes = [
        Keyframe(time_ms=0, value=[0.05, 0.05], interpolation="bezier"),
        Keyframe(time_ms=1300, value=[1.0, 1.0], interpolation="bezier"),
    ]
    logo.transform.rotation.keyframes = [
        Keyframe(time_ms=0, value=-120 + index * 15, interpolation="bezier"),
        Keyframe(time_ms=1300, value=0.0, interpolation="bezier"),
    ]
    label = MotionLayer(
        name="Wordmark",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "TIGER",
            "width": 420,
            "height": 100,
            "font_family": "Segoe UI",
            "font_size": 64,
            "font_weight": 800,
            "fill": "#ffffff",
            "alignment": "center",
            "text_animation": {
                "in": "typewriter-in",
                "hold": "none",
                "out": "none",
                "in_duration_ms": 1200,
                "out_duration_ms": 0,
                "stagger_ms": 90,
            },
        }),
        in_ms=500,
        out_ms=2200,
    )
    label.transform.position.default = [480, 430]
    return MotionComposition(
        name=logo.name,
        width=SAMPLE_SIZE[0],
        height=SAMPLE_SIZE[1],
        duration_ms=2200,
        layers=[label, logo],
    )


def _infographic_sample(index: int) -> MotionComposition:
    colors = ["#57e0c0", "#ffb853", "#88aaff"]
    paths = [
        (
            [[40, 180], [250, 70], [470, 160], [700, 35], [880, 100]],
            [[40, 170], [250, 120], [470, 55], [700, 145], [880, 45]],
        ),
        (
            [[40, 80], [250, 150], [470, 40], [700, 175], [880, 90]],
            [[40, 150], [250, 40], [470, 170], [700, 60], [880, 130]],
        ),
        (
            [[40, 160], [250, 90], [470, 140], [700, 65], [880, 165]],
            [[40, 90], [250, 165], [470, 70], [700, 150], [880, 45]],
        ),
    ]

    def path(points: list[list[int]]) -> dict[str, Any]:
        return {
            "closed": False,
            "points": [{"position": point} for point in points],
        }

    line = MotionLayer(
        name=f"Infographic Path {index + 1}",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "path",
            "width": 920,
            "height": 220,
            "path": path(paths[index][0]),
            "fill": "#00000000",
            "stroke": colors[index],
            "stroke_width": 14,
            "cap": "round",
            "join": "round",
            "stroke_taper": {"start": 0.25, "end": 1.0},
        }),
        out_ms=2200,
    )
    set_layer_path_morph(line, [
        {"time_ms": 0, "path": path(paths[index][0])},
        {"time_ms": 1800, "path": path(paths[index][1])},
    ])
    line.transform.position.default = [480, 280]
    title = MotionLayer(
        name="Metric",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": ["AUDIENCE +84%", "WATCH TIME +61%", "CONVERSION +37%"][index],
            "width": 760,
            "height": 100,
            "font_family": "Segoe UI",
            "font_size": 54,
            "font_weight": 700,
            "fill": "#f4f7fb",
            "alignment": "left",
            "text_animation": {
                "in": "slide-right-in",
                "hold": "none",
                "out": "none",
                "in_duration_ms": 900,
                "out_duration_ms": 0,
            },
        }),
        out_ms=2200,
    )
    title.transform.position.default = [480, 90]
    return MotionComposition(
        name=line.name,
        width=SAMPLE_SIZE[0],
        height=SAMPLE_SIZE[1],
        duration_ms=2200,
        layers=[title, line],
    )


def build_acceptance_corpus() -> list[MotionComposition]:
    kinetic = [
        _text_sample(index, animation)
        for index, animation in enumerate([
            "typewriter-in",
            "wave-in",
            "cascade-in",
            "spiral-in",
            "stamp-in",
        ])
    ]
    logos = [_logo_sample(index) for index in range(5)]
    infographics = [_infographic_sample(index) for index in range(3)]
    return [*kinetic, *logos, *infographics]


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    data = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(),
        converted.bytesPerLine(),
    )
    return data[:, : converted.width() * 4].reshape(
        converted.height(),
        converted.width(),
        4,
    ).copy()


def _contact_sheet(rows: list[tuple[str, QImage]], output: Path) -> None:
    cell_width, cell_height = 480, 304
    columns = 3
    row_count = (len(rows) + columns - 1) // columns
    sheet = QImage(
        cell_width * columns,
        cell_height * row_count,
        QImage.Format_RGBA8888_Premultiplied,
    )
    sheet.fill(QColor("#0b0e13"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setFont(QFont("Segoe UI", 11, 600))
    for index, (name, image) in enumerate(rows):
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        painter.drawImage(
            QRect(x + 8, y + 8, cell_width - 16, 261),
            image,
        )
        painter.setPen(QColor("#e8edf5"))
        painter.drawText(QRect(x + 12, y + 271, cell_width - 24, 28), name)
    painter.end()
    if not sheet.save(str(output), "PNG"):
        raise RuntimeError(f"Could not save contact sheet: {output}")


def main() -> int:
    QApplication.instance() or QApplication([])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=16)
    results: list[dict[str, Any]] = []
    contact_rows: list[tuple[str, QImage]] = []
    for index, composition in enumerate(build_acceptance_corpus()):
        start = renderer.render_frame(composition, 150, use_cache=False)
        finish = renderer.render_frame(composition, 1900, use_cache=False)
        start_rgba, finish_rgba = _rgba(start), _rgba(finish)
        difference = np.abs(
            start_rgba.astype(np.int16) - finish_rgba.astype(np.int16),
        )
        alpha_pixels = int(np.count_nonzero(finish_rgba[..., 3]))
        changed_pixels = int(np.count_nonzero(np.any(difference > 6, axis=2)))
        path = OUTPUT / f"{index + 1:02d}_{composition.name.lower().replace(' ', '_')}.png"
        if not finish.save(str(path), "PNG"):
            raise RuntimeError(f"Could not save QA frame: {path}")
        row = {
            "name": composition.name,
            "path": str(path),
            "alpha_pixels": alpha_pixels,
            "changed_pixels": changed_pixels,
            "ok": alpha_pixels > 500 and changed_pixels > 250,
        }
        results.append(row)
        contact_rows.append((composition.name, finish))

    edge_layer = MotionLayer(
        name="4K Edge",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "star",
            "width": 720,
            "height": 720,
            "sides": 11,
            "inner_ratio": 0.58,
            "fill": "#42d9b5",
            "stroke": "#ffffff",
            "stroke_width": 5,
            "offset_path": {"amount": 3, "join": "round"},
        }),
        out_ms=1000,
    )
    edge_layer.transform.position.default = [960, 540]
    edge_composition = MotionComposition(
        name="4K Vector Edge",
        width=1920,
        height=1080,
        duration_ms=1000,
        layers=[edge_layer],
    )
    edge_image = renderer.render_frame(
        edge_composition,
        500,
        width=3840,
        height=2160,
        use_cache=False,
    )
    edge_rgba = _rgba(edge_image)
    partial_alpha = int(np.count_nonzero(
        (edge_rgba[..., 3] > 0) & (edge_rgba[..., 3] < 255),
    ))
    edge_path = OUTPUT / "14_4k_vector_edge.png"
    if not edge_image.save(str(edge_path), "PNG"):
        raise RuntimeError(f"Could not save 4K edge frame: {edge_path}")
    edge_report = {
        "path": str(edge_path),
        "size": [edge_image.width(), edge_image.height()],
        "partial_alpha_pixels": partial_alpha,
        "ok": edge_image.size().width() == 3840 and partial_alpha > 100,
    }
    contact_path = OUTPUT / "m16_typography_vector_contact_sheet.png"
    _contact_sheet(contact_rows, contact_path)
    counts = {
        "kinetic_typography": 5,
        "logo_reveal": 5,
        "infographic_path_animation": 3,
    }
    report = {
        "ok": all(row["ok"] for row in results) and edge_report["ok"],
        "counts": counts,
        "samples": results,
        "edge_4k": edge_report,
        "contact_sheet": str(contact_path),
    }
    report_path = OUTPUT / "m16_typography_vector_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(report_path)
    if not report["ok"]:
        raise RuntimeError(f"M16 typography/vector QA failed: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
