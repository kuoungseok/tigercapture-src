"""Mouse-gesture QA for commercial timeline edit modes.

This checks that TrackRow's actual Qt mouse path mutates clips correctly for
trim, ripple, roll, slip, and slide. It complements the pure timeline-model
tests by validating press/move/release state cleanup and one commit pulse per
gesture.
"""
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


def _clip_snapshot(track) -> list[dict[str, int]]:
    return [
        {
            "id": int(getattr(c, "id", -1)),
            "timeline_in_ms": int(getattr(c, "timeline_in_ms", 0)),
            "timeline_out_ms": int(getattr(c, "timeline_out_ms", 0)),
            "source_in_ms": int(getattr(c, "source_in_ms", 0)),
            "source_out_ms": int(getattr(c, "effective_source_out_ms", 0)),
        }
        for c in sorted(getattr(track, "clips", []) or [], key=lambda c: int(getattr(c, "id", 0)))
    ]


def _make_track():
    from app.timeline_model import VideoClip, VideoTrack

    clips = [
        VideoClip(id=1, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
        VideoClip(id=2, source_duration_ms=5000, timeline_in_ms=1000, source_in_ms=1000, source_out_ms=2000),
        VideoClip(id=3, source_duration_ms=5000, timeline_in_ms=2000, source_in_ms=0, source_out_ms=1000),
    ]
    track = VideoTrack(id=1, clips=clips)
    track.offset_ms = 0
    track.source_path = None
    track.thumbnails = []
    track.speed_segments = []
    track.fades = []
    track.cuts = []
    track.typography_actors = []
    track.zoom_actors = []
    return track


def _setup_row(track):
    app = _ensure_app()
    from app.i18n import initialize, set_language
    from app.video_editor_window import TrackRow

    initialize()
    set_language("en")
    row = TrackRow(track)
    row.set_px_per_sec(100.0)
    row.resize(760, max(92, row.sizeHint().height()))
    row.show()
    app.processEvents()
    return row


def _drag(row, *, start_ms: int, delta_ms: int, modifiers=None) -> int:
    app = _ensure_app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    mods = modifiers if modifiers is not None else Qt.KeyboardModifier.NoModifier
    y = int(row.LABEL_H + row.TIMELINE_H / 2)
    start_x = int(row._project_ms_to_x(int(start_ms)))
    end_x = int(row._project_ms_to_x(int(start_ms + delta_ms)))
    commits: list[int] = []
    row.drag_committed.connect(lambda track_id: commits.append(int(track_id)))
    QTest.mousePress(row, Qt.MouseButton.LeftButton, mods, QPoint(start_x, y))
    QTest.mouseMove(row, QPoint(end_x, y), delay=0)
    app.processEvents()
    QTest.mouseRelease(row, Qt.MouseButton.LeftButton, mods, QPoint(end_x, y))
    app.processEvents()
    return len(commits)


def _case(out_dir: Path, *, mode: str) -> dict[str, Any]:
    track = _make_track()
    row = _setup_row(track)
    before = _clip_snapshot(track)
    row.set_edit_tool_mode("select")
    delta = 0
    start_ms = 0

    if mode == "trim":
        start_ms = 1000
        delta = -200
    elif mode == "ripple":
        row.set_edit_tool_mode("ripple")
        start_ms = 1000
        delta = -200
    elif mode == "roll":
        row.set_edit_tool_mode("roll")
        start_ms = 1000
        delta = 200
    elif mode == "slip":
        row.set_edit_tool_mode("slip")
        start_ms = 1500
        delta = 300
    elif mode == "slide":
        row.set_edit_tool_mode("slide")
        start_ms = 1500
        delta = 200
    else:
        raise ValueError(f"unknown mode: {mode}")

    commits = _drag(row, start_ms=start_ms, delta_ms=delta)
    after = _clip_snapshot(track)
    shot = out_dir / f"timeline_edit_{mode}.png"
    row.grab().save(str(shot))
    row.close()
    row.deleteLater()
    _ensure_app().processEvents()

    by_id = {row["id"]: row for row in after}
    ok = commits == 1 and shot.exists()
    checks: dict[str, bool] = {"one_commit": commits == 1, "screenshot": shot.exists()}
    if mode == "trim":
        checks["clip1_trimmed_right"] = by_id[1]["source_out_ms"] == 800
        checks["clip2_unmoved"] = by_id[2]["timeline_in_ms"] == 1000
    elif mode == "ripple":
        checks["clip1_trimmed_right"] = by_id[1]["source_out_ms"] == 800
        checks["clip2_rippled_left"] = by_id[2]["timeline_in_ms"] == 800
        checks["clip3_rippled_left"] = by_id[3]["timeline_in_ms"] == 1800
    elif mode == "roll":
        checks["clip1_extended"] = by_id[1]["source_out_ms"] == 1200
        checks["clip2_rolled_source"] = by_id[2]["source_in_ms"] == 1200
        checks["clip2_rolled_timeline"] = by_id[2]["timeline_in_ms"] == 1200
        checks["outer_span_preserved"] = by_id[3]["timeline_out_ms"] == 3000
    elif mode == "slip":
        checks["clip2_timeline_unchanged"] = by_id[2]["timeline_in_ms"] == 1000 and by_id[2]["timeline_out_ms"] == 2000
        checks["clip2_source_slipped"] = by_id[2]["source_in_ms"] == 1300 and by_id[2]["source_out_ms"] == 2300
    elif mode == "slide":
        checks["clip2_slid_right"] = by_id[2]["timeline_in_ms"] == 1200 and by_id[2]["timeline_out_ms"] == 2200
        checks["clip1_extended"] = by_id[1]["source_out_ms"] == 1200
        checks["clip3_trimmed_left"] = by_id[3]["source_in_ms"] == 200 and by_id[3]["timeline_in_ms"] == 2200
        checks["outer_span_preserved"] = by_id[3]["timeline_out_ms"] == 3000
    ok = ok and all(checks.values())
    return {
        "mode": mode,
        "ok": bool(ok),
        "checks": checks,
        "commits": commits,
        "before": before,
        "after": after,
        "screenshot": str(shot),
    }


def run_timeline_edit_gestures_qa(
    *, out_dir: Path | str = Path("debugCapture/timeline_edit_gestures_qa")
) -> dict[str, Any]:
    out_path = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cases = [_case(out_path, mode=mode) for mode in ("trim", "ripple", "roll", "slip", "slide")]
    report = {
        "ok": all(row.get("ok") for row in cases),
        "summary": {
            "cases": len(cases),
            "passed": sum(1 for row in cases if row.get("ok")),
            "screenshots": [row["screenshot"] for row in cases],
        },
        "cases": cases,
    }
    (out_path / "timeline_edit_gestures_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run timeline edit-mode mouse gesture QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_edit_gestures_qa"))
    args = parser.parse_args()
    report = run_timeline_edit_gestures_qa(out_dir=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
