"""Render a PNG summary for VSeeFace graphics/capture diagnostics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_capture_diagnostics import analyze_graphics_probe_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VSeeFace graphics probe summary.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    diagnostics = analyze_graphics_probe_report(report)
    row_count = len([row for row in diagnostics.get("variants") or [] if isinstance(row, dict)])
    image_height = max(620, 245 + row_count * 44 + 120)
    image = Image.new("RGB", (1280, image_height), (22, 27, 33))
    draw = ImageDraw.Draw(image)
    big = _font(42)
    font = _font(25)
    small = _font(19)

    draw.text((48, 42), "VSeeFace Window Capture Probe", font=big, fill=(243, 247, 250))
    status = str(diagnostics.get("status") or "unknown")
    status_color = (92, 226, 155) if diagnostics.get("ok") else (255, 178, 83)
    draw.text((52, 102), f"Status: {status}", font=font, fill=status_color)
    draw.text((52, 138), "D3D11 window capture is black; Vulkan/GLCore show Unity graphics init failure.", font=small, fill=(184, 194, 206))

    y = 195
    draw.text((52, y), "Backend", font=small, fill=(150, 162, 176))
    draw.text((455, y), "Result", font=small, fill=(150, 162, 176))
    draw.text((720, y), "Mean", font=small, fill=(150, 162, 176))
    draw.text((850, y), "Colors", font=small, fill=(150, 162, 176))
    draw.text((1010, y), "Cam", font=small, fill=(150, 162, 176))
    y += 34
    for row in diagnostics.get("variants") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        if row.get("graphics_failed"):
            result = "graphics init failed"
            color = (255, 132, 132)
        elif row.get("content_nonblack"):
            result = "usable"
            color = (92, 226, 155)
        else:
            result = "black client area"
            color = (255, 190, 95)
        draw.text((52, y), name, font=font, fill=(239, 243, 247))
        draw.text((455, y), result, font=font, fill=color)
        draw.text((720, y), str(row.get("mean_luma")), font=font, fill=(239, 243, 247))
        draw.text((850, y), str(row.get("unique_colors")), font=font, fill=(239, 243, 247))
        draw.text((1010, y), _camera_status(report, name), font=font, fill=_camera_color(report, name))
        y += 44

    recs = diagnostics.get("recommendations") or []
    if recs:
        rec_y = y + 20
        draw.text((52, rec_y), "Next capture backend: Spout2 or virtual camera, not Win32 window capture.", font=font, fill=(242, 247, 250))
        draw.text((52, rec_y + 41), "Bridge remains external sidecar; preview must not block when VSeeFace capture is black.", font=small, fill=(184, 194, 206))

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


def _camera_status(report: dict, variant_name: str) -> str:
    camera = _camera_for_variant(report, variant_name)
    if not camera:
        return "-"
    if camera.get("content_nonblack"):
        return "OK"
    if camera.get("opened"):
        return "BLACK"
    return "FAIL"


def _camera_color(report: dict, variant_name: str) -> tuple[int, int, int]:
    status = _camera_status(report, variant_name)
    if status == "OK":
        return (92, 226, 155)
    if status == "BLACK":
        return (255, 190, 95)
    return (255, 132, 132)


def _camera_for_variant(report: dict, variant_name: str) -> dict:
    for row in report.get("variants") or []:
        if isinstance(row, dict) and str(row.get("name") or "") == variant_name:
            camera = row.get("virtual_camera")
            return camera if isinstance(camera, dict) else {}
    return {}


if __name__ == "__main__":
    raise SystemExit(main())
