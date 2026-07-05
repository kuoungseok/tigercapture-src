#!/usr/bin/env python
"""Create and validate a tiny Screen Studio-style render-result smoke video."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _frame_signature(frame) -> int:
    try:
        import numpy as np  # type: ignore
    except Exception:
        return 0
    if frame is None:
        return 0
    samples = frame[:: max(1, frame.shape[0] // 12), :: max(1, frame.shape[1] // 12)]
    return int(np.asarray(samples, dtype="uint32").sum() & 0xFFFFFFFF)


def _draw_smoke_frame(width: int, height: int, frame_index: int, frame_count: int):
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    t = frame_index / max(1, frame_count - 1)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)[None, :]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.clip(28 + 42 * x + 22 * t, 0, 255)
    frame[:, :, 1] = np.clip(30 + 54 * y + 28 * (1.0 - t), 0, 255)
    frame[:, :, 2] = np.clip(44 + 80 * (1.0 - x) + 48 * t, 0, 255)

    pad = 42 + int(18 * t)
    crop_w = int(width * (0.60 + 0.08 * t))
    crop_h = int(height * (0.54 + 0.04 * t))
    crop_x = int(width * 0.18 + 28 * t)
    crop_y = int(height * 0.18 - 10 * t)
    cv2.rectangle(frame, (crop_x, crop_y), (crop_x + crop_w, crop_y + crop_h), (235, 239, 250), -1)
    cv2.rectangle(frame, (crop_x, crop_y), (crop_x + crop_w, crop_y + crop_h), (98, 103, 145), 2)
    cv2.rectangle(frame, (crop_x + pad, crop_y + 54), (crop_x + crop_w - pad, crop_y + 92), (58, 67, 104), -1)
    cv2.rectangle(frame, (crop_x + pad, crop_y + 116), (crop_x + crop_w - pad * 2, crop_y + 148), (105, 118, 179), -1)

    cursor_x = int(width * (0.32 + 0.31 * t))
    cursor_y = int(height * (0.64 - 0.26 * t))
    pulse = 8 + int(10 * (1.0 - abs(0.5 - t) * 2.0))
    cv2.circle(frame, (cursor_x, cursor_y), 34 + pulse, (180, 92, 255), 3)
    cv2.circle(frame, (cursor_x, cursor_y), 9, (255, 255, 255), -1)
    cv2.circle(frame, (cursor_x, cursor_y), 13, (255, 105, 72), 2)

    knob_x = int(width * 0.80)
    knob_y = int(height * 0.78)
    cv2.circle(frame, (knob_x, knob_y), 38, (42, 48, 76), -1)
    cv2.circle(frame, (knob_x, knob_y), 30, (106, 93, 255), 4)
    cv2.line(frame, (knob_x, knob_y), (knob_x + int(18 * t), knob_y - 21), (255, 181, 83), 4)
    cv2.putText(frame, "1.0x", (knob_x - 25, knob_y + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 216, 160), 2)
    return frame


def _make_smoke_video(video_path: Path, *, width: int = 640, height: int = 360, frames: int = 48, fps: float = 24.0) -> dict[str, Any]:
    import cv2  # type: ignore

    video_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    if not writer.isOpened():
        return {"ok": False, "error": "video_writer_open_failed"}
    try:
        for idx in range(frames):
            writer.write(_draw_smoke_frame(width, height, idx, frames))
    finally:
        writer.release()
    return {"ok": video_path.exists(), "path": str(video_path), "frames_written": frames, "fps": fps, "width": width, "height": height}


def _validate_smoke_video(video_path: Path) -> dict[str, Any]:
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:
        return {"ok": False, "error": f"opencv_unavailable:{type(exc).__name__}"}
    cap = cv2.VideoCapture(str(video_path))
    if not cap or not cap.isOpened():
        return {"ok": False, "error": "video_open_failed"}
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    ok_first, first = cap.read()
    mid = None
    if frames > 4:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(1, frames // 2))
        _, mid = cap.read()
    cap.release()
    size_bytes = video_path.stat().st_size if video_path.exists() else 0
    first_sig = _frame_signature(first if ok_first else None)
    mid_sig = _frame_signature(mid)
    cursor_pixels = 0
    if mid is not None:
        purple = (mid[:, :, 0] > 120) & (mid[:, :, 1] < 125) & (mid[:, :, 2] > 120)
        cursor_pixels = int(np.count_nonzero(purple))
    checks = {
        "file_written": size_bytes > 4096,
        "frame_count": frames >= 24,
        "fps_valid": fps >= 20.0,
        "frame_readable": bool(ok_first and first is not None),
        "frames_change": bool(first_sig and mid_sig and first_sig != mid_sig),
        "cursor_highlight_pixels": cursor_pixels > 50,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "summary": {
            "size_bytes": int(size_bytes),
            "frames": int(frames),
            "fps": float(fps),
            "first_signature": first_sig,
            "mid_signature": mid_sig,
            "cursor_pixels": cursor_pixels,
        },
    }


def run_screenstudio_render_result_smoke(out_path: str | Path | None = None, *, video_path: str | Path | None = None) -> dict[str, Any]:
    out = Path(out_path or "debugCapture/screenstudio_render_result_smoke/screenstudio_render_result_smoke_report.json")
    video = Path(video_path or out.parent / "screenstudio_default_smoke.mp4")
    try:
        created = _make_smoke_video(video)
        validated = _validate_smoke_video(video) if created.get("ok") else {"ok": False, "error": created.get("error", "create_failed")}
    except Exception as exc:
        created = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        validated = {"ok": False, "error": "not_validated"}
    report = {
        "ok": bool(created.get("ok") and validated.get("ok")),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "kind": "screenstudio_render_result_smoke",
        "video_path": str(video),
        "create": created,
        "validation": validated,
        "summary": dict(validated.get("summary") or {}),
        "checks": dict(validated.get("checks") or {}),
    }
    _write_json(out, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="debugCapture/screenstudio_render_result_smoke/screenstudio_render_result_smoke_report.json")
    parser.add_argument("--video", default="")
    args = parser.parse_args()
    report = run_screenstudio_render_result_smoke(args.out, video_path=args.video or None)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
