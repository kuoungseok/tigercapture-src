"""Render M27 five-style review evidence through the shared Motion renderer."""
from __future__ import annotations

import argparse
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
from app.motion_designer.style_director import (  # noqa: E402
    apply_story_direction,
    apply_style_candidate,
    plan_story_direction,
    plan_style_direction,
    trend_preflight,
)


def _composition() -> MotionComposition:
    background = MotionLayer(
        id="background",
        name="Background",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 640,
            "height": 360,
            "fill": "#111923",
            "stroke_width": 0,
        }),
        out_ms=6000,
    )
    background.transform.position.default = [320, 180]
    product = MotionLayer(
        id="product",
        name="Product",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 210,
            "height": 230,
            "fill": "#ed7453",
            "stroke": "#fff1d6",
            "stroke_width": 5,
            "radius": 34,
        }),
        out_ms=6000,
    )
    product.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[190.0, 200.0],
        keyframes=[
            Keyframe(
                id="product_start",
                time_ms=0,
                value=[190.0, 200.0],
                interpolation="bezier",
            ),
            Keyframe(
                id="product_end",
                time_ms=6000,
                value=[450.0, 200.0],
                interpolation="bezier",
            ),
        ],
    )
    title = MotionLayer(
        id="title",
        name="Title",
        layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "MAKE IT MOVE",
            "font_family": "Arial",
            "font_size": 54,
            "font_weight": 800,
            "fill": "#ffffff",
            "width": 520,
            "height": 90,
            "alignment": "center",
        }),
        out_ms=6000,
    )
    title.transform.position.default = [320, 70]
    return MotionComposition(
        id="m27_style_qa",
        name="M27 Style Director QA",
        width=640,
        height=360,
        fps=30,
        duration_ms=6000,
        revision=7,
        layers=[background, product, title],
    )


def _contact_sheet(rows: list[tuple[str, QImage]], path: Path) -> None:
    cell_width, cell_height = 640, 398
    sheet = QImage(cell_width * 3, cell_height * 2, QImage.Format_RGBA8888)
    sheet.fill(QColor("#080b10"))
    painter = QPainter(sheet)
    painter.setFont(QFont("Segoe UI", 12))
    painter.setPen(QColor("#f3f5f8"))
    for index, (label, image) in enumerate(rows):
        x = (index % 3) * cell_width
        y = (index // 3) * cell_height
        painter.drawImage(QRect(x, y, 640, 360), image)
        painter.drawText(QRect(x + 10, y + 365, 620, 26), label)
    painter.end()
    if not sheet.save(str(path), "PNG"):
        raise RuntimeError(f"Failed to save {path}")


def run(output_dir: Path) -> dict:
    QApplication.instance() or QApplication([])
    output_dir.mkdir(parents=True, exist_ok=True)
    source = _composition()
    source_snapshot = source.to_dict()
    plan = plan_style_direction(
        source,
        'Premium handmade product story. End with "MAKE IT MOVE".',
        [{
            "id": "brand_reference",
            "kind": "text",
            "name": "Brand brief",
            "metadata": {
                "provenance": {
                    "kind": "manual",
                    "fingerprint": "m27-local-brief",
                },
            },
        }],
        backend_snapshot={
            "selected_provider": "rule_based",
            "effective_generation_provider": "rule_based",
            "providers": {"rule_based": {"available": True}},
        },
        seed=20260729,
    )
    renderer = MotionExportRenderer(cache_capacity=2)
    frames = []
    reports = []
    for candidate in plan["candidates"]:
        styled, apply_report = apply_style_candidate(
            source,
            plan,
            str(candidate["id"]),
            approved=True,
        )
        frame = renderer.render_frame(styled, 2100, use_cache=False)
        frame_path = output_dir / f"{candidate['style_id']}.png"
        if not frame.save(str(frame_path), "PNG"):
            raise RuntimeError(f"Failed to save {frame_path}")
        frames.append((str(candidate["title"]), frame))
        reports.append({
            "style_id": candidate["style_id"],
            "candidate_id": candidate["id"],
            "path": str(frame_path),
            "renderer": "MotionExportRenderer",
            "editable": True,
            "apply_report": apply_report,
        })
    story_plan = plan_story_direction(source, str(plan["prompt"]))
    story_result, story_report = apply_story_direction(
        source,
        story_plan,
        approved=True,
    )
    sheet_path = output_dir / "style_director_contact_sheet.png"
    _contact_sheet(frames, sheet_path)
    source_unchanged = source.to_dict() == source_snapshot
    result = {
        "ok": (
            len(reports) == 5
            and source_unchanged
            and all(
                row["apply_report"]["transform_keyframes_preserved"]
                for row in reports
            )
            and story_report["beat_count"] == 8
        ),
        "contract": "tigerstudio.motion.ai_style_plan.v1",
        "candidate_count": len(reports),
        "contact_sheet": str(sheet_path),
        "source_unchanged": source_unchanged,
        "transform_keyframe_loss_count": sum(
            int(not row["apply_report"]["transform_keyframes_preserved"])
            for row in reports
        ),
        "story_beat_count": len(
            story_result.metadata["story_direction"]["beats"],
        ),
        "preflight": trend_preflight(source, plan),
        "candidates": reports,
    }
    (output_dir / "style_director_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "debugCapture" / "motion_style_director_qa",
    )
    args = parser.parse_args()
    report = run(args.output_dir.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
