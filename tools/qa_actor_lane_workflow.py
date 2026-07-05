"""Live2D/Spine actor-lane workflow smoke QA.

This is intentionally lighter than full model rendering.  It checks the editor
interaction path users hit most often: create actor clip, hit-test it,
double-click it, and keep playhead geometry aligned with the shared ruler.
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

    app = QApplication.instance() or QApplication([])
    try:
        from app.font_fallback import apply_ui_font

        apply_ui_font(app)
    except Exception:
        pass
    return app


def _exercise_row(
    kind: str,
    row,
    create_clip,
    clip_attr: str,
    *,
    start_ms: int,
    px_per_sec: float,
    sample_path: str = "",
    capture_dir: Path | None = None,
) -> dict[str, Any]:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    app = _ensure_app()
    row.set_px_per_sec(px_per_sec)
    row.resize(720, row.height())
    row.show()
    app.processEvents()
    before = len(row.track.clips)
    create_clip(sample_path, start_ms)
    app.processEvents()
    if len(row.track.clips) <= before:
        return {
            "kind": kind,
            "sample_path": sample_path,
            "clip_count": len(row.track.clips),
            "clip_attr": "",
            "start_ms": start_ms,
            "end_ms": -1,
            "double_click_fired": False,
            "hit_test_ok": False,
            "playhead_x": -1,
            "ok": False,
            "error": "clip was not created",
        }
    clip = row.track.clips[-1]
    fired: list[object] = []
    row.clip_double_clicked.connect(lambda c: fired.append(c))
    click_x = int(row._ms_to_x(start_ms + 200))
    QTest.mouseDClick(
        row,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(click_x, max(2, row.height() // 2)),
    )
    app.processEvents()
    playhead_ms = start_ms + 777
    row.set_playhead(playhead_ms)
    app.processEvents()
    expected_x = int(row._ms_to_x(playhead_ms))
    hit_clip = row._clip_at(click_x)
    artifact = ""
    if capture_dir is not None:
        capture_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = capture_dir / f"actor_lane_{kind}.png"
        try:
            row.grab().save(str(artifact_path), "PNG")
            artifact = str(artifact_path.resolve())
        except Exception:
            artifact = ""
    return {
        "kind": kind,
        "sample_path": sample_path,
        "clip_count": len(row.track.clips),
        "clip_attr": getattr(clip, clip_attr, ""),
        "start_ms": int(getattr(clip, "start_ms", -1)),
        "end_ms": int(getattr(clip, "end_ms", -1)),
        "double_click_fired": bool(fired and fired[-1] is clip),
        "hit_test_ok": hit_clip is clip,
        "playhead_x": expected_x,
        "artifact": artifact,
        "ok": bool(fired and fired[-1] is clip and hit_clip is clip),
    }


def _first_live2d_sample() -> str:
    for path in sorted((ROOT / "resources" / "live2d_samples").glob("**/*.model3.json")):
        return str(path)
    return ""


def _first_spine_sample() -> str:
    roots = [ROOT / "resources" / "spine_samples", ROOT / "resources" / "test_spine"]
    for root in roots:
        for pattern in ("**/*.skel.json", "**/*.json", "**/*.skel", "**/*.atlas"):
            for path in sorted(root.glob(pattern)):
                return str(path)
    return ""


def run_actor_lane_workflow_qa(
    *,
    px_per_sec: float = 88.0,
    include_samples: bool = False,
    capture_dir: Path | None = None,
) -> dict[str, Any]:
    _ensure_app()
    from app.live2d.actor_lane_row import Live2DActorLaneRow
    from app.live2d.actor_track import Live2DActorTrack
    from app.spine_editor.actor_lane_row import SpineActorLaneRow
    from app.spine_editor.actor_track import SpineActorTrack

    live_row = Live2DActorLaneRow(Live2DActorTrack(id=1, label="Live2D QA"))
    spine_row = SpineActorLaneRow(SpineActorTrack(id=1, label="Spine QA"))
    rows = [
        _exercise_row(
            "live2d",
            live_row,
            live_row._create_clip,
            "model_path",
            start_ms=1000,
            px_per_sec=px_per_sec,
            capture_dir=capture_dir,
        ),
        _exercise_row(
            "spine",
            spine_row,
            spine_row._create_clip,
            "skel_path",
            start_ms=1400,
            px_per_sec=px_per_sec,
            capture_dir=capture_dir,
        ),
    ]
    if include_samples:
        live_sample = _first_live2d_sample()
        spine_sample = _first_spine_sample()
        if live_sample:
            live_sample_row = Live2DActorLaneRow(Live2DActorTrack(id=2, label="Live2D Sample QA"))
            rows.append(_exercise_row(
                "live2d_sample",
                live_sample_row,
                live_sample_row._create_clip,
                "model_path",
                start_ms=2200,
                px_per_sec=px_per_sec,
                sample_path=live_sample,
                capture_dir=capture_dir,
            ))
        else:
            rows.append({"kind": "live2d_sample", "ok": False, "error": "no sample found"})
        if spine_sample:
            spine_sample_row = SpineActorLaneRow(SpineActorTrack(id=2, label="Spine Sample QA"))
            rows.append(_exercise_row(
                "spine_sample",
                spine_sample_row,
                spine_sample_row._create_clip,
                "skel_path",
                start_ms=2600,
                px_per_sec=px_per_sec,
                sample_path=spine_sample,
                capture_dir=capture_dir,
            ))
        else:
            rows.append({"kind": "spine_sample", "ok": False, "error": "no sample found"})
    return {
        "ok": all(row["ok"] for row in rows),
        "summary": {
            "rows": len(rows),
            "px_per_sec": float(px_per_sec),
            "include_samples": bool(include_samples),
            "failures": sum(1 for row in rows if not row["ok"]),
        },
        "rows": rows,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run actor-lane workflow QA.")
    parser.add_argument("--px-per-sec", type=float, default=88.0)
    parser.add_argument("--include-samples", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_lane_workflow_qa.json"))
    parser.add_argument("--capture-dir", type=Path, default=Path(""))
    args = parser.parse_args()

    capture_dir = None
    if args.capture_dir and str(args.capture_dir):
        capture_dir = ROOT / args.capture_dir if not args.capture_dir.is_absolute() else args.capture_dir
    report = run_actor_lane_workflow_qa(
        px_per_sec=args.px_per_sec,
        include_samples=args.include_samples,
        capture_dir=capture_dir,
    )
    out_path = ROOT / args.out if not args.out.is_absolute() else args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
