from __future__ import annotations

import argparse
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation import ppt_export
from app.review_automation.fonts import load_pil_font
from app.review_automation.paths import DEFAULT_REVIEW_ROOT, DEFAULT_REVIEW_VIDEO_SOURCE_DIR, review_paths
from tools.generate_review_assets import generate_review_assets


SLIDE_W = 1280
SLIDE_H = 720


def _rgb(hex_color: str) -> tuple[int, int, int]:
    raw = str(hex_color or ppt_export.THEME_INK).strip().lstrip("#")
    if len(raw) != 6:
        raw = ppt_export.THEME_INK
    return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))


def _px_emu(value: int, axis: str) -> int:
    source = ppt_export.SLIDE_W if axis == "x" else ppt_export.SLIDE_H
    target = SLIDE_W if axis == "x" else SLIDE_H
    return int(round(int(value) * target / source))


def _pt_to_px(size: int) -> int:
    return max(8, int(round((int(size) / 100.0) * 96.0 / 72.0)))


def _cover_image(path: Path, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGB", (max(1, width), max(1, height)), _rgb(ppt_export.THEME_PANEL_2))
    if not path.exists():
        return canvas
    try:
        image = Image.open(path).convert("RGB")
    except Exception:
        return canvas
    scale = max(width / max(1, image.width), height / max(1, image.height))
    resized = image.resize(
        (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        current = ""
        for word in paragraph.split(" "):
            test = f"{current} {word}".strip()
            if not current or draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def render_slide_png(slide: dict[str, Any], out_path: Path, *, locale: str = "en") -> Path:
    image = Image.new("RGB", (SLIDE_W, SLIDE_H), _rgb(ppt_export.THEME_BG))
    draw = ImageDraw.Draw(image)
    for row in slide.get("rects", []):
        x, y, w, h, fill, line = row[:6]
        box = (
            _px_emu(x, "x"),
            _px_emu(y, "y"),
            _px_emu(x + w, "x"),
            _px_emu(y + h, "y"),
        )
        draw.rectangle(box, fill=_rgb(fill), outline=_rgb(line), width=2)
    for media_path, x, y, w, h in slide.get("images", []):
        left, top = _px_emu(x, "x"), _px_emu(y, "y")
        width, height = _px_emu(w, "x"), _px_emu(h, "y")
        image.paste(_cover_image(Path(media_path), width, height), (left, top))
    for row in slide.get("texts", []):
        x, y, w, h, text, size, bold, color, *extra = row
        left, top = _px_emu(x, "x"), _px_emu(y, "y")
        width, height = _px_emu(w, "x"), _px_emu(h, "y")
        align = str(extra[0]) if len(extra) >= 1 else "l"
        caps = bool(extra[1]) if len(extra) >= 2 else False
        raw_text = str(text or "")
        if caps:
            raw_text = raw_text.upper()
        font = load_pil_font(_pt_to_px(size), bold=bool(bold), locale=locale)
        line_h = int(_pt_to_px(size) * 1.12)
        cursor_y = top
        for line in _wrap(draw, raw_text, font, width):
            if cursor_y + line_h > top + height + 8:
                break
            bbox = draw.textbbox((0, 0), line, font=font)
            text_x = left
            if align in {"ctr", "c", "center"}:
                text_x = left + (width - (bbox[2] - bbox[0])) // 2
            elif align == "r":
                text_x = left + width - (bbox[2] - bbox[0])
            draw.text((text_x, cursor_y), line, font=font, fill=_rgb(color))
            cursor_y += line_h
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, quality=95)
    return out_path


def _pptx_path(output_dir: Path, mode: str, locale: str = "en") -> Path:
    mode_suffix = "" if mode == "summary" else "_" + mode.replace("-", "_")
    locale_suffix = "_ko" if str(locale or "").lower().startswith("ko") else ""
    suffix = f"{mode_suffix}{locale_suffix}"
    return output_dir / f"TigerCapture_Review_Automation{suffix}.pptx"


def _render_mode(args: argparse.Namespace, mode: str, locale: str = "en") -> dict[str, Any]:
    paths = review_paths(args.review_root)
    gen_args = Namespace(
        review_root=args.review_root,
        out_dir=paths["outputs"],
        report=paths["report"],
        sample_root=paths["samples"],
        sample_report=paths["sample_report"],
        video_source_dir=args.video_source_dir,
        synthetic_video=False,
        run_qa=False,
        skip_html=False,
        skip_ppt=False,
        manifest_only=False,
        force=bool(args.force),
        deck_mode=mode,
    )
    report = generate_review_assets(gen_args)
    slides, _media = ppt_export._build_slides(report, ROOT, deck_mode=mode, locale=locale)
    slide_dir = paths["outputs"] / "deck_pngs" / (mode if locale == "en" else f"{mode}_{locale}")
    slide_dir.mkdir(parents=True, exist_ok=True)
    for old in slide_dir.glob("slide_*.png"):
        old.unlink()
    for index, slide in enumerate(slides, start=1):
        render_slide_png(slide, slide_dir / f"slide_{index:03d}.png", locale=locale)
    return {
        "mode": mode,
        "locale": locale,
        "ok": bool(report.get("ok")),
        "slides": len(slides),
        "png_dir": str(slide_dir),
        "pptx": str(_pptx_path(paths["outputs"], mode, locale)),
        "summary": report.get("summary", {}),
    }


def _write_office_pptx(results: list[dict[str, Any]]) -> None:
    items = [
        {
            "mode": row["mode"],
            "dir": row["png_dir"],
            "out": row["pptx"],
        }
        for row in results
    ]
    script = r"""
$ErrorActionPreference='Stop'
$items = @'
__ITEMS_JSON__
'@ | ConvertFrom-Json
$pp = New-Object -ComObject PowerPoint.Application
try {
  foreach($item in $items){
    $pngs = Get-ChildItem -LiteralPath $item.dir -Filter 'slide_*.png' | Sort-Object Name
    if($pngs.Count -lt 1){ throw "No PNG slides for $($item.mode)" }
    if(Test-Path -LiteralPath $item.out){ Remove-Item -LiteralPath $item.out -Force }
    $pres = $pp.Presentations.Add($false)
    $pres.PageSetup.SlideWidth = 960
    $pres.PageSetup.SlideHeight = 540
    $idx = 1
    foreach($png in $pngs){
      $slide = $pres.Slides.Add($idx, 12)
      $null = $slide.Shapes.AddPicture($png.FullName, $false, $true, 0, 0, $pres.PageSetup.SlideWidth, $pres.PageSetup.SlideHeight)
      $idx++
    }
    $pres.SaveAs($item.out)
    $pres.Close()
  }
} finally {
  $pp.Quit()
}
"""
    script = script.replace("__ITEMS_JSON__", json.dumps(items, ensure_ascii=False))
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Office-valid review PPTX decks from automated review evidence.")
    parser.add_argument("--review-root", type=Path, default=DEFAULT_REVIEW_ROOT)
    parser.add_argument("--video-source-dir", type=Path, default=DEFAULT_REVIEW_VIDEO_SOURCE_DIR)
    parser.add_argument("--deck-mode", choices=("summary", "detailed", "evidence-full", "all"), default="all")
    parser.add_argument("--locale", choices=("en", "ko", "both"), default="en")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-office", action="store_true", help="Only render slide PNGs; do not use PowerPoint COM.")
    args = parser.parse_args()
    modes = ("summary", "detailed", "evidence-full") if args.deck_mode == "all" else (args.deck_mode,)
    locales = ("en", "ko") if args.locale == "both" else (args.locale,)
    results = [_render_mode(args, mode, locale) for locale in locales for mode in modes]
    manifest_path = review_paths(args.review_root)["outputs"] / "deck_pngs" / "deck_render_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.skip_office:
        _write_office_pptx(results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(row.get("ok") for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
