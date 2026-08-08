from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
os.environ.setdefault("QT_FONT_DPI", "96")

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageStat
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.drawing import PaintDialog, create_blank_paint_pixmap
from app.font_fallback import apply_ui_font
from app.painter_ui_document import active_ui_page_document
from app.painter_ui_templates import instantiate_ui_template
from app.painter_ui_umg_widget_view import PainterUMGWidgetView
from tools.qa_painter_ui_unreal_umg import (
    _activate_template_artboard,
    _prepare_builtin_template_qa_document,
)


BATCH_REPORT = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_all_samples_20260806"
    / "builtins_batch_final"
    / "batch_report.json"
)
WORKSPACE = ROOT / "tmp" / "pdfs" / "painter_umg_comparison"
TOOL_OUTPUT_DIR = WORKSPACE / "tool_window_captures"
UMG_OUTPUT_DIR = WORKSPACE / "umg_widget_views"
REPORT_PATH = WORKSPACE / "umg_widget_view_capture_report.json"
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080


def _capture_selection(document: dict, artboard_id: str) -> dict:
    rows = [
        row
        for row in document.get("objects", [])
        if str(row.get("artboard_id") or "") == str(artboard_id)
    ]
    selected = next(
        (
            row
            for preferred_kind in (
                "button",
                "image",
                "text",
                "rectangle",
                "frame",
            )
            for row in reversed(rows)
            if str(row.get("kind") or "").lower() == preferred_kind
        ),
        rows[-1] if rows else None,
    )
    if selected is None:
        document["selection"] = {"object_id": "", "object_ids": []}
        return {}
    object_id = str(selected.get("id") or "")
    document["selection"] = {
        "object_id": object_id,
        "object_ids": [object_id],
    }
    return selected


def _image_evidence(path: Path) -> dict:
    with Image.open(path) as source:
        image = source.convert("RGB")
        extrema = image.getextrema()
        stat = ImageStat.Stat(image)
        return {
            "width": image.width,
            "height": image.height,
            "extrema": [list(value) for value in extrema],
            "mean": [round(value, 3) for value in stat.mean],
            "visible_content": any(high > low for low, high in extrema),
        }


def capture(*, screen_ids: set[str] | None = None) -> dict:
    batch = json.loads(BATCH_REPORT.read_text(encoding="utf-8"))
    samples = [
        row
        for row in batch.get("samples") or []
        if not screen_ids or str(row.get("screen_id") or "") in screen_ids
    ]
    if not batch.get("ok") or not samples:
        raise RuntimeError("A passing built-in Unreal batch is required")

    TOOL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UMG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    apply_ui_font(app)

    rows: list[dict] = []
    for index, sample in enumerate(samples, start=1):
        template_id = str(sample.get("id") or "")
        artboard_id = str(sample.get("artboard_id") or "")
        screen_id = str(sample.get("screen_id") or "")
        source_document, _template_report = instantiate_ui_template(template_id)
        source_document, artboard = _activate_template_artboard(
            source_document,
            artboard_id,
        )
        document, preparation = _prepare_builtin_template_qa_document(
            source_document
        )
        selected = _capture_selection(document, artboard_id)
        source_display = active_ui_page_document(document)
        source_artboard = next(
            row
            for row in source_display.get("artboards", [])
            if str(row.get("id") or "") == artboard_id
        )
        source_display["artboards"] = [
            {**source_artboard, "x": 0.0, "y": 0.0}
        ]
        source_display["objects"] = [
            row
            for row in source_display.get("objects", [])
            if str(row.get("artboard_id") or "") == artboard_id
        ]
        source_display["active_artboard_id"] = artboard_id
        for page in source_display.get("pages", []):
            if str(page.get("id") or "") == str(
                source_artboard.get("page_id") or ""
            ):
                page["active_artboard_id"] = artboard_id

        safe_screen_id = screen_id.replace(":", "_").replace("/", "_")
        tool_target = TOOL_OUTPUT_DIR / f"{index:02d}_{safe_screen_id}.png"
        painter = PaintDialog(
            background_pixmap=create_blank_paint_pixmap(
                1440,
                900,
                "transparent",
            ),
            initial_strokes=[],
            time_ms=0,
            standalone=True,
        )
        try:
            painter.setWindowTitle(
                f"Painter UI - {sample.get('name')} - {sample.get('artboard_name')}"
            )
            painter.resize(CAPTURE_WIDTH, CAPTURE_HEIGHT)
            registry = ActionRegistry(owner=painter)
            workspace_result = registry.execute(
                "paint.ui.workspace.set",
                {"mode": "ui_design"},
            )
            if not workspace_result.ok:
                raise RuntimeError(workspace_result.message)
            painter._painter_ui_document = source_display
            painter._set_painter_ui_empty_page_mode(False)
            painter._refresh_painter_ui_overlay()
            painter.show()
            for _ in range(3):
                app.processEvents()
            # PaintDialog deliberately clamps its initial size to the current
            # monitor.  Resize once more after showEvent so the deterministic
            # offscreen evidence uses the requested review resolution.
            painter.resize(CAPTURE_WIDTH, CAPTURE_HEIGHT)
            fit_result = registry.execute(
                "paint.ui.view.fit",
                {"mode": "artboard"},
            )
            if not fit_result.ok:
                raise RuntimeError(fit_result.message)
            for _ in range(3):
                app.processEvents()
            tool_pixmap = painter.grab()
            if tool_pixmap.isNull() or not tool_pixmap.save(
                str(tool_target),
                "PNG",
            ):
                raise RuntimeError(f"Painter tool capture failed: {screen_id}")
            tool_evidence = _image_evidence(tool_target)
            if (
                tool_evidence["width"] != CAPTURE_WIDTH
                or tool_evidence["height"] != CAPTURE_HEIGHT
                or not tool_evidence["visible_content"]
            ):
                raise RuntimeError(
                    f"Painter tool capture is invalid: {screen_id}: {tool_evidence}"
                )
        finally:
            painter.close()
            painter.deleteLater()
            app.processEvents()

        view = PainterUMGWidgetView()
        try:
            view.setWindowTitle(
                f"UMG Widget View - {sample.get('name')} - {sample.get('artboard_name')}"
            )
            view.resize(CAPTURE_WIDTH, CAPTURE_HEIGHT)
            view.set_document(document, artboard_id=artboard_id, force=True)
            view.show()
            for _ in range(3):
                app.processEvents()
            # Keep the full provider-neutral projection on the target, but
            # isolate/rebase only the source display.  Secondary built-in
            # artboards have non-zero board positions while the UMG proxy
            # canvas is rooted at zero; a shared unrebased view state would
            # otherwise pan the target offscreen.
            view.source_pane.set_document(source_display)
            view.fit_views()
            for _ in range(3):
                app.processEvents()
            view.ensurePolished()
            view.repaint()
            app.processEvents()

            target = UMG_OUTPUT_DIR / f"{index:02d}_{safe_screen_id}.png"
            pixmap = view.grab()
            if pixmap.isNull() or not pixmap.save(str(target), "PNG"):
                raise RuntimeError(f"UMG Widget View capture failed: {screen_id}")
            evidence = _image_evidence(target)
            if (
                evidence["width"] != CAPTURE_WIDTH
                or evidence["height"] != CAPTURE_HEIGHT
                or not evidence["visible_content"]
            ):
                raise RuntimeError(
                    f"UMG Widget View capture is invalid: {screen_id}: {evidence}"
                )

            projection = view.report()
            rows.append(
                {
                    "screen_id": screen_id,
                    "template_id": template_id,
                    "artboard_id": artboard_id,
                    "artboard": artboard,
                    "selection_id": str(selected.get("id") or ""),
                    "selection_name": str(selected.get("name") or ""),
                    "preparation_mode": str(preparation.get("mode") or ""),
                    "tool_capture": str(tool_target),
                    "tool_evidence": tool_evidence,
                    "umg_widget_view_capture": str(target),
                    "umg_widget_view_evidence": evidence,
                    "projection_ready": bool(projection.get("ready")),
                    "projection_complete": bool(projection.get("complete")),
                    "native_count": int(
                        (projection.get("counts") or {}).get("Native") or 0
                    ),
                    "material_count": int(
                        (projection.get("counts") or {}).get("Material") or 0
                    ),
                    "baked_count": int(
                        (projection.get("counts") or {}).get("Baked") or 0
                    ),
                    "blocked_count": int(
                        (projection.get("counts") or {}).get("Blocked") or 0
                    ),
                }
            )
        finally:
            view.close()
            view.deleteLater()
            app.processEvents()

    report = {
        "schema": "tigerstudio.painter_umg_widget_view_pdf_capture.v1",
        "ok": (
            len(rows) == len(samples)
            and all(row["tool_evidence"]["visible_content"] for row in rows)
            and all(
                row["umg_widget_view_evidence"]["visible_content"]
                for row in rows
            )
            and all(row["projection_ready"] for row in rows)
            and all(row["projection_complete"] for row in rows)
            and all(row["blocked_count"] == 0 for row in rows)
        ),
        "source_batch_report": str(BATCH_REPORT),
        "capture_size": [CAPTURE_WIDTH, CAPTURE_HEIGHT],
        "requested_count": len(samples),
        "captured_count": len(rows),
        "captures": rows,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not report["ok"]:
        raise RuntimeError(f"UMG Widget View capture QA failed: {REPORT_PATH}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screen-id", action="append", default=[])
    args = parser.parse_args()
    report = capture(screen_ids={str(value) for value in args.screen_id})
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "captured_count": report["captured_count"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
