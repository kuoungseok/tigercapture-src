"""Screenshot QA for timeline drag feedback chips and destination ghosts.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_timeline_drag_feedback.py --out debugCapture/timeline_drag_feedback_qa

The script uses real Qt mouse events against ``TrackRow`` and captures the
drag-in-progress state before mouse release, so it verifies the visible feedback
path instead of only the pure timeline math.
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


def _pixel_count(path: Path, *, mode: str) -> int:
    from PySide6.QtGui import QImage

    image = QImage(str(path))
    if image.isNull():
        return 0
    count = 0
    step = max(1, min(image.width(), image.height()) // 140)
    for y in range(0, image.height(), step):
        for x in range(0, image.width(), step):
            c = image.pixelColor(x, y)
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            if a < 18:
                continue
            if mode == "blocked" and r >= 190 and g <= 145 and b <= 170:
                count += 1
            elif mode == "snap" and b >= 185 and g >= 145 and r <= 180:
                count += 1
    return count


def _make_track(*, blocked: bool = False):
    from app.timeline_model import VideoClip, VideoTrack

    moving = VideoClip(
        id=1,
        source_duration_ms=1000,
        timeline_in_ms=1000,
        source_in_ms=0,
        source_out_ms=1000,
    )
    clips = [moving]
    if not blocked:
        clips.append(
            VideoClip(
                id=2,
                source_duration_ms=1000,
                timeline_in_ms=3600,
                source_in_ms=0,
                source_out_ms=1000,
            )
        )
    track = VideoTrack(id=1, clips=clips)
    track.offset_ms = 0
    track.source_path = None
    track.thumbnails = []
    track.speed_segments = []
    track.fades = []
    track.cuts = []
    track.typography_actors = []
    track.zoom_actors = []
    return track, moving


def _capture_drag_case(out_dir: Path, *, mode: str) -> dict[str, Any]:
    app = _ensure_app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.i18n import initialize, set_language
    from app.video_editor_window import TrackRow

    initialize()
    set_language("en")
    track, moving = _make_track(blocked=(mode == "blocked"))
    row = TrackRow(track)
    row.set_px_per_sec(100.0)
    row.set_extra_snap_targets([2050])
    row.set_selected_clip_ids({1})
    row.resize(760, max(92, row.sizeHint().height()))
    row.show()
    app.processEvents()

    if mode == "blocked":
        row.set_clip_drag_validator(
            lambda _track_id, _clip_ids, _delta: {
                "ok": False,
                "reason": "locked_track",
                "message": "Drag blocked: track is locked",
            }
        )

    start_x = int(row._project_ms_to_x(int(moving.timeline_in_ms) + 500))
    y = int(row.LABEL_H + row.TIMELINE_H / 2)
    delta_px = 100 if mode == "snap" else 70
    QTest.mousePress(row, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(start_x, y))
    QTest.mouseMove(row, QPoint(start_x + delta_px, y), delay=0)
    app.processEvents()

    shot = out_dir / f"timeline_drag_{mode}.png"
    row.grab().save(str(shot))
    color_hits = _pixel_count(shot, mode=mode)
    feedback = str(getattr(row, "_drag_feedback_text", "") or "")
    preview_visible = getattr(row, "_drag_preview_start_ms", None) is not None
    ok = shot.exists() and color_hits >= 8 and feedback and preview_visible
    if mode == "snap":
        ok = ok and "Snap" in feedback
    else:
        ok = ok and "locked" in feedback.lower()

    QTest.mouseRelease(row, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(start_x + delta_px, y))
    row.close()
    row.deleteLater()
    app.processEvents()
    return {
        "mode": mode,
        "ok": bool(ok),
        "screenshot": str(shot),
        "color_hits": int(color_hits),
        "feedback": feedback,
        "preview_visible": bool(preview_visible),
    }


def run_timeline_drag_feedback_qa(
    *, out_dir: Path | str = Path("debugCapture/timeline_drag_feedback_qa")
) -> dict[str, Any]:
    out_path = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cases = [
        _capture_drag_case(out_path, mode="snap"),
        _capture_drag_case(out_path, mode="blocked"),
    ]
    report = {
        "ok": all(row.get("ok") for row in cases),
        "summary": {
            "cases": len(cases),
            "screenshots": [row["screenshot"] for row in cases],
            "min_color_hits": min((int(row.get("color_hits", 0)) for row in cases), default=0),
        },
        "cases": cases,
    }
    (out_path / "timeline_drag_feedback_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Capture timeline drag feedback QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_drag_feedback_qa"))
    args = parser.parse_args()
    report = run_timeline_drag_feedback_qa(out_dir=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
