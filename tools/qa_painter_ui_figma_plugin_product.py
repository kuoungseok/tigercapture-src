from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _write_package(root: Path, plugin_id: str, source: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "code.js").write_text(source, encoding="utf-8")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "name": plugin_id,
                "id": plugin_id,
                "api": "1.0.0",
                "editorType": ["figma"],
                "main": "code.js",
                "documentAccess": "dynamic-page",
                "networkAccess": {"allowedDomains": ["none"]},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return root / "manifest.json"


def run_product_qa(output: Path) -> dict:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.drawing import PaintDialog
    from app.painter_ui_figma_plugin_manager_dialog import (
        PainterFigmaPluginManagerDialog,
    )
    from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry

    app = QApplication.instance() or QApplication([])
    bundled_families: list[str] = []
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for font_name in ("malgun.ttf", "malgunsl.ttf"):
        font_path = windows_fonts / font_name
        if font_path.exists():
            font_id = QFontDatabase.addApplicationFont(str(font_path))
            if font_id >= 0:
                bundled_families.extend(QFontDatabase.applicationFontFamilies(font_id))
    preferred_font = next(
        (
            family
            for family in (
                *bundled_families,
                "Malgun Gothic",
                "맑은 고딕",
                "Noto Sans CJK KR",
                "Arial",
            )
            if family in QFontDatabase.families()
        ),
        app.font().family(),
    )
    app.setFont(QFont(preferred_font, 10))
    output.mkdir(parents=True, exist_ok=True)
    for name in ("success_registry", "failure_registry", "packages"):
        generated = (output / name).resolve()
        generated.relative_to(output.resolve())
        if generated.exists():
            shutil.rmtree(generated)

    canvas = QPixmap(960, 600)
    canvas.fill(QColor("#F5F5F5"))
    owner = PaintDialog(canvas, [], 0, standalone=True)
    owner.setWindowFlag(Qt.WindowType.FramelessWindowHint, False)
    owner.resize(1180, 760)
    owner._set_canvas_workspace_mode("ui_design")
    owner.show()
    app.processEvents()
    warnings: list[dict] = []
    original_warning = QMessageBox.warning
    QMessageBox.warning = staticmethod(
        lambda _parent, title, text, *args, **kwargs: warnings.append(
            {"title": str(title), "text": str(text)}
        )
        or QMessageBox.StandardButton.Ok
    )
    try:
        success_root = output / "success_registry"
        success_registry = PainterFigmaPluginRegistry(
            [success_root], install_root=success_root
        )
        success_registry.install(
            _write_package(
                output / "packages" / "success",
                "qa.product.success",
                "const n=figma.createRectangle();"
                "n.name='Plugin card';n.x=24;n.y=32;n.resize(180,96);"
                "n.fills=[{type:'SOLID',color:{r:0.15,g:0.55,b:0.95}}];"
                "figma.currentPage.selection=[n];figma.notify('Card created');",
            )
        )
        success = PainterFigmaPluginManagerDialog(owner, registry=success_registry)
        success.show()
        app.processEvents()
        success_ok = success._run_current()
        app.processEvents()
        success_capture = output / "plugin_success.png"
        success.grab().save(str(success_capture))
        created_count = len(owner._painter_ui_document["objects"])
        undo_label = owner._undo_labels[-1] if owner._undo_labels else ""
        owner._fit_painter_ui_view("selection")
        app.processEvents()
        after_run_capture = output / "painter_after_plugin.png"
        owner.grab().save(str(after_run_capture))
        owner._undo()
        owner._fit_painter_ui_view("artboard")
        app.processEvents()
        undo_ok = len(owner._redo_stack) == 1
        undo_object_count = len(owner._painter_ui_document["objects"])
        after_undo_capture = output / "painter_after_undo.png"
        owner.grab().save(str(after_undo_capture))
        success.close()

        failure_root = output / "failure_registry"
        failure_registry = PainterFigmaPluginRegistry(
            [failure_root], install_root=failure_root
        )
        failure_registry.install(
            _write_package(
                output / "packages" / "failure",
                "qa.product.failure",
                "throw new Error('intentional product QA failure');",
            )
        )
        before_failure = json.dumps(owner._painter_ui_document, sort_keys=True)
        failure = PainterFigmaPluginManagerDialog(owner, registry=failure_registry)
        failure.show()
        app.processEvents()
        failure_ok = failure._run_current()
        app.processEvents()
        failure_capture = output / "plugin_failure.png"
        failure.grab().save(str(failure_capture))
        failure_unchanged = (
            json.dumps(owner._painter_ui_document, sort_keys=True) == before_failure
        )
        failure_state = failure.runtime_status.property("runtimeState")
        failure.close()
    finally:
        QMessageBox.warning = original_warning
        owner.close()

    report = {
        "schema": "tigercapture.painter.figma_plugin_product_qa.v1",
        "ui_font": preferred_font,
        "success": {
            "run_returned": bool(success_ok),
            "created_count": created_count,
            "undo_label": undo_label,
            "undo_returned": undo_ok,
            "object_count_after_undo": undo_object_count,
            "capture": str(success_capture),
            "painter_after_run_capture": str(after_run_capture),
            "painter_after_undo_capture": str(after_undo_capture),
        },
        "failure": {
            "run_returned": bool(failure_ok),
            "document_unchanged": failure_unchanged,
            "status_state": str(failure_state),
            "warning_count": len(warnings),
            "capture": str(failure_capture),
        },
    }
    report["passed"] = bool(
        success_ok
        and created_count == 1
        and undo_label == "Run Figma plugin"
        and undo_ok
        and undo_object_count == 0
        and not failure_ok
        and failure_unchanged
        and failure_state == "error"
        and len(warnings) == 1
        and success_capture.exists()
        and failure_capture.exists()
        and after_run_capture.exists()
        and after_undo_capture.exists()
    )
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(ROOT / "debugCapture" / "painter_ui_figma_plugin_product"),
    )
    args = parser.parse_args()
    report = run_product_qa(Path(args.output))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
