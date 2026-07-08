"""Render a VTuber broadcast studio UI concept from local tracking/render assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout  # noqa: E402


DEFAULT_REPORT = ROOT / "debugCapture" / "milica_vrm_source_framing_bust_up_head_desk_occluded.json"
DEFAULT_AVATAR = ROOT / "debugCapture" / "milica_vrm_source_framing_bust_up_head_desk_occluded.png"
DEFAULT_VIDEO = ""
DEFAULT_BRIDGE_STATUS = ROOT / "debugCapture" / "vseeface_bridge_status_internal_fallback.json"
DEFAULT_OUT = ROOT / "debugCapture" / "vtuber_broadcast_studio_ui_trump.png"

BG = (17, 17, 17)
SURFACE = (24, 25, 27)
PANEL = (31, 34, 37)
PANEL_2 = (38, 42, 46)
EDGE = (82, 90, 96)
TEXT = (247, 242, 233)
MUTED = (170, 177, 193)
RED = (255, 91, 76)
YELLOW = (255, 210, 92)
GREEN = (90, 222, 144)
BLUE = (92, 168, 255)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a standalone VTuber broadcast studio UI screenshot.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--avatar", default=str(DEFAULT_AVATAR))
    parser.add_argument("--video", default=str(DEFAULT_VIDEO), help="Optional explicit Performance Source video for the Source Tracking panel.")
    parser.add_argument("--bridge-status", default=str(DEFAULT_BRIDGE_STATUS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1120)
    args = parser.parse_args(argv)

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    bridge_status = _read_json_optional(Path(args.bridge_status)) if args.bridge_status else {}
    avatar = Image.open(args.avatar).convert("RGBA")
    video_path = Path(args.video) if str(args.video or "").strip() else None
    source = _read_source_frame(video_path, int((report.get("frame") or {}).get("time_ms") or 0))
    layout = _build_layout(
        report,
        video_path.name if video_path else "Performance Source",
        video_path or Path(""),
        bridge_status=bridge_status,
    )
    image = render_studio_ui(layout, report, source, avatar, size=(int(args.width), int(args.height)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(json.dumps({"ok": True, "out": str(out), "schema": layout["schema"]}, ensure_ascii=False))
    return 0


def render_studio_ui(
    layout: dict[str, Any],
    report: dict[str, Any],
    source_frame: Image.Image,
    avatar_frame: Image.Image,
    *,
    size: tuple[int, int],
) -> Image.Image:
    width, height = size
    canvas = Image.new("RGBA", (width, height), BG + (255,))
    draw = ImageDraw.Draw(canvas, "RGBA")
    fonts = _fonts()
    _draw_header(draw, width, fonts, layout)

    margin = 28
    header_h = 82
    gap = 20
    program_rect = (margin, header_h, width - margin, 650)
    bottom_y = program_rect[3] + gap
    source_rect = (margin, bottom_y, 560, height - margin)
    avatar_rect = (580, bottom_y, 1120, height - margin)
    control_rect = (1140, bottom_y, width - margin, height - margin)

    _draw_program(canvas, program_rect, layout, source_frame, avatar_frame, report, fonts)
    _draw_source_tracking(canvas, source_rect, source_frame, report, fonts)
    _draw_avatar_mapping(canvas, avatar_rect, avatar_frame, report, fonts)
    _draw_controls(canvas, control_rect, layout, report, fonts)
    return canvas.convert("RGB")


def _build_layout(
    report: dict[str, Any],
    source_name: str,
    source_path: Path,
    *,
    bridge_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    framing = dict(report.get("framing") or {})
    control = dict(report.get("framing_control") or {})
    if not control:
        control = {
            "automatic": {"model_view": framing.get("model_view") or {}, "track_rotation": framing.get("track_rotation") or []},
            "user_offset": {},
            "final": {"model_view": framing.get("model_view") or {}, "track_rotation": framing.get("track_rotation") or []},
        }
    diag = dict(framing.get("diagnostics") or {})
    frame = dict(report.get("frame") or {})
    return build_vtuber_broadcast_studio_layout(
        source_name=source_name,
        avatar_name=Path(str(report.get("vrm") or "Milica.vrm")).name,
        framing_control=control,
        tracking={
            "confidence": frame.get("confidence"),
            "face_box": diag.get("face_box") or frame.get("face_box"),
            "subject_box": diag.get("subject_box"),
            "subject_source": diag.get("subject_source"),
        },
        capture_ready=True,
        bridge_status=bridge_status,
        timeline_tracks=[
            {
                "label": "Performance Source",
                "kind": "vtuber_performance_source",
                "clips": [
                    {
                        "label": source_name,
                        "kind": "video",
                        "source_path": str(source_path),
                        "timeline_in_ms": 0,
                        "duration_ms": max(60_000, int(frame.get("time_ms") or 0) + 10_000),
                        "performance_source": True,
                    }
                ],
            }
        ],
        time_ms=int(frame.get("time_ms") or 0),
    )


def _draw_header(draw: ImageDraw.ImageDraw, width: int, fonts: dict[str, Any], layout: dict[str, Any]) -> None:
    draw.rectangle((0, 0, width, 82), fill=(14, 15, 16, 255))
    draw.text((28, 18), "VTuber Broadcast Studio", font=fonts["title"], fill=TEXT)
    draw.text(
        (30, 51),
        f"Performance Source: {layout['performance_source_name']}  |  Avatar: {layout['avatar_name']}",
        font=fonts["small"],
        fill=MUTED,
    )
    bridge = dict(layout.get("bridge") or {})
    fallback = dict(bridge.get("fallback") or {})
    if fallback.get("active"):
        _pill(draw, (width - 474, 20, width - 316, 52), "INTERNAL VRM", YELLOW, fonts["small_bold"])
        _pill(draw, (width - 302, 20, width - 154, 52), "VSEEFACE OPT", BLUE, fonts["small_bold"])
    else:
        _pill(draw, (width - 286, 20, width - 190, 52), "REC", RED, fonts["small_bold"])
    _pill(draw, (width - 140, 20, width - 28, 52), "PROGRAM", GREEN, fonts["small_bold"])


def _draw_program(
    canvas: Image.Image,
    rect: tuple[int, int, int, int],
    layout: dict[str, Any],
    source: Image.Image,
    avatar: Image.Image,
    report: dict[str, Any],
    fonts: dict[str, Any],
) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    _panel(draw, rect, "PROGRAM OUTPUT", fonts)
    inner = _inset(rect, 16, 42, 16, 16)
    background = dict((layout.get("program") or {}).get("background") or {})
    bg = _program_background_frame(background, source, _size(inner))
    canvas.paste(bg, inner[:2])

    avatar_cutout = _avatar_cutout(avatar, lower_y=_model_view(report).get("lower_occlusion_y", 0.68))
    target_h = int(_height(inner) * 1.05)
    target_w = max(1, int(avatar_cutout.width * target_h / max(1, avatar_cutout.height)))
    avatar_cutout = avatar_cutout.resize((target_w, target_h), Image.Resampling.LANCZOS)
    ax = inner[0] + (_width(inner) - target_w) // 2 + 90
    ay = inner[1] - int(target_h * 0.12)
    canvas.alpha_composite(avatar_cutout, (ax, ay))

    desk_y = int(inner[1] + _height(inner) * float(_model_view(report).get("lower_occlusion_y", 0.68)))
    if str(background.get("kind") or "") != "green_chroma":
        draw.rectangle((inner[0], desk_y, inner[2], inner[3]), fill=(31, 37, 42, 236))
        draw.rectangle((inner[0], desk_y, inner[2], desk_y + 5), fill=(88, 102, 110, 210))
    else:
        draw.rectangle((inner[0], desk_y, inner[2], desk_y + 3), fill=(35, 70, 42, 190))
    label = _program_background_label(background)
    fallback = dict(((layout.get("program") or {}).get("fallback") or {}))
    renderer_label = "internal VRM fallback" if fallback.get("active") else "avatar output"
    draw.text((inner[0] + 18, inner[1] + 16), "LIVE COMPOSITE", font=fonts["small_bold"], fill=TEXT)
    draw.text((inner[0] + 18, inner[1] + 42), f"{label} + {renderer_label}", font=fonts["small"], fill=MUTED)


def _draw_source_tracking(canvas: Image.Image, rect: tuple[int, int, int, int], source: Image.Image, report: dict[str, Any], fonts: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    _panel(draw, rect, "SOURCE TRACKING", fonts)
    inner = _inset(rect, 14, 42, 14, 98)
    frame = ImageOps.fit(source.convert("RGB"), _size(inner), method=Image.Resampling.LANCZOS)
    canvas.paste(frame, inner[:2])
    report_size = tuple((report.get("source_frame_size") or [640, 360])[:2])
    diag = dict((report.get("framing") or {}).get("diagnostics") or {})
    _draw_scaled_box(draw, diag.get("subject_box"), report_size, inner, GREEN, "subject", fonts)
    _draw_scaled_box(draw, diag.get("face_box") or (report.get("frame") or {}).get("face_box"), report_size, inner, RED, "face", fonts)
    frame_info = dict(report.get("frame") or {})
    y = rect[3] - 82
    draw.text((rect[0] + 18, y), f"confidence {float(frame_info.get('confidence') or 0):.2f}", font=fonts["small_bold"], fill=TEXT)
    draw.text((rect[0] + 18, y + 26), f"subject {diag.get('subject_source', 'none')}", font=fonts["small"], fill=MUTED)
    draw.text((rect[0] + 18, y + 50), f"time {int(frame_info.get('time_ms') or 0) / 1000.0:.2f}s", font=fonts["small"], fill=MUTED)


def _draw_avatar_mapping(canvas: Image.Image, rect: tuple[int, int, int, int], avatar: Image.Image, report: dict[str, Any], fonts: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    _panel(draw, rect, "AVATAR MAPPING", fonts)
    inner = _inset(rect, 14, 42, 14, 98)
    frame = ImageOps.contain(avatar.convert("RGBA"), _size(inner), method=Image.Resampling.LANCZOS)
    px = inner[0] + (_width(inner) - frame.width) // 2
    py = inner[1] + (_height(inner) - frame.height) // 2
    canvas.alpha_composite(frame, (px, py))
    mv = _model_view(report)
    line_y = int(inner[1] + _height(inner) * float(mv.get("lower_occlusion_y", 0.68)))
    draw.line((inner[0], line_y, inner[2], line_y), fill=YELLOW + (230,), width=3)
    y = rect[3] - 82
    draw.text((rect[0] + 18, y), f"zoom {float(mv.get('zoom') or 0):.2f}   pan {float(mv.get('pan_x') or 0):+.2f}, {float(mv.get('pan_y') or 0):+.2f}", font=fonts["small_bold"], fill=TEXT)
    draw.text((rect[0] + 18, y + 26), f"desk line {float(mv.get('lower_occlusion_y') or 0):.2f}", font=fonts["small"], fill=MUTED)
    draw.text((rect[0] + 18, y + 50), "drag avatar, wheel zoom, move desk line", font=fonts["small"], fill=MUTED)


def _draw_controls(canvas: Image.Image, rect: tuple[int, int, int, int], layout: dict[str, Any], report: dict[str, Any], fonts: dict[str, Any]) -> None:
    draw = ImageDraw.Draw(canvas, "RGBA")
    _panel(draw, rect, "STUDIO CONTROLS", fonts)
    x = rect[0] + 20
    y = rect[1] + 54
    _button(draw, (x, y, rect[2] - 20, y + 44), "GO LIVE", GREEN, fonts)
    y += 58
    _button(draw, (x, y, rect[2] - 20, y + 44), "RECORD", RED, fonts)
    y += 66
    control_region = next(region for region in layout["regions"] if region["id"] == "controls")
    values = {item["id"]: item.get("value") for item in control_region["controls"]}
    _slider(draw, x, y, rect[2] - 20, "Horizontal", float(values.get("pan_x") or 0.0), -0.6, 0.6, BLUE, fonts)
    y += 66
    _slider(draw, x, y, rect[2] - 20, "Vertical", float(values.get("pan_y") or 0.0), -0.6, 0.6, BLUE, fonts)
    y += 66
    _slider(draw, x, y, rect[2] - 20, "Zoom", float(values.get("zoom_scale") or 1.0), 0.5, 1.5, YELLOW, fonts)
    y += 66
    _slider(draw, x, y, rect[2] - 20, "Desk line", float(_model_view(report).get("lower_occlusion_y") or 0.68), 0.45, 0.95, GREEN, fonts)
    y += 86
    draw.text((x, y), "Pipeline", font=fonts["small_bold"], fill=TEXT)
    fallback = dict(((layout.get("program") or {}).get("fallback") or {}))
    steps = (
        ["source tracking", "internal VRM pose", "fallback render", "broadcast output"]
        if fallback.get("active")
        else ["source tracking", "avatar mapping", "composite", "broadcast output"]
    )
    for index, step in enumerate(steps):
        sy = y + 34 + index * 34
        draw.ellipse((x, sy, x + 14, sy + 14), fill=GREEN + (255,))
        draw.text((x + 24, sy - 4), step, font=fonts["small"], fill=MUTED)


def _read_json_optional(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _read_source_frame(video_path: Path | None, time_ms: int) -> Image.Image:
    if video_path is None or not video_path.is_file():
        image = Image.new("RGB", (1280, 720), (45, 48, 52))
        draw = ImageDraw.Draw(image, "RGBA")
        draw.text((48, 48), "Performance Source video not selected", fill=(210, 216, 224))
        return image
    try:
        import cv2  # type: ignore
    except Exception:
        return Image.new("RGB", (1280, 720), (45, 48, 52))
    cap = cv2.VideoCapture(str(video_path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(time_ms)))
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok or frame is None:
        return Image.new("RGB", (1280, 720), (45, 48, 52))
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame)


def _program_background_frame(background: dict[str, Any], source: Image.Image, size: tuple[int, int]) -> Image.Image:
    kind = str(background.get("kind") or "")
    if kind == "green_chroma":
        color = background.get("color") if isinstance(background.get("color"), list) else [0, 255, 0, 255]
        rgb = tuple(int(v) for v in (color + [255, 255, 255])[:3])
        image = Image.new("RGB", size, rgb)
        draw = ImageDraw.Draw(image, "RGBA")
        draw.rectangle((0, 0, size[0], size[1]), fill=rgb + (255,))
        return image
    bg = ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    return bg.filter(ImageFilter.GaussianBlur(radius=3)).point(lambda p: int(p * 0.56))


def _program_background_label(background: dict[str, Any]) -> str:
    kind = str(background.get("kind") or "")
    if kind == "green_chroma":
        return "green chroma fallback"
    if kind == "capture":
        return f"capture: {background.get('clip_label') or background.get('track_label') or 'active'}"
    if kind == "media":
        return f"track clip: {background.get('clip_label') or background.get('track_label') or 'active'}"
    return "program background"


def _avatar_cutout(image: Image.Image, *, lower_y: float) -> Image.Image:
    import numpy as np

    rgba = image.convert("RGBA")
    arr = np.array(rgba)
    rgb = arr[:, :, :3].astype("int16")
    brightness = rgb.mean(axis=2)
    saturation = rgb.max(axis=2) - rgb.min(axis=2)
    y_limit = int(arr.shape[0] * max(0.0, min(1.0, float(lower_y))))
    mask = ((brightness > 116) | (saturation > 24)).astype("uint8") * 255
    mask[y_limit:, :] = 0
    arr[:, :, 3] = mask
    return Image.fromarray(arr, "RGBA")


def _model_view(report: dict[str, Any]) -> dict[str, Any]:
    control = report.get("framing_control") if isinstance(report.get("framing_control"), dict) else {}
    final = control.get("final") if isinstance(control.get("final"), dict) else {}
    if isinstance(final.get("model_view"), dict):
        return dict(final["model_view"])
    framing = report.get("framing") if isinstance(report.get("framing"), dict) else {}
    return dict(framing.get("model_view") or {})


def _draw_scaled_box(draw: ImageDraw.ImageDraw, box: Any, source_size: tuple[Any, Any], target: tuple[int, int, int, int], color: tuple[int, int, int], label: str, fonts: dict[str, Any]) -> None:
    if not box:
        return
    sw, sh = max(1, int(source_size[0])), max(1, int(source_size[1]))
    x, y, w, h = [float(v) for v in box[:4]]
    tx0 = target[0] + x / sw * _width(target)
    ty0 = target[1] + y / sh * _height(target)
    tx1 = target[0] + (x + w) / sw * _width(target)
    ty1 = target[1] + (y + h) / sh * _height(target)
    draw.rectangle((tx0, ty0, tx1, ty1), outline=color + (240,), width=3)
    draw.rectangle((tx0, ty0 - 24, tx0 + 92, ty0), fill=color + (220,))
    draw.text((tx0 + 8, ty0 - 22), label, font=fonts["tiny_bold"], fill=(10, 12, 13))


def _panel(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], title: str, fonts: dict[str, Any]) -> None:
    draw.rounded_rectangle(rect, radius=8, fill=PANEL + (255,), outline=EDGE + (160,), width=1)
    draw.rectangle((rect[0] + 1, rect[1] + 1, rect[2] - 1, rect[1] + 38), fill=(21, 23, 25, 255))
    draw.text((rect[0] + 16, rect[1] + 10), title, font=fonts["small_bold"], fill=TEXT)


def _button(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], label: str, color: tuple[int, int, int], fonts: dict[str, Any]) -> None:
    draw.rounded_rectangle(rect, radius=7, fill=color + (220,))
    tw = draw.textlength(label, font=fonts["button"])
    draw.text((rect[0] + (_width(rect) - tw) / 2, rect[1] + 12), label, font=fonts["button"], fill=(12, 14, 16))


def _slider(draw: ImageDraw.ImageDraw, x0: int, y: int, x1: int, label: str, value: float, min_v: float, max_v: float, color: tuple[int, int, int], fonts: dict[str, Any]) -> None:
    draw.text((x0, y), f"{label}  {value:+.2f}", font=fonts["small"], fill=TEXT)
    track_y = y + 30
    draw.rounded_rectangle((x0, track_y, x1, track_y + 8), radius=4, fill=(55, 60, 64, 255))
    t = max(0.0, min(1.0, (value - min_v) / max(0.0001, max_v - min_v)))
    knob_x = int(x0 + (x1 - x0) * t)
    draw.rounded_rectangle((x0, track_y, knob_x, track_y + 8), radius=4, fill=color + (220,))
    draw.ellipse((knob_x - 7, track_y - 5, knob_x + 7, track_y + 13), fill=color + (255,), outline=(245, 248, 250, 220), width=1)


def _pill(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], text: str, color: tuple[int, int, int], font: Any) -> None:
    draw.rounded_rectangle(rect, radius=16, fill=color + (210,))
    tw = draw.textlength(text, font=font)
    draw.text((rect[0] + (_width(rect) - tw) / 2, rect[1] + 8), text, font=font, fill=(12, 14, 16))


def _inset(rect: tuple[int, int, int, int], left: int, top: int, right: int, bottom: int) -> tuple[int, int, int, int]:
    return (rect[0] + left, rect[1] + top, rect[2] - right, rect[3] - bottom)


def _size(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    return (_width(rect), _height(rect))


def _width(rect: tuple[int, int, int, int]) -> int:
    return max(1, int(rect[2] - rect[0]))


def _height(rect: tuple[int, int, int, int]) -> int:
    return max(1, int(rect[3] - rect[1]))


def _fonts() -> dict[str, Any]:
    base = "C:/Windows/Fonts/malgun.ttf"
    bold = "C:/Windows/Fonts/malgunbd.ttf"
    try:
        return {
            "title": ImageFont.truetype(bold, 25),
            "button": ImageFont.truetype(bold, 17),
            "small_bold": ImageFont.truetype(bold, 14),
            "small": ImageFont.truetype(base, 14),
            "tiny_bold": ImageFont.truetype(bold, 11),
        }
    except OSError:
        fallback = ImageFont.load_default()
        return {key: fallback for key in ("title", "button", "small_bold", "small", "tiny_bold")}


if __name__ == "__main__":
    raise SystemExit(main())
