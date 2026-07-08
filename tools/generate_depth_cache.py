"""Generate a TigerCapture AR/PBR depth cache from a video file.

Example:
    python tools/generate_depth_cache.py clip.mp4 --interval-ms 200 --max-frames 60
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _frames_with_cv2(path: Path, *, interval_ms: int, max_frames: int) -> Iterator[tuple[int, Any]]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path}")
    try:
        duration_ms = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(1.0, cap.get(cv2.CAP_PROP_FPS)) * 1000.0)
    except Exception:
        duration_ms = 0
    count = 0
    t = 0
    while max_frames <= 0 or count < max_frames:
        if duration_ms > 0 and t > duration_ms:
            break
        cap.set(cv2.CAP_PROP_POS_MSEC, float(t))
        ok, frame = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        yield int(t), rgb
        count += 1
        t += max(1, int(interval_ms))
    cap.release()


def _frames_with_imageio(path: Path, *, interval_ms: int, max_frames: int) -> Iterator[tuple[int, Any]]:
    import imageio.v3 as iio

    fps = 30.0
    try:
        props = iio.improps(path)
        fps = float(getattr(props, "fps", fps) or fps)
    except Exception:
        fps = 30.0
    step = max(1, int(round((max(1, interval_ms) / 1000.0) * fps)))
    count = 0
    for index, frame in enumerate(iio.imiter(path)):
        if index % step:
            continue
        yield int(round(index / fps * 1000.0)), frame
        count += 1
        if max_frames > 0 and count >= max_frames:
            break


def iter_video_frames(path: Path, *, interval_ms: int, max_frames: int) -> Iterator[tuple[int, Any]]:
    try:
        yield from _frames_with_cv2(path, interval_ms=interval_ms, max_frames=max_frames)
        return
    except Exception:
        pass
    yield from _frames_with_imageio(path, interval_ms=interval_ms, max_frames=max_frames)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate TigerCapture depth cache for AR/PBR compositing.")
    parser.add_argument("video", help="Input video path.")
    parser.add_argument("--provider", default=None, help="Depth provider id. Default: auto.")
    parser.add_argument("--interval-ms", type=int, default=200, help="Sampling interval in milliseconds.")
    parser.add_argument("--max-frames", type=int, default=60, help="Maximum sampled frames. <=0 means all sampled frames.")
    parser.add_argument("--no-refine", action="store_true", help="Disable lightweight depth refinement.")
    parser.add_argument("--no-temporal", action="store_true", help="Disable temporal smoothing.")
    parser.add_argument("--json", dest="json_path", default="", help="Optional output JSON path.")
    args = parser.parse_args(argv)

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"video not found: {video}")
    from app.depth.jobs import depth_cache_job_summary, generate_depth_cache_for_frames

    manifest = generate_depth_cache_for_frames(
        str(video),
        iter_video_frames(video, interval_ms=max(1, args.interval_ms), max_frames=int(args.max_frames)),
        provider=args.provider,
        refine=not args.no_refine,
        temporal=not args.no_temporal,
    )
    summary = depth_cache_job_summary(manifest)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if args.json_path:
        out = Path(args.json_path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
