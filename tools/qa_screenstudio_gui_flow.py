from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT_DIR = ROOT / "debugCapture" / "screenstudio_gui_flow"


def _save_widget(widget, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = widget.grab()
    return bool(pixmap.save(str(path), "PNG"))


def _make_contact_sheet(images: list[tuple[str, Path]], out_path: Path) -> bool:
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    thumbs: list[tuple[str, QPixmap]] = []
    for label, path in images:
        pix = QPixmap(str(path))
        if pix.isNull():
            continue
        thumbs.append((
            label,
            pix.scaled(
                420,
                260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        ))
    if not thumbs:
        return False
    pad = 16
    label_h = 28
    col_w = 452
    row_h = 304
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    sheet = QPixmap(cols * col_w + pad, rows * row_h + pad)
    sheet.fill(QColor("#070912"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont()
    font.setPixelSize(13)
    font.setBold(True)
    painter.setFont(font)
    for idx, (label, pix) in enumerate(thumbs):
        col = idx % cols
        row = idx // cols
        x = pad + col * col_w
        y = pad + row * row_h
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111523"))
        painter.drawRoundedRect(QRect(x, y, col_w - pad, row_h - pad), 18, 18)
        painter.setPen(QColor("#EEF2FF"))
        painter.drawText(QRect(x + 14, y + 8, col_w - 28, label_h), Qt.AlignmentFlag.AlignVCenter, label)
        px = x + (col_w - pad - pix.width()) // 2
        py = y + label_h + 14 + (row_h - pad - label_h - 22 - pix.height()) // 2
        painter.drawPixmap(px, py, pix)
    painter.end()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(sheet.save(str(out_path), "PNG"))


def _looks_mojibake(text: Any) -> bool:
    value = str(text or "")
    if "\ufffd" in value:
        return True
    tokens = (
        "?쒗",
        "?몄",
        "諛",
        "鍮",
        "硫",
        "媛",
        "곗",
        "섎",
        "蹂",
        "쁽",
        "쒖",
    )
    return any(token in value for token in tokens)


def run_screenstudio_gui_flow_qa(*, out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QFrame, QPushButton

    from app.main_window import MainWindow
    from app.modes import CaptureMode
    from app.new_project_dialog import DEFAULT_STARTER_TEMPLATE_ID, NewProjectDialog
    from app.qa_dashboard import QADashboardDialog, build_qa_dashboard_rows
    from app.video_editor_window import VideoEditorWindow

    app = QApplication.instance() or QApplication([])
    out_dir = out_dir if out_dir.is_absolute() else ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    checks: dict[str, bool] = {}
    metrics: dict[str, Any] = {}
    artifacts: dict[str, str] = {}
    screenshots: list[tuple[str, Path]] = []

    def screenshot(label: str, widget, filename: str) -> None:
        path = out_dir / filename
        ok = _save_widget(widget, path)
        checks[f"{label}_screenshot"] = ok
        artifacts[label] = str(path)
        if ok:
            screenshots.append((label, path))

    launcher_events: list[dict[str, Any]] = []
    launcher = MainWindow()
    try:
        launcher.new_capture_requested.connect(
            lambda mode, delay, include_cursor: launcher_events.append({
                "event": "new_capture",
                "mode": getattr(mode, "name", str(mode)),
                "delay": int(delay),
                "include_cursor": bool(include_cursor),
            })
        )
        launcher.open_video_editor_requested.connect(
            lambda payload: launcher_events.append({
                "event": "open_video_editor",
                "payload": payload if isinstance(payload, dict) else {"source_path": str(payload), "workspace_mode": "standard"},
            })
        )
        launcher.open_template_requested.connect(
            lambda payload: launcher_events.append({
                "event": "open_template",
                "payload_id": str((payload or {}).get("id") or ""),
                "payload_name": str((payload or {}).get("name") or ""),
            })
        )
        launcher.resize(560, 660)
        launcher.show()
        app.processEvents()
        screenshot("launcher", launcher, "launcher.png")

        mini_cards = launcher.findChildren(QPushButton, "LauncherMiniCard")
        start_cards = launcher.findChildren(QPushButton, "LauncherStartCard")
        template_panels = launcher.findChildren(QFrame, "LauncherTemplatePanel")
        checks["launcher_is_compact"] = len(mini_cards) == 0 and len(template_panels) == 0
        checks["launcher_quick_start_cards"] = len(start_cards) == 2 and all(card.isVisible() for card in start_cards)
        checks["launcher_workspace_default_standard"] = (
            hasattr(launcher, "launcher_workspace_standard_btn")
            and launcher.launcher_workspace_standard_btn.isChecked()
            and launcher.launcher_workspace_mode() == "standard"
        )
        quick_texts = [
            str(getattr(card, "text", lambda: "")())
            for card in start_cards
        ]
        quick_tooltips = [
            str(getattr(card, "toolTip", lambda: "")())
            for card in start_cards
        ]
        checks["launcher_quick_start_text_clean"] = bool(quick_texts) and not any(_looks_mojibake(text) for text in quick_texts)
        checks["launcher_quick_start_tooltips_clean"] = not any(_looks_mojibake(text) for text in quick_tooltips)
        checks["launcher_quick_start_label"] = (
            hasattr(launcher, "_pro_editor_label")
            and launcher._pro_editor_label.text() == launcher._quick_start_title_text()
            and not _looks_mojibake(launcher._pro_editor_label.text())
        )
        checks["launcher_has_editor_header_shortcut"] = hasattr(launcher, "templates_btn") and launcher.templates_btn.isVisible()
        checks["launcher_has_editor_entry"] = hasattr(launcher, "pro_editor_btn") and launcher.pro_editor_btn.isVisible()
        checks["launcher_no_template_first_cards"] = (
            not hasattr(launcher, "quick_template_btn")
            and len(template_panels) == 0
            and not any("Template" in text or "템플릿" in text for text in quick_texts)
        )
        checks["launcher_cursor_default_enabled"] = bool(getattr(launcher, "cursor_check", None).isChecked())
        metrics["launcher"] = {
            "size": [launcher.width(), launcher.height()],
            "mini_cards": len(mini_cards),
            "start_cards": len(start_cards),
            "start_card_texts": quick_texts,
            "start_card_tooltips": quick_tooltips,
            "template_panels": len(template_panels),
        }

        for mode, button in getattr(launcher, "_mode_buttons", []):
            if mode is CaptureMode.VIDEO:
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                break
        QTest.mouseClick(launcher.new_capture_btn, Qt.MouseButton.LeftButton)
        app.processEvents()
        checks["launcher_video_capture_signal"] = any(
            event.get("event") == "new_capture"
            and event.get("mode") == "VIDEO"
            and event.get("include_cursor") is True
            for event in launcher_events
        )
        QTest.mouseClick(launcher.pro_editor_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(90)
        app.processEvents()
        checks["launcher_editor_signal"] = any(event.get("event") == "open_video_editor" for event in launcher_events)
        checks["launcher_editor_signal_uses_workspace_payload"] = any(
            event.get("event") == "open_video_editor"
            and isinstance(event.get("payload"), dict)
            and dict(event.get("payload") or {}).get("workspace_mode") in {"standard", "simple"}
            for event in launcher_events
        )
        opening_text = str(getattr(launcher.pro_editor_btn, "text", lambda: "")())
        checks["launcher_inline_opening_feedback"] = "여는 중" in opening_text or "Opening" in opening_text
        checks["launcher_no_busy_popup_for_editor_open"] = bool(launcher._startup_busy.isHidden())
        screenshot("launcher_opening", launcher, "launcher_opening.png")
        metrics["launcher_events"] = launcher_events
    finally:
        launcher.close()

    project = NewProjectDialog()
    try:
        project.show()
        app.processEvents()
        screenshot("new_project_dialog", project, "new_project_dialog.png")
        starter = project._starter_combo.currentData() or {}
        res = project._res_combo.currentData()
        fps_text = project._fps_combo.currentText()
        checks["new_project_screenstudio_default"] = str(starter.get("id") or "") == DEFAULT_STARTER_TEMPLATE_ID
        checks["new_project_16x9"] = str(getattr(project, "_ratio", "")) == "16:9"
        checks["new_project_1080p"] = tuple(res or ()) == (1920, 1080)
        checks["new_project_60fps"] = "60" in fps_text
        project._on_create()
        settings = project.result_settings
        checks["new_project_result_settings"] = bool(
            settings
            and settings.starter_template_id == DEFAULT_STARTER_TEMPLATE_ID
            and settings.width == 1920
            and settings.height == 1080
            and abs(float(settings.fps) - 60.0) < 0.001
        )
        metrics["new_project"] = {
            "starter": starter,
            "resolution": list(res or []),
            "fps_text": fps_text,
        }
    finally:
        project.close()

    editor = VideoEditorWindow()
    try:
        editor.resize(1280, 820)
        editor.show()
        app.processEvents()
        screenshot("editor_empty", editor, "editor_empty.png")
        create_menu_labels: list[str] = []
        create_menu_btn = getattr(editor, "_create_menu_btn", None)
        if create_menu_btn is not None:
            try:
                create_menu_btn.pressed.emit()
                app.processEvents()
                menu = create_menu_btn.menu()
                if menu is not None:
                    create_menu_labels = [
                        str(action.text())
                        for action in menu.actions()
                        if not action.isSeparator()
                    ]
            except Exception:
                create_menu_labels = []
        template_direct = (
            hasattr(editor, "template_browser_btn")
            and editor.template_browser_btn.isVisible()
            and "template" in editor.template_browser_btn.toolTip().lower()
        )
        auto_polish_direct = (
            hasattr(editor, "auto_polish_btn")
            and editor.auto_polish_btn.isVisible()
            and "Auto Polish" in editor.auto_polish_btn.toolTip()
            and "zoom" in editor.auto_polish_btn.toolTip().lower()
        )
        template_grouped = "Template Browser" in create_menu_labels
        auto_polish_grouped = "Auto Polish" in create_menu_labels
        checks["editor_auto_polish_button"] = (
            auto_polish_direct or auto_polish_grouped
        )
        checks["editor_template_button"] = (
            template_direct or template_grouped
        )
        checks["editor_export_button"] = hasattr(editor, "export_btn") and editor.export_btn.isVisible()
        screenstudio_note = editor._screenstudio_export_badge_note()
        checks["editor_screenstudio_status_note"] = (
            "Screen Studio" in screenstudio_note
            and "MP4/high" in screenstudio_note
            and "1920x1080" in screenstudio_note
            and "handoff" in screenstudio_note
            and "fps" in screenstudio_note
        )
        checks["editor_export_defaults"] = (
            str(getattr(editor, "_export_format_id", "")) == "mp4"
            and str(getattr(editor, "_export_quality_id", "")) == "high"
            and bool(getattr(editor, "export_btn", None))
            and bool(getattr(editor, "resolution_btn", None))
            and bool(getattr(editor, "fps_btn", None))
        )
        metrics["editor"] = {
            "format_id": str(getattr(editor, "_export_format_id", "")),
            "quality_id": str(getattr(editor, "_export_quality_id", "")),
            "auto_polish_tooltip": editor.auto_polish_btn.toolTip(),
            "catalog_command_groups": bool(getattr(editor, "_catalog_command_groups_active", False)),
            "create_menu_labels": create_menu_labels,
            "template_direct_visible": bool(template_direct),
            "auto_polish_direct_visible": bool(auto_polish_direct),
            "screenstudio_export_note": screenstudio_note,
        }
    finally:
        editor.close()

    dashboard = QADashboardDialog()
    try:
        dashboard.resize(960, 620)
        dashboard.show()
        app.processEvents()
        screenshot("qa_dashboard", dashboard, "qa_dashboard.png")
        rows = build_qa_dashboard_rows()
        kinds = {str(row.get("kind") or "") for row in rows}
        screenstudio_rows = sorted(kind for kind in kinds if kind.startswith("screenstudio_"))
        checks["dashboard_has_screenstudio_gui_flow"] = "screenstudio_gui_flow" in kinds
        checks["dashboard_has_capcut_creator_flow"] = "capcut_creator_workflow" in kinds
        checks["dashboard_has_local_ml_backend"] = "local_ml_backend" in kinds
        checks["dashboard_has_screenstudio_suite"] = {
            "screenstudio_auto_polish",
            "screenstudio_visual_polish",
            "screenstudio_app_flow",
            "screenstudio_gui_flow",
            "screenstudio_export_handoff",
        }.issubset(kinds)
        gui_row = next((row for row in rows if row.get("kind") == "screenstudio_gui_flow"), None)
        command = QADashboardDialog._command_for_row(gui_row)
        checks["dashboard_can_run_gui_flow"] = bool(command) and "qa_screenstudio_gui_flow.py" in " ".join(command)
        metrics["dashboard"] = {
            "rows": len(rows),
            "screenstudio_rows": screenstudio_rows,
            "gui_flow_command": command,
        }
    finally:
        dashboard.close()

    contact_sheet = out_dir / "screenstudio_gui_flow_contact_sheet.png"
    checks["contact_sheet"] = _make_contact_sheet(screenshots, contact_sheet)
    artifacts["contact_sheet"] = str(contact_sheet)

    failures = [
        {"check": name, "message": "check failed"}
        for name, passed in checks.items()
        if not passed
    ]
    report = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "checks": len(checks),
            "passing": sum(1 for passed in checks.values() if passed),
            "failing": len(failures),
            "screenshots": len(screenshots),
            "screenstudio_dashboard_rows": len(metrics.get("dashboard", {}).get("screenstudio_rows", [])),
        },
        "checks": checks,
        "metrics": metrics,
        "artifacts": artifacts,
        "contact_sheet": str(contact_sheet),
        "failures": failures,
    }
    report_path = out_dir / "screenstudio_gui_flow_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio launcher/editor GUI-flow QA.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    report = run_screenstudio_gui_flow_qa(out_dir=args.out_dir)
    report_path = Path(str(report["report"]))
    if args.report is not None:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(report_path), "contact_sheet": report["contact_sheet"]}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
