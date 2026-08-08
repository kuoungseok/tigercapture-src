from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruct a reference through public paint.study.* actions."
    )
    parser.add_argument("reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--seed", type=int, default=240725)
    parser.add_argument("--refinement-passes", type=int, default=2)
    parser.add_argument(
        "--focus-region",
        action="append",
        default=[],
        help="id,x0,y0,x1,y1,priority in normalized coordinates",
    )
    return parser.parse_args()


def _focus_regions(values: list[str]) -> list[dict]:
    rows: list[dict] = []
    for value in values:
        parts = [part.strip() for part in str(value).split(",")]
        if len(parts) != 6:
            raise ValueError("--focus-region requires id,x0,y0,x1,y1,priority")
        rows.append(
            {
                "id": parts[0],
                "bbox_norm": [float(part) for part in parts[1:5]],
                "priority": float(parts[5]),
            }
        )
    return rows


def _execute(registry, action: str, params: dict) -> dict:
    result = registry.execute_action(action, params).to_dict()
    if not result.get("ok"):
        raise RuntimeError(f"{action} failed: {result.get('error') or 'unknown error'}")
    return dict(result.get("result") or {})


def main() -> int:
    args = _args()
    reference = args.reference.resolve()
    source = Image.open(reference)
    width = max(256, min(1600, int(args.width)))
    height = max(256, round(width * source.height / max(1, source.width)))

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(width, height, "#111827"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    action_log: list[dict] = []

    def run(action: str, params: dict | None = None) -> dict:
        payload = dict(params or {})
        result = _execute(registry, action, payload)
        action_log.append({"action": action, "params": payload, "result": result})
        return result

    run(
        "paint.study.analyze_reference",
        {
            "reference_path": str(reference),
            "target_width": width,
            "region_count": 14,
            "seed": int(args.seed),
            "focus_regions": _focus_regions(args.focus_region),
        },
    )
    run("paint.study.segment_regions")
    phases = [
        ("paint.study.build_underpaint", "", 16000),
        ("paint.study.generate_strokes", "forms", 1500),
        ("paint.study.generate_strokes", "detail", 1300),
        ("paint.study.generate_strokes", "accent", 450),
        ("paint.study.trace_contours", "", 800),
    ]
    for action, phase, limit in phases:
        params = {"max_strokes": limit}
        if phase:
            params["phase"] = phase
        run(action, params)
    comparison = run("paint.study.compare_render")["study"]
    for index in range(max(0, int(args.refinement_passes))):
        run(
            "paint.study.refine_region",
            {
                "max_strokes": 5000,
                "layer_name": f"AI Study Refinement {index + 1}",
                "seed_offset": (index + 1) * 1000,
            },
        )
        comparison = run("paint.study.compare_render")["study"]
    quality = run("paint.study.quality_report")["study"]

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    export = _execute(
        registry,
        "paint.document.export_png",
        {"path": str(output), "include_background": True},
    )
    log_path = output.with_suffix(".study.json")
    log_path.write_text(
        json.dumps(
            {
                "schema": "tigerstudio.painter.ai_study_run.v1",
                "reference": str(reference),
                "output": str(output),
                "quality": quality,
                "comparison": comparison,
                "actions": action_log,
                "export": export,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": output.exists(),
                "output": str(output),
                "log": str(log_path),
                "quality": quality,
            },
            ensure_ascii=False,
        )
    )
    dialog.close()
    return 0 if output.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
