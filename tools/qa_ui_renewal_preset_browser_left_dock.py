from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from tools.qa_workbench_node_action_flow import _default_media, _force_viewer_frame, _save_widget, _wait  # noqa: E402


SECTION_CONFIGS = {
    "effects": {
        "header": "_effects_library_header",
        "panel": "_effects_preset_panel",
        "artifact": "left_dock_effects_browser.png",
        "key": "effects",
    },
    "titles": {
        "header": "_title_presets_header",
        "panel": "_title_presets_panel",
        "artifact": "left_dock_titles_browser.png",
        "key": "titles",
    },
    "transitions": {
        "header": "_transitions_header",
        "panel": "_transitions_panel",
        "artifact": "left_dock_transitions_browser.png",
        "key": "transitions",
    },
    "workflows": {
        "header": "_workflow_presets_header",
        "panel": "_workflow_presets_panel",
        "artifact": "left_dock_workflows_browser.png",
        "key": "workflows",
    },
}


def _set_section_open(header: Any, opened: bool) -> bool:
    from PySide6.QtWidgets import QPushButton

    if header is None:
        return False
    buttons = [
        button
        for button in header.findChildren(QPushButton)
        if button.objectName() == "SectionDisclosure"
    ]
    if not buttons:
        return False
    buttons[0].setChecked(bool(opened))
    return True


def run_preset_browser_left_dock_capture(
    *,
    out_dir: str | Path = ROOT / "debugCapture" / "ui_renewal_preset_browser_left_dock",
    language: str = "ko",
    section: str = "effects",
) -> dict[str, Any]:
    from PySide6.QtWidgets import QApplication

    from app.font_fallback import apply_ui_font
    from app.i18n import initialize, set_language
    from app.style import APP_QSS
    from app.video_editor_window import VideoEditorWindow

    out = Path(out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    section = str(section or "effects").strip().casefold()
    config = SECTION_CONFIGS.get(section)
    if config is None:
        raise ValueError(f"unknown preset browser section: {section}")

    app = QApplication.instance() or QApplication([])
    apply_ui_font(app)
    app.setStyleSheet(APP_QSS)
    active_language = initialize()
    if language:
        set_language(language)
        active_language = language

    editor = VideoEditorWindow()
    checks: dict[str, bool] = {}
    artifacts: dict[str, str] = {}
    media_path = _default_media()
    try:
        try:
            editor._autosave_timer.stop()
            editor._do_autosave = lambda *_args, **_kwargs: None
        except Exception:
            pass
        editor.resize(1480, 920)
        editor.show()
        _wait(app, 260)

        try:
            editor._media_pool.add_path(media_path)
        except Exception:
            pass
        try:
            from app.actions import build_default_action_registry

            registry = build_default_action_registry(editor)
            imported = registry.execute(
                "media.import_to_timeline",
                {
                    "path": str(media_path),
                    "kind": "video",
                    "at_ms": 0,
                    "duration_ms": 40000,
                    "name": "Preset preview source",
                },
            ).to_dict()
            checks["timeline_imported"] = bool(imported.get("ok", False))
            registry.execute("timeline.set_playhead", {"ms": 8000}).to_dict()
            checks["preview_frame_ready"] = bool(_force_viewer_frame(editor, Path(media_path), 8000, out))
        except Exception:
            checks["timeline_imported"] = False
            checks["preview_frame_ready"] = False
        _set_section_open(getattr(editor, "_media_pool_header", None), False)
        _set_section_open(getattr(editor, "_actor_library_header", None), False)
        for name, row in SECTION_CONFIGS.items():
            opened = name == section
            result = _set_section_open(getattr(editor, str(row["header"]), None), opened)
            if opened:
                checks[f"{row['key']}_opened"] = result
        _wait(app, 280)

        scroll = getattr(editor, "_left_dock_scroll", None)
        panel = getattr(editor, str(config["panel"]), None)
        if scroll is not None and panel is not None:
            try:
                scroll.ensureWidgetVisible(panel, 0, 0)
            except Exception:
                pass
        from PySide6.QtWidgets import QComboBox, QFrame, QLineEdit, QToolButton, QWidget

        category_button = None
        category_combo = None
        search = None
        inspector = None
        target_strip = None
        if panel is not None:
            for browser in panel.findChildren(QWidget):
                cards = list(getattr(browser, "_all_cards", []) or [])
                inspect = getattr(browser, "_inspect_card", None)
                if cards and callable(inspect):
                    try:
                        inspect(cards[0])
                        checks["hover_preview_refreshed"] = True
                    except Exception:
                        checks["hover_preview_refreshed"] = False
                    break
            else:
                checks["hover_preview_refreshed"] = False
            _wait(app, 160)
            category_button = getattr(panel, "_category_filter_btn", None) or panel.findChild(
                QToolButton, "PresetCategoryFilterButton"
            )
            category_combo = getattr(panel, "_category_combo", None) or panel.findChild(
                QComboBox, "PresetCategoryCombo"
            )
            search = getattr(panel, "_search", None) or panel.findChild(QLineEdit, "PresetSearch")
            inspector = panel.findChild(QFrame, "PresetInspectorPanel")
            target_strip = panel.findChild(QWidget, "PresetTargetStrip")
        checks[f"{config['key']}_panel_visible"] = bool(panel is not None and panel.isVisible())
        checks["category_button_visible"] = bool(category_button is not None and category_button.isVisible())
        checks["category_combo_hidden"] = bool(category_combo is not None and not category_combo.isVisible())
        checks["search_visible"] = bool(search is not None and search.isVisible())
        checks["integrated_preview_visible"] = bool(inspector is not None and inspector.isVisible())
        checks["target_strip_visible"] = bool(target_strip is not None and target_strip.isVisible())

        png = out / str(config["artifact"])
        checks["screenshot"] = bool(scroll is not None and _save_widget(scroll, png))
        artifacts[f"left_dock_{config['key']}_browser"] = str(png.resolve())
    finally:
        editor.close()
        app.processEvents()
        time.sleep(0.05)
        app.processEvents()

    ok = all(checks.values())
    report = {
        "ok": bool(ok),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": active_language,
        "section": section,
        "media": str(media_path),
        "checks": checks,
        "artifacts": artifacts,
    }
    report_path = out / "preset_browser_left_dock_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report"] = str(report_path.resolve())
    return report


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Capture the renewed preset browser inside the left dock.")
    parser.add_argument("--out-dir", default=str(ROOT / "debugCapture" / "ui_renewal_preset_browser_left_dock"))
    parser.add_argument("--language", default="ko")
    parser.add_argument("--section", default="effects", choices=sorted(SECTION_CONFIGS))
    args = parser.parse_args()
    report = run_preset_browser_left_dock_capture(out_dir=args.out_dir, language=args.language, section=args.section)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
