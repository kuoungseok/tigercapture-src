"""Mouse-hover QA for timeline edit affordances.

The goal is to catch the subtle "what am I about to edit?" polish issues:
hover chips, native tooltips, and cursor shapes must stay aligned for the
select, trim, roll, slip, and slide paths.
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


def _shape_name(shape: object) -> str:
    return str(getattr(shape, "name", "") or str(shape).split(".")[-1])


def _make_track(*, adjacent: bool) -> object:
    from app.timeline_model import VideoClip, VideoTrack

    clips = [
        VideoClip(id=1, source_duration_ms=5000, timeline_in_ms=0, source_in_ms=0, source_out_ms=1000),
        VideoClip(
            id=2,
            source_duration_ms=5000,
            timeline_in_ms=1000 if adjacent else 1400,
            source_in_ms=1000,
            source_out_ms=2000,
        ),
        VideoClip(
            id=3,
            source_duration_ms=5000,
            timeline_in_ms=2000 if adjacent else 2600,
            source_in_ms=0,
            source_out_ms=1000,
        ),
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


def _setup_row(*, adjacent: bool, mode: str):
    app = _ensure_app()
    from app.i18n import initialize, set_language
    from app.video_editor_window import TrackRow

    initialize()
    set_language("en")
    row = TrackRow(_make_track(adjacent=adjacent))
    row.set_px_per_sec(120.0)
    row.resize(860, max(92, row.sizeHint().height()))
    row.set_edit_tool_mode(mode)
    row.show()
    app.processEvents()
    return row


def _hover(row, *, project_ms: int, repeat: bool = False) -> None:
    app = _ensure_app()
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    y = int(row.LABEL_H + row.TIMELINE_H / 2)
    x = int(row._project_ms_to_x(int(project_ms)))
    QTest.mouseMove(row, QPoint(1, y), delay=0)
    app.processEvents()
    QTest.mouseMove(row, QPoint(x, y), delay=0)
    app.processEvents()
    if repeat:
        QTest.mouseMove(row, QPoint(x + 1, y), delay=0)
        app.processEvents()


def _case(out_dir: Path, spec: dict[str, Any]) -> dict[str, Any]:
    from PySide6.QtCore import Qt

    row = _setup_row(adjacent=bool(spec.get("adjacent")), mode=str(spec["mode"]))
    _hover(row, project_ms=int(spec["project_ms"]), repeat=bool(spec.get("repeat")))
    hint = str(getattr(row, "_hover_hint_text", "") or "")
    tooltip = str(row.toolTip() or "")
    cursor = row.cursor().shape()
    expected_cursor = spec["cursor"]
    shot = out_dir / f"timeline_hover_{spec['name']}.png"
    row.grab().save(str(shot))
    row.close()
    row.deleteLater()
    _ensure_app().processEvents()

    expected_shape = getattr(Qt.CursorShape, expected_cursor)
    checks = {
        "hint": hint == spec["hint"],
        "tooltip_synced": tooltip == spec["hint"],
        "cursor": cursor == expected_shape,
        "screenshot": shot.exists(),
    }
    return {
        "name": spec["name"],
        "ok": all(checks.values()),
        "checks": checks,
        "hint": hint,
        "tooltip": tooltip,
        "cursor": _shape_name(cursor),
        "expected": {
            "hint": spec["hint"],
            "cursor": expected_cursor,
        },
        "screenshot": str(shot),
    }


def run_timeline_hover_affordance_qa(
    *, out_dir: Path | str = Path("debugCapture/timeline_hover_affordance_qa")
) -> dict[str, Any]:
    out_path = ROOT / out_dir if not Path(out_dir).is_absolute() else Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    cases = [
        {
            "name": "move_repeat",
            "mode": "select",
            "adjacent": True,
            "project_ms": 500,
            "hint": "Move clip",
            "cursor": "OpenHandCursor",
            "repeat": True,
        },
        {
            "name": "trim_gap_edge",
            "mode": "select",
            "adjacent": False,
            "project_ms": 1000,
            "hint": "Trim edge",
            "cursor": "SizeHorCursor",
        },
        {
            "name": "roll_shared_edge",
            "mode": "roll",
            "adjacent": True,
            "project_ms": 1000,
            "hint": "Roll edit",
            "cursor": "SizeHorCursor",
        },
        {
            "name": "slip_body",
            "mode": "slip",
            "adjacent": True,
            "project_ms": 1500,
            "hint": "Slip source",
            "cursor": "SizeHorCursor",
        },
        {
            "name": "slide_body",
            "mode": "slide",
            "adjacent": True,
            "project_ms": 1500,
            "hint": "Slide clip",
            "cursor": "SizeHorCursor",
        },
    ]
    rows = [_case(out_path, spec) for spec in cases]
    report = {
        "ok": all(row.get("ok") for row in rows),
        "summary": {
            "cases": len(rows),
            "passed": sum(1 for row in rows if row.get("ok")),
            "screenshots": [row["screenshot"] for row in rows],
        },
        "cases": rows,
    }
    (out_path / "timeline_hover_affordance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run timeline hover affordance QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/timeline_hover_affordance_qa"))
    args = parser.parse_args()
    report = run_timeline_hover_affordance_qa(out_dir=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
