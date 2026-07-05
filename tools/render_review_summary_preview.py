from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation.fonts import load_pil_font


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    return load_pil_font(size, bold=bold)


def _wrap(draw: ImageDraw.ImageDraw, text: Any, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = str(text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _text_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: Any,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    max_width: int,
    *,
    leading: int = 8,
) -> int:
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += int(getattr(font, "size", 20)) + leading
    return y


BG = (5, 7, 11)
INK = (246, 241, 232)
MUTED = (170, 177, 194)
DIM = (111, 119, 139)
ACCENT = (255, 95, 69)
CYAN = (105, 231, 214)
LIME = (185, 255, 102)
PANEL = (16, 20, 31)
PANEL2 = (24, 29, 43)
LINE = (50, 58, 79)
WARN = (255, 209, 102)
BAD = (255, 104, 128)


def _contain(path: Path, box: tuple[int, int, int, int], *, fill: tuple[int, int, int] = PANEL2) -> Image.Image:
    w, h = box[2] - box[0], box[3] - box[1]
    canvas = Image.new("RGB", (w, h), fill)
    if not path.exists():
        return canvas
    image = Image.open(path).convert("RGB")
    image.thumbnail((w, h), Image.Resampling.LANCZOS)
    canvas.paste(image, ((w - image.width) // 2, (h - image.height) // 2))
    return canvas


def _cover(path: Path, box: tuple[int, int, int, int], *, fill: tuple[int, int, int] = PANEL2) -> Image.Image:
    w, h = box[2] - box[0], box[3] - box[1]
    canvas = Image.new("RGB", (w, h), fill)
    if not path.exists():
        return canvas
    image = Image.open(path).convert("RGB")
    scale = max(w / image.width, h / image.height)
    scaled = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.LANCZOS)
    left = max(0, (scaled.width - w) // 2)
    top = max(0, (scaled.height - h) // 2)
    canvas.paste(scaled.crop((left, top, left + w, top + h)), (0, 0))
    return canvas


def _new_slide() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    slide = Image.new("RGB", (1280, 720), BG)
    draw = ImageDraw.Draw(slide)
    for x in range(1280):
        if x > 590:
            draw.line([(x, 0), (x, 720)], fill=(6 + (x - 590) // 90, 9 + (x - 590) // 80, 15 + (x - 590) // 70))
    return slide, draw


def _slide_footer(draw: ImageDraw.ImageDraw, number: int, total: int = 4) -> None:
    small = _font(15)
    draw.text((1148, 664), f"{number:02}/{total:02}", font=small, fill=DIM)


def _draw_spec_row(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    number: str,
    label: str,
    value: str,
    accent: tuple[int, int, int],
) -> None:
    draw.text((x, y), number, font=_font(31, bold=True), fill=accent)
    draw.text((x + 86, y + 5), label, font=_font(22, bold=True), fill=INK)
    draw.text((x + 86, y + 35), value, font=_font(18), fill=MUTED)


def _asset(output_root: Path, primary: str, fallback: str = "") -> Path:
    path = output_root / "assets" / primary
    if path.exists():
        return path
    return output_root / "assets" / fallback if fallback else path


def _draw_title_slide(report: dict[str, Any], output_root: Path) -> Image.Image:
    summary = dict(report.get("summary") or {})
    slide, draw = _new_slide()
    draw.rectangle((590, 0, 1280, 720), fill=PANEL)
    draw.rectangle((618, 40, 626, 630), fill=ACCENT)
    draw.text((56, 46), "TIGERCAPTURE STUDIO 2026", font=_font(18, bold=True), fill=CYAN)
    draw.text((56, 95), "Creator", font=_font(74, bold=True), fill=INK)
    draw.text((56, 168), "Editing", font=_font(74, bold=True), fill=INK)
    draw.text((56, 241), "Suite", font=_font(74, bold=True), fill=INK)
    _text_block(
        draw,
        62,
        350,
        "Record, edit, composite, finish. A local studio for creator demos, actor overlays, and multilingual delivery.",
        _font(23),
        MUTED,
        460,
        leading=8,
    )
    draw.line((56, 463, 505, 463), fill=LINE, width=2)
    _draw_spec_row(draw, 62, 488, "01", "Screen capture", "polish cursor, clicks, and zooms", ACCENT)
    _draw_spec_row(draw, 62, 562, "02", "Timeline + actors", "Live2D lanes beside normal video", CYAN)
    draw.text((62, 636), "03", font=_font(31, bold=True), fill=LIME)
    draw.text((148, 641), "Multilingual publish", font=_font(22, bold=True), fill=INK)
    editor = _cover(_asset(output_root, "catalog_editor_surface.png"), (0, 0, 545, 307))
    slide.paste(editor, (650, 64))
    poster = _cover(_asset(output_root, "catalog_timeline_detail.png"), (0, 0, 380, 214))
    slide.paste(poster, (782, 455))
    draw.text((650, 424), f"{summary.get('ready_artifacts', 0)} assets / {summary.get('sample_resources_ready', 0)} samples", font=_font(19, bold=True), fill=LIME)
    _slide_footer(draw, 1)
    return slide


def _draw_visual_slide(report: dict[str, Any], output_root: Path) -> Image.Image:
    slide, draw = _new_slide()
    draw.text((54, 45), "EDITOR SURFACE", font=_font(18, bold=True), fill=CYAN)
    draw.text((54, 86), "One canvas for creator work", font=_font(42, bold=True), fill=INK)
    draw.rectangle((46, 164, 934, 622), fill=PANEL2, outline=LINE, width=2)
    editor = _cover(_asset(output_root, "catalog_editor_surface.png"), (0, 0, 842, 474))
    slide.paste(editor, (70, 186))
    draw.rectangle((956, 164, 1220, 622), fill=PANEL, outline=LINE, width=2)
    specs = [
        ("MEDIA POOL", "Import, relink, proxy, and organize creator assets.", CYAN),
        ("TIMELINE", "Cut clips, place actors, stack effects, and preview instantly.", ACCENT),
        ("WORKBENCH", "Color, masks, subtitles, audio cleanup, and render queue.", LIME),
    ]
    y = 198
    for label, value, color in specs:
        draw.text((984, y), label, font=_font(18, bold=True), fill=color)
        y = _text_block(draw, 984, y + 36, value, _font(18), MUTED, 190, leading=5) + 28
    draw.rectangle((46, 616, 1234, 620), fill=ACCENT)
    draw.text(
        (58, 642),
        "A clean public screenshot is generated separately from QA evidence captures.",
        font=_font(18),
        fill=MUTED,
    )
    _slide_footer(draw, 2)
    return slide


def _draw_feature_slide(report: dict[str, Any]) -> Image.Image:
    summary = dict(report.get("summary") or {})
    slide, draw = _new_slide()
    draw.text((54, 46), "SIGNATURE WORKFLOWS", font=_font(18, bold=True), fill=ACCENT)
    draw.text((54, 94), "The parts people remember.", font=_font(48, bold=True), fill=INK)
    draw.rectangle((46, 230, 780, 590), fill=PANEL, outline=LINE, width=2)
    rows = [
        ("01", "Capture polish", "cursor trails / click rings / auto zoom", ACCENT),
        ("02", "Actor timeline", "Live2D lanes beside normal video", CYAN),
        ("03", "Six-language UI", "KR / EN / JP / CN / FR / DE", LIME),
        ("04", "Creator assist", "captions / shorts / publish copy / prompt edits", ACCENT),
        ("05", "Finishing tools", "color / audio cleanup / masks / presets", CYAN),
    ]
    y = 258
    for number, label, value, color in rows:
        _draw_spec_row(draw, 76, y, number, label, value, color)
        y += 62
    draw.rectangle((796, 84, 1198, 590), fill=PANEL2, outline=LINE, width=2)
    draw.text((828, 112), str(summary.get("evidence_ready", 0)), font=_font(96, bold=True), fill=LIME)
    draw.text((848, 210), "ready features", font=_font(21, bold=True), fill=MUTED)
    draw.text((838, 292), "6", font=_font(66, bold=True), fill=CYAN)
    draw.text((918, 316), "languages", font=_font(23, bold=True), fill=MUTED)
    draw.text((838, 404), "Local-first", font=_font(26, bold=True), fill=CYAN)
    _text_block(
        draw,
        838,
        446,
        "Sample media, screenshots, and generated catalogs stay in the developer workspace.",
        _font(19),
        MUTED,
        300,
        leading=6,
    )
    draw.rectangle((46, 616, 1234, 620), fill=CYAN)
    _slide_footer(draw, 3)
    return slide


def _draw_contract_slide(report: dict[str, Any]) -> Image.Image:
    summary = dict(report.get("summary") or {})
    slide, draw = _new_slide()
    draw.text((54, 46), "CATALOG KIT", font=_font(18, bold=True), fill=CYAN)
    draw.text((54, 96), "Three editions,", font=_font(54, bold=True), fill=INK)
    draw.text((54, 158), "one product story.", font=_font(54, bold=True), fill=INK)
    _text_block(
        draw,
        66,
        272,
        "Use it as a product introduction, a feature catalog, or a showroom handoff when the spec changes.",
        _font(24),
        MUTED,
        560,
        leading=8,
    )
    draw.rectangle((680, 84, 1212, 470), fill=PANEL, outline=LINE, width=2)
    draw.text((708, 110), "DELIVERABLES", font=_font(20, bold=True), fill=ACCENT)
    rows = [
        ("SUMMARY DECK", "for quick sharing"),
        ("DETAILED BOOK", "feature-by-feature catalog"),
        ("VISUAL APPENDIX", "full screenshot set"),
        ("HTML CATALOG", "browser-ready showroom"),
    ]
    y = 164
    for label, value in rows:
        draw.text((708, y), label, font=_font(16, bold=True), fill=CYAN)
        draw.text((708, y + 27), value, font=_font(17), fill=INK)
        y += 70
    draw.rectangle((56, 552, 1204, 628), fill=PANEL2, outline=LINE, width=2)
    draw.text(
        (84, 578),
        f"{summary.get('ready_artifacts', 0)} assets / {summary.get('sample_resources_ready', 0)} sample files / 3 deck modes",
        font=_font(21, bold=True),
        fill=LIME,
    )
    draw.rectangle((46, 650, 1234, 654), fill=ACCENT)
    _slide_footer(draw, 4)
    return slide


def _summary_slides(report_path: Path) -> list[Image.Image]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    output_root = report_path.parent
    return [
        _draw_title_slide(report, output_root),
        _draw_visual_slide(report, output_root),
        _draw_feature_slide(report),
        _draw_contract_slide(report),
    ]


def render_summary_preview(report_path: Path, out_path: Path) -> Path:
    slides = _summary_slides(report_path)
    thumb_w, thumb_h = 1180, 664
    pad, gutter = 58, 40
    width = pad * 2 + thumb_w * 2 + gutter
    height = pad * 2 + thumb_h * 2 + gutter
    sheet = Image.new("RGB", (width, height), (8, 10, 16))
    draw = ImageDraw.Draw(sheet)
    draw.text((pad, 18), "TigerCapture Studio · PRODUCT CATALOG preview", font=_font(24, bold=True), fill=INK)
    for idx, slide in enumerate(slides):
        thumb = slide.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = pad + (idx % 2) * (thumb_w + gutter)
        y = pad + (idx // 2) * (thumb_h + gutter)
        draw.rounded_rectangle((x - 5, y - 5, x + thumb_w + 5, y + thumb_h + 5), radius=10, fill=(20, 24, 34), outline=LINE, width=2)
        sheet.paste(thumb, (x, y))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, quality=95)
    return out_path


def render_phone_preview(report_path: Path, out_path: Path) -> Path:
    slides = _summary_slides(report_path)
    target_w = 1080
    margin = 24
    gap = 34
    resized = [
        slide.resize((target_w, int(slide.height * target_w / slide.width)), Image.Resampling.LANCZOS)
        for slide in slides
    ]
    total_h = margin * 2 + sum(slide.height for slide in resized) + gap * (len(resized) - 1)
    canvas = Image.new("RGB", (target_w + margin * 2, total_h), (8, 10, 16))
    y = margin
    for slide in resized:
        canvas.paste(slide, (margin, y))
        y += slide.height + gap
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a single PNG preview for the review summary.")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("E:/ClaudeCodeApp/ReviewAutomationWorkspace/outputs/review_report.json"),
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--phone-out", type=Path, default=None)
    args = parser.parse_args()
    out = args.out or args.report.parent / "review_summary_preview.png"
    print(render_summary_preview(args.report, out))
    if args.phone_out:
        print(render_phone_preview(args.report, args.phone_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
