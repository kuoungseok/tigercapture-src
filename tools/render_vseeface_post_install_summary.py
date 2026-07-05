"""Render a PNG summary for VSeeFace post-install verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VSeeFace post-install verification summary.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    image = Image.new("RGB", (1280, 640), (22, 27, 33))
    draw = ImageDraw.Draw(image)
    big = _font(42)
    font = _font(25)
    small = _font(19)

    status = str(report.get("status") or "unknown")
    ok = bool(report.get("ok"))
    color = (92, 226, 155) if ok else (255, 190, 95)
    draw.text((48, 42), "VSeeFace Post-Install Verification", font=big, fill=(243, 247, 250))
    draw.text((52, 108), f"Status: {status}", font=font, fill=color)
    draw.text((52, 144), str(report.get("next_action") or ""), font=small, fill=(184, 194, 206))

    preflight = report.get("preflight") if isinstance(report.get("preflight"), dict) else {}
    virtual = preflight.get("virtual_camera") if isinstance(preflight.get("virtual_camera"), dict) else {}
    spout = preflight.get("spout2") if isinstance(preflight.get("spout2"), dict) else {}
    video = report.get("video_source") if isinstance(report.get("video_source"), dict) else {}
    camera = report.get("virtual_camera") if isinstance(report.get("virtual_camera"), dict) else {}
    ffmpeg_camera = camera.get("ffmpeg_camera") if isinstance(camera.get("ffmpeg_camera"), dict) else {}

    rows = [
        ("VSeeFaceCamera registered", _yesno(virtual.get("registered")), bool(virtual.get("registered"))),
        ("VSeeFaceCamera bundle", _yesno(virtual.get("bundle_available")), bool(virtual.get("bundle_available"))),
        ("Spout sender", _yesno(spout.get("sender_available")), bool(spout.get("sender_available"))),
        ("Spout receiver", _yesno(spout.get("receiver_available")), bool(spout.get("receiver_available"))),
        ("Video tracking", _passfail(video.get("ok")) if video else "not run", bool(video.get("ok")) if video else False),
        ("FFmpeg DirectShow", _passfail(ffmpeg_camera.get("opened")) if ffmpeg_camera else "not run", bool(ffmpeg_camera.get("opened")) if ffmpeg_camera else False),
        ("Virtual camera pixels", _pixel_status(camera, ffmpeg_camera), bool(camera.get("ok"))),
    ]
    y = 220
    for key, value, row_ok in rows:
        draw.text((72, y), key, font=font, fill=(225, 232, 239))
        row_color = (92, 226, 155) if row_ok else (255, 178, 83)
        draw.text((540, y), value, font=font, fill=row_color)
        y += 46

    errors = report.get("errors") if isinstance(report.get("errors"), list) else []
    if errors:
        draw.text((72, 535), "Errors: " + ", ".join(str(item) for item in errors[:3]), font=small, fill=(255, 178, 83))
    selected = camera.get("selected") if isinstance(camera.get("selected"), dict) else None
    if selected:
        draw.text((72, 570), f"Selected camera index: {selected.get('index')} / sample: {selected.get('sample_path')}", font=small, fill=(184, 194, 206))
    elif ffmpeg_camera.get("sample_path"):
        draw.text((72, 570), f"FFmpeg sample: {ffmpeg_camera.get('sample_path')}", font=small, fill=(184, 194, 206))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(str(out))
    return 0


def _yesno(value) -> str:
    return "yes" if bool(value) else "no"


def _passfail(value) -> str:
    return "PASS" if bool(value) else "FAIL"


def _pixel_status(camera: dict, ffmpeg_camera: dict) -> str:
    if camera.get("ok"):
        return "PASS"
    if ffmpeg_camera.get("opened"):
        return "BLACK"
    if camera:
        return "FAIL"
    return "not run"


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


if __name__ == "__main__":
    raise SystemExit(main())
