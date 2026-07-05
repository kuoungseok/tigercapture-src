from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat


DEFAULT_CROP = (300, 185, 1010, 520)


def _parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = [int(part.strip()) for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be x0,y0,x1,y1")
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        raise argparse.ArgumentTypeError("crop x1/y1 must be larger than x0/y0")
    return x0, y0, x1, y1


def _run_capture(
    *,
    gpu_tool: Path,
    asset: Path,
    output: Path,
    mode: str,
    texture_max_size: int,
    screenshot_delay_ms: int,
    enable_shadow_map: bool,
) -> None:
    command = [
        sys.executable,
        str(gpu_tool),
        "--asset",
        str(asset),
        "--texture-max-size",
        str(max(256, int(texture_max_size))),
        "--preview-uv-v-flip",
        str(mode),
        "--screenshot",
        str(output),
        "--screenshot-delay-ms",
        str(max(100, int(screenshot_delay_ms))),
    ]
    if enable_shadow_map:
        command.append("--enable-shadow-map")
    subprocess.run(command, cwd=str(gpu_tool.parents[1]), check=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_diff_metrics(left: Path, right: Path) -> dict[str, float | bool]:
    left_image = Image.open(left).convert("RGB")
    right_image = Image.open(right).convert("RGB")
    if left_image.size != right_image.size:
        return {
            "same_size": False,
            "identical": False,
            "mean_abs_channel_diff": float("inf"),
            "max_abs_channel_diff": float("inf"),
        }
    diff = ImageChops.difference(left_image, right_image)
    extrema = diff.getextrema()
    max_abs = max(channel[1] for channel in extrema)
    mean_abs = sum(ImageStat.Stat(diff).mean) / 3.0
    return {
        "same_size": True,
        "identical": bool(max_abs == 0),
        "mean_abs_channel_diff": float(mean_abs),
        "max_abs_channel_diff": float(max_abs),
    }


def _write_report(
    captures: dict[str, Path],
    *,
    sheet: Path,
    report: Path,
    asset: Path,
    crop_box: tuple[int, int, int, int],
) -> dict[str, object]:
    by_mode = {
        "off": captures["OFF (old)"],
        "auto": captures["AUTO (fixed)"],
        "on": captures["ON (forced)"],
    }
    hashes = {mode: _sha256_file(path) for mode, path in by_mode.items()}
    diffs = {
        "auto_vs_on": _image_diff_metrics(by_mode["auto"], by_mode["on"]),
        "auto_vs_off": _image_diff_metrics(by_mode["auto"], by_mode["off"]),
    }
    report_data: dict[str, object] = {
        "asset": str(asset),
        "sheet": str(sheet),
        "crop_box": list(crop_box),
        "captures": {mode: str(path) for mode, path in by_mode.items()},
        "sha256": hashes,
        "diffs": diffs,
        "verdict": {
            "auto_matches_forced_on": bool(diffs["auto_vs_on"]["identical"]),
            "auto_differs_from_old_off": bool(not diffs["auto_vs_off"]["identical"]),
            "uv_v_flip_auto_active": bool(
                diffs["auto_vs_on"]["identical"] and not diffs["auto_vs_off"]["identical"]
            ),
        },
    }
    report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_data


def _make_compare_sheet(
    captures: dict[str, Path],
    *,
    output: Path,
    crop_box: tuple[int, int, int, int],
) -> None:
    images = {label: Image.open(path).convert("RGB") for label, path in captures.items()}
    font = ImageFont.load_default()
    full_w, full_h = 560, 326
    crop_w, crop_h = 560, 264
    pad = 14
    label_h = 24
    sheet_w = len(images) * full_w + (len(images) + 1) * pad
    sheet_h = pad + label_h + full_h + pad + label_h + crop_h + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (30, 34, 42))
    draw = ImageDraw.Draw(sheet)

    x = pad
    for label, image in images.items():
        draw.rectangle(
            (x - 2, pad - 2, x + full_w + 1, pad + label_h + full_h + 1),
            outline=(76, 86, 110),
            width=2,
        )
        draw.text((x + 8, pad + 6), label, fill=(235, 240, 255), font=font)
        sheet.paste(image.resize((full_w, full_h), Image.Resampling.LANCZOS), (x, pad + label_h))

        y2 = pad + label_h + full_h + pad
        draw.rectangle(
            (x - 2, y2 - 2, x + crop_w + 1, y2 + label_h + crop_h + 1),
            outline=(76, 86, 110),
            width=2,
        )
        draw.text((x + 8, y2 + 6), f"{label} crop", fill=(235, 240, 255), font=font)
        crop = image.crop(crop_box).resize((crop_w, crop_h), Image.Resampling.LANCZOS)
        sheet.paste(crop, (x, y2 + label_h))
        crop.save(output.with_name(f"{output.stem}_{label.lower().split()[0]}_crop.png"))
        x += full_w + pad

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _make_diff_sheet(
    captures: dict[str, Path],
    *,
    output: Path,
    amplify: int = 6,
) -> None:
    pairs = [
        ("AUTO vs OFF", captures["AUTO (fixed)"], captures["OFF (old)"]),
        ("AUTO vs ON", captures["AUTO (fixed)"], captures["ON (forced)"]),
    ]
    font = ImageFont.load_default()
    panel_w, panel_h = 720, 419
    pad = 14
    label_h = 24
    sheet_w = len(pairs) * panel_w + (len(pairs) + 1) * pad
    sheet_h = pad + label_h + panel_h + pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (30, 34, 42))
    draw = ImageDraw.Draw(sheet)

    x = pad
    for label, left_path, right_path in pairs:
        left = Image.open(left_path).convert("RGB")
        right = Image.open(right_path).convert("RGB")
        if left.size != right.size:
            right = right.resize(left.size, Image.Resampling.BILINEAR)
        diff = ImageChops.difference(left, right)
        factor = max(1, int(amplify))
        diff = diff.point(lambda value: min(255, value * factor))
        draw.rectangle(
            (x - 2, pad - 2, x + panel_w + 1, pad + label_h + panel_h + 1),
            outline=(76, 86, 110),
            width=2,
        )
        draw.text((x + 8, pad + 6), label, fill=(235, 240, 255), font=font)
        sheet.paste(diff.resize((panel_w, panel_h), Image.Resampling.LANCZOS), (x, pad + label_h))
        x += panel_w + pad

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _diff_bbox(
    left_path: Path,
    right_path: Path,
    *,
    threshold: int = 8,
    padding: int = 40,
) -> tuple[int, int, int, int]:
    threshold = max(0, int(threshold))
    padding = max(0, int(padding))
    left = Image.open(left_path).convert("RGB")
    right = Image.open(right_path).convert("RGB")
    if left.size != right.size:
        right = right.resize(left.size, Image.Resampling.BILINEAR)
    diff = ImageChops.difference(left, right).convert("L")
    mask = diff.point(lambda value: 255 if value > threshold else 0)
    bbox = mask.getbbox()
    width, height = left.size
    if bbox is None:
        return 0, 0, width, height
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 - padding),
        max(0, y0 - padding),
        min(width, x1 + padding),
        min(height, y1 + padding),
    )


def _fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, (20, 23, 30))
    fitted = image.convert("RGB")
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    panel.paste(fitted, (x, y))
    return panel


def _make_focus_sheet(
    captures: dict[str, Path],
    *,
    output: Path,
    threshold: int = 8,
    padding: int = 40,
    amplify: int = 6,
) -> tuple[int, int, int, int]:
    focus_box = _diff_bbox(
        captures["AUTO (fixed)"],
        captures["OFF (old)"],
        threshold=threshold,
        padding=padding,
    )
    labels = ["OFF (old)", "AUTO (fixed)", "ON (forced)"]
    images = {label: Image.open(captures[label]).convert("RGB").crop(focus_box) for label in labels}
    diff = ImageChops.difference(images["AUTO (fixed)"], images["OFF (old)"])
    factor = max(1, int(amplify))
    diff = diff.point(lambda value: min(255, value * factor))
    images["AUTO vs OFF diff"] = diff

    font = ImageFont.load_default()
    panel_w, panel_h = 420, 260
    pad = 14
    label_h = 24
    columns = 2
    rows = 2
    sheet_w = columns * panel_w + (columns + 1) * pad
    sheet_h = rows * (label_h + panel_h) + (rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (30, 34, 42))
    draw = ImageDraw.Draw(sheet)

    for idx, (label, image) in enumerate(images.items()):
        col = idx % columns
        row = idx // columns
        x = pad + col * (panel_w + pad)
        y = pad + row * (label_h + panel_h + pad)
        draw.rectangle(
            (x - 2, y - 2, x + panel_w + 1, y + label_h + panel_h + 1),
            outline=(76, 86, 110),
            width=2,
        )
        draw.text((x + 8, y + 6), label, fill=(235, 240, 255), font=font)
        sheet.paste(_fit_panel(image, (panel_w, panel_h)), (x, y + label_h))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return focus_box


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture AR/PBR UV flip comparison screenshots.")
    parser.add_argument("--asset", default=os.environ.get("AR_PBR_UV_COMPARE_ASSET", ""))
    parser.add_argument("--out-dir", default=str(Path(".tmp")))
    parser.add_argument("--prefix", default="ar_pbr_uv_compare")
    parser.add_argument("--texture-max-size", type=int, default=2048)
    parser.add_argument("--screenshot-delay-ms", type=int, default=1400)
    parser.add_argument("--crop", type=_parse_crop, default=DEFAULT_CROP)
    parser.add_argument("--diff-amplify", type=int, default=6)
    parser.add_argument("--focus-threshold", type=int, default=8)
    parser.add_argument("--focus-padding", type=int, default=40)
    parser.add_argument("--no-shadow-map", action="store_true")
    parser.add_argument("--skip-capture", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    gpu_tool = Path(__file__).resolve().with_name("ar_pbr_gpu_window.py")
    if not str(args.asset or "").strip():
        parser.error("--asset is required unless AR_PBR_UV_COMPARE_ASSET is set")
    asset = Path(args.asset).expanduser().resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    modes = [("OFF (old)", "off"), ("AUTO (fixed)", "auto"), ("ON (forced)", "on")]
    captures: dict[str, Path] = {}
    for label, mode in modes:
        output = out_dir / f"{args.prefix}_{mode}.png"
        if not args.skip_capture:
            _run_capture(
                gpu_tool=gpu_tool,
                asset=asset,
                output=output,
                mode=mode,
                texture_max_size=int(args.texture_max_size),
                screenshot_delay_ms=int(args.screenshot_delay_ms),
                enable_shadow_map=not bool(args.no_shadow_map),
            )
        captures[label] = output

    sheet = out_dir / f"{args.prefix}_sheet.png"
    _make_compare_sheet(captures, output=sheet, crop_box=args.crop)
    diff_sheet = out_dir / f"{args.prefix}_diff.png"
    _make_diff_sheet(captures, output=diff_sheet, amplify=int(args.diff_amplify))
    focus_sheet = out_dir / f"{args.prefix}_focus.png"
    focus_box = _make_focus_sheet(
        captures,
        output=focus_sheet,
        threshold=int(args.focus_threshold),
        padding=int(args.focus_padding),
        amplify=int(args.diff_amplify),
    )
    report = out_dir / f"{args.prefix}_report.json"
    report_data = _write_report(captures, sheet=sheet, report=report, asset=asset, crop_box=args.crop)
    report_data["focus_sheet"] = str(focus_sheet)
    report_data["focus_box"] = list(focus_box)
    report_data["visual_diff"] = {
        "sheet": str(diff_sheet),
        "amplify": max(1, int(args.diff_amplify)),
        "focus_threshold": max(0, int(args.focus_threshold)),
        "focus_padding": max(0, int(args.focus_padding)),
    }
    report.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(sheet)
    print(diff_sheet)
    print(focus_sheet)
    print(report)
    print(json.dumps(report_data["verdict"], ensure_ascii=False, sort_keys=True))
    for path in captures.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
