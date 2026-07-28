"""Render real M25 stop-motion timing and material evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer  # noqa: E402
from app.motion_designer.schema import (  # noqa: E402
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.stop_motion import (  # noqa: E402
    preflight_stop_motion,
    set_stop_motion,
    set_stop_motion_material,
)


SCENARIOS = (
    ("clay_mascot_6s", 6000, "clay", "contact_settle", "#ef7357"),
    ("miniature_product_10s", 10_000, "painted_wood", "overshoot", "#54b7bd"),
    ("paper_replacement_8s", 8000, "cardboard", "replacement_pop", "#e4bd55"),
)


def _scenario(
    name: str,
    duration_ms: int,
    material: str,
    style: str,
    fill: str,
) -> MotionComposition:
    background = MotionLayer(
        name="Miniature Stage",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 640,
            "height": 360,
            "fill": "#17202a",
            "stroke_width": 0,
        }),
        out_ms=duration_ms,
    )
    background.transform.position.default = [320, 180]
    subject = MotionLayer(
        name=name.replace("_", " ").title(),
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 180,
            "height": 210,
            "fill": fill,
            "stroke": "#f5ead9",
            "stroke_width": 5,
            "radius": 28,
        }),
        out_ms=duration_ms,
    )
    subject.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[130.0, 200.0],
        keyframes=[
            Keyframe(time_ms=0, value=[130.0, 200.0], interpolation="linear"),
            Keyframe(
                time_ms=duration_ms // 2,
                value=[500.0, 145.0],
                interpolation="linear",
            ),
            Keyframe(
                time_ms=duration_ms,
                value=[220.0, 205.0],
                interpolation="linear",
            ),
        ],
    )
    composition = MotionComposition(
        name=name,
        width=640,
        height=360,
        fps=30,
        duration_ms=duration_ms,
        layers=[background, subject],
    )
    set_stop_motion(composition, {
        "enabled": True,
        "exposure_frames": 3,
        "pose_jitter_px": 2.2,
        "rotation_jitter_deg": 0.65,
        "scale_jitter": 0.012,
        "motion_style": style,
        "seed": 20260729,
        "onion_skin_frames": 1,
    })
    set_stop_motion_material(
        composition,
        [subject.id],
        preset=material,
        seed=20260729,
    )
    return composition


def _digest(image: QImage) -> str:
    return hashlib.sha256(bytes(image.constBits())).hexdigest()


def _sheet(rows: list[tuple[str, QImage]], output: Path) -> None:
    cell_width, cell_height = 640, 400
    sheet = QImage(cell_width * 3, cell_height * len(SCENARIOS), QImage.Format_RGBA8888)
    sheet.fill(QColor("#090c11"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 12))
    painter.setPen(QColor("#f4f6fa"))
    for index, (label, image) in enumerate(rows):
        row, column = divmod(index, 3)
        x, y = column * cell_width, row * cell_height
        painter.drawImage(QRect(x, y, 640, 360), image)
        painter.drawText(QRect(x + 10, y + 366, 620, 28), label)
    painter.end()
    if not sheet.save(str(output), "PNG"):
        raise RuntimeError(f"Failed to save {output}")


def run(output_dir: Path) -> dict:
    QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=2)
    evidence: list[tuple[str, QImage]] = []
    reports: list[dict] = []
    cadence_violations = 0
    unintended_interpolation = 0
    for name, duration, material, style, fill in SCENARIOS:
        composition = _scenario(name, duration, material, style, fill)
        # 105 and 166 ms are inside the same three-frame exposure at 30 fps.
        times = (105.0, 166.0, 205.0)
        frames = [
            renderer.render_frame(composition, time_ms, use_cache=False)
            for time_ms in times
        ]
        digests = [_digest(frame) for frame in frames]
        hold_ok = digests[0] == digests[1]
        next_exposure_changes = digests[1] != digests[2]
        unintended_interpolation += int(not hold_ok)
        report = preflight_stop_motion(composition)
        cadence_violations += int(report["summary"]["cadence_violation_count"])
        for label, frame in zip(("hold A", "hold B", "next exposure"), frames):
            evidence.append((f"{name}: {label}", frame))
        reports.append({
            "name": name,
            "duration_ms": duration,
            "material": material,
            "motion_style": style,
            "hold_pixel_identical": hold_ok,
            "next_exposure_changes": next_exposure_changes,
            "digests": digests,
            "preflight": report,
        })
    sheet_path = output_dir / "stop_motion_contact_sheet.png"
    _sheet(evidence, sheet_path)
    result = {
        "ok": (
            cadence_violations == 0
            and unintended_interpolation == 0
            and all(row["next_exposure_changes"] for row in reports)
        ),
        "contract": "tigerstudio.motion.stop_motion.v1",
        "scenario_count": len(reports),
        "cadence_violation_count": cadence_violations,
        "unintended_interpolation_inside_holds": unintended_interpolation,
        "contact_sheet": str(sheet_path),
        "scenarios": reports,
    }
    (output_dir / "stop_motion_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "debugCapture" / "motion_stop_motion_qa",
    )
    args = parser.parse_args()
    report = run(args.output_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
