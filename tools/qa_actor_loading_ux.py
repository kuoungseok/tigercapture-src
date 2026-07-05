from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from types import SimpleNamespace


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_actor_loading_ux_qa() -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if str(_repo_root()) not in sys.path:
        sys.path.insert(0, str(_repo_root()))

    from PySide6.QtWidgets import QApplication

    from app.actor_loading_status import actor_clip_badge, set_actor_clip_status
    from app.live2d.live2d_viewer import Live2DEditorWindow
    from app.spine_editor.editor_window import SpineEditorWindow

    app = QApplication.instance() or QApplication([])
    issues: list[dict] = []

    live = Live2DEditorWindow(autoload_sample=False)
    spine = SpineEditorWindow(autoload_sample=False)
    try:
        for name, win, deferred_name in (
            ("live2d", live, "load_model_deferred"),
            ("spine", spine, "load_character_deferred"),
        ):
            for attr in (
                "_loading_bar",
                "_cancel_load_btn",
                "_load_log_list",
                "_retry_load_btn",
                "_open_location_btn",
                "_sample_load_btn",
            ):
                widget = getattr(win, attr, None)
                if widget is None:
                    issues.append({"area": name, "code": "missing_widget", "detail": attr})
            if not hasattr(win, deferred_name):
                issues.append({"area": name, "code": "missing_deferred_load", "detail": deferred_name})
            win.show()
            app.processEvents()
            win._set_loading(True, "qa loading", progress=42, stage="isolated_probe")
            app.processEvents()
            if not win._loading_bar.isVisible() or not win._cancel_load_btn.isVisible():
                issues.append({"area": name, "code": "loading_not_visible"})
            if win._loading_bar.minimum() != 0 or win._loading_bar.maximum() != 100:
                issues.append({"area": name, "code": "loading_not_determinate"})
            if win._loading_bar.value() != 42:
                issues.append({"area": name, "code": "loading_progress_not_staged", "detail": win._loading_bar.value()})
            win._set_loading(False, "qa done")
            app.processEvents()
            if win._loading_bar.isVisible() or win._cancel_load_btn.isVisible():
                issues.append({"area": name, "code": "loading_not_hidden"})

        clip = SimpleNamespace()
        expected = {
            "loading": "LOAD",
            "ready": "OK",
            "error": "ERR",
            "timeout": "TIME",
            "cancelled": "STOP",
        }
        for status, badge_text in expected.items():
            set_actor_clip_status(clip, status, f"{status} message")
            badge = actor_clip_badge(clip)
            if not badge or badge[0] != badge_text:
                issues.append({"area": "timeline", "code": "bad_badge", "detail": status})
        try:
            from app.actor_loading_cache import actor_loading_cache_report, clear_actor_loading_cache, record_actor_load
            import tempfile

            cache_path = Path(tempfile.gettempdir()) / "tigercapture_actor_loading_ux_cache.json"
            clear_actor_loading_cache(cache_path)
            record_actor_load("live2d", "qa.model3.json", status="loading", stage="parse", message="qa", cache_path=cache_path)
            report = actor_loading_cache_report(cache_path)
            if report.get("summary", {}).get("entries") != 1:
                issues.append({"area": "cache", "code": "record_missing"})
        except Exception as exc:
            issues.append({"area": "cache", "code": "cache_exception", "detail": repr(exc)})
    finally:
        live.close()
        live.deleteLater()
        spine.close()
        spine.deleteLater()

    return {
        "ok": not issues,
        "issues": issues,
        "areas": {
            "live2d": "progress/cancel/timeout/recovery/log UI",
            "spine": "progress/cancel/timeout/recovery/log UI",
            "timeline": "actor load status badges",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Live2D/Spine actor loading UX wiring.")
    parser.add_argument("--out", default="debugCapture/actor_loading_ux_qa.json")
    args = parser.parse_args()
    report = run_actor_loading_ux_qa()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
