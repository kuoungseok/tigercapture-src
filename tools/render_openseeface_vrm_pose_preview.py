"""Render a visual proof that OpenSeeFace motion drives VRM pose channels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.motion_quality import representative_frame_indices, summarize_motion_frames  # noqa: E402
from app.vtuber.openseeface_motion import load_openseeface_motion_csv, summarize_openseeface_motion  # noqa: E402
from app.vtuber.vrm_pose_driver import build_vrm_pose_frames, summarize_vrm_pose_frames  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render OpenSeeFace to VRM pose preview.")
    parser.add_argument("--csv", required=True, help="OpenSeeFace facetracker --log-data CSV")
    parser.add_argument("--out", default=str(ROOT / "debugCapture" / "openseeface_vrm_pose_preview.png"))
    parser.add_argument("--json-out", default="")
    args = parser.parse_args(argv)

    motion_frames = load_openseeface_motion_csv(args.csv)
    pose_frames = build_vrm_pose_frames(motion_frames)
    motion_summary = summarize_motion_frames(motion_frames)
    openseeface_summary = summarize_openseeface_motion(motion_frames)
    pose_summary = summarize_vrm_pose_frames(pose_frames)
    report = {
        "schema": "tigerstudio.vtuber.openseeface_vrm_pose_preview.v1",
        "ok": bool(motion_frames and pose_summary.get("animated")),
        "csv": str(Path(args.csv)),
        "openseeface": openseeface_summary,
        "motion": motion_summary,
        "vrm_pose": pose_summary,
    }

    image = _render(args.csv, motion_frames, pose_frames, report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    json_out = Path(args.json_out) if args.json_out else out.with_suffix(".json")
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "json_out": str(json_out)}, ensure_ascii=False))
    return 0 if report["ok"] else 2


def _render(csv_path: str, motion_frames, pose_frames, report: dict) -> Image.Image:
    canvas = Image.new("RGB", (1280, 760), (22, 27, 33))
    draw = ImageDraw.Draw(canvas)
    big, font, small = _fonts()
    draw.text((44, 34), "OpenSeeFace -> VRM Pose Preview", font=big, fill=(242, 247, 250))
    subtitle = f"{Path(csv_path).name} | {len(motion_frames)} tracking frames"
    draw.text((46, 88), _fit(subtitle, 118), font=small, fill=(180, 191, 203))
    ok_text = "POSE CHANNELS ACTIVE" if report.get("ok") else "NO POSE MOTION"
    ok_color = (92, 226, 155) if report.get("ok") else (255, 178, 83)
    draw.text((940, 42), ok_text, font=font, fill=ok_color)

    slots = representative_frame_indices(len(motion_frames), 4)
    for slot_index, frame_index in enumerate(slots):
        x = 58 + slot_index * 290
        y = 150
        _draw_avatar_pose(draw, (x, y), motion_frames[frame_index], pose_frames[frame_index])
        f = motion_frames[frame_index]
        draw.text((x - 18, y + 265), f"{f.time_ms / 1000.0:.2f}s", font=small, fill=(220, 228, 236))
        draw.text((x - 18, y + 292), f"yaw {f.yaw_deg:+.1f}  pitch {f.pitch_deg:+.1f}", font=small, fill=(220, 228, 236))
        draw.text((x - 18, y + 319), f"blink {max(f.blink_l, f.blink_r):.2f}  A {f.mouth_open:.2f}", font=small, fill=(220, 228, 236))

    graph = (58, 550, 818, 710)
    _draw_graph(draw, graph, motion_frames)
    _draw_summary(draw, (855, 530, 1220, 714), report, font, small)
    return canvas


def _draw_avatar_pose(draw: ImageDraw.ImageDraw, origin: tuple[int, int], frame, pose_frame) -> None:
    x, y = origin
    cx = x + 90
    hips = (cx, y + 210)
    chest = (cx + frame.yaw_deg * 0.35, y + 128)
    neck = (cx + frame.yaw_deg * 0.58, y + 88 + frame.pitch_deg * 0.2)
    head = (cx + frame.yaw_deg * 0.82, y + 42 + frame.pitch_deg * 0.35)
    shoulder_l = (chest[0] - 58, chest[1] + 8)
    shoulder_r = (chest[0] + 58, chest[1] + 8)
    arm_l = (shoulder_l[0] - 35, shoulder_l[1] + 72)
    arm_r = (shoulder_r[0] + 35, shoulder_r[1] + 72)
    leg_l = (hips[0] - 36, hips[1] + 70)
    leg_r = (hips[0] + 36, hips[1] + 70)

    draw.rounded_rectangle((x - 24, y - 18, x + 208, y + 348), radius=10, fill=(30, 36, 43), outline=(70, 82, 96), width=2)
    for a, b in [(hips, chest), (chest, neck), (neck, head), (shoulder_l, shoulder_r), (shoulder_l, arm_l), (shoulder_r, arm_r), (hips, leg_l), (hips, leg_r)]:
        draw.line((a[0], a[1], b[0], b[1]), fill=(130, 181, 255), width=7)
    for p in [hips, chest, neck, shoulder_l, shoulder_r, arm_l, arm_r, leg_l, leg_r]:
        draw.ellipse((p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7), fill=(232, 237, 242))

    head_radius = 32
    draw.ellipse((head[0] - head_radius, head[1] - head_radius, head[0] + head_radius, head[1] + head_radius), fill=(242, 202, 154), outline=(255, 236, 205), width=3)
    eye_y = head[1] - 5
    blink = max(frame.blink_l, frame.blink_r)
    if blink > 0.5:
        draw.line((head[0] - 15, eye_y, head[0] - 4, eye_y), fill=(28, 34, 40), width=3)
        draw.line((head[0] + 4, eye_y, head[0] + 15, eye_y), fill=(28, 34, 40), width=3)
    else:
        draw.ellipse((head[0] - 16, eye_y - 4, head[0] - 8, eye_y + 4), fill=(28, 34, 40))
        draw.ellipse((head[0] + 8, eye_y - 4, head[0] + 16, eye_y + 4), fill=(28, 34, 40))
    mouth_h = 3 + int(frame.mouth_open * 18)
    draw.rounded_rectangle((head[0] - 10, head[1] + 13, head[0] + 10, head[1] + 13 + mouth_h), radius=6, fill=(108, 45, 52))

    head_bone = (pose_frame.bones.get("Head") or {}).get("rotation") or [0, 0, 0, 1]
    draw.text((x - 14, y + 12), f"Head q {head_bone[3]:.3f}", font=_fonts()[2], fill=(172, 184, 198))


def _draw_graph(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], frames) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=8, fill=(31, 36, 42), outline=(74, 85, 98), width=2)
    _plot(draw, rect, frames, "yaw_deg", -45.0, 45.0, (255, 214, 102))
    _plot(draw, rect, frames, "pitch_deg", -35.0, 35.0, (100, 210, 255))
    _plot(draw, rect, frames, "roll_deg", -30.0, 30.0, (214, 130, 255))
    _plot(draw, rect, frames, "blink_l", 0.0, 1.0, (255, 151, 92))


def _plot(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], frames, name: str, low: float, high: float, color: tuple[int, int, int]) -> None:
    if len(frames) < 2:
        return
    x0, y0, x1, y1 = rect
    left, top, right, bottom = x0 + 16, y0 + 12, x1 - 16, y1 - 14
    t0 = frames[0].time_ms
    span = max(1, frames[-1].time_ms - t0)
    points = []
    for frame in frames:
        value = getattr(frame, name)
        n = max(0.0, min(1.0, (value - low) / max(0.0001, high - low)))
        t = (frame.time_ms - t0) / span
        points.append((left + t * (right - left), bottom - n * (bottom - top)))
    draw.line(points, fill=color, width=3)


def _draw_summary(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], report: dict, font, small) -> None:
    x0, y0, x1, y1 = rect
    draw.rounded_rectangle(rect, radius=8, fill=(35, 42, 49), outline=(80, 92, 105), width=2)
    draw.text((x0 + 22, y0 + 18), "VRM Pose Summary", font=font, fill=(242, 247, 250))
    pose = report.get("vrm_pose") or {}
    motion = report.get("openseeface") or {}
    rows = [
        ("Animated", str(bool(pose.get("animated")))),
        ("Bones", ", ".join(pose.get("animated_bones") or [])),
        ("Blends", ", ".join(pose.get("animated_blends") or [])),
        ("Head q range", f"{pose.get('head_rotation_range', 0):.4f}"),
        ("Confidence", f"{motion.get('confidence_mean', 0):.3f}"),
    ]
    for i, (key, value) in enumerate(rows):
        y = y0 + 62 + i * 28
        draw.text((x0 + 22, y), key, font=small, fill=(167, 179, 193))
        draw.text((x0 + 145, y), _fit(value, 27), font=small, fill=(235, 241, 247))


def _fonts():
    try:
        return (
            ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 38),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 23),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18),
        )
    except OSError:
        fallback = ImageFont.load_default()
        return fallback, fallback, fallback


def _fit(value: str, limit: int) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: max(0, limit - 3)] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
