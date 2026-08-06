"""Measure the Painter Blockout Action projection viewport contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter_ns


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_3d_blockout import (  # noqa: E402
    add_blockout_primitive,
    default_blockout_scene,
    project_blockout_scene,
)


VIEWPORTS = ((64, 64), (640, 360), (8192, 8192))
PRIMITIVES = ("box", "sphere", "cylinder", "cone", "plane", "arch")
EXPECTED_GEOMETRY = {"faces": 145, "edges": 515, "floor_tiles": 685}


def _percentile_95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, ceil(len(ordered) * 0.95) - 1)]


def build_report(*, iterations: int = 25) -> dict[str, object]:
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("iterations must be a positive integer")
    scene = default_blockout_scene()
    for index, kind in enumerate(PRIMITIVES):
        scene = add_blockout_primitive(
            scene,
            kind=kind,
            x=index - 3,
            y=index * 0.25,
            z=0.5,
        )
    scene_payload = scene.to_dict()
    scene_bytes = json.dumps(
        scene_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    results: list[dict[str, object]] = []
    expected_geometry: dict[str, int] | None = None
    for width, height in VIEWPORTS:
        samples_ms: list[float] = []
        geometry: dict[str, int] | None = None
        for _ in range(iterations):
            started = perf_counter_ns()
            projection = project_blockout_scene(scene, width, height)
            samples_ms.append((perf_counter_ns() - started) / 1_000_000.0)
            expected_viewport = {"width": width, "height": height}
            if projection["viewport"] != expected_viewport:
                raise AssertionError(
                    f"projection viewport mismatch: {projection['viewport']!r} != "
                    f"{expected_viewport!r}"
                )
            current = {
                "faces": int(projection["face_count"]),
                "edges": int(projection["edge_count"]),
                "floor_tiles": len(projection["floor_tiles"]),
            }
            if geometry is None:
                geometry = current
            elif current != geometry:
                raise AssertionError("projection geometry changed between identical runs")
        if expected_geometry is None:
            expected_geometry = geometry
        elif geometry != expected_geometry:
            raise AssertionError("viewport changed serialized projection complexity")
        if geometry != EXPECTED_GEOMETRY:
            raise AssertionError(
                f"projection geometry mismatch: {geometry!r} != {EXPECTED_GEOMETRY!r}"
            )
        results.append(
            {
                "viewport": {"width": width, "height": height},
                "iterations": iterations,
                "geometry": geometry,
                "samples_ms": [round(value, 6) for value in samples_ms],
                "median_ms": round(float(median(samples_ms)), 6),
                "p95_ms": round(float(_percentile_95(samples_ms)), 6),
            }
        )
    return {
        "schema": "tigerstudio.painter.qa.blockout_projection_viewport.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "tools/qa_painter_blockout_projection_viewport.py",
        "python": sys.version,
        "python_optimize": int(sys.flags.optimize),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "scene_sha256": hashlib.sha256(scene_bytes).hexdigest(),
        "primitive_kinds": list(PRIMITIVES),
        "result": "pass",
        "measurements": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "debugCapture" / "painter" / "blockout_projection_viewport" / "report.json",
    )
    args = parser.parse_args()
    report = build_report(iterations=args.iterations)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(output), "result": report["result"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
