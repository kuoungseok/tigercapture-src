from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "editor_export_bake_qa"
DEFAULT_REPORT = ROOT / "debugCapture" / "editor_export_bake_qa.json"


def _ensure_qa_corpus() -> None:
    source = ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4"
    if source.exists():
        return
    from tools.build_qa_corpus import build_corpus

    build_corpus(ROOT / "qa_corpus")


def _run_export(exporter) -> dict[str, Any]:
    events: dict[str, Any] = {"success": None, "error": ""}

    def _success(path, size):
        events["success"] = {"path": str(path), "size": int(size)}

    def _error(message):
        events["error"] = str(message)

    exporter.finished_success.connect(_success)
    exporter.finished_error.connect(_error)
    exporter.run()
    try:
        exporter.deleteLater()
    except Exception:
        pass
    ok = bool(events.get("success")) and not bool(events.get("error"))
    events["ok"] = ok
    return events


def _read_video_probe(path: Path, *, frame_index: int = 6, still_path: Path | None = None) -> dict[str, Any]:
    import cv2  # type: ignore
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    if not cap or not cap.isOpened():
        return {"ok": False, "error": "open_failed"}
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    idx = max(0, min(int(frame_index), max(0, frames - 1)))
    if frames > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, frame_bgr = cap.read()
    cap.release()
    if not ok or frame_bgr is None:
        return {
            "ok": False,
            "error": "frame_read_failed",
            "frames": frames,
            "fps": fps,
            "width": width,
            "height": height,
        }
    if still_path is not None:
        still_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(still_path), frame_bgr)
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    arr = rgb.astype(np.float32)
    luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    pink = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 140) & (rgb[:, :, 2] > 110)
    dark_ui = (rgb[:, :, 0] < 60) & (rgb[:, :, 1] < 80) & (rgb[:, :, 2] < 120)
    return {
        "ok": True,
        "frames": frames,
        "fps": round(float(fps), 3),
        "width": width,
        "height": height,
        "frame_index": idx,
        "mean_luma": round(float(luma.mean()), 3),
        "std_luma": round(float(luma.std()), 3),
        "signature": int(arr[:: max(1, height // 16), :: max(1, width // 16)].sum()) & 0xFFFFFFFF,
        "pink_pixels": int(np.count_nonzero(pink)),
        "dark_ui_pixels": int(np.count_nonzero(dark_ui)),
        "still": str(still_path) if still_path is not None else "",
    }


def _frame_diff(a_path: Path, b_path: Path, *, frame_index: int = 6) -> dict[str, Any]:
    import cv2  # type: ignore
    import numpy as np

    frames = []
    for path in (a_path, b_path):
        cap = cv2.VideoCapture(str(path))
        if not cap or not cap.isOpened():
            return {"ok": False, "error": f"open_failed:{path}"}
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        idx = max(0, min(int(frame_index), max(0, total - 1)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, bgr = cap.read()
        cap.release()
        if not ok or bgr is None:
            return {"ok": False, "error": f"read_failed:{path}"}
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    a, b = frames
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_LINEAR)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    changed = np.any(delta > 12, axis=2)
    return {
        "ok": True,
        "mean_abs_diff": round(float(delta.mean()), 3),
        "max_abs_diff": int(delta.max()),
        "changed_pixel_ratio": round(float(changed.mean()), 4),
    }


def _make_text_clip():
    from app.typography import TextClip, TextStyle

    clip = TextClip(start_ms=0, end_ms=1200, text="QA EXPORT")
    clip.style = TextStyle(
        font_family="Arial",
        font_size=86,
        font_weight=900,
        color="#FF4FA3",
        position_x=0.5,
        position_y=0.5,
        outline_color="#FFFFFF",
        outline_width=3,
        shadow_color="#111827",
        shadow_offset_x=4,
        shadow_offset_y=4,
        background_color="#131A2F",
        background_padding=22,
        background_radius=16,
    )
    clip.animation.in_duration = 0.0
    clip.animation.out_duration = 0.0
    clip.animation.hold_animation = "none"
    return clip


def run_editor_export_bake_qa(*, out_dir: Path = DEFAULT_OUT_DIR, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.color_grading import ColorGrade
    from app.timeline_model import ZoomActor
    from app.video_exporter import VideoExportThread
    from app.video_filters import VideoFilterParams

    _ensure_qa_corpus()
    QApplication.instance() or QApplication([])
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    report_path = report_path if report_path.is_absolute() else ROOT / report_path
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    source = ROOT / "qa_corpus" / "assets" / "qa_motion_720p.mp4"
    baseline = out_dir / "baseline.mp4"
    processed = out_dir / "processed_baked.mp4"
    for path in (baseline, processed):
        try:
            path.unlink()
        except OSError:
            pass

    segments = [(0, 1200, 1.0)]
    common = {
        "source_path": source,
        "segments": segments,
        "quality_id": "low",
        "format_id": "mp4",
        "target_fps": 12.0,
    }

    baseline_exporter = VideoExportThread(
        source,
        baseline,
        segments,
        quality_id="low",
        format_id="mp4",
        target_fps=12.0,
    )
    baseline_result = _run_export(baseline_exporter)

    clip_effect = SimpleNamespace(
        video_filters=VideoFilterParams(
            sharpen=1.15,
            vignette=0.52,
            vignette_feather=0.62,
            chroma_aberration=0.85,
        ),
        chroma_key=None,
        bg_removal=None,
        stabilizer=None,
        cursor_events=[],
        screenstudio_polish={},
    )
    text_clip = _make_text_clip()
    zoom = ZoomActor(
        id=1,
        start_ms=0,
        end_ms=1200,
        target_x=360,
        target_y=160,
        target_w=520,
        target_h=300,
        zoom_in_ms=180,
        zoom_out_ms=180,
        easing="smooth_pop",
        motion_blur=0.12,
    )
    processed_exporter = VideoExportThread(
        source,
        processed,
        segments,
        text_actors_source=[(0, 1200, text_clip)],
        clip_effects=[clip_effect],
        zoom_actors=[zoom],
        color_grade=ColorGrade(brightness=24, contrast=18, saturation=26),
        quality_id="low",
        format_id="mp4",
        target_fps=12.0,
    )
    processed_config_exercised = bool(
        processed_exporter._clip_effects
        and processed_exporter._text_actors_source
        and processed_exporter._zoom_actors
        and processed_exporter._color_grade is not None
    )
    processed_result = _run_export(processed_exporter)

    baseline_probe = _read_video_probe(
        baseline,
        frame_index=6,
        still_path=out_dir / "baseline_frame.jpg",
    ) if baseline.exists() else {"ok": False, "error": "missing_baseline"}
    processed_probe = _read_video_probe(
        processed,
        frame_index=6,
        still_path=out_dir / "processed_frame.jpg",
    ) if processed.exists() else {"ok": False, "error": "missing_processed"}
    diff = _frame_diff(baseline, processed, frame_index=6) if baseline.exists() and processed.exists() else {"ok": False, "error": "missing_output"}

    checks = {
        "baseline_export_ok": bool(baseline_result.get("ok")) and baseline.exists() and baseline.stat().st_size > 4096,
        "processed_export_ok": bool(processed_result.get("ok")) and processed.exists() and processed.stat().st_size > 4096,
        "baseline_readable": bool(baseline_probe.get("ok")) and int(baseline_probe.get("frames", 0) or 0) >= 8,
        "processed_readable": bool(processed_probe.get("ok")) and int(processed_probe.get("frames", 0) or 0) >= 8,
        "processed_has_text_highlight_pixels": int(processed_probe.get("pink_pixels", 0) or 0) > 120,
        "processed_has_ui_background_pixels": int(processed_probe.get("dark_ui_pixels", 0) or 0) > 200,
        "processed_differs_from_baseline": bool(diff.get("ok"))
        and float(diff.get("mean_abs_diff", 0.0) or 0.0) > 8.0
        and float(diff.get("changed_pixel_ratio", 0.0) or 0.0) > 0.08,
        "export_config_exercised_effects": processed_config_exercised,
    }
    failures = [
        {"check": name, "message": "check failed"}
        for name, passed in checks.items()
        if not passed
    ]
    report = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "editor_export_bake",
        "source": str(source),
        "outputs": {
            "baseline": str(baseline),
            "processed": str(processed),
            "baseline_frame": str(out_dir / "baseline_frame.jpg"),
            "processed_frame": str(out_dir / "processed_frame.jpg"),
        },
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for passed in checks.values() if passed),
            "failing": len(failures),
            "processed_size": processed.stat().st_size if processed.exists() else 0,
            "mean_abs_diff": diff.get("mean_abs_diff", 0),
            "changed_pixel_ratio": diff.get("changed_pixel_ratio", 0),
            "pink_pixels": processed_probe.get("pink_pixels", 0),
        },
        "checks": checks,
        "baseline_export": baseline_result,
        "processed_export": processed_result,
        "baseline_probe": baseline_probe,
        "processed_probe": processed_probe,
        "diff": diff,
        "failures": failures,
        "config": common,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run final MP4 export-bake smoke QA.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = run_editor_export_bake_qa(out_dir=args.out_dir, report_path=args.report)
    print(json.dumps({
        "ok": report.get("ok"),
        "report": report.get("report"),
        "summary": report.get("summary"),
        "outputs": report.get("outputs"),
    }, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
