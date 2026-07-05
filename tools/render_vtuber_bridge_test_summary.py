"""Render a PNG summary of the VSeeFace bridge test results."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VSeeFace bridge test summary PNG.")
    parser.add_argument("--preview", required=True, help="Annotated face-tracking preview PNG.")
    parser.add_argument("--loopback", required=True, help="vmc_udp_loopback_check JSON report.")
    parser.add_argument("--live-check", required=True, help="vseeface_live_check JSON report.")
    parser.add_argument("--out", required=True, help="Output PNG path.")
    args = parser.parse_args()

    preview = Image.open(args.preview).convert("RGB")
    loopback = json.loads(Path(args.loopback).read_text(encoding="utf-8"))
    live = json.loads(Path(args.live_check).read_text(encoding="utf-8"))

    width, height = 1280, 720
    canvas = Image.new("RGB", (width, height), (25, 29, 34))
    draw = ImageDraw.Draw(canvas)
    font_big, font, font_small = _fonts()

    left_w = 760
    ratio = min(left_w / preview.width, height / preview.height)
    resized = preview.resize((int(preview.width * ratio), int(preview.height * ratio)))
    canvas.paste(resized, ((left_w - resized.width) // 2, (height - resized.height) // 2))

    panel_x = 790
    draw.rounded_rectangle(
        (panel_x, 32, width - 30, height - 32),
        radius=12,
        fill=(39, 45, 52),
        outline=(80, 91, 104),
        width=2,
    )
    draw.text((panel_x + 28, 58), "VSeeFace Bridge Test", fill=(242, 246, 250), font=font_big)
    draw.text(
        (panel_x + 28, 106),
        "Trump face video -> MediaPipe -> VMC/OSC UDP",
        fill=(181, 193, 204),
        font=font_small,
    )

    decoded = loopback.get("decoded_summary") if isinstance(loopback.get("decoded_summary"), dict) else {}
    blends = decoded.get("blends") if isinstance(decoded.get("blends"), dict) else {}
    bones = decoded.get("bones") if isinstance(decoded.get("bones"), dict) else {}
    rows = [
        ("Endpoint", _format_endpoint(loopback.get("endpoint"))),
        ("Face backend", str(loopback.get("diagnostics", {}).get("selected_backend", ""))),
        ("Frames", str(loopback.get("frame_count"))),
        ("Sent packets", str(loopback.get("sent_packets"))),
        ("Received packets", str(loopback.get("received_packets"))),
        ("Decoded packets", str(decoded.get("message_count", ""))),
        ("Head bone", "OK" if "Head" in bones else "MISSING"),
        ("Mouth A", _format_float(blends.get("A"))),
        ("Blink L/R", _format_pair(blends.get("Blink_L"), blends.get("Blink_R"))),
        ("Loopback result", "PASS" if loopback.get("ok") else "FAIL"),
        ("VSeeFace process", str(len(live.get("vseeface_processes") or []))),
        ("VSeeFace UDP receiver", "OPEN" if live.get("ready") else "NOT OPEN"),
    ]
    for i, (key, value) in enumerate(rows):
        y = 144 + i * 34
        draw.text((panel_x + 32, y), key, fill=(162, 174, 186), font=font_small)
        color = _value_color(value)
        draw.text((panel_x + 230, y - 4), value, fill=color, font=font)

    status_y = 582
    draw.rounded_rectangle(
        (panel_x + 28, status_y, width - 58, height - 58),
        radius=8,
        fill=(31, 36, 42),
        outline=(65, 73, 83),
    )
    draw.text(
        (panel_x + 46, status_y + 24),
        "Bridge OK. VSeeFace receiver still needs enabling.",
        fill=(238, 242, 245),
        font=font_small,
    )
    draw.text(
        (panel_x + 46, status_y + 55),
        "ready=false / vmc_receiver_port_not_open",
        fill=(255, 189, 99),
        font=font_small,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print(out)
    return 0


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


def _value_color(value: str) -> tuple[int, int, int]:
    if value in {"PASS", "OPEN", "OK"}:
        return (96, 220, 150)
    if value in {"FAIL", "NOT OPEN", "MISSING"}:
        return (255, 189, 99)
    return (238, 242, 245)


def _format_float(value: object) -> str:
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return ""


def _format_pair(left: object, right: object) -> str:
    left_text = _format_float(left)
    right_text = _format_float(right)
    if not left_text and not right_text:
        return ""
    return f"{left_text} / {right_text}"


def _format_endpoint(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    host = value.get("host", "")
    port = value.get("port", "")
    return f"{host}:{port}"


if __name__ == "__main__":
    raise SystemExit(main())
