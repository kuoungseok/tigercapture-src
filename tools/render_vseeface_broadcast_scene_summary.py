"""Render a PNG summary for the VSeeFace BroadcastScene source contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_bridge import (  # noqa: E402
    CAPTURE_STATUS_BLOCKED_REGISTRATION,
    CAPTURE_STATUS_NOT_PROBED,
    CAPTURE_STATUS_READY,
    CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
    CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED,
    CAPTURE_VIRTUAL_CAMERA,
    build_vseeface_bridge_status,
    default_vseeface_bridge_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render VSeeFace BroadcastScene contract summary.")
    parser.add_argument("--capture-report", default="", help="Optional capture diagnostics JSON.")
    parser.add_argument("--capture-status", default=CAPTURE_STATUS_NOT_PROBED)
    parser.add_argument("--capture-method", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args(argv)

    capture_diagnostics = _load_capture_report(args.capture_report) or _diagnostics_for_status(str(args.capture_status))
    config = default_vseeface_bridge_config(ROOT)
    if args.capture_method:
        config.capture.method = str(args.capture_method)
    elif str(args.capture_status) in {
        CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK,
        CAPTURE_STATUS_BLOCKED_REGISTRATION,
        CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED,
    }:
        config.capture.method = CAPTURE_VIRTUAL_CAMERA
    status = build_vseeface_bridge_status(
        config,
        width=int(args.width),
        height=int(args.height),
        capture_diagnostics=capture_diagnostics,
    )
    scene = status["scene"]
    scene_diag = status["scene_diagnostics"]
    source = scene["sources"][1]
    settings = source["settings"]
    health = settings["capture_health"]
    view = status.get("view") if isinstance(status.get("view"), dict) else {}
    badge = view.get("badge") if isinstance(view.get("badge"), dict) else {}
    primary_action = view.get("primary_action") if isinstance(view.get("primary_action"), dict) else {}
    dependency = view.get("dependency") if isinstance(view.get("dependency"), dict) else {}
    fallback = view.get("fallback") if isinstance(view.get("fallback"), dict) else {}
    secondary_actions = view.get("secondary_actions") if isinstance(view.get("secondary_actions"), list) else []
    start_probe_action = next(
        (item for item in secondary_actions if isinstance(item, dict) and item.get("id") == "start_vseeface_and_probe"),
        {},
    )

    image = Image.new("RGB", (1280, 940), (24, 29, 35))
    draw = ImageDraw.Draw(image)
    big, font, small = _fonts()

    draw.text((48, 42), "VSeeFace Broadcast Source Contract", font=big, fill=(243, 247, 250))
    draw.text((52, 102), "External sidecar source guarded against black capture frames", font=small, fill=(184, 194, 206))

    label = str(badge.get("text") or "")
    tone = str(badge.get("tone") or "info")
    status_color = _severity_color(tone)
    draw.rounded_rectangle((52, 150, 520, 246), radius=10, fill=(37, 44, 52), outline=(73, 84, 97))
    draw.text((78, 174), "Capture status", font=small, fill=(160, 174, 188))
    draw.text((78, 202), label, font=font, fill=status_color)

    draw.rounded_rectangle((552, 150, 1040, 246), radius=10, fill=(37, 44, 52), outline=(73, 84, 97))
    draw.text((578, 174), "Scene diagnostics", font=small, fill=(160, 174, 188))
    diag_label = "OK" if scene_diag.get("ok") else "MISSING"
    draw.text((578, 202), diag_label, font=font, fill=_value_color(diag_label))

    rows = [
        ("Dependency", str(dependency.get("state") or "unknown")),
        ("Dependency action", str((dependency.get("primary_action") or {}).get("label") or "none")),
        ("Bridge state", str(status.get("state"))),
        ("Source id", str(source.get("id"))),
        ("Capture method", str(settings.get("capture_method"))),
        ("Capture ready", str(settings.get("capture_ready"))),
        ("Capture status", str(settings.get("capture_status"))),
        ("Fallback", str(settings.get("fallback_behavior"))),
        ("Fallback mode", str(fallback.get("label") or settings.get("fallback_mode") or "none")),
        ("Fallback source", str(fallback.get("source_id") or settings.get("fallback_source_id") or "none")),
        ("Suppress black frame", str(settings.get("suppress_black_frame"))),
        ("Missing sources", ", ".join(scene_diag.get("missing_frame_sources") or []) or "none"),
        ("Degraded sources", ", ".join(scene_diag.get("degraded_frame_sources") or []) or "none"),
        ("Primary action", str(primary_action.get("label") or "none")),
        ("Start/probe action", str(start_probe_action.get("label") or "none")),
    ]
    y = 302
    for key, value in rows:
        draw.text((78, y), key, font=small, fill=(160, 174, 188))
        draw.text((360, y - 4), value, font=font, fill=_row_value_color(value))
        y += 38

    action = str(primary_action.get("id") or (status.get("ui") if isinstance(status.get("ui"), dict) else {}).get("action") or "")
    draw.text((78, 900), f"UI action: {action}  |  Dependency: {dependency.get('text') or 'none'}", font=small, fill=(184, 194, 206))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(str(out))
    return 0


def _diagnostics_for_status(status: str) -> dict:
    if status == CAPTURE_STATUS_READY:
        return {"ok": True, "status": "ready_for_capture", "usable_window_capture": True}
    if status == CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK:
        return {"ok": False, "status": status, "errors": [status]}
    if status == CAPTURE_STATUS_BLOCKED_REGISTRATION:
        return {
            "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
            "ok": False,
            "status": status,
            "preflight": {
                "virtual_camera": {
                    "registered": False,
                    "requires_admin_registration": True,
                }
            },
            "errors": ["vseeface_camera_not_registered"],
        }
    if status == CAPTURE_STATUS_VIRTUAL_CAMERA_FAILED:
        return {
            "schema": "tigerstudio.vtuber.vseeface_post_install_verification.v1",
            "ok": False,
            "status": status,
            "errors": [status],
        }
    return {}


def _load_capture_report(path_text: str) -> dict:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    try:
        return (
            ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 34),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 24),
            ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 18),
        )
    except Exception:
        fallback = ImageFont.load_default()
        return fallback, fallback, fallback


def _severity_color(value: str) -> tuple[int, int, int]:
    if value == "ok":
        return (96, 220, 150)
    if value == "blocked":
        return (255, 183, 82)
    if value == "warning":
        return (255, 211, 112)
    return (165, 201, 255)


def _value_color(value: str) -> tuple[int, int, int]:
    if value == "OK":
        return (96, 220, 150)
    return (255, 183, 82)


def _row_value_color(value: str) -> tuple[int, int, int]:
    if value in {"True", "OK", "ready"}:
        return (96, 220, 150)
    if value in {"False", CAPTURE_STATUS_VIRTUAL_CAMERA_BLACK, "vseeface"}:
        return (255, 183, 82)
    return (235, 241, 247)


if __name__ == "__main__":
    raise SystemExit(main())
