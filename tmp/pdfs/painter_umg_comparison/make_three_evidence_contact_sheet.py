from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat
from pypdf import PdfReader


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]

DEFAULT_CAPTURE_REPORT = SCRIPT_DIR / "umg_widget_view_capture_report.json"
DEFAULT_BATCH_REPORT = (
    REPO_ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_all_samples_20260806"
    / "builtins_batch_final"
    / "batch_report.json"
)
DEFAULT_PDF = REPO_ROOT / "output" / "pdf" / "painter_umg_sample_comparison.pdf"
DEFAULT_OUTPUT = SCRIPT_DIR / "three_evidence_contact_sheet.png"
DEFAULT_QA_REPORT = SCRIPT_DIR / "three_evidence_contact_sheet_report.json"

SHEET_BACKGROUND = "#08111F"
ROW_BACKGROUND = "#0D1828"
ROW_BACKGROUND_ALT = "#101D2F"
CARD_BACKGROUND = "#121F31"
IMAGE_BACKGROUND = "#050A12"
TEXT_PRIMARY = "#F2F7FF"
TEXT_SECONDARY = "#AFC0D6"
ACCENT_TOOL = "#65A7FF"
ACCENT_SIMULATOR = "#F1B84B"
ACCENT_UNREAL = "#55D6A4"
DIVIDER = "#29405C"

MARGIN = 24
COLUMN_GAP = 16
ROW_GAP = 14
CARD_WIDTH = 620
CARD_PADDING = 10
CARD_LABEL_HEIGHT = 34
IMAGE_HEIGHT = 340
CARD_FOOTER_HEIGHT = 28
ROW_TITLE_HEIGHT = 42
ROW_HEIGHT = ROW_TITLE_HEIGHT + CARD_LABEL_HEIGHT + IMAGE_HEIGHT + CARD_FOOTER_HEIGHT + 20
HEADER_HEIGHT = 92
COLUMN_COUNT = 3


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate all Painter/UMG/Unreal evidence and create a 21-row, "
            "three-column visual QA contact sheet."
        )
    )
    parser.add_argument("--capture-report", type=Path, default=DEFAULT_CAPTURE_REPORT)
    parser.add_argument("--batch-report", type=Path, default=DEFAULT_BATCH_REPORT)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_QA_REPORT)
    parser.add_argument("--expected-count", type=int, default=21)
    return parser.parse_args()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_json(path: Path) -> dict[str, Any]:
    _require(path.is_file(), f"Required report does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    _require(isinstance(payload, dict), f"Expected a JSON object: {path}")
    return payload


def _font(filename: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts") / filename,
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


FONT_TITLE = _font("segoeuib.ttf", 24)
FONT_SUBTITLE = _font("segoeui.ttf", 15)
FONT_ROW = _font("segoeuib.ttf", 17)
FONT_CARD = _font("segoeuib.ttf", 15)
FONT_META = _font("segoeui.ttf", 13)


def _image_evidence(path_value: Any, *, label: str) -> dict[str, Any]:
    _require(isinstance(path_value, str) and path_value.strip(), f"{label} has no image path")
    path = Path(path_value)
    _require(path.is_file(), f"{label} image does not exist: {path}")
    with Image.open(path) as source:
        source.load()
        rgb = source.convert("RGB")
        width, height = rgb.size
        _require(width > 0 and height > 0, f"{label} image has invalid dimensions: {path}")
        gray = ImageOps.grayscale(rgb)
        extrema = gray.getextrema()
        stddev = float(ImageStat.Stat(gray).stddev[0])
    dynamic_range = int(extrema[1] - extrema[0])
    visible_content = dynamic_range >= 8 and stddev >= 3.0
    _require(
        visible_content,
        f"{label} image appears blank or nearly uniform "
        f"(range={dynamic_range}, stddev={stddev:.3f}): {path}",
    )
    return {
        "path": str(path.resolve()),
        "width": width,
        "height": height,
        "luminance_extrema": list(extrema),
        "luminance_dynamic_range": dynamic_range,
        "luminance_stddev": round(stddev, 3),
        "visible_content": True,
    }


def _unique_by_screen_id(items: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items, start=1):
        _require(isinstance(item, dict), f"{label} item {index} is not an object")
        screen_id = item.get("screen_id")
        _require(isinstance(screen_id, str) and screen_id, f"{label} item {index} has no screen_id")
        _require(screen_id not in result, f"Duplicate {label} screen_id: {screen_id}")
        result[screen_id] = item
    return result


def _validate_sources(
    capture_report_path: Path,
    batch_report_path: Path,
    pdf_path: Path,
    expected_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    capture_report = _load_json(capture_report_path)
    batch_report = _load_json(batch_report_path)

    _require(capture_report.get("ok") is True, "Painter capture report is not successful")
    _require(batch_report.get("ok") is True, "Unreal batch report is not successful")

    captures = capture_report.get("captures")
    samples = batch_report.get("samples")
    _require(isinstance(captures, list), "Painter capture report has no captures list")
    _require(isinstance(samples, list), "Unreal batch report has no samples list")
    _require(
        capture_report.get("requested_count") == expected_count,
        f"Expected requested_count={expected_count}, got {capture_report.get('requested_count')}",
    )
    _require(
        capture_report.get("captured_count") == expected_count,
        f"Expected captured_count={expected_count}, got {capture_report.get('captured_count')}",
    )
    _require(len(captures) == expected_count, f"Expected {expected_count} Painter captures, found {len(captures)}")
    _require(len(samples) == expected_count, f"Expected {expected_count} Unreal samples, found {len(samples)}")

    summary = batch_report.get("summary")
    _require(isinstance(summary, dict), "Unreal batch report has no summary")
    for key in ("total", "screen_count", "passed", "editor_screenshots"):
        _require(
            summary.get(key) == expected_count,
            f"Expected Unreal summary.{key}={expected_count}, got {summary.get(key)}",
        )

    capture_size = capture_report.get("capture_size")
    _require(
        isinstance(capture_size, list)
        and len(capture_size) == 2
        and all(isinstance(value, int) and value > 0 for value in capture_size),
        f"Invalid Painter capture_size: {capture_size}",
    )
    expected_capture_size = tuple(capture_size)
    _require(
        expected_capture_size[0] >= 1280 and expected_capture_size[1] >= 720,
        f"Painter evidence is too small for a full-window QA capture: {expected_capture_size}",
    )

    capture_by_id = _unique_by_screen_id(captures, label="Painter capture")
    sample_by_id = _unique_by_screen_id(samples, label="Unreal sample")
    _require(
        set(capture_by_id) == set(sample_by_id),
        "Painter and Unreal screen_id sets differ: "
        f"Painter-only={sorted(set(capture_by_id) - set(sample_by_id))}, "
        f"Unreal-only={sorted(set(sample_by_id) - set(capture_by_id))}",
    )

    _require(pdf_path.is_file(), f"Comparison PDF does not exist: {pdf_path}")
    pdf_reader = PdfReader(str(pdf_path))
    pdf_page_count = len(pdf_reader.pages)
    _require(
        pdf_page_count == expected_count,
        f"Expected {expected_count} PDF pages, found {pdf_page_count}: {pdf_path}",
    )
    _require(
        pdf_path.stat().st_mtime_ns >= capture_report_path.stat().st_mtime_ns,
        "Comparison PDF is older than the completed Painter capture report; rebuild the PDF first",
    )

    records: list[dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        screen_id = str(sample["screen_id"])
        capture = capture_by_id[screen_id]

        _require(sample.get("ok") is True, f"Unreal sample is not successful: {screen_id}")
        _require(capture.get("projection_ready") is True, f"Projection is not ready: {screen_id}")
        _require(capture.get("projection_complete") is True, f"Projection is incomplete: {screen_id}")
        _require(capture.get("blocked_count") == 0, f"Projection has blocked items: {screen_id}")

        for evidence_key in ("tool_evidence", "umg_widget_view_evidence"):
            evidence = capture.get(evidence_key)
            _require(isinstance(evidence, dict), f"Missing {evidence_key}: {screen_id}")
            _require(evidence.get("visible_content") is True, f"{evidence_key} is not visible: {screen_id}")

        tool = _image_evidence(capture.get("tool_capture"), label=f"Painter tool [{screen_id}]")
        simulator = _image_evidence(
            capture.get("umg_widget_view_capture"),
            label=f"Painter UMG Widget View [{screen_id}]",
        )
        _require(
            (tool["width"], tool["height"]) == expected_capture_size,
            f"Painter tool capture size mismatch for {screen_id}: "
            f"{tool['width']}x{tool['height']} != {expected_capture_size[0]}x{expected_capture_size[1]}",
        )
        _require(
            (simulator["width"], simulator["height"]) == expected_capture_size,
            f"UMG Widget View capture size mismatch for {screen_id}: "
            f"{simulator['width']}x{simulator['height']} != "
            f"{expected_capture_size[0]}x{expected_capture_size[1]}",
        )

        editor = sample.get("editor_screenshot")
        _require(isinstance(editor, dict), f"Missing Unreal editor screenshot metadata: {screen_id}")
        _require(editor.get("requested") is True, f"Unreal WGC capture was not requested: {screen_id}")
        _require(editor.get("ok") is True, f"Unreal WGC capture failed: {screen_id}")
        _require(editor.get("exists") is True, f"Unreal WGC capture is marked missing: {screen_id}")
        _require(editor.get("status") == "captured", f"Unreal capture status is not captured: {screen_id}")
        _require(editor.get("backend") == "wgc_window", f"Unreal capture is not WGC: {screen_id}")
        unreal = _image_evidence(editor.get("path"), label=f"Unreal WGC [{screen_id}]")

        artboard = sample.get("artboard") if isinstance(sample.get("artboard"), dict) else {}
        records.append(
            {
                "index": index,
                "screen_id": screen_id,
                "sample_name": str(sample.get("name") or sample.get("id") or screen_id),
                "artboard_name": str(sample.get("artboard_name") or artboard.get("name") or ""),
                "tool": {
                    **tool,
                    "capture_kind": "actual_painter_tool_qwidget_grab",
                },
                "simulator": {
                    **simulator,
                    "capture_kind": "actual_painter_umg_widget_view_qwidget_grab",
                    "projection_ready": True,
                    "projection_complete": True,
                    "blocked_count": 0,
                },
                "unreal": {
                    **unreal,
                    "capture_kind": "actual_unreal_widget_blueprint_designer_wgc",
                    "backend": "wgc_window",
                    "status": "captured",
                },
            }
        )

    validation = {
        "capture_size": list(expected_capture_size),
        "pdf_page_count": pdf_page_count,
        "pdf_is_newer_than_capture_report": True,
        "matched_screen_ids": expected_count,
        "unreal_wgc_captures": expected_count,
        "projection_complete_count": expected_count,
        "blocked_count": 0,
    }
    return records, validation


def _fit_for_card(path: Path, available_width: int, available_height: int) -> Image.Image:
    with Image.open(path) as source:
        rgb = source.convert("RGB")
        fitted = ImageOps.contain(
            rgb,
            (available_width, available_height),
            method=Image.Resampling.LANCZOS,
        )
        return fitted.copy()


def _draw_card(
    sheet: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    title: str,
    evidence: dict[str, Any],
    accent: str,
    footer: str,
) -> None:
    card_height = CARD_LABEL_HEIGHT + IMAGE_HEIGHT + CARD_FOOTER_HEIGHT
    draw.rounded_rectangle(
        (x, y, x + CARD_WIDTH, y + card_height),
        radius=10,
        fill=CARD_BACKGROUND,
        outline=accent,
        width=2,
    )
    draw.text((x + CARD_PADDING, y + 8), title, fill=TEXT_PRIMARY, font=FONT_CARD)

    viewport_x = x + CARD_PADDING
    viewport_y = y + CARD_LABEL_HEIGHT
    viewport_width = CARD_WIDTH - CARD_PADDING * 2
    draw.rectangle(
        (viewport_x, viewport_y, viewport_x + viewport_width, viewport_y + IMAGE_HEIGHT),
        fill=IMAGE_BACKGROUND,
    )
    fitted = _fit_for_card(Path(evidence["path"]), viewport_width, IMAGE_HEIGHT)
    image_x = viewport_x + (viewport_width - fitted.width) // 2
    image_y = viewport_y + (IMAGE_HEIGHT - fitted.height) // 2
    sheet.paste(fitted, (image_x, image_y))

    meta_y = viewport_y + IMAGE_HEIGHT + 7
    dimensions = f"{evidence['width']} x {evidence['height']}"
    draw.text((x + CARD_PADDING, meta_y), dimensions, fill=TEXT_SECONDARY, font=FONT_META)
    footer_bbox = draw.textbbox((0, 0), footer, font=FONT_META)
    footer_width = footer_bbox[2] - footer_bbox[0]
    draw.text(
        (x + CARD_WIDTH - CARD_PADDING - footer_width, meta_y),
        footer,
        fill=accent,
        font=FONT_META,
    )


def _build_contact_sheet(records: list[dict[str, Any]], output_path: Path) -> tuple[int, int]:
    sheet_width = MARGIN * 2 + CARD_WIDTH * COLUMN_COUNT + COLUMN_GAP * (COLUMN_COUNT - 1)
    sheet_height = (
        MARGIN * 2
        + HEADER_HEIGHT
        + len(records) * ROW_HEIGHT
        + max(0, len(records) - 1) * ROW_GAP
    )
    sheet = Image.new("RGB", (sheet_width, sheet_height), SHEET_BACKGROUND)
    draw = ImageDraw.Draw(sheet)

    draw.text((MARGIN, MARGIN), "Painter -> UMG Widget View -> Unreal", fill=TEXT_PRIMARY, font=FONT_TITLE)
    draw.text(
        (MARGIN, MARGIN + 38),
        f"Three real evidence captures per sample | {len(records)} samples | no crop, full frame",
        fill=TEXT_SECONDARY,
        font=FONT_SUBTITLE,
    )
    draw.line(
        (MARGIN, MARGIN + HEADER_HEIGHT - 12, sheet_width - MARGIN, MARGIN + HEADER_HEIGHT - 12),
        fill=DIVIDER,
        width=2,
    )

    y = MARGIN + HEADER_HEIGHT
    for record in records:
        row_background = ROW_BACKGROUND if record["index"] % 2 else ROW_BACKGROUND_ALT
        draw.rounded_rectangle(
            (MARGIN, y, sheet_width - MARGIN, y + ROW_HEIGHT),
            radius=12,
            fill=row_background,
            outline=DIVIDER,
            width=1,
        )
        row_title = f"{record['index']:02d}. {record['sample_name']}"
        if record["artboard_name"]:
            row_title += f" / {record['artboard_name']}"
        draw.text((MARGIN + 14, y + 10), row_title, fill=TEXT_PRIMARY, font=FONT_ROW)
        screen_bbox = draw.textbbox((0, 0), record["screen_id"], font=FONT_META)
        screen_width = screen_bbox[2] - screen_bbox[0]
        draw.text(
            (sheet_width - MARGIN - 14 - screen_width, y + 13),
            record["screen_id"],
            fill=TEXT_SECONDARY,
            font=FONT_META,
        )

        card_y = y + ROW_TITLE_HEIGHT
        columns = [
            (
                "Tiger Studio Painter - full tool",
                record["tool"],
                ACCENT_TOOL,
                "actual QWidget",
            ),
            (
                "Painter UMG Widget View - source + simulation",
                record["simulator"],
                ACCENT_SIMULATOR,
                "complete / blocked 0",
            ),
            (
                "Unreal Widget Blueprint Designer",
                record["unreal"],
                ACCENT_UNREAL,
                "actual WGC window",
            ),
        ]
        for column_index, (title, evidence, accent, footer) in enumerate(columns):
            card_x = MARGIN + column_index * (CARD_WIDTH + COLUMN_GAP)
            _draw_card(
                sheet,
                draw,
                x=card_x,
                y=card_y,
                title=title,
                evidence=evidence,
                accent=accent,
                footer=footer,
            )
        y += ROW_HEIGHT + ROW_GAP

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, "PNG", compress_level=6)
    return sheet_width, sheet_height


def main() -> int:
    args = _parse_args()
    capture_report_path = args.capture_report.resolve()
    batch_report_path = args.batch_report.resolve()
    pdf_path = args.pdf.resolve()
    output_path = args.output.resolve()
    qa_report_path = args.report.resolve()

    _require(args.expected_count > 0, "--expected-count must be positive")
    records, validation = _validate_sources(
        capture_report_path,
        batch_report_path,
        pdf_path,
        args.expected_count,
    )
    width, height = _build_contact_sheet(records, output_path)

    qa_report = {
        "schema": "tigerstudio.painter_umg.three_evidence_contact_sheet_qa.v1",
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_count": args.expected_count,
        "sample_count": len(records),
        "sources": {
            "painter_capture_report": str(capture_report_path),
            "unreal_batch_report": str(batch_report_path),
            "comparison_pdf": str(pdf_path),
        },
        "validation": validation,
        "contact_sheet": {
            "path": str(output_path),
            "width": width,
            "height": height,
            "rows": len(records),
            "columns": COLUMN_COUNT,
            "evidence_per_sample": 3,
            "placeholder_count": 0,
        },
        "samples": records,
    }
    qa_report_path.parent.mkdir(parents=True, exist_ok=True)
    with qa_report_path.open("w", encoding="utf-8") as handle:
        json.dump(qa_report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(output_path)
    print(qa_report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
