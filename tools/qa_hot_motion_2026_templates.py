"""Render a visual QA sheet for the ten Hot Motion 2026 templates."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.templates import instantiate_template, list_templates


OUTPUT = ROOT / "debugCapture" / "motion_hot_2026"


def render() -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    rows = [row for row in list_templates() if row["category"] == "Hot Motion 2026"]
    if len(rows) != 10:
        raise RuntimeError(f"Expected 10 Hot Motion templates, found {len(rows)}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=4)
    frames: list[tuple[Path, Path, Path]] = []
    reports: list[dict[str, object]] = []
    for row in rows:
        template_id = str(row["id"])
        composition = instantiate_template(template_id, variant="16:9")
        template_frames: list[Path] = []
        for beat_name, fraction in (("in", .18), ("mid", .50), ("out", .82)):
            time_ms = round(composition.duration_ms * fraction)
            frame = OUTPUT / f"{template_id}_{beat_name}.png"
            image = renderer.render_frame(
                composition,
                time_ms,
                width=320,
                height=180,
                use_cache=False,
            )
            if not image.save(str(frame), "PNG"):
                raise RuntimeError(f"Could not save QA frame: {frame}")
            template_frames.append(frame)
        frames.append(tuple(template_frames))
        reports.append({
            "id": template_id,
            "name": row["name"],
            "duration_ms": composition.duration_ms,
            "layer_count": len(composition.layers),
            "frames": [str(frame.resolve()) for frame in template_frames],
        })

    tile_width, tile_height, label_height = 320, 180, 38
    sheet = Image.new("RGB", (tile_width * 6, (tile_height + label_height) * 5), "#0b0e12")
    draw = ImageDraw.Draw(sheet)
    for index, (template_frames, row) in enumerate(zip(frames, rows)):
        group_column, line = index % 2, index // 2
        group_x = group_column * tile_width * 3
        y = line * (tile_height + label_height)
        for beat_index, frame in enumerate(template_frames):
            with Image.open(frame) as loaded:
                image = loaded.convert("RGB")
            sheet.paste(image, (group_x + beat_index * tile_width, y))
        draw.text((group_x + 10, y + tile_height + 7), str(row["name"]), fill="#f3f0e8")
        draw.text((group_x + tile_width * 2 + 236, y + tile_height + 7), "IN / MID / OUT", fill="#7fd7e8")
    sheet_path = OUTPUT / "hot_motion_2026_contact_sheet.png"
    sheet.save(sheet_path)
    report = {
        "schema": "tigerstudio.motion.hot_2026_qa.v1",
        "ok": len(frames) == 10 and all(path.is_file() for group in frames for path in group),
        "count": len(frames),
        "contact_sheet": str(sheet_path.resolve()),
        "templates": reports,
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(render(), ensure_ascii=False, indent=2))
