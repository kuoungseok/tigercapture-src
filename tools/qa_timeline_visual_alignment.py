"""Visual screenshot QA for stacked timeline playhead alignment."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def run_timeline_visual_alignment_qa(
    *,
    playhead_ms: int = 2500,
    px_per_sec: float = 80.0,
    out_dir: Path | str = Path("debugCapture/timeline_visual_alignment_qa"),
) -> dict[str, Any]:
    app = _ensure_app()
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.live2d.actor_lane_row import Live2DActorLaneRow
    from app.live2d.actor_track import Live2DActorTrack
    from app.spine_editor.actor_lane_row import SpineActorLaneRow
    from app.spine_editor.actor_track import SpineActorTrack
    from app.timeline_ruler import TimelineRuler
    from app.video_editor_window import TrackRow, VideoTrack

    out_path = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    ruler = TimelineRuler()
    ruler.set_px_per_sec(px_per_sec)
    ruler.set_project_duration(8000)
    ruler.set_playhead(playhead_ms)
    video_track = VideoTrack(id=1, source_path=None, offset_ms=0, duration_ms=8000)
    video = TrackRow(video_track)
    video.set_px_per_sec(px_per_sec)
    video.set_position(playhead_ms)
    live = Live2DActorLaneRow(Live2DActorTrack(id=1, label="Live2D QA"))
    live.set_px_per_sec(px_per_sec)
    live.set_playhead(playhead_ms)
    spine = SpineActorLaneRow(SpineActorTrack(id=1, label="Spine QA"))
    spine.set_px_per_sec(px_per_sec)
    spine.set_playhead(playhead_ms)

    for widget in (ruler, video, live, spine):
        widget.setFixedWidth(760)
        layout.addWidget(widget)
    host.resize(760, sum(widget.height() for widget in (ruler, video, live, spine)))
    host.show()
    app.processEvents()
    shot = out_path / "timeline_visual_alignment.png"
    pix = host.grab()
    pix.save(str(shot))

    expected_x = int(TimelineRuler.MARGIN + playhead_ms / 1000.0 * px_per_sec)
    measured = {
        "ruler": expected_x,
        "video": int(video._project_ms_to_x(playhead_ms)),
        "live2d": int(live._ms_to_x(playhead_ms)),
        "spine": int(spine._ms_to_x(playhead_ms)),
    }
    drifts = {name: value - expected_x for name, value in measured.items()}
    report = {
        "ok": all(abs(value) <= 0 for value in drifts.values()) and shot.exists(),
        "summary": {
            "playhead_ms": int(playhead_ms),
            "px_per_sec": float(px_per_sec),
            "expected_x": expected_x,
            "max_abs_drift_px": max((abs(v) for v in drifts.values()), default=0),
            "screenshot": str(shot),
        },
        "measured": measured,
        "drift": drifts,
    }
    (out_path / "timeline_visual_alignment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    host.close()
    app.processEvents()
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Capture timeline visual alignment QA.")
    parser.add_argument("--playhead-ms", type=int, default=2500)
    parser.add_argument("--px-per-sec", type=float, default=80.0)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_visual_alignment_qa"))
    args = parser.parse_args()
    report = run_timeline_visual_alignment_qa(
        playhead_ms=args.playhead_ms,
        px_per_sec=args.px_per_sec,
        out_dir=args.out,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
