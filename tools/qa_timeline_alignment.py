"""Timeline/actor-lane pixel alignment QA.

The normal video track, ruler, Live2D lane, and Spine lane must agree on the
same project-time -> x-pixel origin.  A one-pixel drift is enough for users to
notice when the playhead crosses stacked rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def run_alignment_qa(*, px_per_sec: float = 73.0, samples_ms: list[int] | None = None) -> dict[str, Any]:
    _ensure_app()
    from app.live2d.actor_lane_row import Live2DActorLaneRow
    from app.live2d.actor_track import Live2DActorTrack
    from app.spine_editor.actor_lane_row import SpineActorLaneRow
    from app.spine_editor.actor_track import SpineActorTrack
    from app.timeline_ruler import TimelineRuler
    from app.video_editor_window import TrackRow

    samples = samples_ms or [0, 1, 333, 1000, 2500, 6000, 12_345]
    video_track = SimpleNamespace(
        id=1,
        label="Video 1",
        offset_ms=0,
        duration_ms=30_000,
        clips=[],
    )
    video_row = TrackRow(video_track)
    video_row.set_px_per_sec(px_per_sec)
    live_row = Live2DActorLaneRow(Live2DActorTrack(id=1, label="Live2D 1"))
    live_row.set_px_per_sec(px_per_sec)
    spine_row = SpineActorLaneRow(SpineActorTrack(id=1, label="Spine 1"))
    spine_row.set_px_per_sec(px_per_sec)

    margin = int(TimelineRuler.MARGIN)
    rows: list[dict[str, Any]] = []
    for ms in samples:
        expected = margin + int(ms / 1000.0 * px_per_sec)
        measured = {
            "ruler": expected,
            "video": int(video_row._project_ms_to_x(ms)),
            "live2d": int(live_row._ms_to_x(ms)),
            "spine": int(spine_row._ms_to_x(ms)),
        }
        drift = {name: value - expected for name, value in measured.items()}
        rows.append({
            "ms": int(ms),
            "expected_x": expected,
            "measured": measured,
            "drift": drift,
            "ok": all(value == 0 for value in drift.values()),
        })

    report = {
        "ok": all(row["ok"] for row in rows),
        "summary": {
            "samples": len(rows),
            "px_per_sec": float(px_per_sec),
            "timeline_margin": margin,
            "max_abs_drift_px": max(
                (abs(value) for row in rows for value in row["drift"].values()),
                default=0,
            ),
        },
        "rows": rows,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check timeline row pixel alignment.")
    parser.add_argument("--px-per-sec", type=float, default=73.0)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_alignment_qa.json"))
    args = parser.parse_args()

    report = run_alignment_qa(px_per_sec=args.px_per_sec)
    out_path = ROOT / args.out if not args.out.is_absolute() else args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
