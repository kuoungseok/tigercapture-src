"""Audit real-video Motion tracking coverage without bundling source media."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.tracking_provider import (
    MotionTrackingRequest,
    generate_tracking_cache,
)
from app.motion_designer.tracking_workflow import track_asset_diagnostics


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def run(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    max_clips: int = 20,
    duration_ms: int = 1800,
) -> dict:
    source = Path(input_dir).expanduser().resolve(strict=False)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    candidates = sorted(
        (
            item for item in source.iterdir()
            if item.is_file() and item.suffix.lower() in VIDEO_SUFFIXES
        ),
        key=lambda item: item.name.casefold(),
    )[:max(1, int(max_clips))]
    clips = []
    for index, path in enumerate(candidates):
        mode = "point" if index % 2 == 0 else "planar"
        try:
            cache = generate_tracking_cache(MotionTrackingRequest(
                video_path=str(path),
                mode=mode,
                start_ms=0,
                end_ms=max(300, int(duration_ms)),
                sample_interval_ms=120,
                max_analysis_dimension=640,
                max_analysis_frames=180,
            ))
            asset = {
                "kind": mode,
                "source_uri": str(path),
                "source_revision": cache.source_revision,
                "samples": [item.to_dict() for item in cache.samples],
                "metadata": cache.metadata,
            }
            diagnostics = track_asset_diagnostics(
                asset,
                current_source_revision=cache.source_revision,
            )
            accepted = (
                float(diagnostics["mean_confidence"]) >= 0.55
                and float(diagnostics["maximum_step_px"]) <= 100.0
                and int(diagnostics["occluded_sample_count"])
                <= max(1, int(diagnostics["sample_count"]) // 2)
            )
            clips.append({
                "name": path.name,
                "ok": True,
                "accepted": accepted,
                "mode": mode,
                **diagnostics,
                "failed_frames": int(cache.metadata.get("failed_frames", 0)),
                "terminated_reason": str(
                    cache.metadata.get("terminated_reason") or ""
                ),
            })
        except Exception as exc:
            clips.append({
                "name": path.name,
                "ok": False,
                "accepted": False,
                "mode": mode,
                "error": str(exc),
            })
    success_count = sum(1 for item in clips if item["ok"])
    accepted_count = sum(1 for item in clips if item["accepted"])
    mean_confidence = (
        sum(float(item.get("mean_confidence", 0.0)) for item in clips if item["ok"])
        / max(1, success_count)
    )
    report = {
        "schema": "tigerstudio.motion.m18_real_tracking_qa.v1",
        "ok": (
            len(clips) >= 20
            and accepted_count >= 18
            and mean_confidence >= 0.55
        ),
        "input_dir": str(source),
        "required_clip_count": 20,
        "available_clip_count": len(clips),
        "success_count": success_count,
        "accepted_count": accepted_count,
        "mean_confidence": mean_confidence,
        "coverage_gap": max(0, 20 - len(clips)),
        "clips": clips,
    }
    (destination / "m18_real_tracking_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument(
        "--output-dir",
        default="debugCapture/motion_designer/m18_real_tracking",
    )
    parser.add_argument("--max-clips", type=int, default=20)
    parser.add_argument("--duration-ms", type=int, default=1800)
    args = parser.parse_args()
    report = run(
        args.input_dir,
        args.output_dir,
        max_clips=args.max_clips,
        duration_ms=args.duration_ms,
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
