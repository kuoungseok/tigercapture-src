"""Run real-video Motion mask tracking QA and write disposable evidence."""
from __future__ import annotations

import json
import sys
from math import cos, radians, sin
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.tracking_provider import MotionTrackingRequest, generate_tracking_cache


SOURCE = ROOT / "external/assets/ai_edit_demo/working_clips/02_lamborghini_moody_detail.mp4"
OUTPUT_DIR = ROOT / "debugCapture/motion_designer"
REPORT_PATH = OUTPUT_DIR / "motion_tracking_provider_report.json"
IMAGE_PATH = OUTPUT_DIR / "motion_tracking_provider_real_video.png"


def _frame_at(capture: cv2.VideoCapture, time_ms: int) -> np.ndarray:
    capture.set(cv2.CAP_PROP_POS_MSEC, int(time_ms))
    ok, frame = capture.read()
    if not ok or frame is None:
        raise RuntimeError(f"could not decode QA frame at {time_ms} ms")
    return frame


def _tracked_corners(roi, sample, origin) -> np.ndarray:
    x, y, width, height = roi
    points = np.asarray(
        [[x, y], [x + width, y], [x + width, y + height], [x, y + height]],
        dtype=np.float64,
    )
    angle = radians(float(sample.rotation))
    scale_x, scale_y = sample.scale
    matrix = np.asarray([
        [cos(angle) * scale_x, -sin(angle) * scale_y],
        [sin(angle) * scale_x, cos(angle) * scale_y],
    ])
    return (points - origin) @ matrix.T + origin + np.asarray(sample.translate)


def main() -> int:
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    capture = cv2.VideoCapture(str(SOURCE))
    if not capture.isOpened():
        raise RuntimeError(f"could not open {SOURCE}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    roi = (width * 0.1875, height / 6.0, width * 0.625, height * 2.0 / 3.0)
    caches = {}
    for mode in ("point", "planar"):
        caches[mode] = generate_tracking_cache(MotionTrackingRequest(
            video_path=str(SOURCE),
            mode=mode,
            end_ms=2000,
            sample_interval_ms=100,
            target_size=(width, height),
            roi=roi,
        ))

    actual_end_ms = min(int(cache.metadata["actual_end_ms"]) for cache in caches.values())
    first = _frame_at(capture, 0)
    final = _frame_at(capture, actual_end_ms)
    capture.release()
    cv2.polylines(
        first,
        [np.rint(_tracked_corners(roi, caches["planar"].samples[0], caches["planar"].origin)).astype(np.int32)],
        True,
        (70, 230, 150),
        5,
        cv2.LINE_AA,
    )
    cv2.polylines(
        final,
        [np.rint(_tracked_corners(roi, caches["planar"].samples[-1], caches["planar"].origin)).astype(np.int32)],
        True,
        (60, 210, 255),
        5,
        cv2.LINE_AA,
    )
    cv2.putText(first, "SOURCE ROI / 0 ms", (28, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (70, 230, 150), 3)
    cv2.putText(
        final,
        f"PLANAR TRACK / {actual_end_ms} ms",
        (28, 52),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (60, 210, 255),
        3,
    )
    evidence = np.hstack([
        cv2.resize(first, (640, 360), interpolation=cv2.INTER_AREA),
        cv2.resize(final, (640, 360), interpolation=cv2.INTER_AREA),
    ])

    rows = {}
    ok = True
    for mode, cache in caches.items():
        final_sample = cache.samples[-1]
        failed_ratio = cache.metadata["failed_frames"] / max(1, cache.metadata["analyzed_frames"])
        row_ok = (
            len(cache.samples) >= 5
            and cache.metadata["mean_confidence"] >= 0.2
            and failed_ratio <= 0.3
        )
        ok = ok and row_ok
        rows[mode] = {
            "ok": row_ok,
            "sample_count": len(cache.samples),
            "final_sample": final_sample.to_dict(),
            "mean_confidence": cache.metadata["mean_confidence"],
            "failed_frames": cache.metadata["failed_frames"],
            "analyzed_frames": cache.metadata["analyzed_frames"],
            "shot_cut_frames": cache.metadata["shot_cut_frames"],
            "actual_end_ms": cache.metadata["actual_end_ms"],
            "terminated_reason": cache.metadata["terminated_reason"],
            "source_revision": cache.source_revision,
        }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(IMAGE_PATH), evidence)
    REPORT_PATH.write_text(json.dumps({
        "ok": ok,
        "source": str(SOURCE),
        "evidence": str(IMAGE_PATH),
        "roi": list(roi),
        "modes": rows,
    }, ensure_ascii=True, indent=2), encoding="utf-8")
    print(REPORT_PATH)
    print(json.dumps(rows, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
