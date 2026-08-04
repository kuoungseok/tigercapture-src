"""Render the ten Hot Motion 2026 templates as review MP4 files."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition
from app.motion_designer.templates import apply_template_to_composition, list_templates


WIDTH = 960
HEIGHT = 540
FPS = 24.0
OUTPUT = ROOT / "debugCapture" / "motion_hot_2026" / "videos"


def _composition(template_id: str, name: str) -> MotionComposition:
    composition = MotionComposition(name=name, width=WIDTH, height=HEIGHT, duration_ms=1000)
    return apply_template_to_composition(
        composition,
        template_id,
        variant="16:9",
        replace_existing=True,
    )


def render_all(*, force: bool = False) -> dict[str, object]:
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    rows = [row for row in list_templates() if row["category"] == "Hot Motion 2026"]
    if len(rows) != 10:
        raise RuntimeError(f"Expected 10 Hot Motion templates, found {len(rows)}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer(cache_capacity=8)
    results: list[dict[str, object]] = []
    started = time.perf_counter()
    for index, row in enumerate(rows, 1):
        template_id = str(row["id"])
        output = OUTPUT / f"{index:02d}_{template_id}.mp4"
        composition = _composition(template_id, str(row["name"]))
        expected_frames = round(composition.duration_ms * FPS / 1000.0)
        if not force and output.is_file() and output.stat().st_size > 64_000:
            status = "reused"
        else:
            output.unlink(missing_ok=True)
            partial = output.with_suffix(output.suffix + ".partial")
            partial.unlink(missing_ok=True)
            print(
                f"RENDER {index:02d}/10 {row['name']} "
                f"{composition.duration_ms / 1000:.1f}s {expected_frames}f",
                flush=True,
            )
            renderer.export_mp4(composition, output, fps=FPS)
            status = "rendered"
        results.append({
            "index": index,
            "id": template_id,
            "name": row["name"],
            "duration_ms": composition.duration_ms,
            "expected_frames": expected_frames,
            "status": status,
            "path": str(output.resolve()),
            "bytes": output.stat().st_size,
        })
        print(f"DONE {index:02d}/10 {output.name} {output.stat().st_size} bytes", flush=True)
    report = {
        "schema": "tigerstudio.motion.hot_2026_video_review.v1",
        "ok": len(results) == 10 and all(int(row["bytes"]) > 64_000 for row in results),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "videos": results,
    }
    (OUTPUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-render existing review videos.")
    args = parser.parse_args()
    print(json.dumps(render_all(force=args.force), ensure_ascii=False, indent=2), flush=True)
