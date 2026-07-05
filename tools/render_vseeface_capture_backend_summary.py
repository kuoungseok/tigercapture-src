"""Render a PNG summary for VSeeFace capture backend preflight."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> int:
    parser = argparse.ArgumentParser(description="Render VSeeFace capture backend summary.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    image = Image.new("RGB", (1280, 620), (22, 27, 33))
    draw = ImageDraw.Draw(image)
    big = _font(42)
    font = _font(25)
    small = _font(19)

    draw.text((48, 42), "VSeeFace Capture Backend Preflight", font=big, fill=(243, 247, 250))
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    status = str(decision.get("status") or "unknown")
    backend = str(decision.get("preferred_backend") or "none")
    status_color = (92, 226, 155) if status == "ready" else (255, 190, 95)
    draw.text((52, 108), f"Preferred: {backend} / {status}", font=font, fill=status_color)
    draw.text((52, 144), str(decision.get("next_action") or ""), font=small, fill=(184, 194, 206))

    spout = report.get("spout2") if isinstance(report.get("spout2"), dict) else {}
    vc = report.get("virtual_camera") if isinstance(report.get("virtual_camera"), dict) else {}
    obs = report.get("obs") if isinstance(report.get("obs"), dict) else {}
    rows = [
        ("Window capture", "blocked by black D3D client area", False),
        ("VSeeFace Spout sender", "available" if spout.get("sender_available") else "missing", bool(spout.get("sender_available"))),
        ("Spout receiver", "available" if spout.get("receiver_available") else "not installed", bool(spout.get("receiver_available"))),
        ("VSeeFaceCamera bundle", "available" if vc.get("bundle_available") else "missing", bool(vc.get("bundle_available"))),
        ("VSeeFaceCamera registered", "registered" if vc.get("registered") else "not registered", bool(vc.get("registered"))),
        ("OBS installed", "available" if obs.get("installed") else "missing", bool(obs.get("installed"))),
        ("OBS virtual camera bundle", "available" if obs.get("virtual_camera_bundle_available") else "missing", bool(obs.get("virtual_camera_bundle_available"))),
    ]
    y = 220
    for key, value, ok in rows:
        draw.text((72, y), key, font=font, fill=(225, 232, 239))
        color = (92, 226, 155) if ok else (255, 178, 83)
        draw.text((520, y), value, font=font, fill=color)
        y += 44

    if vc.get("requires_admin_registration"):
        draw.text((72, 552), "Next practical step: register VSeeFaceCamera with admin rights, then capture that DirectShow device.", font=small, fill=(245, 248, 252))

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
