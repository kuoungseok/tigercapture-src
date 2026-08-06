from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image
import pdfplumber
from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

BATCH_REPORT = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_all_samples_20260806"
    / "builtins_batch_final"
    / "batch_report.json"
)
WORKSPACE = ROOT / "tmp" / "pdfs" / "painter_umg_comparison"
WIDGET_VIEW_CAPTURE_REPORT = WORKSPACE / "umg_widget_view_capture_report.json"
OUTPUT_PDF = ROOT / "output" / "pdf" / "painter_umg_sample_comparison.pdf"
QA_REPORT = WORKSPACE / "qa_report.json"

PAGE_WIDTH, PAGE_HEIGHT = landscape(A3)
MARGIN = 28.0
GUTTER = 18.0
HEADER_HEIGHT = 78.0
FOOTER_HEIGHT = 34.0
PANEL_BOTTOM = MARGIN + FOOTER_HEIGHT
PANEL_TOP = PAGE_HEIGHT - MARGIN - HEADER_HEIGHT
PANEL_HEIGHT = PANEL_TOP - PANEL_BOTTOM
AVAILABLE_PANEL_WIDTH = PAGE_WIDTH - MARGIN * 2 - GUTTER
LEFT_COLUMN_WIDTH = AVAILABLE_PANEL_WIDTH * 0.58
RIGHT_COLUMN_WIDTH = AVAILABLE_PANEL_WIDTH - LEFT_COLUMN_WIDTH
STACK_GUTTER = 12.0
LEFT_PANEL_HEIGHT = (PANEL_HEIGHT - STACK_GUTTER) / 2


def _register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\malgun.ttf")
    bold = Path(r"C:\Windows\Fonts\malgunbd.ttf")
    if regular.is_file() and bold.is_file():
        pdfmetrics.registerFont(TTFont("TigerSans", str(regular)))
        pdfmetrics.registerFont(TTFont("TigerSansBold", str(bold)))
        return "TigerSans", "TigerSansBold"
    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = _register_fonts()


def _draw_fitted_image(
    pdf: canvas.Canvas,
    image_path: Path,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict[str, float | int]:
    with Image.open(image_path) as source:
        image_width, image_height = source.size
    scale = min(width / image_width, height / image_height)
    drawn_width = image_width * scale
    drawn_height = image_height * scale
    drawn_x = x + (width - drawn_width) / 2
    drawn_y = y + (height - drawn_height) / 2
    pdf.drawImage(
        str(image_path),
        drawn_x,
        drawn_y,
        width=drawn_width,
        height=drawn_height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )
    return {
        "source_width": image_width,
        "source_height": image_height,
        "drawn_width": round(drawn_width, 3),
        "drawn_height": round(drawn_height, 3),
    }


def _draw_panel(
    pdf: canvas.Canvas,
    *,
    title: str,
    subtitle: str,
    image_path: Path,
    x: float,
    y: float,
    width: float,
    height: float,
) -> dict[str, float | int]:
    pdf.setFillColor(HexColor("#121D2E"))
    pdf.roundRect(x, y, width, height, 12, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#EAF2FF"))
    pdf.setFont(FONT_BOLD, 13)
    pdf.drawString(x + 16, y + height - 24, title)
    pdf.setFillColor(HexColor("#91A6C5"))
    pdf.setFont(FONT_REGULAR, 8)
    pdf.drawString(x + 16, y + height - 39, subtitle)

    image_x = x + 14
    image_y = y + 14
    image_width = width - 28
    image_height = height - 62
    pdf.setFillColor(HexColor("#08111F"))
    pdf.roundRect(
        image_x,
        image_y,
        image_width,
        image_height,
        8,
        fill=1,
        stroke=0,
    )
    return _draw_fitted_image(
        pdf,
        image_path,
        x=image_x + 8,
        y=image_y + 8,
        width=image_width - 16,
        height=image_height - 16,
    )


def _report_path(value: object, *, label: str) -> Path:
    path = Path(str(value or ""))
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        raise RuntimeError(f"{label} is missing: {path}")
    return path


def _validate_qwidget_capture(
    capture: dict,
    *,
    path_key: str,
    evidence_key: str,
    label: str,
) -> tuple[Path, dict]:
    evidence = capture.get(evidence_key) or {}
    if not isinstance(evidence, dict) or not evidence.get("visible_content"):
        raise RuntimeError(f"{label} has no visible capture evidence")
    path = _report_path(capture.get(path_key), label=label)
    with Image.open(path) as image:
        actual_size = image.size
    evidence_size = (
        int(evidence.get("width") or 0),
        int(evidence.get("height") or 0),
    )
    if evidence_size[0] <= 0 or evidence_size[1] <= 0:
        raise RuntimeError(f"{label} has invalid evidence dimensions: {evidence_size}")
    if actual_size != evidence_size:
        raise RuntimeError(
            f"{label} evidence dimensions do not match the image: "
            f"{evidence_size} != {actual_size}"
        )
    return path, evidence


def main() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    batch = json.loads(BATCH_REPORT.read_text(encoding="utf-8"))
    samples = list(batch.get("samples") or [])
    if not batch.get("ok") or len(samples) != 21:
        raise RuntimeError("The source Unreal batch must be a clean 21-artboard run")
    if any(not sample.get("ok") for sample in samples):
        raise RuntimeError("The source Unreal batch contains a failed sample")

    widget_capture_report = json.loads(
        WIDGET_VIEW_CAPTURE_REPORT.read_text(encoding="utf-8")
    )
    captures = list(widget_capture_report.get("captures") or [])
    if not widget_capture_report.get("ok") or len(captures) != 21:
        raise RuntimeError("The Painter/UMG Widget View capture report must contain 21 clean captures")
    if int(widget_capture_report.get("requested_count") or 0) != 21:
        raise RuntimeError("The Painter/UMG Widget View report did not request all 21 samples")
    if int(widget_capture_report.get("captured_count") or 0) != 21:
        raise RuntimeError("The Painter/UMG Widget View report did not capture all 21 samples")
    captures_by_screen_id: dict[str, dict] = {}
    for capture in captures:
        screen_id = str(capture.get("screen_id") or "")
        if not screen_id:
            raise RuntimeError("A Painter/UMG Widget View capture has no screen_id")
        if screen_id in captures_by_screen_id:
            raise RuntimeError(f"Duplicate Painter/UMG Widget View capture: {screen_id}")
        captures_by_screen_id[screen_id] = capture
    expected_screen_ids = {str(sample.get("screen_id") or "") for sample in samples}
    if set(captures_by_screen_id) != expected_screen_ids:
        missing = sorted(expected_screen_ids - set(captures_by_screen_id))
        extra = sorted(set(captures_by_screen_id) - expected_screen_ids)
        raise RuntimeError(
            f"Painter/UMG Widget View capture set does not match the Unreal batch; "
            f"missing={missing}, extra={extra}"
        )

    pdf = canvas.Canvas(str(OUTPUT_PDF), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    pdf.setTitle("Tiger Studio Painter - UMG Widget View - Unreal Comparison")
    pdf.setAuthor("Tiger Studio QA")
    pdf.setSubject(
        "Painter tool, UMG Widget View simulation, and actual Unreal Widget Blueprint evidence"
    )
    pdf.setCreator("Tiger Studio UMG QA / ReportLab")

    page_records: list[dict] = []
    for index, sample in enumerate(samples, start=1):
        screen_id = str(sample.get("screen_id") or "")
        capture = captures_by_screen_id[screen_id]
        tool_path, tool_evidence = _validate_qwidget_capture(
            capture,
            path_key="tool_capture",
            evidence_key="tool_evidence",
            label=f"Painter tool capture for {screen_id}",
        )
        umg_widget_view_path, umg_widget_view_evidence = _validate_qwidget_capture(
            capture,
            path_key="umg_widget_view_capture",
            evidence_key="umg_widget_view_evidence",
            label=f"Painter UMG Widget View capture for {screen_id}",
        )
        if not capture.get("projection_ready") or not capture.get("projection_complete"):
            raise RuntimeError(f"Painter UMG projection is incomplete: {screen_id}")
        if int(capture.get("blocked_count") or 0) != 0:
            raise RuntimeError(f"Painter UMG projection contains blocked output: {screen_id}")

        editor_capture = sample.get("editor_screenshot") or {}
        if not (
            editor_capture.get("requested")
            and editor_capture.get("ok")
            and editor_capture.get("exists")
            and str(editor_capture.get("status") or "") == "captured"
            and str(editor_capture.get("backend") or "") == "wgc_window"
        ):
            raise RuntimeError(
                f"Unreal editor capture did not pass: {sample.get('screen_id')}"
            )
        unreal_path = _report_path(
            editor_capture.get("path"),
            label=f"Unreal Widget Blueprint editor screenshot for {screen_id}",
        )
        renderer_evidence = sample.get("renderer") or {}
        if not renderer_evidence.get("ok"):
            raise RuntimeError(
                f"The supporting FWidgetRenderer evidence is missing: {sample.get('screen_id')}"
            )
        renderer_path = _report_path(
            renderer_evidence.get("path"),
            label=f"Supporting FWidgetRenderer image for {screen_id}",
        )

        artboard = sample.get("artboard") or {}
        sample_name = str(sample.get("name") or sample.get("id") or "Sample")
        artboard_name = str(sample.get("artboard_name") or sample.get("artboard_id") or "")
        category = str(sample.get("category") or "")
        source_size = f"{int(float(artboard.get('width') or 0))} x {int(float(artboard.get('height') or 0))}"

        pdf.setFillColor(HexColor("#08111F"))
        pdf.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#F5F8FF"))
        pdf.setFont(FONT_BOLD, 22)
        pdf.drawString(MARGIN, PAGE_HEIGHT - MARGIN - 22, sample_name)
        pdf.setFillColor(HexColor("#AAB9D0"))
        pdf.setFont(FONT_REGULAR, 11)
        pdf.drawString(
            MARGIN,
            PAGE_HEIGHT - MARGIN - 43,
            f"{artboard_name}  |  {category}  |  source {source_size}",
        )
        pdf.setFillColor(HexColor("#37D996"))
        pdf.setFont(FONT_BOLD, 10)
        pdf.drawRightString(
            PAGE_WIDTH - MARGIN,
            PAGE_HEIGHT - MARGIN - 21,
            "TOOL + SIMULATION + ACTUAL UE",
        )
        pdf.setFillColor(HexColor("#91A6C5"))
        pdf.setFont(FONT_REGULAR, 8.5)
        pdf.drawRightString(
            PAGE_WIDTH - MARGIN,
            PAGE_HEIGHT - MARGIN - 42,
            "Plugin 1.8.2 | compile - save - reopen | runtime render verified",
        )

        top_left_y = PANEL_BOTTOM + LEFT_PANEL_HEIGHT + STACK_GUTTER
        tool_metrics = _draw_panel(
            pdf,
            title="Tiger Studio Painter",
            subtitle="Actual full PaintDialog QWidget capture",
            image_path=tool_path,
            x=MARGIN,
            y=top_left_y,
            width=LEFT_COLUMN_WIDTH,
            height=LEFT_PANEL_HEIGHT,
        )
        umg_widget_view_metrics = _draw_panel(
            pdf,
            title="Tiger Studio UMG Widget View",
            subtitle="Actual source + UMG simulation QWidget capture",
            image_path=umg_widget_view_path,
            x=MARGIN,
            y=PANEL_BOTTOM,
            width=LEFT_COLUMN_WIDTH,
            height=LEFT_PANEL_HEIGHT,
        )
        unreal_metrics = _draw_panel(
            pdf,
            title="Unreal Widget Blueprint Designer",
            subtitle="Actual Unreal Editor WGC window capture",
            image_path=unreal_path,
            x=MARGIN + LEFT_COLUMN_WIDTH + GUTTER,
            y=PANEL_BOTTOM,
            width=RIGHT_COLUMN_WIDTH,
            height=PANEL_HEIGHT,
        )

        pdf.setFillColor(HexColor("#7185A4"))
        pdf.setFont(FONT_REGULAR, 8)
        pdf.drawString(
            MARGIN,
            18,
            f"{screen_id}  |  tool {tool_metrics['source_width']}x{tool_metrics['source_height']} / "
            f"UMG view {umg_widget_view_metrics['source_width']}x{umg_widget_view_metrics['source_height']} / "
            f"UE {unreal_metrics['source_width']}x{unreal_metrics['source_height']}",
        )
        pdf.drawRightString(
            PAGE_WIDTH - MARGIN,
            18,
            f"{index} / {len(samples)}",
        )
        pdf.showPage()
        page_records.append(
            {
                "index": index,
                "screen_id": sample.get("screen_id"),
                "sample_name": sample_name,
                "artboard_name": artboard_name,
                "tool_image": str(tool_path),
                "tool_capture_evidence": tool_evidence,
                "umg_widget_view_image": str(umg_widget_view_path),
                "umg_widget_view_capture_evidence": umg_widget_view_evidence,
                "umg_projection_evidence": {
                    "ready": bool(capture.get("projection_ready")),
                    "complete": bool(capture.get("projection_complete")),
                    "native_count": int(capture.get("native_count") or 0),
                    "material_count": int(capture.get("material_count") or 0),
                    "baked_count": int(capture.get("baked_count") or 0),
                    "blocked_count": int(capture.get("blocked_count") or 0),
                },
                "unreal_editor_image": str(unreal_path),
                "unreal_editor_capture": editor_capture,
                "fwidget_renderer_image": str(renderer_path),
                "fwidget_renderer_evidence": renderer_evidence,
                "tool_image_metrics": tool_metrics,
                "umg_widget_view_image_metrics": umg_widget_view_metrics,
                "unreal_editor_image_metrics": unreal_metrics,
            }
        )

    pdf.save()

    reader = PdfReader(str(OUTPUT_PDF))
    if len(reader.pages) != len(samples):
        raise RuntimeError("PDF page count does not match sample count")
    extracted_pages: list[str] = []
    with pdfplumber.open(str(OUTPUT_PDF)) as inspected:
        if len(inspected.pages) != len(samples):
            raise RuntimeError("pdfplumber page count does not match sample count")
        for sample, page in zip(samples, inspected.pages):
            text = page.extract_text() or ""
            expected = str(sample.get("artboard_name") or "")
            if expected and expected not in text:
                raise RuntimeError(f"PDF page text is missing artboard title: {expected}")
            extracted_pages.append(text)

    qa = {
        "schema": "tigerstudio.painter_umg_comparison_pdf.v3",
        "ok": True,
        "pdf": str(OUTPUT_PDF),
        "page_count": len(reader.pages),
        "source_batch_report": str(BATCH_REPORT),
        "source_batch_ok": bool(batch.get("ok")),
        "source_batch_summary": batch.get("summary"),
        "source_widget_view_capture_report": str(WIDGET_VIEW_CAPTURE_REPORT),
        "source_widget_view_capture_ok": bool(widget_capture_report.get("ok")),
        "source_widget_view_capture_summary": {
            "requested_count": int(widget_capture_report.get("requested_count") or 0),
            "captured_count": int(widget_capture_report.get("captured_count") or 0),
            "capture_size": widget_capture_report.get("capture_size"),
        },
        "pages": page_records,
        "text_page_count": len(extracted_pages),
        "pdf_size_bytes": OUTPUT_PDF.stat().st_size,
    }
    QA_REPORT.write_text(
        json.dumps(qa, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "pdf": str(OUTPUT_PDF), "qa": str(QA_REPORT)}))


if __name__ == "__main__":
    main()
