from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _save_widget(widget, path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    pm = widget.grab()
    return bool(pm.save(str(path)))


def run_startup_flow_qa(out_dir: Path | str | None = None) -> dict[str, Any]:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QPushButton, QFrame
    from app.main_window import MainWindow
    from app.preset_library import preset_by_id
    from app.video_editor_window import (
        VideoEditorWindow,
        _render_preset_ab_application_preview,
    )

    app = QApplication.instance() or QApplication([])
    out = Path(out_dir or "debugCapture/qa_startup_flow").resolve()
    out.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str] = {}
    checks: dict[str, bool] = {}
    events: list[dict[str, Any]] = []

    launcher = MainWindow()
    try:
        launcher.open_template_requested.connect(
            lambda payload: events.append({
                "event": "open_template",
                "payload_id": str((payload or {}).get("id") or ""),
                "payload_name": str((payload or {}).get("name") or ""),
            })
        )
        launcher.open_video_editor_requested.connect(
            lambda payload: events.append({
                "event": "open_video_editor",
                "payload": payload if isinstance(payload, dict) else {"source_path": str(payload) if payload is not None else "", "workspace_mode": "standard"},
            })
        )
        launcher.show()
        app.processEvents()
        startup_path = out / "startup_launcher.png"
        checks["startup_screenshot"] = _save_widget(launcher, startup_path)
        artifacts["startup_launcher"] = str(startup_path)
        mini_cards = launcher.findChildren(QPushButton, "LauncherMiniCard")
        start_cards = launcher.findChildren(QPushButton, "LauncherStartCard")
        visible_start_cards = [card for card in start_cards if card.isVisible()]
        template_panels = launcher.findChildren(QFrame, "LauncherTemplatePanel")
        checks["launcher_templates_collapsed"] = (
            hasattr(launcher, "templates_btn")
            and not hasattr(launcher, "_template_row_layout")
            and not template_panels
        )
        checks["launcher_no_recent_cards"] = len(mini_cards) == 0
        checks["launcher_quick_start_cards"] = (
            len(visible_start_cards) == 1
            and all(card.isVisible() for card in visible_start_cards)
            and all("템플릿" not in card.text() and "Template" not in card.text() for card in start_cards)
        )
        checks["launcher_quick_start_label"] = (
            hasattr(launcher, "_pro_editor_label")
            and launcher._pro_editor_label.text() == launcher._quick_start_title_text()
        )
        checks["launcher_studio_entry_hidden_by_default"] = (
            hasattr(launcher, "pro_editor_btn")
            and hasattr(launcher, "templates_btn")
            and not launcher.pro_editor_btn.isVisible()
            and not launcher.templates_btn.isVisible()
        )
        checks["launcher_workspace_default_standard"] = (
            hasattr(launcher, "launcher_workspace_standard_btn")
            and launcher.launcher_workspace_standard_btn.isChecked()
            and launcher.launcher_workspace_mode() == "standard"
        )
        if hasattr(launcher, "pro_editor_btn"):
            QTest.mouseClick(launcher.pro_editor_btn, Qt.MouseButton.LeftButton)
            QTest.qWait(90)
            app.processEvents()
        checks["launcher_direct_editor_signal"] = any(event.get("event") == "open_video_editor" for event in events)
        checks["launcher_direct_editor_standard_payload"] = any(
            event.get("event") == "open_video_editor"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("workspace_mode") == "standard"
            for event in events
        )
        metrics = {
            "mini_card_count": len(mini_cards),
            "start_card_count": len(start_cards),
            "visible_start_card_count": len(visible_start_cards),
            "start_card_texts": [card.text() for card in start_cards],
            "template_panel_count": len(template_panels),
            "has_templates_button": hasattr(launcher, "templates_btn"),
            "window_size": [launcher.width(), launcher.height()],
            "events": events,
        }
        metrics_path = out / "startup_layout_metrics.json"
        metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        artifacts["startup_layout_metrics"] = str(metrics_path)

        launcher.show_startup_busy("Opening editor...")
        app.processEvents()
        checks["busy_visible"] = not launcher._startup_busy.isHidden()
        busy_path = out / "startup_busy.png"
        checks["busy_screenshot"] = _save_widget(launcher, busy_path)
        artifacts["startup_busy"] = str(busy_path)
        launcher.clear_startup_busy()
    finally:
        launcher.close()

    old_studio_env = os.environ.get("TIGERCAPTURE_CAPTURE_TO_STUDIO")
    os.environ["TIGERCAPTURE_CAPTURE_TO_STUDIO"] = "1"
    studio_launcher = MainWindow()
    try:
        studio_launcher.open_video_editor_requested.connect(
            lambda payload: events.append({
                "event": "open_video_editor",
                "payload": payload if isinstance(payload, dict) else {"source_path": str(payload) if payload is not None else "", "workspace_mode": "standard"},
            })
        )
        studio_launcher.show()
        app.processEvents()
        checks["launcher_direct_editor_card"] = (
            hasattr(studio_launcher, "pro_editor_btn")
            and studio_launcher.pro_editor_btn.isVisible()
            and bool(str(studio_launcher.pro_editor_btn.text()).strip())
        )
        QTest.mouseClick(studio_launcher.pro_editor_btn, Qt.MouseButton.LeftButton)
        QTest.qWait(90)
        app.processEvents()
        checks["launcher_direct_editor_signal"] = any(event.get("event") == "open_video_editor" for event in events)
        checks["launcher_direct_editor_standard_payload"] = any(
            event.get("event") == "open_video_editor"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("workspace_mode") == "standard"
            for event in events
        )
    finally:
        studio_launcher.close()
        if old_studio_env is None:
            os.environ.pop("TIGERCAPTURE_CAPTURE_TO_STUDIO", None)
        else:
            os.environ["TIGERCAPTURE_CAPTURE_TO_STUDIO"] = old_studio_env

    editor = VideoEditorWindow()
    try:
        editor.show_startup_template_hint(
            "template-screenstudio-test",
            "Screen Studio Test",
        )
        status = editor._startup_template_status()
        checks["editor_startup_template_status"] = (
            status.get("id") == "template-screenstudio-test"
            and status.get("state") == "ready"
            and status.get("pending") is True
            and status.get("preview_placeholder") == "template"
        )
        checks["editor_template_button_pending"] = (
            hasattr(editor, "template_browser_btn")
            and editor.template_browser_btn.property("startupTemplate") is True
            and "Screen Studio Test" in editor.template_browser_btn.toolTip()
        )
        banner = getattr(editor, "_status_banner", None)
        if banner is not None:
            banner.hide()
        editor.show()
        app.processEvents()
        editor_path = out / "editor_empty_template.png"
        checks["editor_empty_template_screenshot"] = _save_widget(editor, editor_path)
        artifacts["editor_empty_template"] = str(editor_path)
    finally:
        editor.close()

    preset = preset_by_id("template-screenstudio-cursor-demo") or preset_by_id("template-wallpaper-palette-hook")
    if preset is not None:
        preview = _render_preset_ab_application_preview(
            preset_id=str(preset.id),
            kind=str(preset.kind),
            label=str(preset.name),
            payload=dict(preset.payload or {}),
            tags=tuple(preset.tags or ()),
            sample_pixmap=None,
            phase=0.42,
        )
        preview_path = out / "template_ab_preview.png"
        checks["template_ab_preview"] = bool(preview.save(str(preview_path), "PNG"))
        artifacts["template_ab_preview"] = str(preview_path)

        summary_editor = VideoEditorWindow()
        try:
            summary_editor.resize(960, 720)
            summary_editor.show()
            app.processEvents()
            rows = summary_editor._workflow_apply_summary_rows(preset)
            summary_editor._show_workflow_apply_summary_toast(preset, rows, duration_ms=8000)
            app.processEvents()
            summary_path = out / "template_apply_summary.png"
            checks["template_apply_summary_screenshot"] = _save_widget(summary_editor, summary_path)
            artifacts["template_apply_summary"] = str(summary_path)
        finally:
            summary_editor.close()
    else:
        checks["template_ab_preview"] = False
        checks["template_apply_summary_screenshot"] = False

    report = {
        "ok": all(checks.values()),
        "checks": checks,
        "artifacts": artifacts,
    }
    report_path = out / "startup_flow_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main() -> int:
    report = run_startup_flow_qa()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
