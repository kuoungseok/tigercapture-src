"""Render a PNG quality report for extracted VTuber face motion."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from app.vtuber.motion_quality import representative_frame_indices, summarize_motion_frames
from app.vtuber.video_face_driver import FaceMotionTuning, VideoFaceMotionExtractor, VideoFaceMotionResult, apply_motion_tuning


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a VTuber face-motion QC PNG.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "vtuber_motion_qc.png"))
    parser.add_argument("--json-out", default="")
    parser.add_argument("--backend", choices=["auto", "mediapipe_tasks", "mediapipe", "opencv"], default="auto")
    parser.add_argument("--duration-seconds", type=float, default=5.0)
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--calibrate-seconds", type=float, default=0.8)
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--no-blink-calibration", action="store_true", help="Disable neutral blink baseline calibration.")
    parser.add_argument("--calibrate-mouth", action="store_true", help="Subtract neutral mouth baseline before plotting mouth blendshapes.")
    args = parser.parse_args(argv)

    extractor = VideoFaceMotionExtractor(max_fps=args.fps, backend=args.backend)
    result = extractor.extract(args.video, duration_seconds=args.duration_seconds)
    tuning = FaceMotionTuning(
        smoothing=args.smoothing,
        calibrate_ms=max(0, int(float(args.calibrate_seconds) * 1000.0)),
        calibrate_blinks=not bool(args.no_blink_calibration),
        calibrate_mouth=bool(args.calibrate_mouth),
    )
    if result.frames:
        diagnostics = dict(result.diagnostics)
        diagnostics["tuning"] = tuning.to_dict()
        result = VideoFaceMotionResult(result.ok, apply_motion_tuning(result.frames, tuning), diagnostics)
    if not result.ok or not result.frames:
        print(json.dumps({"ok": False, "errors": result.diagnostics.get("errors") or ["no_motion_frames"]}, ensure_ascii=False))
        return 2

    summary = summarize_motion_frames(result.frames)
    report = {
        "schema": "tigerstudio.vtuber.motion_qc.render.v1",
        "ok": True,
        "video": str(args.video),
        "motion": summary,
        "diagnostics": result.diagnostics,
    }

    image = _render_report(args.video, result.frames, summary, result.diagnostics)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)

    json_out = Path(args.json_out) if args.json_out else out.with_suffix(".json")
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(json_out), "frame_count": len(result.frames)}, ensure_ascii=False))
    return 0


def _render_report(video_path: str, frames, summary: dict, diagnostics: dict) -> Image.Image:
    canvas = Image.new("RGB", (1280, 720), (24, 28, 33))
    draw = ImageDraw.Draw(canvas)
    font_big, font, font_small = _fonts()
    draw.text((34, 28), "VTuber Motion QC", fill=(245, 248, 250), font=font_big)
    subtitle = f"{Path(video_path).name} | {diagnostics.get('selected_backend', '')} | {len(frames)} frames"
    draw.text((36, 76), _fit_text(subtitle, 112), fill=(180, 191, 203), font=font_small)

    thumbs = _load_thumbnails(video_path, frames, width=350, height=198, count=3)
    for i, (thumb, frame) in enumerate(thumbs):
        x = 34 + i * 382
        y = 116
        canvas.paste(thumb, (x, y))
        draw.rectangle((x, y, x + thumb.width - 1, y + thumb.height - 1), outline=(92, 105, 118), width=2)
        label = f"{frame.time_ms / 1000.0:.2f}s yaw={frame.yaw_deg:.1f} mouth={frame.mouth_open:.2f} blink={max(frame.blink_l, frame.blink_r):.2f}"
        draw.text((x, y + thumb.height + 10), _fit_text(label, 41), fill=(224, 230, 236), font=font_small)

    graph = (42, 386, 805, 660)
    _draw_graph(draw, graph, frames)
    _draw_legend(draw, graph[0], graph[1] - 34, font_small)

    panel = (835, 374, 1246, 662)
    draw.rounded_rectangle(panel, radius=10, fill=(36, 42, 49), outline=(82, 94, 108), width=2)
    draw.text((panel[0] + 24, panel[1] + 22), "Motion Summary", fill=(243, 246, 249), font=font)
    rows = _summary_rows(summary)
    for i, (key, value, ok) in enumerate(rows):
        y = panel[1] + 66 + i * 31
        draw.text((panel[0] + 24, y), key, fill=(168, 180, 192), font=font_small)
        draw.text((panel[0] + 210, y - 2), value, fill=(105, 222, 156) if ok else (255, 191, 101), font=font_small)
    return canvas


def _load_thumbnails(video_path: str, frames, *, width: int, height: int, count: int):
    import cv2

    selected = [frames[index] for index in representative_frame_indices(len(frames), count)]
    cap = cv2.VideoCapture(video_path)
    thumbs = []
    for frame in selected:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(frame.time_ms)))
        ok, image = cap.read()
        if not ok:
            image = None
        if image is not None:
            if frame.face_box:
                x, y, w, h = frame.face_box
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 220, 255), 3)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            thumb = Image.fromarray(rgb)
        else:
            thumb = Image.new("RGB", (width, height), (18, 21, 25))
        thumb.thumbnail((width, height), Image.Resampling.LANCZOS)
        fitted = Image.new("RGB", (width, height), (16, 19, 23))
        fitted.paste(thumb, ((width - thumb.width) // 2, (height - thumb.height) // 2))
        thumbs.append((fitted, frame))
    cap.release()
    return thumbs


def _draw_graph(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], frames) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=8, fill=(31, 36, 42), outline=(74, 85, 98), width=2)
    for i in range(1, 5):
        y = y0 + (y1 - y0) * i / 5
        draw.line((x0 + 12, y, x1 - 12, y), fill=(49, 56, 65), width=1)
    _plot_channel(draw, rect, frames, "yaw_deg", -45.0, 45.0, (255, 214, 102))
    _plot_channel(draw, rect, frames, "pitch_deg", -35.0, 35.0, (100, 210, 255))
    _plot_channel(draw, rect, frames, "roll_deg", -30.0, 30.0, (214, 130, 255))
    _plot_channel(draw, rect, frames, "mouth_open", 0.0, 1.0, (105, 222, 156))
    blink_values = [
        {"time_ms": frame.time_ms, "blink": max(frame.blink_l, frame.blink_r)}
        for frame in frames
    ]
    _plot_channel(draw, rect, blink_values, "blink", 0.0, 1.0, (255, 151, 92))


def _plot_channel(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], frames, name: str, low: float, high: float, color: tuple[int, int, int]) -> None:
    if not frames:
        return
    x0, y0, x1, y1 = rect
    left, top, right, bottom = x0 + 18, y0 + 16, x1 - 18, y1 - 18
    t0 = float(_frame_value(frames[0], "time_ms", 0))
    t1 = float(_frame_value(frames[-1], "time_ms", 1))
    span = max(1.0, t1 - t0)
    points = []
    for frame in frames:
        t = (float(_frame_value(frame, "time_ms", 0)) - t0) / span
        value = float(_frame_value(frame, name, 0.0))
        n = (value - low) / max(0.0001, high - low)
        n = max(0.0, min(1.0, n))
        points.append((left + t * (right - left), bottom - n * (bottom - top)))
    if len(points) >= 2:
        draw.line(points, fill=color, width=3)


def _draw_legend(draw: ImageDraw.ImageDraw, x: int, y: int, font) -> None:
    items = [
        ("yaw", (255, 214, 102)),
        ("pitch", (100, 210, 255)),
        ("roll", (214, 130, 255)),
        ("mouth", (105, 222, 156)),
        ("blink", (255, 151, 92)),
    ]
    cursor = x
    for label, color in items:
        draw.rounded_rectangle((cursor, y + 5, cursor + 22, y + 15), radius=3, fill=color)
        draw.text((cursor + 30, y), label, fill=(210, 218, 226), font=font)
        cursor += 104


def _summary_rows(summary: dict) -> list[tuple[str, str, bool]]:
    channels = summary.get("channels", {})
    checks = summary.get("checks", {})
    return [
        ("Head range", f"{max(channels.get('yaw_deg', {}).get('range', 0), channels.get('pitch_deg', {}).get('range', 0), channels.get('roll_deg', {}).get('range', 0)):.2f} deg", bool(checks.get("head_motion"))),
        ("Mouth max", f"{channels.get('mouth_open', {}).get('max', 0):.3f}", bool(checks.get("mouth_motion"))),
        ("Blink max", f"{max(channels.get('blink_l', {}).get('max', 0), channels.get('blink_r', {}).get('max', 0)):.3f}", bool(checks.get("blink_motion"))),
        ("Confidence avg", f"{channels.get('confidence', {}).get('mean', 0):.3f}", bool(checks.get("confidence_ok"))),
        ("Duration", f"{summary.get('duration_ms', 0) / 1000.0:.2f}s", True),
        ("Frames", str(summary.get("frame_count", 0)), bool(summary.get("frame_count", 0))),
    ]


def _fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        return (
            ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 22),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 17),
        )
    except Exception:
        fallback = ImageFont.load_default()
        return fallback, fallback, fallback


def _frame_value(frame, name: str, default):
    if isinstance(frame, dict):
        return frame.get(name, default)
    return getattr(frame, name, default)


def _fit_text(text: str, max_chars: int) -> str:
    value = str(text)
    return value if len(value) <= max_chars else value[: max(0, max_chars - 3)] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
