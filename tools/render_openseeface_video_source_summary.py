"""Render a PNG summary for the OpenSeeFace video-source probe."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description="Render OpenSeeFace video-source probe summary.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    image = Image.new("RGB", (1000, 520), (24, 30, 36))
    draw = ImageDraw.Draw(image)
    font = _font(28)
    big = _font(44)
    small = _font(22)

    draw.text((50, 46), "OpenSeeFace Video Source", font=big, fill=(244, 247, 250))
    draw.text((52, 105), "VSeeFace bundled facetracker.exe <- raw RGB video frames", font=small, fill=(180, 190, 202))
    endpoint = report.get("endpoint") or {}
    rows = [
        ("Result", "PASS" if report.get("ok") else "FAIL"),
        ("Frames written", str(report.get("frames_written"))),
        ("Tracking rows", str(report.get("tracking_rows"))),
        ("UDP packets", str(report.get("udp_packets"))),
        ("Endpoint", f"{endpoint.get('host')}:{endpoint.get('port')}"),
        ("Crop", str(report.get("crop"))),
        ("Confidence tail", "~0.90 from facetracker output"),
    ]
    y = 170
    for key, value in rows:
        draw.text((70, y), key, font=font, fill=(170, 181, 194))
        color = (92, 226, 155) if value == "PASS" else (245, 248, 252)
        draw.text((380, y), value, font=font, fill=color)
        y += 44
    if report.get("warnings"):
        draw.text((70, 470), "Note: finite video probes stop facetracker after feeding frames.", font=small, fill=(255, 190, 95))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(str(out))
    return 0


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


if __name__ == "__main__":
    raise SystemExit(main())
